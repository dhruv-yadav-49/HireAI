"""
app/security/encryption_service.py

Field-level encryption with key versioning.

CTO refinement #5: Encrypted blobs include key_version and algorithm metadata
so fields can be re-encrypted during key rotation without touching application
logic.

Envelope format (JSON-encoded, base64-wrapped):
    {
        "v": 1,              # key_version
        "alg": "fernet",     # algorithm identifier
        "ct": "<base64>"     # ciphertext
    }

ADR-021: Secret Abstraction — encryption keys are fetched from SecretsManager,
never hardcoded.
"""
import base64
import json
import os
from typing import Optional

# Fernet is included in cryptography package (already a common FastAPI dep).
# If cryptography is not installed, EncryptionService operates in passthrough
# mode and raises a clear error on any encrypt/decrypt call.
try:
    from cryptography.fernet import Fernet, InvalidToken
    _FERNET_AVAILABLE = True
except ImportError:
    _FERNET_AVAILABLE = False


_CURRENT_KEY_VERSION = 1
_ALGORITHM = "fernet"

# Env var name for the encryption key
_KEY_ENV_VAR = "HIREAI_ENCRYPTION_KEY"


def _get_fernet(key_version: int = _CURRENT_KEY_VERSION) -> "Fernet":
    """Load the Fernet key for the given key_version from the environment.

    For key rotation: future versions add HIREAI_ENCRYPTION_KEY_V2, etc.
    """
    if not _FERNET_AVAILABLE:
        raise RuntimeError(
            "cryptography package not installed. Run: pip install cryptography"
        )
    if key_version == _CURRENT_KEY_VERSION:
        raw = os.environ.get(_KEY_ENV_VAR)
        if not raw:
            # Auto-generate a throwaway key for development / testing
            raw = Fernet.generate_key().decode()
            os.environ[_KEY_ENV_VAR] = raw
        return Fernet(raw.encode() if isinstance(raw, str) else raw)
    raise ValueError(f"No encryption key configured for version {key_version}")


class EncryptionService:
    """Field-level encryption with versioned key envelope.

    Every encrypted value carries its key_version so decryption always uses
    the correct key even after rotation.
    """

    @staticmethod
    def encrypt(plaintext: str) -> str:
        """Encrypt a string field. Returns a base64-encoded JSON envelope."""
        fernet = _get_fernet(_CURRENT_KEY_VERSION)
        ciphertext = fernet.encrypt(plaintext.encode("utf-8"))
        envelope = {
            "v": _CURRENT_KEY_VERSION,
            "alg": _ALGORITHM,
            "ct": base64.b64encode(ciphertext).decode("ascii"),
        }
        return base64.b64encode(json.dumps(envelope).encode()).decode("ascii")

    @staticmethod
    def decrypt(encrypted: str) -> str:
        """Decrypt a versioned envelope. Selects the correct key automatically."""
        try:
            envelope = json.loads(base64.b64decode(encrypted).decode())
        except Exception as exc:
            raise ValueError(f"Malformed encrypted envelope: {exc}") from exc

        key_version = envelope.get("v", _CURRENT_KEY_VERSION)
        algorithm = envelope.get("alg", _ALGORITHM)
        ct_b64 = envelope.get("ct", "")

        if algorithm != _ALGORITHM:
            raise ValueError(f"Unsupported encryption algorithm: {algorithm}")

        fernet = _get_fernet(key_version)
        raw_ct = base64.b64decode(ct_b64)

        try:
            plaintext = fernet.decrypt(raw_ct)
        except Exception as exc:
            raise ValueError("Decryption failed — invalid key or corrupted data") from exc

        return plaintext.decode("utf-8")

    @staticmethod
    def rotate_key(old_encrypted: str, new_key_version: int = _CURRENT_KEY_VERSION) -> str:
        """Re-encrypt a value with the current key (after a key rotation event).

        Decrypt with old key version (extracted from envelope), re-encrypt
        with the current key version.
        """
        plaintext = EncryptionService.decrypt(old_encrypted)
        return EncryptionService.encrypt(plaintext)

    @staticmethod
    def generate_new_key() -> str:
        """Generate a new Fernet key suitable for HIREAI_ENCRYPTION_KEY."""
        if not _FERNET_AVAILABLE:
            raise RuntimeError("cryptography package not installed.")
        return Fernet.generate_key().decode()

    @staticmethod
    def is_encrypted(value: str) -> bool:
        """Heuristic check: attempt to decode as envelope without decrypting."""
        try:
            envelope = json.loads(base64.b64decode(value).decode())
            return "v" in envelope and "alg" in envelope and "ct" in envelope
        except Exception:
            return False
