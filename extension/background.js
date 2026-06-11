// Service worker de la extensión: única pieza que conoce el token y habla con la API.
// El token vive cifrado con el PIN en chrome.storage.local; al desbloquear se guarda
// en chrome.storage.session (memoria, se borra al cerrar el navegador) por un tiempo
// limitado y deslizante. El token y las contraseñas JAMÁS se exponen a las páginas:
// solo viajan al content script en respuesta a una acción explícita del usuario.

import { encryptWithPin, decryptWithPin } from './crypto.js';

const UNLOCK_MS = 5 * 60 * 1000;       // ventana de desbloqueo (deslizante)
const MAX_PIN_ATTEMPTS = 5;            // intentos fallidos antes de borrar todo
const PENDING_SAVE_TTL_MS = 2 * 60 * 1000;

// ─── Helpers de storage ──────────────────────────────────────────────────────

async function getLocal(keys) {
  return chrome.storage.local.get(keys);
}

async function getSession(keys) {
  return chrome.storage.session.get(keys);
}

async function wipeAll() {
  await chrome.storage.local.clear();
  await chrome.storage.session.clear();
}

// ─── Estado de desbloqueo ────────────────────────────────────────────────────

async function getUnlockedToken() {
  const { token, unlockedUntil } = await getSession(['token', 'unlockedUntil']);
  if (!token || !unlockedUntil || Date.now() > unlockedUntil) return null;
  return token;
}

async function renewUnlock() {
  await chrome.storage.session.set({ unlockedUntil: Date.now() + UNLOCK_MS });
}

async function status() {
  const { apiUrl, email, encToken } = await getLocal(['apiUrl', 'email', 'encToken']);
  const token = await getUnlockedToken();
  const { unlockedUntil } = await getSession(['unlockedUntil']);
  return {
    configured: Boolean(encToken && apiUrl),
    unlocked: Boolean(token),
    email: email || null,
    apiUrl: apiUrl || null,
    unlockedUntil: token ? unlockedUntil : null,
  };
}

// ─── Llamadas a la API ───────────────────────────────────────────────────────

async function api(path, { method = 'GET', body = null, token = null } = {}) {
  const { apiUrl } = await getLocal(['apiUrl']);
  if (!apiUrl) throw new Error('Extensión no configurada');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${apiUrl}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      const data = await res.json();
      if (data.detail) detail = typeof data.detail === 'string' ? data.detail : detail;
    } catch (_) { /* respuesta no-JSON */ }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
    if (res.status === 204) return null;
  return res.json();
}

// ─── Handlers de mensajes ────────────────────────────────────────────────────

async function handleLogin({ apiUrl, email, password, pin, deviceName }) {
  const cleanUrl = apiUrl.trim().replace(/\/+$/, '');
  await chrome.storage.local.set({ apiUrl: cleanUrl });
  const data = await api('/api/extension/login', {
    method: 'POST',
    body: { email, password, name: deviceName || 'Chrome' },
  });
  const encToken = await encryptWithPin(data.token, pin);
  await chrome.storage.local.set({ apiUrl: cleanUrl, email: data.email, encToken, pinAttempts: 0 });
  await chrome.storage.session.set({ token: data.token, unlockedUntil: Date.now() + UNLOCK_MS });
  return { ok: true, email: data.email };
}

async function handleUnlock({ pin }) {
  const { encToken, pinAttempts = 0 } = await getLocal(['encToken', 'pinAttempts']);
  if (!encToken) return { ok: false, error: 'Extensión no configurada' };
  try {
    const token = await decryptWithPin(encToken, pin);
    await chrome.storage.local.set({ pinAttempts: 0 });
    await chrome.storage.session.set({ token, unlockedUntil: Date.now() + UNLOCK_MS });
    return { ok: true };
  } catch (_) {
    const attempts = pinAttempts + 1;
    if (attempts >= MAX_PIN_ATTEMPTS) {
      await wipeAll();
      return { ok: false, wiped: true, error: 'Demasiados intentos. Sesión borrada: vuelve a conectar la extensión.' };
    }
    await chrome.storage.local.set({ pinAttempts: attempts });
    return { ok: false, error: `PIN incorrecto (${attempts}/${MAX_PIN_ATTEMPTS})` };
  }
}

async function handleLock() {
  await chrome.storage.session.remove(['token', 'unlockedUntil']);
  return { ok: true };
}

async function handleLogout() {
  const token = await getUnlockedToken();
  if (token) {
    try { await api('/api/extension/logout', { method: 'POST', token }); } catch (_) { /* revocar es best-effort */ }
  }
  await wipeAll();
  return { ok: true };
}

// Guard anti-confusión: recordamos qué credenciales se ofrecieron a cada tab y
// para qué dominio, y solo entregamos el secreto si el FILL viene de ese mismo
// dominio y de un id ofrecido. (sessionStorage por tab)
async function rememberMatch(tabId, domain, ids) {
  await chrome.storage.session.set({ [`match_${tabId}`]: { domain, ids, at: Date.now() } });
}

async function handleMatch({ domain }, sender) {
  const token = await getUnlockedToken();
  if (!token) return { ok: false, locked: true };
  const data = await api(`/api/extension/credentials/match?domain=${encodeURIComponent(domain)}`, { token });
  await renewUnlock();
  if (sender.tab?.id != null) {
    await rememberMatch(sender.tab.id, data.domain, data.items.map((i) => i.id));
  }
  return { ok: true, items: data.items };
}

async function handleFill({ credId }, sender) {
  const token = await getUnlockedToken();
  if (!token) return { ok: false, locked: true };

  const tabId = sender.tab?.id;
  const senderDomain = hostnameOf(sender.url || sender.tab?.url || '');
  const stored = tabId != null ? (await getSession([`match_${tabId}`]))[`match_${tabId}`] : null;
  const allowed = stored
    && stored.ids.includes(credId)
    && (senderDomain === stored.domain || senderDomain.endsWith('.' + stored.domain));
  if (!allowed) return { ok: false, error: 'Credencial no ofrecida para esta página' };

  const data = await api(`/api/extension/credentials/${credId}/secret`, { token });
  await renewUnlock();
  return { ok: true, username: data.username, password: data.password };
}

async function handleSubmitDetected({ domain, url, username, password }, sender) {
  if (!username || !password || sender.tab?.id == null) return { ok: true };
  await chrome.storage.session.set({
    [`pending_${sender.tab.id}`]: { domain, url, username, password, at: Date.now() },
  });
  return { ok: true };
}

async function handleGetPendingSave(_msg, sender) {
  const tabId = sender.tab?.id;
  if (tabId == null) return { pending: null };
  const key = `pending_${tabId}`;
  const stored = (await getSession([key]))[key];
  if (!stored || Date.now() - stored.at > PENDING_SAVE_TTL_MS) {
    if (stored) await chrome.storage.session.remove([key]);
    return { pending: null };
  }
  // Solo ofrecer guardar en el MISMO dominio donde se hizo el login.
  const senderDomain = hostnameOf(sender.url || '');
  if (senderDomain !== stored.domain) return { pending: null };
  return { pending: { domain: stored.domain, username: stored.username } };
}

async function handleDismissPending(_msg, sender) {
  if (sender.tab?.id != null) await chrome.storage.session.remove([`pending_${sender.tab.id}`]);
  return { ok: true };
}

async function handleSavePending(_msg, sender) {
  const token = await getUnlockedToken();
  if (!token) return { ok: false, locked: true };
  const tabId = sender.tab?.id;
  const key = `pending_${tabId}`;
  const stored = (await getSession([key]))[key];
  if (!stored) return { ok: false, error: 'Nada pendiente por guardar' };

  // Evitar duplicados: si ya existe una credencial del dominio con el mismo usuario.
  const match = await api(`/api/extension/credentials/match?domain=${encodeURIComponent(stored.domain)}`, { token });
  const exists = match.items.some((i) => (i.username || '').toLowerCase() === stored.username.toLowerCase());
  if (exists) {
    await chrome.storage.session.remove([key]);
    return { ok: true, already: true };
  }

  await api('/api/extension/credentials', {
    method: 'POST',
    token,
    body: {
      label: stored.domain,
      username: stored.username,
      password: stored.password,
      url: `https://${stored.domain}`,
    },
  });
  await chrome.storage.session.remove([key]);
  await renewUnlock();
  return { ok: true };
}

function hostnameOf(url) {
  try {
    let host = new URL(url).hostname.toLowerCase();
    return host.startsWith('www.') ? host.slice(4) : host;
  } catch (_) {
    return '';
  }
}

// ─── Router de mensajes ──────────────────────────────────────────────────────

const HANDLERS = {
  STATUS: () => status(),
  LOGIN: (msg) => handleLogin(msg),
  UNLOCK: (msg) => handleUnlock(msg),
  LOCK: () => handleLock(),
  LOGOUT: () => handleLogout(),
  MATCH: (msg, sender) => handleMatch(msg, sender),
  FILL: (msg, sender) => handleFill(msg, sender),
  SUBMIT_DETECTED: (msg, sender) => handleSubmitDetected(msg, sender),
  GET_PENDING_SAVE: (msg, sender) => handleGetPendingSave(msg, sender),
  DISMISS_PENDING: (msg, sender) => handleDismissPending(msg, sender),
  SAVE_PENDING: (msg, sender) => handleSavePending(msg, sender),
};

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  const handler = HANDLERS[msg?.type];
  if (!handler) return false;
  handler(msg, sender)
    .then(sendResponse)
    .catch((err) => sendResponse({ ok: false, error: err.message || 'Error inesperado' }));
  return true; // respuesta asíncrona
});
