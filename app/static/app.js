var _htmxLoader = null;

// CSRF doble-submit: lee la cookie csrf_token y la manda como X-CSRFToken en
// cada petición HTMX y fetch. El middleware backend compara cookie vs header.
function _readCookie(name) {
  var match = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[2]) : '';
}

function _csrfToken() {
  // Preferimos el meta tag (se setea por render del server); fallback a cookie.
  var meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') : _readCookie('csrf_token');
}

// Etiqueta del atajo según el sistema operativo: ⌘ es la tecla Command de Mac;
// en Windows/Linux el equivalente es Ctrl. Mostrar "⌘K" a un usuario de Windows
// confunde porque esa tecla no existe en su teclado. Rellenamos cada
// [data-shortcut="cmdk"] con el símbolo correcto. data-shortcut, no texto fijo,
// para que también aplique a contenido que llega por HTMX.
function _isMac() {
  var p = (navigator.platform || navigator.userAgent || '').toLowerCase();
  return p.indexOf('mac') !== -1 || p.indexOf('iphone') !== -1 || p.indexOf('ipad') !== -1;
}

function applyShortcutLabels(root) {
  var label = _isMac() ? '⌘ K' : 'Ctrl K';
  (root || document).querySelectorAll('[data-shortcut="cmdk"]').forEach(function (el) {
    el.textContent = label;
  });
}

document.addEventListener('DOMContentLoaded', function () {
  _htmxLoader = document.getElementById('htmx-loader');
  applyShortcutLabels(document);
});

// HTMX: inyecta X-CSRFToken en cada request que tenga body (POST/PATCH/DELETE).
document.addEventListener('htmx:configRequest', function (evt) {
  var token = _csrfToken();
  if (token) {
    evt.detail.headers['X-CSRFToken'] = token;
  }
});

// Contenido recargado por HTMX puede traer badges nuevos: re-aplicar.
document.addEventListener('htmx:afterSwap', function (e) {
  applyShortcutLabels(e.target || document);
});

document.addEventListener('htmx:beforeRequest', function () {
  var el = _htmxLoader || document.getElementById('htmx-loader');
  if (el) el.removeAttribute('hidden');
});

document.addEventListener('htmx:afterRequest', function () {
  var el = _htmxLoader || document.getElementById('htmx-loader');
  if (el) el.setAttribute('hidden', '');
});
