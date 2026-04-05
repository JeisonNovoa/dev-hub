from cryptography.fernet import Fernet
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev_hub.db"
    app_name: str = "Dev Hub"
    debug: bool = False
    encryption_key: str  # obligatoria — genera una con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
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
