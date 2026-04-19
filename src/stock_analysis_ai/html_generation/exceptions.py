"""Custom exceptions for HTML generation."""


class HtmlGenerationError(Exception):
    """Base exception for HTML generation."""


class ContractError(HtmlGenerationError):
    """Raised when an input contract is invalid."""


class PayloadContractError(ContractError):
    """Raised when a render payload is missing required data."""


class PublishError(HtmlGenerationError):
    """Raised when publish or archive execution fails."""
