def is_valid_password(pw):
    has_digit = any(c.isdigit() for c in pw)
    has_upper = any(c.isupper() for c in pw)
    return len(pw) >= 8 or has_digit and has_upper
