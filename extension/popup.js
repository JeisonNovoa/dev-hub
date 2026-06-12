// Lógica del popup. Flujo en pasos: login (email+pass) → crear PIN (una vez) →
// desbloqueado. Si ya hay PIN definido y está bloqueado, pide solo el PIN con
// casillas segmentadas y desbloqueo automático al completar los dígitos.

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

// Mensajería blindada: si el service worker estaba dormido y la respuesta se
// pierde (puerto cerrado, sin respuesta), devolvemos un error visible en vez de
// dejar el clic muerto en silencio.
async function send(msg) {
  try {
    const res = await chrome.runtime.sendMessage(msg);
    return res ?? { ok: false, error: 'Sin respuesta de la extensión — intenta de nuevo' };
  } catch (err) {
    return { ok: false, error: err?.message || 'Error de comunicación interna' };
  }
}

function showError(id, message) {
  const el = $(id);
  el.textContent = message;
  el.hidden = false;
}

// ─── Íconos SVG (los mismos del dashboard de Dev Hub) ───────────────────────

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

const EYE_OPEN_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" width="14" height="14">' +
  '<path d="M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"/>' +
  '<path fill-rule="evenodd" d="M1.38 8.28a.87.87 0 0 1 0-.566 7.003 7.003 0 0 1 13.238.006.87.87 0 0 1 0 .566A7.003 7.003 0 0 1 1.379 8.28ZM11 8a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" clip-rule="evenodd"/></svg>';

const EYE_CLOSED_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" width="14" height="14">' +
  '<path fill-rule="evenodd" d="M3.28 2.22a.75.75 0 0 0-1.06 1.06l.345.345A7.024 7.024 0 0 0 .88 7.434a.87.87 0 0 0 0 .566 7.003 7.003 0 0 0 9.68 4.124l.642.643a.75.75 0 0 0 1.06-1.061L3.28 2.22Zm3.89 5.012 2.828 2.827a1.5 1.5 0 0 1-2.828-2.827Z" clip-rule="evenodd"/>' +
  '<path d="M7.245 1.017a7.003 7.003 0 0 1 7.874 6.42.87.87 0 0 1 0 .566 6.98 6.98 0 0 1-1.449 2.86l-1.08-1.08A5.5 5.5 0 0 0 13.5 8a5.5 5.5 0 0 0-6.255-5.44Zm1.282 2.873 1.386 1.386a1.5 1.5 0 0 0-1.386-1.386Z"/></svg>';

const GEN_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" width="14" height="14">' +
  '<path fill-rule="evenodd" d="M13.836 2.477a.75.75 0 0 1 .75.75v3.182a.75.75 0 0 1-.75.75h-3.182a.75.75 0 0 1 0-1.5h1.37l-.84-.841a4.5 4.5 0 0 0-7.08.932.75.75 0 0 1-1.3-.75 6 6 0 0 1 9.44-1.242l.842.84V3.227a.75.75 0 0 1 .75-.75Zm-.911 7.5A.75.75 0 0 1 13.199 11a6 6 0 0 1-9.44 1.241l-.84-.84v1.371a.75.75 0 0 1-1.5 0V9.591a.75.75 0 0 1 .75-.75H5.35a.75.75 0 0 1 0 1.5H3.98l.841.841a4.5 4.5 0 0 0 7.08-.932.75.75 0 0 1 1.024-.273Z" clip-rule="evenodd"/></svg>';

// Conecta un botón "ojo" con su input: alterna password/text y el ícono.
function wireEyeToggle(btnId, inputId) {
  const btn = $(btnId);
  const input = $(inputId);
  const sync = () => { btn.innerHTML = input.type === 'password' ? EYE_OPEN_SVG : EYE_CLOSED_SVG; };
  btn.addEventListener('click', () => {
    input.type = input.type === 'password' ? 'text' : 'password';
    sync();
  });
  sync();
  return sync;
}

// Botón destructivo en dos pasos: el primer clic "arma" la confirmación,
// el segundo (antes de 3 s) ejecuta. Reemplaza el confirm() nativo.
function armConfirm(btn, confirmLabel, fn) {
  const label = btn.textContent;
  let armed = false;
  let timer = null;
  btn.addEventListener('click', () => {
    if (!armed) {
      armed = true;
      btn.textContent = confirmLabel;
      btn.classList.add('armed');
      timer = setTimeout(() => {
        armed = false;
        btn.textContent = label;
        btn.classList.remove('armed');
      }, 3000);
      return;
    }
    clearTimeout(timer);
    armed = false;
    btn.textContent = label;
    btn.classList.remove('armed');
    fn();
  });
}

// ─── Toast ───────────────────────────────────────────────────────────────────

let toastTimer = null;
function showToast(message, type = 'success') {
  const t = $('toast');
  t.textContent = message;
  t.className = `toast show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.classList.remove('show'); }, 2400);
}

// ─── Estado general ──────────────────────────────────────────────────────────

let lastStatus = null;
let remainingTimer = null;

async function refresh() {
  clearInterval(remainingTimer);
  const st = await send({ type: 'STATUS' });
  lastStatus = st;

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
    buildPinUI(st);
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

// ─── Desbloqueo con PIN segmentado ───────────────────────────────────────────
// Si se conoce la cantidad de dígitos (solo la longitud, nunca el PIN), se pintan
// casillas y se intenta desbloquear al escribir el último dígito. Si no (sesión
// creada antes de esta versión), input libre + Enter; la longitud se aprende en
// el primer acierto.

const pinState = { length: null, busy: false };

function buildPinUI(st) {
  const boxes = $('pin-boxes');
  const input = $('unlock-pin');
  pinState.length = st.pinLength || null;
  pinState.busy = false;
  input.value = '';
  boxes.innerHTML = '';

  if (pinState.length) {
    for (let i = 0; i < pinState.length; i++) {
      boxes.appendChild(Object.assign(document.createElement('div'), { className: 'pin-box' }));
    }
    boxes.hidden = false;
    input.classList.add('pin-hidden');
    input.maxLength = pinState.length;
    $('unlock-hint').hidden = true;
    updatePinBoxes();
  } else {
    boxes.hidden = true;
    input.classList.remove('pin-hidden');
    input.maxLength = 12;
    input.placeholder = '••••';
    $('unlock-hint').hidden = false;
  }

  $('unlock-error').hidden = true;
  const warn = $('unlock-warn');
  if (st.attempts >= 3) {
    warn.textContent = `⚠ ${st.attempts}/5 intentos fallidos — al 5º se borra la sesión`;
    warn.hidden = false;
  } else {
    warn.hidden = true;
  }
  input.focus();
}

function updatePinBoxes() {
  if (!pinState.length) return;
  const value = $('unlock-pin').value;
  const focused = document.activeElement === $('unlock-pin');
  Array.from($('pin-boxes').children).forEach((box, i) => {
    box.textContent = i < value.length ? '•' : '';
    box.classList.toggle('filled', i < value.length);
    box.classList.toggle('active', focused && i === value.length && !pinState.busy);
  });
}

async function unlock() {
  if (pinState.busy) return;
  const input = $('unlock-pin');
  const pin = input.value.trim();
  if (!pin) return;
  pinState.busy = true;
  $('unlock-error').hidden = true;

  const res = await send({ type: 'UNLOCK', pin });
  if (res.ok) {
    await refresh();
    return;
  }

  pinState.busy = false;
  input.value = '';
  updatePinBoxes();
  const wrap = $('pin-wrap');
  wrap.classList.remove('shake');
  void wrap.offsetWidth; // reinicia la animación
  wrap.classList.add('shake');
  showError('unlock-error', res.error);
  if (res.wiped) {
    await refresh();
  } else {
    input.focus();
  }
}

$('unlock-pin').addEventListener('input', () => {
  const input = $('unlock-pin');
  input.value = input.value.replace(/\D/g, '').slice(0, pinState.length || 12);
  if (!pinState.length) return;
  updatePinBoxes();
  if (input.value.length === pinState.length) unlock();
});
$('unlock-pin').addEventListener('keydown', (e) => { if (e.key === 'Enter') unlock(); });
$('unlock-pin').addEventListener('focus', updatePinBoxes);
$('unlock-pin').addEventListener('blur', updatePinBoxes);
$('pin-boxes').addEventListener('click', () => $('unlock-pin').focus());

// ─── Bóveda ──────────────────────────────────────────────────────────────────

let allCreds = [];
let activeDomain = null;

async function writeClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (_) { /* sigue el respaldo execCommand */ }
  try {
    // Respaldo para cuando la Clipboard API rechaza (gesto expirado, foco raro).
    // Con el permiso clipboardWrite, execCommand funciona sin gesto en extensiones.
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    return ok;
  } catch (_) {
    return false;
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

let menuDocListener = null;

function closeMenus() {
  document.querySelectorAll('.cred-menu').forEach((m) => m.remove());
  if (menuDocListener) {
    document.removeEventListener('click', menuDocListener);
    menuDocListener = null;
  }
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
  menuDocListener = (e) => { if (!menu.contains(e.target)) closeMenus(); };
  setTimeout(() => document.addEventListener('click', menuDocListener), 0);
}

// Feedback de copiado: chulito temporal sin perder el ícono original aunque se
// copie varias veces seguidas.
function flashCheck(btn) {
  if (!btn._origIcon) btn._origIcon = btn.firstChild;
  clearTimeout(btn._flashTimer);
  btn.replaceChildren(svgIcon('check'));
  btn.classList.add('copied');
  btn._flashTimer = setTimeout(() => {
    btn.replaceChildren(btn._origIcon);
    btn.classList.remove('copied');
  }, 1400);
}

// Copia un valor ya disponible localmente (p. ej. el usuario, que viene en la
// lista de la bóveda): escribe dentro del gesto del clic → confiable siempre.
async function copyLocalValue(value, btn) {
  const ok = await writeClipboard(value || '');
  if (ok) flashCheck(btn);
  else showToast('No se pudo copiar al portapapeles', 'error');
}

// Copia la contraseña usando el secreto pedido al ABRIR el menú (prefetch):
// si ya llegó, la escritura ocurre dentro del gesto del clic; si el servidor
// va lento, se muestra estado ocupado y se usa el respaldo execCommand.
async function copyPasswordFromPromise(secretPromise, btn) {
  btn.classList.add('busy');
  try {
    const res = await secretPromise;
    if (!res.ok) {
      showToast(res.error || 'No se pudo obtener la contraseña', 'error');
      if (res.locked) refresh();
      return;
    }
    const ok = await writeClipboard(res.password || '');
    if (ok) flashCheck(btn);
    else showToast('No se pudo copiar — intenta de nuevo', 'error');
  } finally {
    btn.classList.remove('busy');
  }
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
    // El usuario ya está en la lista local (sin servidor). La contraseña se
    // pide AHORA (al abrir el menú) para que al elegir la opción el valor ya
    // esté disponible y se copie dentro del gesto del clic.
    const options = [{ label: 'Copiar usuario', onClick: () => copyLocalValue(cred.username, copy) }];
    if (isEmailLogin) {
      const secretPromise = send({ type: 'GET_SECRET', credId: cred.id });
      options.push({ label: 'Copiar contraseña', onClick: () => copyPasswordFromPromise(secretPromise, copy) });
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
      { label: 'Eliminar', danger: true, onClick: () => showDeleteConfirm(cred, row) },
    );
    openMenu(more, options);
  });
  actions.appendChild(more);

  row.append(fav, info, actions);
  return row;
}

// Confirmación de borrado dentro de la propia fila (sin confirm() nativo).
function showDeleteConfirm(cred, row) {
  row.replaceChildren();
  row.classList.add('cred-confirm');

  const txt = document.createElement('span');
  txt.className = 'confirm-text';
  txt.textContent = `¿Mover "${cred.label}" a la papelera?`;

  const yes = document.createElement('button');
  yes.className = 'confirm-btn danger';
  yes.textContent = 'Eliminar';
  yes.addEventListener('click', async () => {
    const res = await send({ type: 'DELETE_CREDENTIAL', credId: cred.id });
    if (res.ok) {
      showToast(`"${cred.label}" movida a la papelera`);
      loadVault();
    } else {
      showToast(res.error || 'No se pudo eliminar', 'error');
      renderVault($('vault-search').value);
    }
  });

  const no = document.createElement('button');
  no.className = 'confirm-btn';
  no.textContent = 'Cancelar';
  no.addEventListener('click', () => renderVault($('vault-search').value));

  row.append(txt, yes, no);
}

function skeletonRow() {
  const row = document.createElement('div');
  row.className = 'skel-row';
  row.innerHTML =
    '<div class="skel skel-fav"></div>' +
    '<div class="skel-lines"><div class="skel skel-line w60"></div><div class="skel skel-line w40"></div></div>';
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
  $('vault-empty').hidden = allCreds.length > 0;
  const noresults = $('vault-noresults');
  if (allCreds.length > 0 && filtered.length === 0) {
    noresults.textContent = q ? `Sin resultados para "${filter.trim()}"` : 'Sin credenciales en esta categoría';
    noresults.hidden = false;
  } else {
    noresults.hidden = true;
  }
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

  // Skeleton solo en la primera carga (sin datos aún): evita parpadeos al refrescar.
  if (!allCreds.length) {
    $('vault-empty').hidden = true;
    $('vault-noresults').hidden = true;
    const list = $('vault-list');
    list.replaceChildren(skeletonRow(), skeletonRow(), skeletonRow());
  }

  const [vault, tab] = await Promise.all([
    send({ type: 'VAULT_LIST' }),
    send({ type: 'ACTIVE_TAB' }),
  ]);
  if (!vault.ok) {
    if (vault.locked) { refresh(); return; }
    $('vault-list').innerHTML = '';
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

$('vault-search').addEventListener('input', (e) => renderVault(e.target.value));
$('vault-category').addEventListener('change', () => renderVault($('vault-search').value));
$('vault-new').addEventListener('click', () => openForm(null));
$('vault-empty-add').addEventListener('click', () => openForm(null));
$('vault-open-web').addEventListener('click', () => {
  if (lastStatus?.apiUrl) chrome.tabs.create({ url: lastStatus.apiUrl });
});
$('vault-open-web').appendChild(svgIcon('open'));

// ─── Formulario (nueva / editar) ─────────────────────────────────────────────

const syncFormEye = wireEyeToggle('form-pwd-toggle', 'form-password');
$('form-pwd-gen').innerHTML = GEN_SVG;

function syncPasswordBlock() {
  // Para accesos OAuth (Google, GitHub…) no hay contraseña propia que guardar.
  const isEmail = $('form-login-via').value === 'email';
  $('form-password-block').hidden = !isEmail;
  $('form-username-label').textContent = isEmail ? 'Usuario / email' : 'Cuenta usada';
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
  $('form-password').type = 'password';
  syncFormEye();
  $('form-password').placeholder = cred ? '(sin cambios)' : '';
  $('form-category').value = cred?.category || 'personal';
  $('form-login-via').value = cred?.login_via || draft?.login_via || 'email';
  $('form-notes').value = cred?.notes || draft?.notes || '';
  $('form-pwd-reveal').hidden = !cred;
  syncPasswordBlock();
  $('form-error').hidden = true;
  showView('view-form');
  $('form-label').focus();
}

$('form-login-via').addEventListener('change', syncPasswordBlock);

$('form-back').addEventListener('click', () => { showView('view-unlocked'); loadVault(); });

// Generador de contraseñas seguras (mismo del dashboard: 20 caracteres aleatorios).
$('form-pwd-gen').addEventListener('click', () => {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';
  const bytes = new Uint8Array(20);
  crypto.getRandomValues(bytes);
  const input = $('form-password');
  input.value = Array.from(bytes, (b) => chars[b % chars.length]).join('');
  input.type = 'text';
  syncFormEye();
});

// Al editar: trae la contraseña actual (vía API) y la muestra en el campo.
$('form-pwd-reveal').addEventListener('click', async () => {
  const id = Number($('form-id').value);
  if (!id) return;
  const res = await send({ type: 'GET_SECRET', credId: id });
  if (!res.ok) {
    showToast(res.error || 'No se pudo obtener la contraseña', 'error');
    if (res.locked) refresh();
    return;
  }
  const input = $('form-password');
  input.value = res.password || '';
  input.type = 'text';
  syncFormEye();
});

$('form-submit').addEventListener('click', async () => {
  $('form-error').hidden = true;
  const id = $('form-id').value;
  const label = $('form-label').value.trim();
  if (!label) { showError('form-error', 'El nombre es obligatorio'); return; }

  const loginVia = $('form-login-via').value;
  const fields = {
    label,
    url: $('form-url').value.trim(),
    username: $('form-username').value.trim(),
    category: $('form-category').value,
    login_via: loginVia,
    notes: $('form-notes').value.trim(),
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
    showToast(id ? 'Credencial actualizada' : 'Credencial guardada');
    showView('view-unlocked');
    await loadVault();
  } catch (err) {
    showError('form-error', err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Guardar';
  }
});

// ─── Login (paso 1) ──────────────────────────────────────────────────────────

wireEyeToggle('login-pwd-toggle', 'login-password');

$('login-advanced-toggle').addEventListener('click', () => {
  const adv = $('login-advanced');
  adv.hidden = !adv.hidden;
});

$('login-submit').addEventListener('click', async () => {
  $('login-error').hidden = true;
  const email = $('login-email').value.trim();
  const password = $('login-password').value;
  const apiUrl = $('login-url').value.trim();
  const totpCode = $('login-totp').value.trim();

  if (!email || !password) return showError('login-error', 'Email y contraseña son obligatorios');

  const btn = $('login-submit');
  btn.disabled = true;
  btn.textContent = 'Entrando…';
  try {
    const res = await send({ type: 'LOGIN', email, password, apiUrl, totpCode, deviceName: 'Chrome' });
    if (!res.ok) {
      // La cuenta tiene 2FA: revelar el campo del código y pedir reintento.
      if ((res.error || '').includes('2FA')) {
        $('login-totp-block').hidden = false;
        $('login-totp').focus();
      }
      throw new Error(res.error || 'No se pudo iniciar sesión');
    }
    $('login-password').value = '';
    $('login-totp').value = '';
    await refresh(); // pasará a "crear PIN"
  } catch (err) {
    showError('login-error', err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Iniciar sesión';
  }
});

$('login-totp').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('login-submit').click(); });

$('login-email').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('login-password').focus(); });
$('login-password').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('login-submit').click(); });

// ─── Crear PIN (paso 2, una sola vez) ────────────────────────────────────────

['setpin-pin', 'setpin-pin2'].forEach((id) => {
  $(id).addEventListener('input', () => { $(id).value = $(id).value.replace(/\D/g, ''); });
});
$('setpin-pin').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('setpin-pin2').focus(); });
$('setpin-pin2').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('setpin-submit').click(); });

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

// ─── Bloquear / cerrar sesión ────────────────────────────────────────────────

$('lock-now').addEventListener('click', async () => {
  await send({ type: 'LOCK' });
  await refresh();
});

async function logout() {
  await send({ type: 'LOGOUT' });
  await refresh();
}

armConfirm($('unlocked-logout'), '¿Seguro? Confirmar', logout);
armConfirm($('locked-logout'), '¿Seguro? Confirmar', logout);

refresh();
