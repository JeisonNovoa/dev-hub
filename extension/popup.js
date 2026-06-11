// Lógica del popup. Flujo en pasos: login (email+pass) → crear PIN (una vez) →
// desbloqueado. Si ya hay PIN definido y está bloqueado, pide solo el PIN.

const $ = (id) => document.getElementById(id);

const views = ['view-loading', 'view-login', 'view-setpin', 'view-locked', 'view-unlocked'];

function showView(id) {
  views.forEach((v) => { $(v).hidden = v !== id; });
}

function setBadge(text, cls) {
  const badge = $('state-badge');
  badge.textContent = text;
  badge.className = `badge ${cls || ''}`;
}

function send(msg) {
  return chrome.runtime.sendMessage(msg);
}

function showError(id, message) {
  const el = $(id);
  el.textContent = message;
  el.hidden = false;
}

let remainingTimer = null;

async function refresh() {
  clearInterval(remainingTimer);
  const st = await send({ type: 'STATUS' });

  if (!st.configured && !st.needsPin) {
    setBadge('sin conectar', '');
    showView('view-login');
    $('login-email').focus();
    return;
  }
  if (st.needsPin) {
    setBadge('crear PIN', 'locked');
    showView('view-setpin');
    $('setpin-pin').focus();
    return;
  }
  if (!st.unlocked) {
    setBadge('bloqueado', 'locked');
    $('locked-email').textContent = st.email || '';
    showView('view-locked');
    $('unlock-pin').value = '';
    $('unlock-pin').focus();
    return;
  }
  setBadge('activo', 'ok');
  $('unlocked-email').textContent = st.email || '';
  showView('view-unlocked');
  const tick = () => {
    const ms = st.unlockedUntil - Date.now();
    if (ms <= 0) { refresh(); return; }
    const m = Math.floor(ms / 60000);
    const s = Math.floor((ms % 60000) / 1000);
    $('unlock-remaining').textContent = `${m}:${String(s).padStart(2, '0')} restantes`;
  };
  tick();
  remainingTimer = setInterval(tick, 1000);
}

// ─── Login (paso 1) ──────────────────────────────────────────────────────────

$('login-advanced-toggle').addEventListener('click', () => {
  const adv = $('login-advanced');
  adv.hidden = !adv.hidden;
});

$('login-submit').addEventListener('click', async () => {
  $('login-error').hidden = true;
  const email = $('login-email').value.trim();
  const password = $('login-password').value;
  const apiUrl = $('login-url').value.trim();

  if (!email || !password) return showError('login-error', 'Email y contraseña son obligatorios');

  const btn = $('login-submit');
  btn.disabled = true;
  btn.textContent = 'Entrando…';
  try {
    const res = await send({ type: 'LOGIN', email, password, apiUrl, deviceName: 'Chrome' });
    if (!res.ok) throw new Error(res.error || 'No se pudo iniciar sesión');
    $('login-password').value = '';
    await refresh(); // pasará a "crear PIN"
  } catch (err) {
    showError('login-error', err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Iniciar sesión';
  }
});

$('login-password').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('login-submit').click(); });

// ─── Crear PIN (paso 2, una sola vez) ────────────────────────────────────────

$('setpin-submit').addEventListener('click', async () => {
  $('setpin-error').hidden = true;
  const pin = $('setpin-pin').value.trim();
  const pin2 = $('setpin-pin2').value.trim();
  if (!/^\d{4,}$/.test(pin)) return showError('setpin-error', 'El PIN debe ser numérico, mínimo 4 dígitos');
  if (pin !== pin2) return showError('setpin-error', 'Los PIN no coinciden');

  const res = await send({ type: 'SET_PIN', pin });
  if (res.ok) {
    await refresh();
  } else {
    showError('setpin-error', res.error || 'No se pudo guardar el PIN');
  }
});

// ─── Desbloquear ─────────────────────────────────────────────────────────────

async function unlock() {
  $('unlock-error').hidden = true;
  const pin = $('unlock-pin').value.trim();
  if (!pin) return;
  const res = await send({ type: 'UNLOCK', pin });
  if (res.ok) {
    await refresh();
  } else {
    showError('unlock-error', res.error);
    $('unlock-pin').value = '';
    if (res.wiped) await refresh();
  }
}

$('unlock-submit').addEventListener('click', unlock);
$('unlock-pin').addEventListener('keydown', (e) => { if (e.key === 'Enter') unlock(); });

// ─── Bloquear / cerrar sesión ────────────────────────────────────────────────

$('lock-now').addEventListener('click', async () => {
  await send({ type: 'LOCK' });
  await refresh();
});

async function logout() {
  if (!confirm('¿Cerrar sesión? Tendrás que volver a iniciar sesión y crear el PIN.')) return;
  await send({ type: 'LOGOUT' });
  await refresh();
}

$('unlocked-logout').addEventListener('click', logout);
$('locked-logout').addEventListener('click', logout);

refresh();
