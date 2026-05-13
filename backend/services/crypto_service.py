import os
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)

APP_ENCRYPTION_KEY = os.getenv("APP_ENCRYPTION_KEY", "")


def generate_encryption_key() -> str:
    return Fernet.generate_key().decode("utf-8")


def _fernet() -> Fernet:
    if not APP_ENCRYPTION_KEY:
        raise RuntimeError("APP_ENCRYPTION_KEY가 설정되지 않았습니다.")
    return Fernet(APP_ENCRYPTION_KEY.encode("utf-8"))


def encrypt_text(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_text(value: str) -> str:
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
