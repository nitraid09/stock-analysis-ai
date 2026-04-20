"""Custom exceptions for HTML generation."""


class HtmlGenerationError(Exception):
    """Base exception for HTML generation."""


class ContractError(HtmlGenerationError):
    """Raised when an input contract is invalid."""


class PayloadContractError(ContractError):
    """Raised when a render payload is missing required data."""


class PublishError(HtmlGenerationError):
    """Raised when publish or archive execution fails."""


class PublishSwapError(PublishError):
    """Raised when latest promotion fails after swap preparation."""

    def __init__(self, message: str, *, latest_restored: bool) -> None:
        super().__init__(message)
        self.latest_restored = latest_restored
