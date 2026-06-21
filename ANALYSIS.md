# Dev Hub — Análisis profundo y roadmap (2026-06-20)

Documento vivo. Cada bloque completado se tacha y se mueve al final como
"hecho". El orden es deliberado: primero tapar agujeros, luego quitar peso,
después invertir en lo que multiplica el valor.

---

## 0. Veredicto del producto

dev-hub es **tres productos pegados con cinta**: un *project ops notebook*
(bueno), un *password manager amateur* (débil vs Bitwarden/1Password), y una
*extensión de navegador* (scope creep caro). Sobrevive como app personal;
no como producto. El nicho real, si existe, es **"segundo cerebro operativo
para devs que vibe-codean"**: grafo proyecto ↔ credencial ↔ servicio +
búsqueda brutal + integración con Claude.

---

## 1. Seguridad CRÍTICA (verificada contra código)

Orden por riesgo × esfuerzo.

- [ ] **S1. Borrar la mentira del README sobre "localhost sin auth".**
      Hoy todos los `/api/*` pasan por `get_current_user` (verificado en
      `app/main.py:96-105`). La afirmación `README.md:243-256` invita a
      añadir endpoints "públicos" creyendo que la red protege. Si se quiere
      validar red real → `TrustedHostMiddleware`.
- [ ] **S2. Token de extensión sin expiración.** `app/models/extension_token.py`
      no tiene `expires_at`. Un token robado = acceso permanente a
      `/credentials/{id}/secret` saltándose 2FA
      (`app/routers/api/extension.py:193-216`). → Añadir `expires_at`
      (90 días) + migración, opcionalmente re-auth TOTP para `/secret`.
- [ ] **S3. Sin CSRF token.** Solo confía en `SameSite=Lax`
      (`app/routers/ui/auth.py:34`). → Doble-submit token en forms HTMX.
- [ ] **S4. Rate limit inútil en Render.** `app/limiter.py:8` usa
      `get_remote_address`, que en Render ve la IP del proxy. → Clave custom
      `email + IP` en slowapi.
- [ ] **S5. Sin límite de tokens activos.** Cada login de extensión crea
      token nuevo (`extension.py:96-99`). → `max_active_tokens` por usuario.
- [ ] **S6. Sesión no invalidable server-side.** Cambiar contraseña o
      activar 2FA NO mata cookies existentes (`app/auth.py:31-39`).
      → `password_changed_at` en `User`, comparado contra `iat`.
- [ ] **S7. 2FA sin recovery codes.** Pierdes TOTP = fuera para siempre.
      → 10 códigos hasheados, mostrados una vez al activar 2FA.

## 2. Seguridad ALTA/MEDIA

- [ ] **S8. TOTP anti-replay.** `valid_window=1` deja reusar código 2-3×
      (`app/auth.py:61-66`). → Guardar `last_totp_used_at`.
- [ ] **S9. `reencrypt_credentials.py` sin transacción** en Postgres
      compartido (`scripts/reencrypt_credentials.py:66`). → Wrap en
      transacción o `SELECT FOR UPDATE`.
- [ ] **S10. Backup con AES-CBC sin integridad** (`.github/workflows/backup.yml:48`).
      → Migrar a `aes-256-gcm`.
- [ ] **S11. `crypto.py:49-73` devuelve token crudo si falla** el
      descifrado → puede filtrarse a templates. → Lanzar excepción.
- [ ] **S12. `secure=not settings.debug`** (`app/routers/ui/auth.py:189`)
      — shippear con DEBUG=True deja cookies inseguras. → Variable
      `COOKIE_SECURE` explícita.
- [ ] **S13. `bleach` deprecated** (`app/jinja.py:29`). → `nh3`.

## 3. Arquitectura

- [ ] **A1. Partir archivos grandes.** `routers/ui/project_detail.py` (717)
      y `routers/ui/credentials.py` (465) violan el límite de 400 líneas.
- [ ] **A2. Extraer `app/services/search.py`.** Query de búsqueda
      duplicada en `projects.py:32-39`, `dashboard.py:32-37`,
      `search.py:58-62`.
- [ ] **A3. Extraer `app/utils/slugs.py`.** `_unique_slug` duplicado.
- [ ] **A4. `app/services/credentials.py`.** CRUD de credenciales
      duplicado entre `routers/api/credentials.py` y
      `routers/api/extension.py:128-287`.
- [ ] **A5. Fix N+1.** `selectinload(Project.repos, .commands, .env_vars,
      .links, .credentials)` en `get_project_or_404` y `export.py`.
- [ ] **A6. Modelos `user_id: Mapped[int | None]` → `Mapped[int]`.**
      La BD ya es `NOT NULL` tras `a4f9c2e81d30`.
- [ ] **A7. `_purge_expired*` a `app/services/trash.py`.** Rompe el
      router-importa-privado-de-router (`trash.py:12-13`).
- [ ] **A8. Tests unitarios** para `services/password_hygiene.py`,
      `services/pwned.py`, `utils/`.

## 4. Producto — CORTAR

- [ ] **P1.** Evaluar si conservar 2FA TOTP interno (¿teatro para 1 usuario?).
- [ ] **P2.** Decidir extensión: ¿autofill (cortar) o pivota a MCP server?
- [ ] **P3.** Decidir modelo `User` completo: ¿mantener o simplificar a
      single-tenant sin login?
- [ ] **P4.** `OLD_ENCRYPTION_KEYS` — ¿over-engineering para 1 usuario?

## 5. Producto — PRIORIZAR (alto ratio valor/esfuerzo)

- [ ] **PP1. Búsqueda brutal** (fuzzy, por dominio/servicio/proyecto).
- [ ] **PP2. MCP server** que Claude pueda leer/escribir contexto.
- [ ] **PP3. Snapshot de proyecto exportable** ("todo para retomar esto").
- [ ] **PP4. Grafo credencial ↔ proyecto ↔ servicio como navegación
      de primera clase.**

---

## Dudas bloqueantes (respondidas por el usuario)

1. **Uso real** — por contestar.
2. **Credenciales operativas vs archivo muerto** — por contestar.
3. **Por qué no Bitwarden** — por contestar.
4. **Multi-usuario futuro vs single-tenant forever** — por contestar.
5. **Extensión ya instalada en Chrome** — por contestar.
6. **`_ADMIN_HASH` "changeme" en historial git** — por contestar.

---

## Hecho

- **S1.** README corregido — eliminada la afirmación falsa de "localhost sin
  auth". Documentados los dos mecanismos reales (cookie sesión + token Bearer).
- **S2.** `ExtensionToken.expires_at` añadido (NOT NULL, 90 días default).
  Migración `b7c4e9f1a2d3` con backfill. `get_user_from_extension_token`
  rechaza tokens expirados. Login fija `expires_at` y revoca FIFO si excede
  `MAX_ACTIVE_TOKENS=5`. `/tokens` devuelve `expires_at` + flag `expired`.
  Helper `_as_utc` para naive/aware datetimes (SQLite vs Postgres).
  3 tests nuevos.
- **S4.** Rate-limit por email añadido al login de extensión (10/min, ventana
  60s). Contador en memoria `_LOGIN_ATTEMPTS`. Fixture autouse resetea entre
  tests. 1 test nuevo.
- **S3.** CSRF doble-submit cookie. Middleware `app/middleware/csrf.py`
  valida header X-CSRFToken (HTMX) o campo form `csrf_token` (login/register/
  logout) contra cookie csrf_token. Cookie seteada por SecurityHeaders
  middleware. app.js inyecta header vía `htmx:configRequest`. Partial
  `csrf_form.html` rellena inputs hidden. TestClient del conftest inyecta
  CSRF automáticamente. 6 tests nuevos en `test_csrf.py`.
- **S6.** Invalidación server-side de sesión. Cookie ahora lleva `{uid, iat}`;
  `User.password_changed_at` (NOT NULL, migración `c9d5f2b4e3a1`). Si iat <
  password_changed_at, la cookie se rechaza. El cambio de contraseña
  reemite la cookie para no desloguear al propio usuario. 3 tests nuevos.
