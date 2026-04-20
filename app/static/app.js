var _htmxLoader = null;

document.addEventListener('DOMContentLoaded', function () {
  _htmxLoader = document.getElementById('htmx-loader');
});

document.addEventListener('htmx:beforeRequest', function () {
  var el = _htmxLoader || document.getElementById('htmx-loader');
  if (el) el.removeAttribute('hidden');
});

document.addEventListener('htmx:afterRequest', function () {
  var el = _htmxLoader || document.getElementById('htmx-loader');
  if (el) el.setAttribute('hidden', '');
});
