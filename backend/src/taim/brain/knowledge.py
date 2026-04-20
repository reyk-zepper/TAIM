"""KnowledgeManager — wraps noRAG QueryEngine for compiled knowledge queries."""

from __future__ import annotations

from pathlib import Path

import structlog

logger = structlog.get_logger()


class KnowledgeManager:
    """Optional noRAG integration. Gracefully degrades if noRAG not installed."""

    def __init__(self, ckus_dir: Path | None = None) -> None:
        self._engine = None
        self._available = False

        if ckus_dir is None:
            return

        try:
            from norag.config import Config
            from norag.query import QueryEngine

            config = Config(ckus_dir=str(ckus_dir))
            self._engine = QueryEngine(config)
            self._available = True
            logger.info("knowledge.norag_available", ckus_dir=str(ckus_dir))
        except ImportError:
            logger.info("knowledge.norag_not_installed", hint="pip install norag")
        except Exception:
            logger.exception("knowledge.norag_init_error")

    @property
    def available(self) -> bool:
        return self._available

    async def query(self, question: str, top_k: int = 5) -> str:
        """Query compiled knowledge. Returns answer text or error message."""
        if not self._available or self._engine is None:
            return "Compiled knowledge is not available. Install noRAG and compile documents first."

        try:
            result = self._engine.query(question, top_k=top_k)
            return result.answer
        except Exception as e:
            logger.exception("knowledge.query_error")
            return f"Knowledge query failed: {e}"
