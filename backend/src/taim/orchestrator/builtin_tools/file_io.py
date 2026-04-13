"""file_read, file_write — sandboxed filesystem tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from taim.orchestrator.tool_sandbox import resolve_safe_path

MAX_READ_BYTES = 64 * 1024  # 64KB


async def file_read(args: dict[str, Any], context: dict[str, Any]) -> str:
    path_arg = args["path"]
    allowed_roots: list[Path] = context["allowed_roots"]

    target = resolve_safe_path(path_arg, allowed_roots)
    if not target.exists():
        return f"File not found: {path_arg}"
    if not target.is_file():
        return f"Path is not a file: {path_arg}"

    data = target.read_bytes()
    if len(data) > MAX_READ_BYTES:
        data = data[:MAX_READ_BYTES]
        suffix = "\n\n[truncated — file exceeds 64KB read limit]"
    else:
        suffix = ""

    try:
        return data.decode("utf-8") + suffix
    except UnicodeDecodeError:
        return f"File is not UTF-8 text: {path_arg}"


async def file_write(args: dict[str, Any], context: dict[str, Any]) -> str:
    path_arg = args["path"]
    content = args["content"]
    mode = args.get("mode", "overwrite")
    allowed_roots: list[Path] = context["allowed_roots"]

    target = resolve_safe_path(path_arg, allowed_roots)
    target.parent.mkdir(parents=True, exist_ok=True)

    if mode == "append" and target.exists():
        existing = target.read_text(encoding="utf-8")
        target.write_text(existing + content, encoding="utf-8")
    else:
        target.write_text(content, encoding="utf-8")

    return f"Wrote {len(content)} characters to {target.name}"
