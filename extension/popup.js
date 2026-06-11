// Lógica del popup: configurar (login + PIN), desbloquear, bloquear, cerrar sesión.

const $ = (id) => document.getElementById(id);

const views = ['view-loading', 'view-setup', 'view-locked', 'view-unlocked'];

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

let remainingTimer = null;

async function refresh() {
  clearInterval(remainingTimer);
  const st = await send({ type: 'STATUS' });

  if (!st.configured) {
    setBadge('sin conectar', '');
    showView('view-setup');
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

function showError(id, message) {
  const el = $(id);
  el.textContent = message;
  el.hidden = false;
}

// ─── Setup (primera vez) ─────────────────────────────────────────────────────

$('setup-submit').addEventListener('click', async () => {
  $('setup-error').hidden = true;
  const apiUrl = $('setup-url').value.trim();
  const email = $('setup-email').value.trim();
  const password = $('setup-password').value;
  const pin = $('setup-pin').value.trim();
  const pin2 = $('setup-pin2').value.trim();

  if (!apiUrl.startsWith('http')) return showError('setup-error', 'Pon la URL completa de tu Dev Hub (https://…)');
  if (!email || !password) return showError('setup-error', 'Email y contraseña son obligatorios');
  if (!/^\d{4,}$/.test(pin)) return showError('setup-error', 'El PIN debe ser numérico, mínimo 4 dígitos');
  if (pin !== pin2) return showError('setup-error', 'Los PIN no coinciden');

  const btn = $('setup-submit');
  btn.disabled = true;
  btn.textContent = 'Conectando…';
  try {
    const res = await send({ type: 'LOGIN', apiUrl, email, password, pin, deviceName: 'Chrome' });
    if (!res.ok) throw new Error(res.error || 'No se pudo conectar');
    $('setup-password').value = '';
    await refresh();
  } catch (err) {
    showError('setup-error', err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Conectar';
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
  if (!confirm('¿Cerrar sesión? Tendrás que volver a conectar la extensión.')) return;
  await send({ type: 'LOGOUT' });
  await refresh();
}

$('unlocked-logout').addEventListener('click', logout);
$('locked-logout').addEventListener('click', logout);

refresh();
