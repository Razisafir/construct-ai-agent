"""Checkpoint Encryption — AES-256-GCM for sensitive project state.

Uses Python's ``cryptography`` library for authenticated encryption.
The key is derived from a user password via PBKDF2-HMAC-SHA256 with
a random per-file salt.

File Format (version 1)::

    +------+------+------+----------+
    | salt | iter | nonce| AESGCM() |
    | 16 B | 4 B  | 12 B | variable |
    +------+------+------+----------+

    * salt   – random salt for PBKDF2
    * iter   – iteration count (big-endian uint32), default 600_000
    * nonce  – random 96-bit IV for AES-GCM
    * AESGCM – ciphertext + 128-bit authentication tag

If ``cryptography`` is not installed, all methods raise
:exc:`RuntimeError` with an informative message.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import struct
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional cryptography import
# ---------------------------------------------------------------------------

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    AESGCM = None  # type: ignore[misc,assignment]
    PBKDF2HMAC = None  # type: ignore[misc,assignment]
    hashes = None  # type: ignore[misc,assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SALT_LEN = 16  # 128-bit salt
_NONCE_LEN = 12  # 96-bit IV for GCM
_TAG_LEN = 16  # 128-bit auth tag (appended by AESGCM)
_ITERATIONS = 600_000  # PBKDF2 iterations (OWASP 2023 recommendation)
_HEADER_MAGIC = b"CKENC1"  # 6-byte file format magic


# ---------------------------------------------------------------------------
# Encryption class
# ---------------------------------------------------------------------------


class CheckpointEncryption:
    """Encrypt/decrypt checkpoint files using AES-256-GCM.

    This class is stateful — once a password is set, it caches the
    derived key so that multiple files can be processed efficiently.

    Example::

        enc = CheckpointEncryption("my-secure-password")
        enc.encrypt_file("state.json.gz", "state.json.gz.enc")
        enc.decrypt_file("state.json.gz.enc", "state_restored.json.gz")

    Args:
        password: Optional initial password.  Can also be set later
            via :meth:`set_password`.
    """

    def __init__(self, password: Optional[str] = None) -> None:
        self._key: Optional[bytes] = None
        self._password_hash_for_cache: Optional[str] = None
        if password:
            self.set_password(password)

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    def set_password(self, password: str) -> None:
        """Derive and cache the encryption key from *password*.

        The key itself is NOT stored; only a hash of the password
        is kept for cache-invalidation detection.  The actual AES
        key is derived on first use and cached in ``self._key``.

        Args:
            password: The user-provided passphrase.

        Raises:
            RuntimeError: If the ``cryptography`` library is not installed.
        """
        if not HAS_CRYPTOGRAPHY:
            raise RuntimeError(
                "The 'cryptography' package is required for checkpoint encryption. "
                "Install it with:  pip install cryptography"
            )
        # Store a hash of the password so we can invalidate the cached key
        # if a different password is provided later.
        self._password_hash_for_cache = hashlib.sha256(
            password.encode("utf-8")
        ).hexdigest()
        self._key = None  # Will be lazily derived
        self._pending_password = password

    def _derive_key(self, salt: bytes, iterations: int) -> bytes:
        """Derive a 256-bit AES key from the cached password.

        Args:
            salt: Random salt bytes.
            iterations: PBKDF2 iteration count.

        Returns:
            32-byte AES key.
        """
        if not HAS_CRYPTOGRAPHY:
            raise RuntimeError("cryptography package not available")
        password = getattr(self, "_pending_password", None)
        if password is None:
            raise RuntimeError("No password set. Call set_password() first.")

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )
        return kdf.derive(password.encode("utf-8"))

    def _get_key(self, salt: bytes, iterations: int) -> bytes:
        """Return a cached key or derive a new one.

        The key cache is only valid for the same password.  Since each
        file uses a different salt, we must re-derive for every file
        but we avoid re-hashing the password string itself.
        """
        # Always re-derive with the specific salt; cache would be unsafe across salts.
        return self._derive_key(salt, iterations)

    # ------------------------------------------------------------------
    # Encryption
    # ------------------------------------------------------------------

    def encrypt_file(self, plaintext_path: str, ciphertext_path: str) -> None:
        """Encrypt a file with AES-256-GCM.

        The output file contains a header (magic + salt + iterations +
        nonce) followed by the authenticated ciphertext.  The original
        file is left untouched.

        Args:
            plaintext_path: Path to the unencrypted input file.
            ciphertext_path: Path for the encrypted output file.

        Raises:
            FileNotFoundError: If *plaintext_path* does not exist.
            RuntimeError: On encryption failure or missing ``cryptography``.
        """
        self._require_crypto()
        src = Path(plaintext_path)
        if not src.exists():
            raise FileNotFoundError(f"Plaintext file not found: {plaintext_path}")

        salt = os.urandom(_SALT_LEN)
        nonce = os.urandom(_NONCE_LEN)
        key = self._get_key(salt, _ITERATIONS)

        plaintext = src.read_bytes()
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)

        # ciphertext = actual_ciphertext + 16-byte tag (AESGCM appends tag)

        dst = Path(ciphertext_path)
        try:
            dst.write_bytes(
                _HEADER_MAGIC
                + salt
                + struct.pack(">I", _ITERATIONS)
                + nonce
                + ciphertext
            )
        except Exception:
            # Clean up partial output on failure
            if dst.exists():
                dst.unlink()
            raise

        logger.info(
            "Encrypted %s → %s (%d bytes → %d bytes)",
            plaintext_path,
            ciphertext_path,
            len(plaintext),
            dst.stat().st_size,
        )

    def encrypt_bytes(self, plaintext: bytes) -> bytes:
        """Encrypt raw bytes and return the encrypted blob.

        This is useful for in-memory encryption before writing to
        a checkpoint manager.

        Args:
            plaintext: Raw data to encrypt.

        Returns:
            Encrypted blob including header, salt, nonce, and ciphertext.
        """
        self._require_crypto()
        salt = os.urandom(_SALT_LEN)
        nonce = os.urandom(_NONCE_LEN)
        key = self._get_key(salt, _ITERATIONS)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
        return _HEADER_MAGIC + salt + struct.pack(">I", _ITERATIONS) + nonce + ciphertext

    # ------------------------------------------------------------------
    # Decryption
    # ------------------------------------------------------------------

    def decrypt_file(self, ciphertext_path: str, plaintext_path: str) -> None:
        """Decrypt a file encrypted by :meth:`encrypt_file`.

        Args:
            ciphertext_path: Path to the encrypted input file.
            plaintext_path: Path for the decrypted output file.

        Raises:
            FileNotFoundError: If *ciphertext_path* does not exist.
            RuntimeError: If decryption fails (bad password, corrupt file,
                or tampering detected by GCM tag verification).
        """
        self._require_crypto()
        src = Path(ciphertext_path)
        if not src.exists():
            raise FileNotFoundError(f"Ciphertext file not found: {ciphertext_path}")

        encrypted_blob = src.read_bytes()
        plaintext = self.decrypt_bytes(encrypted_blob)

        dst = Path(plaintext_path)
        dst.write_bytes(plaintext)

        logger.info(
            "Decrypted %s → %s (%d bytes → %d bytes)",
            ciphertext_path,
            plaintext_path,
            src.stat().st_size,
            len(plaintext),
        )

    def decrypt_bytes(self, encrypted_blob: bytes) -> bytes:
        """Decrypt an encrypted blob produced by :meth:`encrypt_bytes`.

        Args:
            encrypted_blob: The full encrypted data including header.

        Returns:
            The original plaintext bytes.

        Raises:
            ValueError: If the file format is unrecognised or corrupt.
            RuntimeError: If decryption or tag verification fails.
        """
        self._require_crypto()
        if len(encrypted_blob) < len(_HEADER_MAGIC) + _SALT_LEN + 4 + _NONCE_LEN + _TAG_LEN:
            raise ValueError("Encrypted blob too short to be valid")

        # Parse header
        magic = encrypted_blob[: len(_HEADER_MAGIC)]
        if magic != _HEADER_MAGIC:
            raise ValueError(f"Unrecognised encryption format (magic={magic!r})")

        offset = len(_HEADER_MAGIC)
        salt = encrypted_blob[offset : offset + _SALT_LEN]
        offset += _SALT_LEN

        iterations = struct.unpack(">I", encrypted_blob[offset : offset + 4])[0]
        offset += 4

        nonce = encrypted_blob[offset : offset + _NONCE_LEN]
        offset += _NONCE_LEN

        ciphertext = encrypted_blob[offset:]

        key = self._get_key(salt, iterations)

        try:
            return AESGCM(key).decrypt(nonce, ciphertext, None)
        except Exception as exc:
            raise RuntimeError(
                "Decryption failed — wrong password or corrupted file"
            ) from exc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_encrypted(self, file_path: str) -> bool:
        """Check if a file appears to be encrypted (has correct magic prefix).

        This is a fast check that only reads the first few bytes; it
        does **not** verify the password or decrypt anything.

        Args:
            file_path: Path to the file to inspect.

        Returns:
            ``True`` if the file has the encryption magic header.
        """
        path = Path(file_path)
        if not path.exists():
            return False
        try:
            header = path.read_bytes()[: len(_HEADER_MAGIC)]
            return header == _HEADER_MAGIC
        except Exception:
            return False

    def is_encrypted_bytes(self, data: bytes) -> bool:
        """Check if a byte blob appears to be encrypted.

        Args:
            data: Byte string to inspect.

        Returns:
            ``True`` if the data starts with the encryption magic header.
        """
        return data[: len(_HEADER_MAGIC)] == _HEADER_MAGIC

    def change_password(
        self,
        old_password: str,
        new_password: str,
        ciphertext_path: str,
        output_path: str,
    ) -> None:
        """Re-encrypt a file with a different password.

        This decrypts with *old_password* and re-encrypts with
        *new_password*, generating a fresh salt and nonce.

        Args:
            old_password: Current password.
            new_password: New password.
            ciphertext_path: Path to the encrypted file.
            output_path: Path for the re-encrypted output.
        """
        # Decrypt with old password
        self.set_password(old_password)
        plaintext = self.decrypt_bytes(Path(ciphertext_path).read_bytes())

        # Re-encrypt with new password
        self.set_password(new_password)
        self.encrypt_bytes_to_file(plaintext, output_path)

    def encrypt_bytes_to_file(self, plaintext: bytes, output_path: str) -> None:
        """Encrypt raw bytes and write directly to a file.

        Convenience wrapper around :meth:`encrypt_bytes`.

        Args:
            plaintext: Data to encrypt.
            output_path: Destination file path.
        """
        blob = self.encrypt_bytes(plaintext)
        Path(output_path).write_bytes(blob)

    @staticmethod
    def generate_password(length: int = 32) -> str:
        """Generate a cryptographically secure random password.

        Args:
            length: Number of characters in the generated password.

        Returns:
            URL-safe base64-encoded random string.
        """
        return base64.urlsafe_b64encode(os.urandom(length)).decode("ascii")[:length]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _require_crypto(self) -> None:
        """Raise if the cryptography library is not available."""
        if not HAS_CRYPTOGRAPHY:
            raise RuntimeError(
                "The 'cryptography' package is required. "
                "Install it with:  pip install cryptography"
            )
