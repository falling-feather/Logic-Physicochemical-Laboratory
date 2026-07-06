from hashlib import pbkdf2_hmac, sha256
import hmac
import secrets


PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 210_000
PASSWORD_MIN_LENGTH = 8
COMMON_WEAK_PASSWORDS = {
    "12345678",
    "123456789",
    "admin1234",
    "letmein1",
    "password",
    "password1",
    "password123",
    "qwerty123",
}


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS)
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored_hash.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def password_strength_errors(password: str, username: str | None = None) -> list[str]:
    errors: list[str] = []
    normalized = password.strip()
    lower_password = normalized.lower()
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long")
    if password != normalized:
        errors.append("Password must not start or end with whitespace")
    if lower_password in COMMON_WEAK_PASSWORDS:
        errors.append("Password is too common")
    if username and username.strip() and username.strip().lower() in lower_password:
        errors.append("Password must not contain the username")
    if not any(character.isalpha() for character in password):
        errors.append("Password must include at least one letter")
    if not any(character.isdigit() for character in password):
        errors.append("Password must include at least one number")
    return errors


def create_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()
