// Content script: detecta formularios de login, pinta el ícono de Dev Hub en los
// campos de contraseña, ofrece autofill (con PIN si está bloqueado) y detecta
// logins nuevos para ofrecer guardarlos.
//
// Seguridad: este script nunca conoce el token. Solo pide datos al background en
// respuesta a un clic del usuario, y el background valida dominio y origen.

(() => {
  'use strict';

  const PREFIX = 'devhub-ext';

  function send(msg) {
    return chrome.runtime.sendMessage(msg);
  }

  function pageDomain() {
    const host = location.hostname.toLowerCase();
    return host.startsWith('www.') ? host.slice(4) : host;
  }

  // ─── Detección de campos de login ──────────────────────────────────────────

  function isVisible(el) {
    const r = el.getBoundingClientRect();
    return r.width > 40 && r.height > 10 && el.offsetParent !== null;
  }

  function findUsernameInput(passwordInput) {
    const scope = passwordInput.form || document;
    const candidates = Array.from(
      scope.querySelectorAll('input[type="email"], input[type="text"], input:not([type])'),
    ).filter(isVisible);
    // El campo de usuario suele ser el input visible inmediatamente anterior al password.
    let best = null;
    for (const c of candidates) {
      const pos = passwordInput.compareDocumentPosition(c);
      if (pos & Node.DOCUMENT_POSITION_PRECEDING) best = c;
    }
    return best;
  }

  function findPasswordInputs() {
    return Array.from(document.querySelectorAll('input[type="password"]')).filter(isVisible);
  }

  // ─── Ícono dentro del campo ────────────────────────────────────────────────

  const decorated = new WeakSet();

  function injectIcon(passwordInput) {
    if (decorated.has(passwordInput)) return;
    decorated.add(passwordInput);

    const icon = document.createElement('button');
    icon.type = 'button';
    icon.className = `${PREFIX}-icon`;
    icon.title = 'Autocompletar con Dev Hub';
    icon.textContent = '▸';
    document.body.appendChild(icon);

    const reposition = () => {
      if (!document.contains(passwordInput) || !isVisible(passwordInput)) {
        icon.style.display = 'none';
        return;
      }
      const r = passwordInput.getBoundingClientRect();
      icon.style.display = 'flex';
      icon.style.top = `${window.scrollY + r.top + (r.height - 20) / 2}px`;
      icon.style.left = `${window.scrollX + r.right - 26}px`;
    };

    reposition();
    window.addEventListener('scroll', reposition, { passive: true, capture: true });
    window.addEventListener('resize', reposition, { passive: true });
    new ResizeObserver(reposition).observe(document.body);

    icon.addEventListener('mousedown', (e) => {
      // mousedown para ganarle al blur del input
      e.preventDefault();
      e.stopPropagation();
      openPanel(passwordInput, icon);
    });
  }

  // ─── Panel flotante (PIN / lista de cuentas / mensajes) ────────────────────

  let panel = null;

  function closePanel() {
    if (panel) { panel.remove(); panel = null; }
  }

  function createPanel(anchorIcon) {
    closePanel();
    panel = document.createElement('div');
    panel.className = `${PREFIX}-panel`;
    const r = anchorIcon.getBoundingClientRect();
    panel.style.top = `${window.scrollY + r.bottom + 6}px`;
    panel.style.left = `${Math.max(8, window.scrollX + r.right - 260)}px`;
    document.body.appendChild(panel);

    setTimeout(() => {
      document.addEventListener('mousedown', function onDoc(e) {
        if (panel && !panel.contains(e.target)) {
          closePanel();
          document.removeEventListener('mousedown', onDoc);
        }
      });
    }, 0);
    return panel;
  }

  function renderMessage(p, text) {
    p.innerHTML = '';
    const msg = document.createElement('p');
    msg.className = `${PREFIX}-msg`;
    msg.textContent = text;
    p.appendChild(msg);
  }

  function renderPinPrompt(p, onUnlocked) {
    p.innerHTML = '';
    const label = document.createElement('p');
    label.className = `${PREFIX}-msg`;
    label.textContent = 'PIN de Dev Hub';

    const input = document.createElement('input');
    input.type = 'password';
    input.inputMode = 'numeric';
    input.className = `${PREFIX}-pin`;
    input.placeholder = '••••';
    input.maxLength = 12;

    const error = document.createElement('p');
    error.className = `${PREFIX}-error`;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `${PREFIX}-btn`;
    btn.textContent = 'Desbloquear';

    const tryUnlock = async () => {
      const pin = input.value.trim();
      if (!pin) return;
      const res = await send({ type: 'UNLOCK', pin });
      if (res.ok) {
        onUnlocked();
      } else {
        error.textContent = res.error || 'PIN incorrecto';
        input.value = '';
        if (res.wiped) setTimeout(closePanel, 2500);
      }
    };

    btn.addEventListener('click', tryUnlock);
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); tryUnlock(); } });

    p.append(label, input, error, btn);
    input.focus();
  }

  function renderAccountList(p, items, passwordInput) {
    p.innerHTML = '';
    const title = document.createElement('p');
    title.className = `${PREFIX}-msg`;
    title.textContent = items.length === 1 ? 'Cuenta guardada' : 'Elige una cuenta';
    p.appendChild(title);

    for (const item of items) {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = `${PREFIX}-account`;

      const label = document.createElement('span');
      label.className = `${PREFIX}-account-label`;
      label.textContent = item.label;

      const user = document.createElement('span');
      user.className = `${PREFIX}-account-user`;
      user.textContent = item.username || '—';

      row.append(label, user);
      row.addEventListener('click', async () => {
        const res = await send({ type: 'FILL', credId: item.id });
        if (!res.ok) {
          renderMessage(p, res.error || 'No se pudo obtener la credencial');
          return;
        }
        fillCredentials(passwordInput, res.username, res.password);
        closePanel();
      });
      p.appendChild(row);
    }
  }

  async function openPanel(passwordInput, icon) {
    const p = createPanel(icon);
    renderMessage(p, 'Cargando…');

    const st = await send({ type: 'STATUS' });
    if (!st.configured) {
      renderMessage(p, 'Configura Dev Hub: clic en el ícono de la extensión.');
      return;
    }

    const loadAccounts = async () => {
      renderMessage(p, 'Buscando credenciales…');
      const res = await send({ type: 'MATCH', domain: pageDomain() });
      if (res.locked) {
        renderPinPrompt(p, loadAccounts);
        return;
      }
      if (!res.ok) {
        renderMessage(p, res.error || 'Error consultando Dev Hub');
        return;
      }
      if (!res.items.length) {
        renderMessage(p, `Sin credenciales guardadas para ${pageDomain()}`);
        return;
      }
      renderAccountList(p, res.items, passwordInput);
    };

    if (!st.unlocked) {
      renderPinPrompt(p, loadAccounts);
    } else {
      await loadAccounts();
    }
  }

  // ─── Rellenar (compatible con React/Vue: setter nativo + eventos) ──────────

  function setNativeValue(input, value) {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function fillCredentials(passwordInput, username, password) {
    if (password) setNativeValue(passwordInput, password);
    const usernameInput = findUsernameInput(passwordInput);
    if (usernameInput && username) setNativeValue(usernameInput, username);
    passwordInput.focus();
  }

  // ─── Detección de login nuevo (para ofrecer guardar) ───────────────────────

  function captureSubmit(passwordInput) {
    const username = findUsernameInput(passwordInput)?.value?.trim();
    const password = passwordInput.value;
    if (!username || !password) return;
    send({
      type: 'SUBMIT_DETECTED',
      domain: pageDomain(),
      url: location.href,
      username,
      password,
    });
  }

  document.addEventListener('submit', (e) => {
    const form = e.target;
    const pwd = form.querySelector?.('input[type="password"]');
    if (pwd && pwd.value) captureSubmit(pwd);
  }, true);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target?.type === 'password' && e.target.value) {
      captureSubmit(e.target);
    }
  }, true);

  document.addEventListener('click', (e) => {
    // Logins sin <form> (SPA): botón de submit cerca de un password con valor.
    const btn = e.target?.closest?.('button[type="submit"], input[type="submit"], button');
    if (!btn) return;
    const scope = btn.closest('form') || document;
    const pwd = scope.querySelector('input[type="password"]');
    if (pwd && pwd.value) captureSubmit(pwd);
  }, true);

  // ─── Banner "¿Guardar en Dev Hub?" ─────────────────────────────────────────

  async function maybeShowSaveBanner() {
    const res = await send({ type: 'GET_PENDING_SAVE' });
    if (!res?.pending) return;

    const banner = document.createElement('div');
    banner.className = `${PREFIX}-banner`;

    const text = document.createElement('span');
    text.className = `${PREFIX}-banner-text`;
    text.textContent = `¿Guardar ${res.pending.domain} (${res.pending.username}) en Dev Hub?`;

    const actions = document.createElement('span');
    actions.className = `${PREFIX}-banner-actions`;

    const saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = `${PREFIX}-btn`;
    saveBtn.textContent = 'Guardar';

    const noBtn = document.createElement('button');
    noBtn.type = 'button';
    noBtn.className = `${PREFIX}-btn ${PREFIX}-btn-ghost`;
    noBtn.textContent = 'No';

    const pinInput = document.createElement('input');
    pinInput.type = 'password';
    pinInput.inputMode = 'numeric';
    pinInput.className = `${PREFIX}-pin ${PREFIX}-banner-pin`;
    pinInput.placeholder = 'PIN';
    pinInput.maxLength = 12;
    pinInput.style.display = 'none';

    const doSave = async () => {
      const res2 = await send({ type: 'SAVE_PENDING' });
      if (res2.locked) {
        pinInput.style.display = 'inline-block';
        text.textContent = 'Pon tu PIN de Dev Hub para guardar:';
        pinInput.focus();
        return;
      }
      if (res2.already) {
        text.textContent = 'Ya estaba guardada en Dev Hub ✓';
      } else if (res2.ok) {
        text.textContent = 'Guardada en Dev Hub ✓';
      } else {
        text.textContent = res2.error || 'No se pudo guardar';
      }
      actions.remove();
      pinInput.remove();
      setTimeout(() => banner.remove(), 2500);
    };

    pinInput.addEventListener('keydown', async (e) => {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      const unlock = await send({ type: 'UNLOCK', pin: pinInput.value.trim() });
      if (unlock.ok) {
        pinInput.style.display = 'none';
        await doSave();
      } else {
        pinInput.value = '';
        text.textContent = unlock.error || 'PIN incorrecto';
        if (unlock.wiped) setTimeout(() => banner.remove(), 2500);
      }
    });

    saveBtn.addEventListener('click', doSave);
    noBtn.addEventListener('click', async () => {
      await send({ type: 'DISMISS_PENDING' });
      banner.remove();
    });

    actions.append(saveBtn, noBtn);
    banner.append(text, pinInput, actions);
    document.body.appendChild(banner);
  }

  // ─── Arranque + observador para SPAs ───────────────────────────────────────

  function scan() {
    findPasswordInputs().forEach(injectIcon);
  }

  let scanTimer = null;
  const observer = new MutationObserver(() => {
    clearTimeout(scanTimer);
    scanTimer = setTimeout(scan, 400);
  });

  scan();
  maybeShowSaveBanner();
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
