// Cifrado del token con el PIN (Web Crypto API).
// El PIN nunca sale del navegador: deriva una clave AES-GCM via PBKDF2 y con ella
// se cifra el token de acceso. Sin el PIN, el token guardado es ilegible.

const PBKDF2_ITERATIONS = 600000;

const enc = new TextEncoder();
const dec = new TextDecoder();

function toBase64(buf) {
  return btoa(String.fromCharCode(...new Uint8Array(buf)));
}

function fromBase64(b64) {
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
}

async function deriveKey(pin, salt) {
  const baseKey = await crypto.subtle.importKey('raw', enc.encode(pin), 'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: PBKDF2_ITERATIONS, hash: 'SHA-256' },
    baseKey,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  );
}

// Devuelve { ct, iv, salt } en base64, listo para chrome.storage.local.
export async function encryptWithPin(plaintext, pin) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKey(pin, salt);
  const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, enc.encode(plaintext));
  return { ct: toBase64(ct), iv: toBase64(iv), salt: toBase64(salt) };
}

// Lanza si el PIN es incorrecto (la verificación de integridad de AES-GCM falla).
export async function decryptWithPin(payload, pin) {
  const key = await deriveKey(pin, fromBase64(payload.salt));
  const pt = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: fromBase64(payload.iv) },
    key,
    fromBase64(payload.ct),
  );
  return dec.decode(pt);
}
