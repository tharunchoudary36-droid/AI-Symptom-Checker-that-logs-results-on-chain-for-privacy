# Symptom Ledger (INNOBLOCK 2.0 · PS 23 Healthcare)
AI symptom checker. Each session is encrypted in the browser and stored off-chain; only its SHA-256 hash, a care level (0 self-care, 1 see a doctor, 2 urgent) and a timestamp go on a testnet.

**Contract:** `0xYOUR_CONTRACT_ADDRESS` on Ethereum Sepolia (verified: add explorer link)

## Why blockchain
A public, tamper-evident record that a check happened and was never altered, with zero symptom data on-chain. Verify recomputes the hash of the stored ciphertext and compares it to the chain.

## Architecture
Browser (ethers.js, AES-GCM key from a wallet signature, user's wallet signs the log tx) → Flask backend (red-flag rules, AI call, stores ciphertext in SQLite) → `SymptomLog` contract.
Red-flag phrases (chest pain, trouble breathing, stroke signs…) are caught by deterministic rules *before* the AI and always return urgent care.

## Setup
1. Remix: open `contracts/SymptomLog.sol`, compile (0.8.20+), deploy via MetaMask on Sepolia. Copy the address into `frontend/config.js`.
2. `cd backend && python -m venv venv && venv\Scripts\activate` (Mac/Linux: `source venv/bin/activate`), `pip install -r requirements.txt`, copy `.env.example` to `.env` (optional: add `ANTHROPIC_API_KEY`), `python app.py`.
3. `cd frontend && python -m http.server 8000`, open http://localhost:8000, connect MetaMask.

## How to test
- Chat: "I have a sore throat" → 2 follow-ups → care level → Save → confirm in MetaMask.
- Red flag: "I have chest pain and trouble breathing" → immediate urgent-care message.
- Timeline → Verify shows ✓. Tamper test: edit a `ciphertext` in `sessions.db` and Verify shows ✗.

## Privacy honesty
Chain and database never see plaintext. The backend and AI provider do see messages during the chat. Wallet addresses are public, so check counts and times are linkable to an address. Use a burner wallet. Testnets only.

## Environment variables (backend/.env, never commit)
`ANTHROPIC_API_KEY` (optional), `AI_MODEL`, `FRONTEND_ORIGIN`, `DB_PATH`. On Render the disk is wiped on restart, so point `DB_PATH` at a persistent disk or swap SQLite for Neon/Supabase.

## Team
Add names and roles.
