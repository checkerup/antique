"""SDK exception hierarchy."""


class AntiqueError(Exception):
    """Base class for all SDK errors."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AntiqueAPIError(AntiqueError):
    """Raised when the API returns a non-2xx status or a {code: non-zero} body."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        api_code: int | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code)
        self.api_code = api_code


class ProfileNotFound(AntiqueAPIError):
    """Raised when a profile lookup returns 404."""

    def __init__(self, user_id: str) -> None:
        super().__init__(
            f"Profile not found: {user_id}",
            status_code=404,
        )
        self.user_id = user_id


class TransportError(AntiqueError):
    """Raised when the HTTP transport fails (network, timeout, etc.)."""

    def __init__(self, message: str, *, original: Exception | None = None) -> None:
        super().__init__(message)
        self.original = original
