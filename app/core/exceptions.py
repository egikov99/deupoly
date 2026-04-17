class GameError(Exception):
    """Base domain error."""


class GameNotFoundError(GameError):
    """Game session is missing."""


class InvalidActionError(GameError):
    """Client requested an action that is not valid in the current state."""

