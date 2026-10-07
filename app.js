const C = window.CONFIG, $ = id => document.getElementById(id);
const LEVELS = ["Self-care", "See a doctor", "Seek urgent care"];
let signer, addr, contract, key, msgs = [], care = null, busy = false;

const b64 = u8 => btoa(String.fromCharCode(...u8));
const unb64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
const status = t => $("st").textContent = t;
function bubble(role, text) {
  const d = document.createElement("div"); d.className = "m " + (role === "user" ? "u" : "a");
  d.textContent = text; $("log").append(d); $("log").scrollTop = 1e9;
}
function showCare(level) {
  const el = $("care"); el.style.display = "block"; el.className = "c" + level;
  el.innerHTML = `<strong>Suggested care level: ${LEVELS[level]}</strong><br>This is not a diagnosis.`;
}

// AES-GCM key derived from a wallet signature: only the wallet owner can decrypt sessions.
async function deriveKey() {
  const sig = await signer.signMessage("Symptom Ledger: derive my encryption key (v1). Safe to sign; costs no gas.");
  const raw = ethers.getBytes(ethers.sha256(ethers.toUtf8Bytes(sig)));
  return crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
}
async function encrypt(obj) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, new TextEncoder().encode(JSON.stringify(obj))));
  const all = new Uint8Array(12 + ct.length); all.set(iv); all.set(ct, 12);
  return b64(all);
}
async function decrypt(b) {
  const all = unb64(b), pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: all.slice(0, 12) }, key, all.slice(12));
  return JSON.parse(new TextDecoder().decode(pt));
}
const hashOf = b => ethers.sha256(unb64(b)); // hash of the ciphertext, never the plaintext
const idFrom = rc => rc.logs.map(l => { try { return contract.interface.parseLog(l); } catch { return null; } }).find(x => x).args.id;

$("connect").onclick = async () => {
  try {
    if (!window.ethereum) return status("No wallet found. Install MetaMask and open this page from http://localhost:8000.");
    const p = new ethers.BrowserProvider(window.ethereum);
    await p.send("eth_requestAccounts", []);
    if ((await p.getNetwork()).chainId !== BigInt(C.CHAIN_ID))
      await p.send("wallet_switchEthereumChain", [{ chainId: "0x" + C.CHAIN_ID.toString(16) }]);
    const prov = new ethers.BrowserProvider(window.ethereum);
    signer = await prov.getSigner(); addr = await signer.getAddress();
    contract = new ethers.Contract(C.CONTRACT_ADDRESS, C.ABI, signer);
    key = await deriveKey();
    $("net").textContent = `${C.CHAIN_NAME} · ${addr.slice(0, 6)}…${addr.slice(-4)}`;
    $("connect").textContent = "Connected"; $("connect").disabled = true;
    status("Wallet connected."); if (care !== null) $("save").disabled = false; loadTimeline();
  } catch (e) { status("Could not connect: " + (e.shortMessage || e.message)); }
};

$("f").onsubmit = async e => {
  e.preventDefault(); const text = $("t").value.trim();
  if (!text || busy) return;
  busy = true; $("t").value = ""; bubble("user", text); msgs.push({ role: "user", content: text });
  try {
    const r = await fetch(C.BACKEND_URL + "/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages: msgs }) });
    const d = await r.json(); if (!r.ok) throw new Error(d.error);
    bubble("assistant", d.reply); msgs.push({ role: "assistant", content: d.reply });
    if (d.care_level !== null) { care = d.care_level; showCare(care); $("save").disabled = !addr; if (!addr) status("Connect your wallet to save this check."); }
  } catch (err) { status("Can't reach the backend. Start it, or open /health and wait a minute if it's asleep."); }
  busy = false;
};

$("save").onclick = async () => {
  try {
    $("save").disabled = true; status("Encrypting session…");
    const ct = await encrypt({ messages: msgs, care, at: new Date().toISOString() });
    const hash = hashOf(ct);
    status("Confirm the transaction in your wallet (pending)…");
    const tx = await contract.log(hash, care);
    status("Pending: waiting for confirmation… " + tx.hash.slice(0, 12) + "…");
    const rc = await tx.wait();
    await fetch(C.BACKEND_URL + "/api/sessions", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hash, care, ciphertext: ct, wallet: addr, tx: tx.hash, chainId: C.CHAIN_ID }) });
    status(`Confirmed: logged as check #${idFrom(rc)}. `);
    const a = document.createElement("a"); a.href = `${C.EXPLORER}/tx/${tx.hash}`; a.target = "_blank"; a.rel = "noopener"; a.textContent = "View transaction";
    $("st").append(a);
    msgs = []; care = null; $("care").style.display = "none"; $("log").innerHTML = ""; loadTimeline();
  } catch (e) { status("Failed: " + (e.shortMessage || e.message)); $("save").disabled = false; }
};

async function loadTimeline() {
  const el = $("tl");
  try {
    const rows = await (await fetch(`${C.BACKEND_URL}/api/sessions?wallet=${addr}`)).json();
    if (!rows.length) return el.innerHTML = '<p class="status">No saved checks yet. Finish a chat, then save it.</p>';
    el.innerHTML = "";
    for (const r of rows) {
      const d = document.createElement("div"); d.className = "row";
      d.innerHTML = `<strong>${LEVELS[r.care]}</strong><small>${new Date(r.ts * 1000).toLocaleString()} · ${r.hash.slice(0, 18)}…</small>
        <div class="btns"><button class="ghost v">Verify on-chain</button><button class="ghost o">Open</button><a href="${C.EXPLORER}/tx/${r.tx}" target="_blank" rel="noopener">tx</a></div><small class="res"></small>`;
      const res = d.querySelector(".res");
      d.querySelector(".v").onclick = async () => {
        try {
          const rc = await contract.runner.provider.getTransactionReceipt(r.tx);
          res.textContent = await contract.verify(idFrom(rc), hashOf(r.ciphertext)) ? "✓ Verified: stored session matches the chain." : "✗ Does not match the chain.";
        } catch (e) { res.textContent = "Could not verify: " + (e.shortMessage || e.message); }
      };
      d.querySelector(".o").onclick = async () => {
        try { const s = await decrypt(r.ciphertext); res.style.whiteSpace = "pre-wrap"; res.textContent = s.messages.map(m => `${m.role}: ${m.content}`).join("\n"); }
        catch { res.textContent = "Could not decrypt with this wallet."; }
      };
      el.append(d);
    }
  } catch { el.innerHTML = '<p class="status">Can\'t load your timeline: backend unreachable.</p>'; }
}
