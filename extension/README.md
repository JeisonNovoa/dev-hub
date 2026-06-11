# Dev Hub — Extensión de navegador (Autofill)

Autocompleta credenciales guardadas en tu Dev Hub y ofrece guardar logins nuevos.
Funciona en Chrome, Edge y Brave. **Costo: $0** (se usa en modo desarrollador).

## Cómo instalarla (una sola vez, ~2 minutos)

1. Abre Chrome y entra a `chrome://extensions` (en Edge: `edge://extensions`).
2. Activa el interruptor **"Modo de desarrollador"** (esquina superior derecha).
3. Clic en **"Cargar descomprimida"** (Load unpacked).
4. Selecciona esta carpeta: `dev-hub/extension`.
5. Aparece "Dev Hub — Autofill" en la lista. Opcional: fija el ícono desde el
   menú de extensiones (puzzle) para tenerlo a mano.

> Si tu Dev Hub NO está en `*.onrender.com` ni en `localhost:8000`, agrega tu
> dominio en `host_permissions` dentro de `manifest.json` y recarga la extensión.

## Cómo conectarla (una sola vez)

1. Clic en el ícono de la extensión.
2. **Inicia sesión** con tu email y contraseña de Dev Hub (como en la web).
   - La extensión usa por defecto el servidor configurado en `background.js`
     (`DEFAULT_API_URL`). Si tu Dev Hub está en otro dominio, ábrelo en
     "Configuración avanzada" y pon la URL — si no, déjalo vacío.
3. **Crea tu PIN** de desbloqueo (numérico, mínimo 4 dígitos — ej. `2026`). Esto
   solo se pide una vez.
4. Listo. De ahí en adelante, cuando la bóveda esté bloqueada solo te pedirá el
   PIN. El dispositivo aparece en Dev Hub → **Extensión**, donde puedes revocarlo.

## Cómo se usa

- **Autocompletar desde el formulario**: en cualquier página de login aparece un
  ícono `▸` dentro del campo de contraseña. Haz clic → si está bloqueado te pide
  el PIN → muestra tus cuentas guardadas para ese dominio (si hay varias, eliges
  cuál) → rellena.
- **La bóveda (popup)**: clic en el ícono de la extensión → desbloqueas con el PIN
  → ves todas tus credenciales con buscador. Si estás en una página con login
  conocido, esa credencial sale arriba en "Este sitio" con botón **rellenar**.
  Por cada credencial: abrir el sitio (↗), **copiar** (usuario o contraseña) y el
  menú **⋮** (autocompletar la página, editar, eliminar).
- **Nueva credencial**: botón **+** en la bóveda → formulario con nombre, URL,
  usuario, contraseña y categoría.
- **Desbloqueo temporal**: tras poner el PIN queda desbloqueado **5 minutos**
  (cada uso renueva el tiempo). Después vuelve a pedir el PIN.
- **Guardar un login nuevo**: inicia sesión normal en un sitio. En la página
  siguiente aparece un aviso "¿Guardar … en Dev Hub?" con tres opciones:
  **Guardar** (rápido), **Editar** (abre la extensión con el formulario
  prellenado para ajustar nombre/categoría antes de guardar) o **No**. Si la
  credencial ya existe en ese dominio, el aviso no aparece.
- **Logins con Google/GitHub/Microsoft (OAuth)**: las credenciales OAuth se
  marcan con su insignia en la bóveda y en el autofill. Al "rellenar" una, se
  completa el correo y te recuerda el método ("aquí inicias con Google usando
  tal correo"). Si la extensión detecta que hiciste clic en "Continuar con
  Google" en un sitio nuevo, al volver te ofrece guardar el acceso — tú
  completas el correo en el formulario (el flujo de Google ocurre fuera de la
  página, así que la cuenta exacta no se puede leer).
- **Bloquear/cerrar sesión**: desde el pie de la bóveda en el popup.

## Seguridad (cómo está diseñada)

- Tu **PIN nunca sale del navegador**: solo se usa para cifrar localmente
  (PBKDF2 + AES-GCM) el token de acceso. Sin PIN, lo guardado es ilegible.
- **5 intentos fallidos de PIN → se borra todo** y hay que reconectar.
- El token y las contraseñas **nunca se exponen a las páginas web**: viven en el
  service worker; el relleno ocurre solo tras tu clic.
- **Match de dominio exacto** (anti-phishing): la credencial de `cartesia.ai`
  solo se ofrece en `cartesia.ai` o sus subdominios — jamás en dominios parecidos.
- El acceso es **revocable** desde Dev Hub → Extensión (cada login de la extensión
  crea un token independiente, hasheado en la base de datos).

## Archivos

| Archivo | Qué hace |
|---|---|
| `manifest.json` | Identidad y permisos de la extensión (Manifest V3) |
| `background.js` | Service worker: guarda el token cifrado, habla con la API |
| `crypto.js` | Cifrado del token con el PIN (PBKDF2 + AES-GCM) |
| `content.js` | Se inyecta en las páginas: ícono, autofill, banner de guardado |
| `content.css` | Estilos del UI inyectado |
| `popup.*` | La ventanita de la extensión: conectar, PIN, bloquear |
