"""Symptom Ledger backend: red-flag rules, AI triage, encrypted-session storage.
It never holds a private key: the user's own wallet signs the on-chain log."""
import json, os, re, sqlite3
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()
app = Flask(__name__)
CORS(app, origins=os.getenv("FRONTEND_ORIGIN", "*"))
DB = os.getenv("DB_PATH", "sessions.db")
NOT_DX = "This is not a diagnosis. It cannot replace a doctor."

# Deterministic red flags: these override the AI model every time.
RED_FLAGS = re.compile(
    r"chest (pain|pressure|tightness)|can'?t breathe|trouble breathing|short(ness)? of breath|"
    r"face droop|slurred speech|sudden (weakness|numbness|confusion)|worst headache|"
    r"coughing (up )?blood|vomiting blood|suicid|overdose|severe bleeding|unconscious|"
    r"seizure|anaphyla|throat (is )?closing", re.I)

SYSTEM = ("You are a symptom triage assistant, not a doctor. Never diagnose. Ask ONE short "
          "follow-up question at a time (onset, severity, duration, other symptoms, age, "
          "conditions). After 3-5 user answers, give a care level. Reply ONLY with JSON: "
          '{"reply": str, "care_level": null|0|1|2} where 0=self-care, 1=see a doctor, '
          "2=urgent care, null while still asking.")

def db():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY, wallet TEXT,
                 chain_id INTEGER, tx TEXT, care INTEGER, ciphertext TEXT, ts INTEGER)""")
    return c

def demo_triage(msgs):
    # Get only the user's messages
    user_texts = [
        m.get("content", "")
        for m in msgs
        if m.get("role") == "user"
    ]

    # Combine user messages for rule-based checking
    text = " ".join(user_texts).lower()

    # ---------------------------------------------------------
    # 1. EMERGENCY RED FLAGS ALWAYS OVERRIDE EVERYTHING
    # ---------------------------------------------------------
    if RED_FLAGS.search(text):
        return {
            "reply": "Your symptoms include a warning sign. "
                     "Please seek urgent medical care now. "
                     "This is not a diagnosis and cannot replace a doctor.",
            "care_level": 2
        }

    # ---------------------------------------------------------
    # 2. ASK FOLLOW-UP QUESTIONS
    # ---------------------------------------------------------
    if len(user_texts) < 3:
        questions = [
            "How long have you had these symptoms, and how severe are they from 1 to 10?",
            "Do you have a fever, or any other symptoms alongside this?"
        ]

        question = questions[len(user_texts) - 1]

        return {
            "reply": " " + question,
            "care_level": None
        }

    # ---------------------------------------------------------
    # 3. EXTRACT NUMERIC SEVERITY
    # Supports:
    # 9/10
    # 9 out of 10
    # 9 out of 10 severity
    # ---------------------------------------------------------
    severity = None

    severity_match = re.search(
        r'\b(10|[1-9])\s*(?:/|out\s+of)\s*10\b',
        text
    )

    if severity_match:
        severity = int(severity_match.group(1))

    # ---------------------------------------------------------
    # 4. CHECK FOR DURATION
    # Examples:
    # 5 days
    # 3 weeks
    # 2 months
    # ---------------------------------------------------------
    duration_days = 0

    day_match = re.search(
        r'\b(\d+)\s*(?:day|days)\b',
        text
    )

    week_match = re.search(
        r'\b(\d+)\s*(?:week|weeks)\b',
        text
    )

    month_match = re.search(
        r'\b(\d+)\s*(?:month|months)\b',
        text
    )

    if day_match:
        duration_days = int(day_match.group(1))

    elif week_match:
        duration_days = int(week_match.group(1)) * 7

    elif month_match:
        duration_days = int(month_match.group(1)) * 30

    # ---------------------------------------------------------
    # 5. VERY HIGH SEVERITY
    # ---------------------------------------------------------
    if severity is not None and severity >= 9:
        return {
            "reply": " Your reported symptom severity is very high. "
                     "You should seek medical evaluation promptly rather than "
                     "relying on self-care alone. "
                     "If you develop difficulty breathing, chest pain, confusion, "
                     "fainting, severe bleeding, or another warning sign, seek "
                     "urgent emergency care immediately. "
                     "This is not a diagnosis.",
            "care_level": 1
        }

    # ---------------------------------------------------------
    # 6. HIGH SEVERITY
    # ---------------------------------------------------------
    if severity is not None and severity >= 7:
        return {
            "reply": " Your symptoms are quite severe. "
                     "Consider getting medical advice promptly, especially if "
                     "the symptoms are worsening or affecting your normal activities. "
                     "This is not a diagnosis.",
            "care_level": 1
        }

    # ---------------------------------------------------------
    # 7. PERSISTENT SYMPTOMS
    # ---------------------------------------------------------
    if duration_days >= 5:
        return {
            "reply": "Your symptoms have been present for several days. "
                     "Because they are persisting, it would be appropriate to "
                     "seek medical advice rather than relying only on self-care. "
                     "If symptoms worsen or warning signs appear, seek urgent care. "
                     "This is not a diagnosis.",
            "care_level": 1
        }

    # ---------------------------------------------------------
    # 8. SEVERE WORDS
    # ---------------------------------------------------------
    severe_words = [
        "severe",
        "very bad",
        "worst",
        "unbearable",
        "getting worse",
        "worsening"
    ]

    if any(word in text for word in severe_words):
        return {
            "reply": " Your symptoms sound significant. "
                     "It would be sensible to speak with a doctor soon. "
                     "This is not a diagnosis.",
            "care_level": 1
        }

    # ---------------------------------------------------------
    # 9. MODERATE SYMPTOMS
    # ---------------------------------------------------------
    if severity is not None and severity >= 5:
        return {
            "reply": " Your symptoms appear moderate. "
                     "Consider getting advice from a healthcare professional "
                     "if they persist or worsen. "
                     "This is not a diagnosis.",
            "care_level": 1
        }

    # ---------------------------------------------------------
    # 10. MILD SYMPTOMS
    # ---------------------------------------------------------
    mild_words = [
        "mild",
        "slight",
        "slightly"
    ]

    if any(word in text for word in mild_words) or (
        severity is not None and severity <= 4
    ):
        return {
            "reply": " Your symptoms appear mild. "
                     "For now, self-care such as rest, hydration, and monitoring "
                     "your symptoms may be reasonable. "
                     "If symptoms worsen, persist, or new warning signs appear, "
                     "seek medical care. This is not a diagnosis.",
            "care_level": 0
        }

    # ---------------------------------------------------------
    # 11. COMMON MILD SYMPTOMS
    # Only use this when there is NO concerning severity/duration.
    # ---------------------------------------------------------
    common_mild = [
        "headache",
        "sore throat",
        "runny nose",
        "stuffy nose",
        "cold",
        "cough",
        "tired",
        "fatigue"
    ]

    if any(word in text for word in common_mild):
        return {
            "reply": "These symptoms may be suitable for "
                     "self-care and monitoring if they remain mild. "
                     "Rest, stay hydrated, and monitor how you feel. "
                     "If symptoms worsen or persist, seek medical advice. "
                     "This is not a diagnosis.",
            "care_level": 0
        }

    # ---------------------------------------------------------
    # 12. DEFAULT
    # ---------------------------------------------------------
    return {
        "reply": "Based on what you shared, "
                 "self-care and monitoring may be reasonable. "
                 "If your symptoms worsen or you develop warning signs, "
                 "seek medical care. This is not a diagnosis.",
        "care_level": 0
    }
def ai_triage(msgs):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return demo_triage(msgs)
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=40,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            json={"model": os.getenv("AI_MODEL", "claude-sonnet-5-5"), "max_tokens": 400,
                  "system": SYSTEM, "messages": msgs})
        r.raise_for_status()
        txt = re.sub(r"```(json)?", "", r.json()["content"][0]["text"]).strip()
        out = json.loads(txt)
        lvl = out.get("care_level")
        return {"reply": str(out["reply"]), "care_level": lvl if lvl in (0, 1, 2) else None}
    except Exception as e:
        app.logger.warning("AI failed, using demo flow: %s", e)
        return demo_triage(msgs)

@app.get("/health")
def health():
    return jsonify(ok=True, ai=bool(os.getenv("ANTHROPIC_API_KEY")))

@app.post("/api/chat")
def chat():
    msgs = [{"role": m["role"], "content": str(m["content"])[:2000]}
            for m in (request.json or {}).get("messages", [])][-20:]
    if not msgs or msgs[-1]["role"] != "user":
        return jsonify(error="send a user message"), 400
    if RED_FLAGS.search(" ".join(m["content"] for m in msgs if m["role"] == "user")):
        return jsonify(reply="Your symptoms include a warning sign. Seek urgent care now: "
                       "call your local emergency number or go to the nearest emergency room. "
                       + NOT_DX, care_level=2, red_flag=True)
    out = ai_triage(msgs)
    if out["care_level"] is not None:
        out["reply"] += "\n\n" + NOT_DX
    return jsonify(**out, red_flag=False)

@app.post("/api/sessions")
def save_session():
    d = request.json or {}
    if not re.fullmatch(r"0x[0-9a-f]{64}", str(d.get("hash", ""))) or d.get("care") not in (0, 1, 2):
        return jsonify(error="bad hash or care level"), 400
    with db() as c:
        c.execute("INSERT OR REPLACE INTO sessions VALUES(?,?,?,?,?,?,strftime('%s','now'))",
                  (d["hash"], str(d.get("wallet", "")).lower(), d.get("chainId"), d.get("tx"),
                   d["care"], d.get("ciphertext", "")))
    return jsonify(ok=True)

@app.get("/api/sessions")
def list_sessions():
    w = request.args.get("wallet", "").lower()
    rows = db().execute("SELECT hash,tx,care,ciphertext,ts FROM sessions WHERE wallet=? ORDER BY ts DESC", (w,)).fetchall()
    return jsonify([dict(zip(("hash", "tx", "care", "ciphertext", "ts"), r)) for r in rows])

if __name__ == "__main__":
    app.run(port=5000, debug=True)
