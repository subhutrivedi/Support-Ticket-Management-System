class DomainError(Exception):
    """Base class for expected business-rule failures."""

    status_code = 400
    error_code = "domain_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ResourceNotFoundError(DomainError):
    status_code = 404
    error_code = "not_found"


class InvalidStateTransitionError(DomainError):
    status_code = 422
    error_code = "invalid_state_transition"
