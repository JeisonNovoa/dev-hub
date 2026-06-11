# Plan: Extensión de navegador para DevHub (gestor de credenciales)

## Contexto y objetivo

Hoy guardar/usar credenciales en DevHub es manual (entrar a la web, copiar, pegar).
La idea: una **extensión de Chrome** que, en cualquier página con formulario de login:

1. **Detecta el formulario** y muestra un ícono de DevHub dentro de los campos.
2. **Autofill bajo demanda**: al hacer clic en el ícono, trae la(s) credencial(es)
   guardada(s) para ese dominio exacto y rellena usuario + contraseña.
3. **Guardar al detectar login nuevo**: si te logueás en un sitio sin credencial
   guardada, un popup pregunta "¿Guardar [dominio] en DevHub?" con el correo visible
   y la contraseña oculta. Solo guarda si confirmás.

**Costo: $0.** Uso personal en modo desarrollador. (Publicar en Chrome Web Store
sería $5 únicos, opcional, no necesario.)

## Decisiones confirmadas

- **Conexión**: token de acceso. DevHub genera un token; se pega una vez en la
  extensión; revocable. (La cookie de sesión es HttpOnly y no sirve para esto.)
- **Autofill**: ícono dentro del campo, clic manual. Nunca rellena solo.
- **Descifrado**: en el servidor. La API devuelve la contraseña en claro vía HTTPS
  solo a peticiones con token válido. (Igual que hoy hace la web.)
- **Match de dominio**: exacto (anti-phishing). Solo ofrece cartesia.ai en cartesia.ai.
- **Guardar**: pregunta antes (popup de confirmación).
- **Navegador**: Chrome (Manifest V3). Edge/Brave quedan cubiertos con el mismo paquete.
- **Contraseña maestra de desbloqueo**: pospuesta (el usuario lo confirmó). Se diseña
  para poder agregarla después sin reescribir.

---

## PARTE A — Backend (cambios en DevHub, repo actual)

### A1. Modelo: token de extensión — `app/models/extension_token.py` (NUEVO)
Tabla `extension_tokens`: `id`, `user_id` (FK), `token_hash` (se guarda el **hash**,
nunca el token en claro), `name` (ej. "Chrome de mi laptop"), `last_used_at`,
`created_at`, `revoked_at` (nullable). Reutiliza `TimestampMixin` de `app/models/common.py`.
- El token en claro se muestra **una sola vez** al generarlo (como GitHub PATs).
- Verificación: hash del token recibido y comparación con `token_hash` (constante-time).

### A2. Migración Alembic
`alembic revision --autogenerate -m "extension tokens"` para crear la tabla.

### A3. Auth por token — extender `app/dependencies.py`
Nueva dependencia `get_user_from_token(request)`:
- Lee header `Authorization: Bearer <token>`.
- Hashea y busca en `extension_tokens` (no revocado), carga el `User`, actualiza `last_used_at`.
- Reutiliza el patrón de `get_current_user` pero por token en vez de cookie.
- Una dependencia combinada `get_current_user_api` que acepta **cookie O token**, para
  que los endpoints de la extensión funcionen con ambos.

### A4. Endpoints nuevos — `app/routers/api/extension.py` (NUEVO), prefix `/api/extension`
Todos protegidos por token (o cookie, para la página de gestión):
- `GET /api/extension/credentials/match?domain=cartesia.ai`
  → devuelve credenciales cuyo `url` haga match de **dominio exacto** con el dado.
  Respuesta mínima (label, username, id) SIN contraseña — para listar opciones.
- `GET /api/extension/credentials/{id}/secret`
  → devuelve `{username, password}` descifrada (este es el único endpoint que expone
  la contraseña; requiere token válido). Loguea el acceso.
- `POST /api/extension/credentials`
  → crea credencial desde la extensión (label = dominio, url, username, password,
  category="personal" por defecto). Reusa la lógica de `create_credential`.
- `GET /api/extension/ping` → valida que el token sirve (para el botón "probar conexión").

Reutiliza: el filtro de dominio puede apoyarse en el filtro `domain` de `app/jinja.py`
(la función `_domain_filter` ya extrae el netloc de una URL) — extraer esa lógica a
`app/utils/url.py` para usarla en backend sin Jinja.

### A5. Gestión de tokens en la web — `app/routers/ui/` + template
Página/sección en el perfil o ajustes: "Extensión del navegador" con botón
"generar token", mostrar el token una vez, listar tokens activos con "revocar".
(Página simple; sigue el patrón de los otros routers UI.)

### A6. CORS
La extensión llama a la API desde un origen `chrome-extension://<id>`. Agregar
`CORSMiddleware` en `app/main.py` permitiendo ese origen (y los métodos/headers
necesarios). Restringido, no `*`.

### A7. Tests — `tests/test_extension.py` (NUEVO)
- Generar token, autenticar con él, revocar y verificar que deja de funcionar.
- Match por dominio exacto: cartesia.ai matchea, cartesia.fake NO.
- `secret` devuelve contraseña descifrada solo con token válido (401 sin token).
- Crear credencial vía extensión queda bajo el `user_id` correcto.
- Aislamiento entre usuarios.

---

## PARTE B — La extensión (carpeta nueva `extension/`, separada del backend)

Estructura mínima de una extensión Manifest V3 (te explico cada archivo al construirlo):

```
extension/
├── manifest.json        # "carné de identidad": permisos, qué scripts corren dónde
├── background.js        # service worker: habla con la API de DevHub (fetch con token)
├── content.js           # se inyecta en las páginas: detecta forms, pinta el ícono, rellena
├── content.css          # estilos del ícono/overlay inyectado
├── popup.html/.js/.css  # la ventanita al hacer clic en el ícono de la extensión
│                        #   (pegar token, probar conexión, ver estado)
├── options.html/.js     # ajustes (URL de tu DevHub, token)
└── icons/               # iconos 16/48/128 px
```

### B1. `manifest.json`
- `manifest_version: 3`, permisos: `storage` (guardar el token localmente),
  `activeTab`/`scripting`. `host_permissions` para tu dominio de Render (la API).
- Registra `content.js` en `<all_urls>` (para detectar logins en cualquier sitio).

### B2. `background.js` (service worker)
- Única pieza que tiene el token y hace `fetch` a la API (`Authorization: Bearer`).
- Mensajería: `content.js` le pide "dame credenciales para cartesia.ai" y responde.
- **El token nunca se expone a las páginas** — solo vive en el background + `chrome.storage`.

### B3. `content.js` (lo que el usuario ve)
- Detecta `<input type=password>` y su form asociado (heurística estándar).
- Inyecta un ícono DevHub en el campo de usuario.
- Al hacer clic: pide al background las credenciales del dominio actual; si hay,
  muestra un mini-dropdown para elegir y rellena `username`+`password` al seleccionar.
- Detecta **submit** de un login nuevo (dominio sin credencial): manda los datos al
  background, que muestra el popup "¿Guardar?".
- **Match de dominio exacto** se valida tanto en cliente como en servidor.

### B4. `popup.html/.js`
- Estado: "conectado / no conectado". Campo para pegar el token + "probar conexión"
  (llama a `/api/extension/ping`). Link a tu DevHub para generar el token.
- Diseño acorde a la estética de DevHub (dark, mono), reutilizando colores.

### B5. Seguridad del lado de la extensión
- Token solo en `chrome.storage.local` y en el background; jamás en el DOM de páginas.
- Autofill solo tras clic explícito; nunca en `<iframe>` de terceros.
- Match exacto de dominio antes de ofrecer u guardar.

---

## Cómo lo construiremos (orden y verificación)

1. **Backend primero** (A1–A7): modelo, migración, endpoints, gestión de token, CORS, tests.
   Verificable con pytest y con `curl`/preview antes de tocar la extensión.
2. **Extensión esqueleto** (B1, B2, B4): manifest + background + popup. La cargás en
   `chrome://extensions` (modo desarrollador) y probás "pegar token → ping OK".
3. **Autofill** (B3 parte 1): detectar form, ícono, traer y rellenar. Probar en un sitio real.
4. **Guardar nuevo** (B3 parte 2): detectar submit, popup, guardar. Probar el ciclo completo
   (loguear en sitio nuevo → guardar → cerrar sesión → volver → autofill).
5. Documentar en un `extension/README.md` cómo cargarla en Chrome paso a paso (para vos).

### Verificación end-to-end (caso Cartesia que describiste)
- Sitio nuevo: entrás a un login, te logueás normal → popup "¿Guardar?" → sí → aparece en DevHub.
- Cerrás sesión, volvés: el ícono DevHub ofrece la credencial → clic → rellena. 
- Probar que en un dominio distinto NO ofrece esa credencial (anti-phishing).

## Fuera de alcance (por ahora, explícito)
- Contraseña maestra de desbloqueo (pospuesta; el diseño la permite agregar después).
- Descifrado zero-knowledge en el cliente (se descifra en servidor por ahora).
- Firefox/Safari (Chrome primero; Edge/Brave salen casi gratis).
- Generación de contraseñas / TOTP / passkeys.

## Nota de privacidad importante (a tener en cuenta)
Una extensión con `content.js` en `<all_urls>` "ve" todas las páginas que visitás.
Es necesario para detectar logins en cualquier sitio (igual que Bitwarden), pero el
código solo actúa sobre formularios de login y solo habla con TU servidor. Lo
mantendremos mínimo y auditable. Si algún día la publicás, Google revisa esto.
