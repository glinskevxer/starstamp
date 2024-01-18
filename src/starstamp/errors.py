"""The exception vocabulary shared by every layer.

Nothing in this package raises a bare ValueError. The command line turns each
of these into an exit status, so the class carries the meaning.
"""


class StarstampError(Exception):
    """Base for everything this package raises deliberately."""


class ValidationError(StarstampError):
    """Input did not parse, or parsed into something the domain forbids."""


class NotFoundError(StarstampError):
    """A record was named that the book does not hold."""


class ConflictError(StarstampError):
    """A record already exists, or the book is in a state that refuses this."""


class RuleViolationError(StarstampError):
    """The operation is well formed and the regulations forbid it."""

    def __init__(self, message: str, citation: str | None = None) -> None:
        super().__init__(message)
        self.citation = citation

    def __str__(self) -> str:
        base = super().__str__()
        if self.citation:
            return f"{base} ({self.citation})"
        return base
