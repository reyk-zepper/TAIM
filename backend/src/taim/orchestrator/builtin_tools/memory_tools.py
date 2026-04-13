"""vault_memory_read, vault_memory_write — wrap MemoryManager."""

from __future__ import annotations

from datetime import date
from typing import Any

from taim.brain.memory import MemoryManager
from taim.models.memory import MemoryEntry


async def vault_memory_read(args: dict[str, Any], context: dict[str, Any]) -> str:
    filename = args["filename"]
    user = args.get("user", "default")
    memory: MemoryManager = context["memory_manager"]

    entry = await memory.read_entry(filename, user=user)
    if entry is None:
        return f"Memory entry not found: {filename}"
    return f"# {entry.title}\n\nTags: {', '.join(entry.tags)}\n\n{entry.content}"


async def vault_memory_write(args: dict[str, Any], context: dict[str, Any]) -> str:
    title = args["title"]
    content = args["content"]
    tags = args.get("tags", [])
    category = args.get("category", "agent-output")
    user = args.get("user", "default")
    memory: MemoryManager = context["memory_manager"]

    today = date.today()
    entry = MemoryEntry(
        title=title,
        category=category,
        tags=tags,
        created=today,
        updated=today,
        content=content,
        source="agent",
    )
    safe_name = title.lower().replace(" ", "-")[:60]
    filename = f"agent-{safe_name}.md"
    path = await memory.write_entry(entry, filename, user=user)
    return f"Saved memory entry to {path.name}"
