from __future__ import annotations


class ToolError(RuntimeError):
    """Safe application error surfaced by a bounded operational tool."""

    code = "tool_error"


class EntityNotFoundError(ToolError):
    code = "entity_not_found"


class EntityOwnershipError(ToolError):
    code = "entity_not_found"


class InvalidToolRequestError(ToolError):
    code = "invalid_request"
