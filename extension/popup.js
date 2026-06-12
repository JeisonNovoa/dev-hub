// Lógica del popup. Flujo en pasos: login (email+pass) → crear PIN (una vez) →
// desbloqueado. Si ya hay PIN definido y está bloqueado, pide solo el PIN.

const $ = (id) => document.getElementById(id);

const views = ['view-loading', 'view-login', 'view-setpin', 'view-locked', 'view-unlocked', 'view-form'];

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
  $('vault-email').textContent = st.email || '';
  $('vault-footer-status').title = `Conectado como ${st.email || ''} en ${st.apiUrl || ''}`;
  showView('view-unlocked');
  const tick = () => {
    const ms = st.unlockedUntil - Date.now();
    if (ms <= 0) { refresh(); return; }
    const m = Math.floor(ms / 60000);
    const s = Math.floor((ms % 60000) / 1000);
    $('unlock-remaining').textContent = `${m}:${String(s).padStart(2, '0')}`;
  };
  tick();
  remainingTimer = setInterval(tick, 1000);
  loadVault();
}

// ─── Bóveda ──────────────────────────────────────────────────────────────────

let allCreds = [];
let activeDomain = null;

// Mismos íconos SVG del dashboard de Dev Hub.
const ICONS = {
  copy: 'M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z',
  open: 'M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14',
  check: 'M5 13l4 4L19 7',
  dots: 'M12 5.5v.01M12 12v.01M12 18.5v.01',
};

function svgIcon(name) {
  const span = document.createElement('span');
  const width = name === 'dots' ? 3 : 2;
  span.innerHTML =
    `<svg width="15" height="15" fill="none" stroke="currentColor" viewBox="0 0 24 24">` +
    `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="${width}" d="${ICONS[name]}"/></svg>`;
  return span.firstChild;
}

let toastTimer = null;
function showToast(message) {
  const t = $('vault-toast');
  t.textContent = message;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2500);
}

async function writeClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (_) {
    // Respaldo para Chrome que bloquee la Clipboard API en el popup.
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    return ok;
  }
}

function buildFavicon(cred) {
  const fav = document.createElement('span');
  fav.className = 'cred-favicon';
  const letter = (cred.label || '?')[0].toUpperCase();
  if (cred.domain) {
    const img = document.createElement('img');
    img.alt = '';
    img.src = `https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://${cred.domain}&size=32`;
    img.addEventListener('error', () => { fav.textContent = letter; });
    fav.appendChild(img);
  } else {
    fav.textContent = letter;
  }
  return fav;
}

function closeMenus() {
  document.querySelectorAll('.cred-menu').forEach((m) => m.remove());
}

function openMenu(anchor, options) {
  closeMenus();
  const menu = document.createElement('div');
  menu.className = 'cred-menu';
  options.forEach((opt) => {
    const b = document.createElement('button');
    b.textContent = opt.label;
    if (opt.danger) b.className = 'danger';
    b.addEventListener('click', (e) => { e.stopPropagation(); closeMenus(); opt.onClick(); });
    menu.appendChild(b);
  });
  document.body.appendChild(menu);
  const r = anchor.getBoundingClientRect();
  menu.style.top = `${Math.min(r.bottom + 4, window.innerHeight - menu.offsetHeight - 8)}px`;
  menu.style.left = `${Math.max(8, r.right - menu.offsetWidth)}px`;
  setTimeout(() => document.addEventListener('click', closeMenus, { once: true }), 0);
}

async function copyField(credId, field, btn) {
  const res = await send({ type: 'COPY_SECRET', credId, field });
  if (!res.ok) {
    showToast(res.error || 'No se pudo obtener el valor');
    if (res.locked) refresh();
    return;
  }
  const ok = await writeClipboard(res.value || '');
  if (!ok) {
    showToast('No se pudo copiar al portapapeles');
    return;
  }
  const previous = btn.firstChild;
  btn.replaceChildren(svgIcon('check'));
  btn.classList.add('copied');
  setTimeout(() => {
    btn.replaceChildren(previous);
    btn.classList.remove('copied');
  }, 1400);
}

function credRow(cred, { showFill = false } = {}) {
  const row = document.createElement('div');
  row.className = 'cred-row';

  const fav = buildFavicon(cred);

  const info = document.createElement('div');
  info.className = 'cred-info';
  const name = document.createElement('div');
  name.className = 'cred-name';
  name.textContent = cred.label;
  if (cred.login_via && cred.login_via !== 'email') {
    const badge = document.createElement('span');
    badge.className = `provider-badge provider-${cred.login_via}`;
    badge.textContent = cred.login_via === 'other' ? 'otro' : cred.login_via;
    name.appendChild(badge);
  }
  const user = document.createElement('div');
  user.className = 'cred-user';
  user.textContent = cred.username || '—';
  info.append(name, user);

  const actions = document.createElement('div');
  actions.className = 'cred-actions';

  // Solo los accesos con email+contraseña se pueden rellenar; los OAuth informan.
  const isEmailLogin = !cred.login_via || cred.login_via === 'email';

  if (showFill && isEmailLogin) {
    const fill = document.createElement('button');
    fill.className = 'cred-action cred-fill';
    fill.textContent = 'rellenar';
    fill.title = 'Rellenar esta página';
    fill.addEventListener('click', async () => {
      const res = await send({ type: 'FILL_ACTIVE_TAB', credId: cred.id });
      if (res.ok) window.close();
    });
    actions.appendChild(fill);
  }

  if (cred.url) {
    const open = document.createElement('button');
    open.className = 'cred-action';
    open.title = 'Abrir sitio';
    open.appendChild(svgIcon('open'));
    open.addEventListener('click', () => chrome.tabs.create({ url: cred.url }));
    actions.appendChild(open);
  }

  const copy = document.createElement('button');
  copy.className = 'cred-action';
  copy.title = 'Copiar';
  copy.appendChild(svgIcon('copy'));
  copy.addEventListener('click', (e) => {
    e.stopPropagation();
    const options = [{ label: 'Copiar usuario', onClick: () => copyField(cred.id, 'username', copy) }];
    if (isEmailLogin) {
      options.push({ label: 'Copiar contraseña', onClick: () => copyField(cred.id, 'password', copy) });
    }
    openMenu(copy, options);
  });
  actions.appendChild(copy);

  const more = document.createElement('button');
  more.className = 'cred-action';
  more.title = 'Más';
  more.appendChild(svgIcon('dots'));
  more.addEventListener('click', (e) => {
    e.stopPropagation();
    const options = [];
    if (isEmailLogin) {
      options.push({
        label: 'Autocompletar esta página',
        onClick: async () => { const r = await send({ type: 'FILL_ACTIVE_TAB', credId: cred.id }); if (r.ok) window.close(); },
      });
    }
    options.push(
      { label: 'Editar', onClick: () => openForm(cred) },
      { label: 'Eliminar', danger: true, onClick: () => deleteCred(cred) },
    );
    openMenu(more, options);
  });
  actions.appendChild(more);

  row.append(fav, info, actions);
  return row;
}

function renderVault(filter = '') {
  const q = filter.trim().toLowerCase();
  const category = $('vault-category').value;
  const list = $('vault-list');
  list.innerHTML = '';

  const filtered = allCreds.filter((c) => {
    if (category && c.category !== category) return false;
    if (!q) return true;
    return (c.label || '').toLowerCase().includes(q) || (c.username || '').toLowerCase().includes(q);
  });

  $('vault-count').textContent = filtered.length ? `(${filtered.length})` : '';
  $('vault-empty').hidden = filtered.length > 0;
  filtered.forEach((c) => list.appendChild(credRow(c)));

  // Sección "este sitio"
  const siteBox = $('vault-site');
  if (activeDomain) {
    const matches = allCreds.filter(
      (c) => c.domain && (c.domain === activeDomain || activeDomain.endsWith('.' + c.domain)),
    );
    if (matches.length) {
      $('vault-site-domain').textContent = activeDomain;
      const siteList = $('vault-site-list');
      siteList.innerHTML = '';
      matches.forEach((c) => siteList.appendChild(credRow(c, { showFill: true })));
      siteBox.hidden = false;
    } else {
      siteBox.hidden = true;
    }
  } else {
    siteBox.hidden = true;
  }
}

async function loadVault() {
  $('vault-error').hidden = true;
  const [vault, tab] = await Promise.all([
    send({ type: 'VAULT_LIST' }),
    send({ type: 'ACTIVE_TAB' }),
  ]);
  if (!vault.ok) {
    if (vault.locked) { refresh(); return; }
    $('vault-empty').hidden = true;
    $('vault-error').textContent =
      `No se pudo cargar la bóveda: ${vault.error || 'error de conexión'}. ` +
      'Si tu Dev Hub está en Render gratis puede estar despertando — espera ~30s y reintenta. ' +
      'Si persiste, revisa la URL del servidor (cerrar sesión → configuración avanzada).';
    $('vault-error').hidden = false;
    return;
  }
  allCreds = vault.items;
  activeDomain = tab.domain || null;
  renderVault($('vault-search').value);

  // Si el banner dejó un borrador ("Editar antes de guardar"), abrir el formulario.
  const { draft } = await send({ type: 'GET_DRAFT' });
  if (draft) {
    await send({ type: 'CLEAR_DRAFT' });
    openForm(null, draft);
  }
}

async function deleteCred(cred) {
  if (!confirm(`¿Mover "${cred.label}" a la papelera?`)) return;
  const res = await send({ type: 'DELETE_CREDENTIAL', credId: cred.id });
  if (res.ok) loadVault();
}

$('vault-search').addEventListener('input', (e) => renderVault(e.target.value));
$('vault-category').addEventListener('change', () => renderVault($('vault-search').value));
$('vault-new').addEventListener('click', () => openForm(null));

// ─── Formulario (nueva / editar) ─────────────────────────────────────────────

function syncPasswordBlock() {
  // Para accesos OAuth (Google, GitHub…) no hay contraseña propia que guardar.
  $('form-password-block').hidden = $('form-login-via').value !== 'email';
}

// cred: credencial existente a editar (o null para nueva).
// draft: datos prellenados (del banner "editar antes de guardar"), opcional.
function openForm(cred, draft = null) {
  $('form-id').value = cred?.id || '';
  $('form-title').textContent = cred ? 'Editar credencial' : 'Nueva credencial';
  $('form-label').value = cred?.label || draft?.label || (activeDomain || '');
  $('form-url').value = cred?.url || draft?.url || (activeDomain ? `https://${activeDomain}` : '');
  $('form-username').value = cred?.username || draft?.username || '';
  $('form-password').value = draft?.password || '';
  $('form-password').placeholder = cred ? '(sin cambios)' : '';
  $('form-category').value = cred?.category || 'personal';
  $('form-login-via').value = cred?.login_via || draft?.login_via || 'email';
  syncPasswordBlock();
  $('form-error').hidden = true;
  showView('view-form');
  $('form-label').focus();
}

$('form-login-via').addEventListener('change', syncPasswordBlock);

$('form-back').addEventListener('click', () => { showView('view-unlocked'); loadVault(); });
$('form-pwd-toggle').addEventListener('click', () => {
  const i = $('form-password');
  i.type = i.type === 'password' ? 'text' : 'password';
});

$('form-submit').addEventListener('click', async () => {
  $('form-error').hidden = true;
  const id = $('form-id').value;
  const label = $('form-label').value.trim();
  if (!label) { $('form-error').textContent = 'El nombre es obligatorio'; $('form-error').hidden = false; return; }

  const loginVia = $('form-login-via').value;
  const fields = {
    label,
    url: $('form-url').value.trim(),
    username: $('form-username').value.trim(),
    category: $('form-category').value,
    login_via: loginVia,
  };
  const pwd = $('form-password').value;
  // Al editar, solo cambia la contraseña si se escribió algo. OAuth no lleva contraseña.
  if (loginVia === 'email' && (pwd || !id)) fields.password = pwd;

  const btn = $('form-submit');
  btn.disabled = true;
  btn.textContent = 'Guardando…';
  try {
    const res = id
      ? await send({ type: 'UPDATE_CREDENTIAL', credId: Number(id), fields })
      : await send({ type: 'CREATE_CREDENTIAL', fields });
    if (!res.ok) throw new Error(res.error || 'No se pudo guardar');
    showView('view-unlocked');
    await loadVault();
  } catch (err) {
    $('form-error').textContent = err.message;
    $('form-error').hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Guardar';
  }
});

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
