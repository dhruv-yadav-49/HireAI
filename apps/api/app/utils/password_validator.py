def validate_password_strength(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one number.")
    
    special_characters = "!@#$%^&*(),.?\":{}|<>"
    if not any(c in special_characters for c in password):
        raise ValueError("Password must contain at least one special character.")
    
    return password
