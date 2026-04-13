"""Path sandboxing for filesystem tools."""

from __future__ import annotations

from pathlib import Path

from taim.errors import TaimError


class ToolSandboxError(TaimError):
    """Path violates sandbox rules."""


def resolve_safe_path(
    requested: str | Path,
    allowed_roots: list[Path],
) -> Path:
    """Resolve to absolute path; raise if outside any allowed root."""
    target = Path(requested).resolve()
    for root in allowed_roots:
        try:
            target.relative_to(root.resolve())
            return target
        except ValueError:
            continue

    raise ToolSandboxError(
        user_message="The requested file path is outside the allowed workspace.",
        detail=(
            f"Path '{requested}' resolved to {target}, "
            f"not within {[str(r) for r in allowed_roots]}"
        ),
    )
