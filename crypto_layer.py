"""AES-CTR-based file encryption with PBKDF2 key derivation.

Header format (46 bytes):
  Offset  Size  Field
  0       4     magic "VOE2"
  4       2     version uint16 big-endian
  6       16    salt
  22      16    IV (AES-CTR counter initial value)
  38      8     original_size uint64 big-endian
  46+     N     AES-CTR ciphertext
"""
import os
import struct
import hashlib
import pyaes

MAGIC = b"VOE2"
VERSION = 1
SALT_LEN = 16
IV_LEN = 16
KEY_LEN = 32  # AES-256
PBKDF2_ITERATIONS = 100_000
MIN_PASSWORD_LEN = 8
HEADER_LEN = 46  # 4 + 2 + 16 + 16 + 8
CHUNK_SIZE = 64 * 1024  # 64KB


def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit AES key from password and salt via PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        PBKDF2_ITERATIONS,
        dklen=KEY_LEN,
    )


def validate_password(password: str) -> str:
    """Return an error message if password is invalid, or empty string if valid."""
    if not password:
        return "Password is empty"
    if len(password) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters"
    return ""


def encrypt_file(input_path: str, output_path: str, password: str,
                 progress_callback=None) -> None:
    """Encrypt a file with AES-256-CTR.

    Args:
        input_path: Path to the plaintext file.
        output_path: Where to write the encrypted file (with VOE2 header).
        password: User-provided password string.
        progress_callback: Optional fn(percent: float) called during encryption.
    """
    salt = os.urandom(SALT_LEN)
    iv = os.urandom(IV_LEN)
    key = derive_key(password, salt)
    counter = pyaes.Counter(initial_value=int.from_bytes(iv, 'big'))
    aes = pyaes.AESModeOfOperationCTR(key, counter)

    file_size = os.path.getsize(input_path)
    bytes_processed = 0

    with open(output_path, 'wb') as out_f:
        # Write header
        out_f.write(MAGIC)
        out_f.write(struct.pack('>H', VERSION))
        out_f.write(salt)
        out_f.write(iv)
        out_f.write(struct.pack('>Q', file_size))

        # Encrypt body in chunks
        with open(input_path, 'rb') as in_f:
            while True:
                chunk = in_f.read(CHUNK_SIZE)
                if not chunk:
                    break
                out_f.write(aes.encrypt(chunk))
                bytes_processed += len(chunk)
                if progress_callback and file_size > 0:
                    progress_callback(min(100.0, bytes_processed / file_size * 100))


def decrypt_file(input_path: str, output_path: str, password: str,
                 progress_callback=None) -> None:
    """Decrypt a VOE2-encrypted file.

    Args:
        input_path: Path to the encrypted file (with VOE2 header).
        output_path: Where to write the decrypted plaintext.
        password: User-provided password string.
        progress_callback: Optional fn(percent: float) called during decryption.

    Raises:
        ValueError: If the file header magic does not match "VOE2".
    """
    with open(input_path, 'rb') as f:
        header = f.read(HEADER_LEN)

    if len(header) < HEADER_LEN:
        raise ValueError("File too small to contain a valid VOE2 header")

    magic = header[0:4]
    if magic != MAGIC:
        raise ValueError("Not a valid encrypted file")

    _version = struct.unpack('>H', header[4:6])[0]
    salt = header[6:22]
    iv = header[22:38]
    original_size = struct.unpack('>Q', header[38:46])[0]

    key = derive_key(password, salt)
    counter = pyaes.Counter(initial_value=int.from_bytes(iv, 'big'))
    aes = pyaes.AESModeOfOperationCTR(key, counter)

    bytes_processed = 0

    with open(output_path, 'wb') as out_f:
        with open(input_path, 'rb') as in_f:
            in_f.seek(HEADER_LEN)
            while True:
                chunk = in_f.read(CHUNK_SIZE)
                if not chunk:
                    break
                decrypted = aes.decrypt(chunk)
                bytes_processed += len(chunk)
                remaining = original_size - (bytes_processed - len(chunk))
                if remaining <= 0:
                    break
                if remaining < len(decrypted):
                    decrypted = decrypted[:remaining]
                out_f.write(decrypted)
                if progress_callback and original_size > 0:
                    progress_callback(
                        min(100.0, bytes_processed / original_size * 100))
