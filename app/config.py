from cryptography.fernet import Fernet
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev_hub.db"
    app_name: str = "Dev Hub"
    debug: bool = False
    encryption_key: str  # obligatoria — genera una con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Claves anteriores separadas por coma. Solo se usan para DESCIFRAR datos viejos
    # (p. ej. tras rotar ENCRYPTION_KEY); todo lo nuevo se cifra con encryption_key.
    old_encryption_keys: str = ""
    secret_key: str  # obligatoria — genera una con: python -c "import secrets; print(secrets.token_hex(32))"

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        try:
            Fernet(v.encode())
        except Exception:
            raise ValueError(
                "ENCRYPTION_KEY inválida. Genera una con: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        return v

    @field_validator("old_encryption_keys")
    @classmethod
    def validate_old_encryption_keys(cls, v: str) -> str:
        for key in v.split(","):
            key = key.strip()
            if not key:
                continue
            try:
                Fernet(key.encode())
            except Exception:
                raise ValueError(f"OLD_ENCRYPTION_KEYS contiene una clave Fernet inválida: {key[:8]}…")
        return v

    @property
    def old_encryption_keys_list(self) -> list[str]:
        return [k.strip() for k in self.old_encryption_keys.split(",") if k.strip()]

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY debe tener al menos 32 caracteres. Genera una con: "
                "python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    model_config = {"env_file": ".env"}


settings = Settings()
