from enum import Enum

class UserRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    SALES = "sales"
    VIEWER = "viewer"
