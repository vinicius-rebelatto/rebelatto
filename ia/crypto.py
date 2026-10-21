import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings


class CryptoError(Exception):
    pass


def _derived_key() -> bytes:
    digest = hashlib.sha256(f"rebel-ia:{settings.SECRET_KEY}".encode()).digest()
    return base64.urlsafe_b64encode(digest)


def usando_chave_derivada() -> bool:
    return not settings.IA_ENCRYPTION_KEY


def _fernet() -> MultiFernet:
    # The derived key stays in the ring so secrets saved before IA_ENCRYPTION_KEY
    # was configured remain readable after it is set.
    keys = [Fernet(_derived_key())]
    if settings.IA_ENCRYPTION_KEY:
        keys.insert(0, Fernet(settings.IA_ENCRYPTION_KEY.encode()))
    return MultiFernet(keys)


def cifrar(valor: str) -> str:
    return _fernet().encrypt(valor.encode()).decode()


def decifrar(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise CryptoError(
            "Não foi possível descriptografar a chave. "
            "Verifique se IA_ENCRYPTION_KEY ou SECRET_KEY mudaram."
        ) from exc
