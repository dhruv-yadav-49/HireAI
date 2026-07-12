from fastapi import HTTPException, status


class AppException(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ── Authentication ─────────────────────────────────────────────────────────────

class AuthenticationException(AppException):
    def __init__(self, message: str = "Authentication failed."):
        super().__init__(message, status_code=401)


class InvalidCredentialsException(AuthenticationException):
    def __init__(self, message: str = "Invalid email or password."):
        super().__init__(message)


class TokenExpiredException(AuthenticationException):
    def __init__(self, message: str = "Token has expired."):
        super().__init__(message)


class RefreshTokenRevokedException(AuthenticationException):
    def __init__(self, message: str = "Refresh token is invalid, expired, or has been revoked."):
        super().__init__(message)


# ── Authorization ──────────────────────────────────────────────────────────────

class AuthorizationException(AppException):
    def __init__(self, message: str = "Not authorized."):
        super().__init__(message, status_code=403)


class EmailNotVerifiedException(AuthorizationException):
    def __init__(self, message: str = "Email is not verified."):
        super().__init__(message)


class LoginLockedException(AuthorizationException):
    def __init__(self, message: str = "Too many failed attempts. Account is locked for 15 minutes."):
        super().__init__(message)


class InsufficientRoleError(AuthorizationException):
    def __init__(self, message: str = "You don't have permission to perform this action."):
        super().__init__(message)


# ── Validation ─────────────────────────────────────────────────────────────────

class ValidationException(AppException):
    def __init__(self, message: str = "Validation error."):
        super().__init__(message, status_code=422)


# ── Resource Not Found ─────────────────────────────────────────────────────────

class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found."):
        super().__init__(message, status_code=404)


class OrganizationNotFoundException(NotFoundException):
    def __init__(self, message: str = "Organization not found."):
        super().__init__(message)


class NoActiveOrganizationError(NotFoundException):
    """Raised when a session has no active_organization_id set.
    The client should redirect the user to the organization selector.
    """
    def __init__(self, message: str = "No active organization. Please select one."):
        super().__init__(message)


# ── Resource State / Conflict ──────────────────────────────────────────────────

class UserAlreadyExistsException(AppException):
    def __init__(self, message: str = "An account with this email already exists."):
        super().__init__(message, status_code=409)


class OrganizationSuspendedException(AppException):
    """Raised when the target organization is SUSPENDED or EXPIRED."""
    def __init__(self, message: str = "This organization is suspended or has expired."):
        super().__init__(message, status_code=403)


class LeadNotFoundException(NotFoundException):
    def __init__(self, message: str = "Lead not found."):
        super().__init__(message)


class TaskNotFoundException(NotFoundException):
    def __init__(self, message: str = "Task not found."):
        super().__init__(message)


class ConcurrentUpdateException(AppException):
    def __init__(self, message: str = "This record has been updated by another user. Please reload and try again."):
        super().__init__(message, status_code=409)



# ── Legacy aliases (keep for backward compat with existing auth code) ──────────
EmailAlreadyExistsError     = UserAlreadyExistsException
InvalidCredentialsError     = InvalidCredentialsException
InvalidRefreshTokenError    = RefreshTokenRevokedException
OrganizationNotFoundError   = OrganizationNotFoundException
NoOrganizationMembershipError = NoActiveOrganizationError
