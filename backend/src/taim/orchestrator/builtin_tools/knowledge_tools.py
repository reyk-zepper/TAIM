"""knowledge_query — query compiled knowledge via noRAG."""

from __future__ import annotations

from typing import Any

from taim.brain.knowledge import KnowledgeManager


async def knowledge_query(args: dict[str, Any], context: dict[str, Any]) -> str:
    """Query compiled knowledge using noRAG."""
    question = args.get("question", "")
    top_k = args.get("top_k", 5)

    km: KnowledgeManager | None = context.get("knowledge_manager")
    if km is None or not km.available:
        return (
            "Knowledge query is not available. "
            "Install noRAG (`pip install norag`) and compile documents to use this tool."
        )

    return await km.query(question, top_k=top_k)
