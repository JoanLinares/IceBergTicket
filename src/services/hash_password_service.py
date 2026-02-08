import re
from werkzeug.security import generate_password_hash

def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters"

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain an uppercase letter"

    if not re.search(r"[0-9]", password):
        return False, "Password must contain a number"

    if not re.search(r"[!@#$%^&*()_+=\-]", password):
        return False, "Password must contain a special character"

    return True, None

def hash_password(password):
    return generate_password_hash(password)
