// Service worker de la extensión: única pieza que conoce el token y habla con la API.
// El token vive cifrado con el PIN en chrome.storage.local; al desbloquear se guarda
// en chrome.storage.session (memoria, se borra al cerrar el navegador) por un tiempo
// limitado y deslizante. El token y las contraseñas JAMÁS se exponen a las páginas:
// solo viajan al content script en respuesta a una acción explícita del usuario.

import { encryptWithPin, decryptWithPin } from './crypto.js';

const DEFAULT_API_URL = 'https://dev-hub-whry8q.fly.dev';

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
  const { email, encToken, pinLength, pinAttempts = 0 } = await getLocal([
    'email', 'encToken', 'pinLength', 'pinAttempts',
  ]);
  const token = await getUnlockedToken();
  const { unlockedUntil } = await getSession(['unlockedUntil']);
  return {
    configured: Boolean(encToken),       // ya tiene PIN definido
    needsPin: Boolean(token) && !encToken, // logueado pero sin PIN aún
    unlocked: Boolean(token),
    email: email || null,
    apiUrl: await resolveApiUrl(),
    unlockedUntil: token ? unlockedUntil : null,
    // Solo la CANTIDAD de dígitos del PIN (para las casillas y el auto-desbloqueo
    // del popup), jamás el PIN ni nada derivado de él.
    pinLength: pinLength || null,
    attempts: pinAttempts,
  };
}

// ─── Llamadas a la API ───────────────────────────────────────────────────────

function resolveApiUrl() {
  return DEFAULT_API_URL;
}

async function api(path, { method = 'GET', body = null, token = null } = {}) {
  const apiUrl = resolveApiUrl();
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

// Paso 1: login con email+contraseña. Crea el token pero aún no se guarda cifrado
// (eso ocurre al definir el PIN). El token queda desbloqueado en sesión.
async function handleLogin({ email, password, totpCode, deviceName }) {
  const data = await api('/api/extension/login', {
    method: 'POST',
    body: { email, password, name: deviceName || 'Chrome', totp_code: totpCode || null },
  });
  await chrome.storage.local.set({ email: data.email });
  await chrome.storage.session.set({ token: data.token, unlockedUntil: Date.now() + UNLOCK_MS });
  return { ok: true, email: data.email };
}

// Paso 2: definir el PIN una sola vez. Cifra el token ya obtenido en el login.
async function handleSetPin({ pin }) {
  const token = await getUnlockedToken();
  if (!token) return { ok: false, error: 'Inicia sesión primero' };
  const encToken = await encryptWithPin(token, pin);
  await chrome.storage.local.set({ encToken, pinAttempts: 0, pinLength: pin.length });
  await renewUnlock();
  return { ok: true };
}

async function handleUnlock({ pin }) {
  const { encToken, pinAttempts = 0 } = await getLocal(['encToken', 'pinAttempts']);
  if (!encToken) return { ok: false, error: 'Extensión no configurada' };
  try {
    const token = await decryptWithPin(encToken, pin);
    // pinLength también aquí: migra instalaciones que crearon el PIN antes de
    // que existiera el auto-desbloqueo (se aprende en el primer acierto).
    await chrome.storage.local.set({ pinAttempts: 0, pinLength: pin.length });
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
  // Un login con contraseña invalida cualquier sospecha de OAuth en esa pestaña.
  await chrome.storage.session.remove([`oauth_${sender.tab.id}`]);
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

  // No ofrecer guardar si ya existe una credencial con ese usuario en el dominio.
  // Requiere estar desbloqueado para consultar; si está bloqueado, no mostramos el
  // banner todavía (evita falsos "¿guardar?" sobre credenciales ya guardadas).
  const token = await getUnlockedToken();
  if (!token) return { pending: null };
  try {
    const match = await api(`/api/extension/credentials/match?domain=${encodeURIComponent(stored.domain)}`, { token });
    const exists = match.items.some(
      (i) => (i.username || '').toLowerCase() === stored.username.toLowerCase(),
    );
    if (exists) {
      await chrome.storage.session.remove([key]);
      return { pending: null };
    }
  } catch (_) {
    return { pending: null };
  }

  return { pending: { domain: stored.domain, username: stored.username } };
}

async function handleDismissPending(_msg, sender) {
  if (sender.tab?.id != null) await chrome.storage.session.remove([`pending_${sender.tab.id}`]);
  return { ok: true };
}

// Abre el popup de la extensión (Chrome 127+). El banner lo usa tras dejar el
// borrador, para llevar al usuario directo al formulario prellenado. Si el
// navegador no lo permite, el banner muestra la instrucción manual.
async function handleOpenPopup() {
  try {
    await chrome.action.openPopup();
    return { opened: true };
  } catch (_) {
    return { opened: false };
  }
}

function hostnameOf(url) {
  try {
    let host = new URL(url).hostname.toLowerCase();
    return host.startsWith('www.') ? host.slice(4) : host;
  } catch (_) {
    return '';
  }
}

// ─── Bóveda en el popup ──────────────────────────────────────────────────────

async function handleVaultList() {
  const token = await getUnlockedToken();
  if (!token) return { ok: false, locked: true };
  const data = await api('/api/extension/credentials', { token });
  await renewUnlock();
  return { ok: true, items: data.items };
}

async function handleGetSecret({ credId }) {
  // Devuelve usuario y contraseña para que el POPUP los use (el portapapeles
  // funciona en el popup, no en el service worker). El popup lo pide al ABRIR
  // el menú de copiar, así el clic posterior escribe dentro del gesto.
  const token = await getUnlockedToken();
  if (!token) return { ok: false, locked: true };
  const data = await api(`/api/extension/credentials/${credId}/secret`, { token });
  await renewUnlock();
  return { ok: true, username: data.username || '', password: data.password || '' };
}

async function handleDeleteCredential({ credId }) {
  const token = await getUnlockedToken();
  if (!token) return { ok: false, locked: true };
  await api(`/api/extension/credentials/${credId}`, { method: 'DELETE', token });
  await renewUnlock();
  return { ok: true };
}

async function handleUpdateCredential({ credId, fields }) {
  const token = await getUnlockedToken();
  if (!token) return { ok: false, locked: true };
  await api(`/api/extension/credentials/${credId}`, { method: 'PATCH', token, body: fields });
  await renewUnlock();
  return { ok: true };
}

async function handleCreateCredential({ fields }) {
  const token = await getUnlockedToken();
  if (!token) return { ok: false, locked: true };
  const data = await api('/api/extension/credentials', { method: 'POST', token, body: fields });
  await renewUnlock();
  return { ok: true, id: data.id };
}

// Borrador de credencial pendiente (desde "Editar antes de guardar" del banner).
// Lo consume el popup al abrirse para prellenar el formulario.
async function handleGetDraft() {
  const { draft } = await getSession(['draft']);
  if (!draft || Date.now() - draft.at > PENDING_SAVE_TTL_MS) {
    if (draft) await chrome.storage.session.remove(['draft']);
    return { draft: null };
  }
  return { draft };
}

async function handleSetDraft({ draft }) {
  await chrome.storage.session.set({ draft: { ...draft, at: Date.now() } });
  return { ok: true };
}

// ─── Detección de logins OAuth (Google/GitHub/Microsoft) ────────────────────
// El content script avisa cuando el usuario hace clic en un botón tipo
// "Continuar con Google". No podemos ver qué cuenta eligió (el flujo ocurre en
// el dominio del proveedor), así que al volver ofrecemos guardar el MÉTODO y el
// usuario completa el correo al editar.

async function handleOauthDetected({ domain, provider }, sender) {
  if (sender.tab?.id == null || !domain || !provider) return { ok: true };
  await chrome.storage.session.set({
    [`oauth_${sender.tab.id}`]: { domain, provider, at: Date.now() },
  });
  return { ok: true };
}

async function handleGetPendingOauth(_msg, sender) {
  const tabId = sender.tab?.id;
  if (tabId == null) return { pending: null };
  const key = `oauth_${tabId}`;
  const stored = (await getSession([key]))[key];
  if (!stored || Date.now() - stored.at > PENDING_SAVE_TTL_MS) {
    if (stored) await chrome.storage.session.remove([key]);
    return { pending: null };
  }
  // Tras el roundtrip por el proveedor se puede aterrizar en un subdominio
  // (app.sitio.com): aceptamos parentesco en ambos sentidos, nunca dominios ajenos.
  const senderDomain = hostnameOf(sender.url || '');
  const related =
    senderDomain === stored.domain ||
    senderDomain.endsWith('.' + stored.domain) ||
    stored.domain.endsWith('.' + senderDomain);
  if (!related) return { pending: null };

  // No ofrecer si ya hay una credencial de ese proveedor en el dominio.
  const token = await getUnlockedToken();
  if (!token) return { pending: null };
  try {
    const match = await api(`/api/extension/credentials/match?domain=${encodeURIComponent(stored.domain)}`, { token });
    if (match.items.some((i) => i.login_via === stored.provider)) {
      await chrome.storage.session.remove([key]);
      return { pending: null };
    }
  } catch (_) {
    return { pending: null };
  }
  return { pending: { domain: stored.domain, provider: stored.provider } };
}

async function handleDismissOauth(_msg, sender) {
  if (sender.tab?.id != null) await chrome.storage.session.remove([`oauth_${sender.tab.id}`]);
  return { ok: true };
}

// Crea el borrador para el formulario del popup (el usuario completa el correo).
async function handleDraftFromOauth(_msg, sender) {
  const tabId = sender.tab?.id;
  if (tabId == null) return { ok: false };
  const key = `oauth_${tabId}`;
  const stored = (await getSession([key]))[key];
  if (!stored) return { ok: false };
  await chrome.storage.session.set({
    draft: {
      label: stored.domain,
      url: `https://${stored.domain}`,
      username: '',
      login_via: stored.provider,
      at: Date.now(),
    },
  });
  await chrome.storage.session.remove([key]);
  return { ok: true };
}

// Convierte el "pending" de una pestaña (con su contraseña) en un borrador editable
// que el popup abrirá en el formulario. Lo usa el botón "Editar" del banner.
async function handleDraftFromPending(_msg, sender) {
  const tabId = sender.tab?.id;
  if (tabId == null) return { ok: false };
  const key = `pending_${tabId}`;
  const stored = (await getSession([key]))[key];
  if (!stored) return { ok: false };
  await chrome.storage.session.set({
    draft: {
      label: stored.domain,
      url: `https://${stored.domain}`,
      username: stored.username,
      password: stored.password,
      at: Date.now(),
    },
  });
  await chrome.storage.session.remove([key]);
  return { ok: true };
}

async function handleClearDraft() {
  await chrome.storage.session.remove(['draft']);
  return { ok: true };
}

// Dominio de la pestaña activa, para la sección "este sitio" del popup.
async function handleActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url || !/^https?:/.test(tab.url)) {
    return { domain: null, tabId: null };
  }
  return { domain: hostnameOf(tab.url), tabId: tab.id, url: tab.url };
}

// Rellena el formulario de la pestaña activa con una credencial (botón del popup).
async function handleFillActiveTab({ credId }) {
  const token = await getUnlockedToken();
  if (!token) return { ok: false, locked: true };

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) return { ok: false, error: 'No hay pestaña activa' };

  const data = await api(`/api/extension/credentials/${credId}/secret`, { token });
  await renewUnlock();

  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    args: [data.username || '', data.password || ''],
    func: (username, password) => {
      const setNativeValue = (input, value) => {
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
        setter.call(input, value);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      };
      const pwd = document.querySelector('input[type="password"]');
      if (pwd && password) setNativeValue(pwd, password);
      // Campo de usuario: el input de texto/email visible más cercano antes del password.
      const scope = pwd?.form || document;
      const userInputs = Array.from(
        scope.querySelectorAll('input[type="email"], input[type="text"], input:not([type])'),
      ).filter((el) => el.offsetParent !== null);
      const userInput = userInputs[userInputs.length - 1];
      if (userInput && username) setNativeValue(userInput, username);
    },
  });
  return { ok: true };
}

// ─── Router de mensajes ──────────────────────────────────────────────────────

const HANDLERS = {
  STATUS: () => status(),
  LOGIN: (msg) => handleLogin(msg),
  SET_PIN: (msg) => handleSetPin(msg),
  UNLOCK: (msg) => handleUnlock(msg),
  LOCK: () => handleLock(),
  LOGOUT: () => handleLogout(),
  MATCH: (msg, sender) => handleMatch(msg, sender),
  FILL: (msg, sender) => handleFill(msg, sender),
  SUBMIT_DETECTED: (msg, sender) => handleSubmitDetected(msg, sender),
  GET_PENDING_SAVE: (msg, sender) => handleGetPendingSave(msg, sender),
  DISMISS_PENDING: (msg, sender) => handleDismissPending(msg, sender),
  OPEN_POPUP: () => handleOpenPopup(),
  VAULT_LIST: () => handleVaultList(),
  GET_SECRET: (msg) => handleGetSecret(msg),
  DELETE_CREDENTIAL: (msg) => handleDeleteCredential(msg),
  UPDATE_CREDENTIAL: (msg) => handleUpdateCredential(msg),
  CREATE_CREDENTIAL: (msg) => handleCreateCredential(msg),
  ACTIVE_TAB: () => handleActiveTab(),
  FILL_ACTIVE_TAB: (msg) => handleFillActiveTab(msg),
  GET_DRAFT: () => handleGetDraft(),
  SET_DRAFT: (msg) => handleSetDraft(msg),
  CLEAR_DRAFT: () => handleClearDraft(),
  DRAFT_FROM_PENDING: (msg, sender) => handleDraftFromPending(msg, sender),
  OAUTH_DETECTED: (msg, sender) => handleOauthDetected(msg, sender),
  GET_PENDING_OAUTH: (msg, sender) => handleGetPendingOauth(msg, sender),
  DISMISS_OAUTH: (msg, sender) => handleDismissOauth(msg, sender),
  DRAFT_FROM_OAUTH: (msg, sender) => handleDraftFromOauth(msg, sender),
};

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  const handler = HANDLERS[msg?.type];
  if (!handler) return false;
  handler(msg, sender)
    .then(sendResponse)
    .catch((err) => sendResponse({ ok: false, error: err.message || 'Error inesperado' }));
  return true; // respuesta asíncrona
});
