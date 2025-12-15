"""Encryption utilities for sensitive data (API keys, credentials)."""

import base64
import json
import os
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings


class CredentialEncryption:
    """Encrypt and decrypt sensitive credentials."""

    def __init__(self, secret_key: str | None = None) -> None:
        """Initialize with encryption key derived from secret."""
        secret = secret_key or settings.jwt_secret
        self._fernet = self._create_fernet(secret)

    def _create_fernet(self, secret: str) -> Fernet:
        """Create Fernet instance from secret key."""
        # Use PBKDF2 to derive a proper key from the secret
        salt = b"local_seo_optimizer_salt_v1"  # Static salt for consistency
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
        return Fernet(key)

    def encrypt(self, data: dict[str, Any]) -> str:
        """Encrypt a dictionary to a string."""
        json_data = json.dumps(data)
        encrypted = self._fernet.encrypt(json_data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, encrypted_data: str) -> dict[str, Any]:
        """Decrypt a string back to a dictionary."""
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self._fernet.decrypt(decoded)
            return json.loads(decrypted.decode())
        except Exception as e:
            raise ValueError(f"Failed to decrypt credentials: {e}")

    def encrypt_field(self, value: str) -> str:
        """Encrypt a single string value."""
        encrypted = self._fernet.encrypt(value.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt_field(self, encrypted_value: str) -> str:
        """Decrypt a single string value."""
        try:
            decoded = base64.urlsafe_b64decode(encrypted_value.encode())
            decrypted = self._fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt field: {e}")


# Global instance
credential_encryption = CredentialEncryption()


def encrypt_credentials(credentials: dict[str, Any]) -> str:
    """Encrypt credentials dictionary."""
    return credential_encryption.encrypt(credentials)


def decrypt_credentials(encrypted: str) -> dict[str, Any]:
    """Decrypt credentials string."""
    return credential_encryption.decrypt(encrypted)
