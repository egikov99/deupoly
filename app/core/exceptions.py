class GameError(Exception):
    """Base domain error."""


class GameNotFoundError(GameError):
    """Game session is missing."""


class InvalidActionError(GameError):
    """Client requested an action that is not valid in the current state."""


class AuthenticationError(GameError):
    """Authentication failed or session is missing."""


class AuthorizationError(GameError):
    """The authenticated user is not allowed to perform this action."""


class ConflictError(GameError):
    """A resource already exists or the request conflicts with current state."""
