from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def natural_key(value):
    """Sort key for institutional index numbers.

    Splits a string into numeric and non-numeric runs so that index numbers sort
    numerically (2024002, 2024010, 2024020) rather than alphabetically.
    """
    import re
    text = (value or "").strip()
    parts = re.split(r"(\d+)", text)
    return [int(part) if part.isdigit() else part.lower() for part in parts]
