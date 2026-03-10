/* ═══════════════════════════════════════════════════
   IBTicket — AJAX helpers
   (Flask session cookie handles auth automatically)
   ═══════════════════════════════════════════════════ */

async function fetchJSON(url, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (opts.body && !(opts.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(url, { ...opts, headers });
  const json = await res.json().catch(() => null);
  if (!res.ok) throw new Error(json?.error || `Error ${res.status}`);
  return json;
}

const doGET    = url       => fetchJSON(url);
const doPOST   = (url, b)  => fetchJSON(url, { method: 'POST',   body: JSON.stringify(b) });
const doDELETE = url       => fetchJSON(url, { method: 'DELETE' });

/* ── Toast ─────────────────────────────────────────── */
function showToast(msg, type = 'info') {
  let c = document.getElementById('toast-container');
  if (!c) {
    c = document.createElement('div');
    c.id = 'toast-container';
    c.className = 'toast-container';
    document.body.appendChild(c);
  }
  const t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

/* ── Utilities ─────────────────────────────────────── */
function esc(s) {
  if (s === null || s === undefined) return '<span class="null-val">NULL</span>';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function formatBytes(b) {
  if (b < 1024)      return b + ' B';
  if (b < 1_048_576) return (b / 1024).toFixed(1) + ' KB';
  return (b / 1_048_576).toFixed(1) + ' MB';
}

function copyText(text) {
  navigator.clipboard.writeText(text);
  showToast('Copiado al portapapeles', 'success');
}
