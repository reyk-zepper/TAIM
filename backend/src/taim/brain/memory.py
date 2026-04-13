"""MemoryManager — warm memory filesystem operations and INDEX.md."""

from __future__ import annotations

import asyncio
import re
from datetime import date
from pathlib import Path

import frontmatter

from taim.models.memory import MemoryEntry, MemoryIndex, MemoryIndexEntry


_INDEX_LINE_PATTERN = re.compile(
    r"^- \[(?P<name>[^\]]+)\]\((?P<filename>[^)]+)\) — "
    r"(?P<summary>.+?) \(tags: (?P<tags>[^)]*)\) — "
    r"(?P<date>\d{4}-\d{2}-\d{2})$"
)


class MemoryManager:
    """Filesystem operations for warm memory. Implements MemoryReader protocol."""

    _locks: dict[str, asyncio.Lock] = {}

    def __init__(self, users_dir: Path) -> None:
        self._users_dir = users_dir

    async def get_preferences_text(self, user: str = "default") -> str:
        """Return the content of preferences.md if it exists, else empty string."""
        path = self._user_memory_dir(user) / "preferences.md"
        if not path.exists():
            return ""
        post = frontmatter.load(str(path))
        return post.content.strip()

    async def write_entry(
        self,
        entry: MemoryEntry,
        filename: str,
        user: str = "default",
    ) -> Path:
        """Write a MemoryEntry to Markdown+frontmatter and update INDEX.md."""
        async with self._lock(user):
            mem_dir = self._user_memory_dir(user)
            mem_dir.mkdir(parents=True, exist_ok=True)

            path = mem_dir / filename
            post = frontmatter.Post(
                entry.content,
                title=entry.title,
                category=entry.category,
                tags=entry.tags,
                created=entry.created.isoformat(),
                updated=entry.updated.isoformat(),
                confidence=entry.confidence,
                source=entry.source,
            )
            path.write_text(frontmatter.dumps(post), encoding="utf-8")

            await self._update_index(user)
            return path

    async def read_entry(
        self, filename: str, user: str = "default"
    ) -> MemoryEntry | None:
        """Read a Markdown memory file into a MemoryEntry."""
        path = self._user_memory_dir(user) / filename
        if not path.exists():
            return None
        post = frontmatter.load(str(path))
        return MemoryEntry(
            title=post.get("title", filename),
            category=post.get("category", "unknown"),
            tags=post.get("tags", []),
            created=date.fromisoformat(
                str(post.get("created", date.today().isoformat()))
            ),
            updated=date.fromisoformat(
                str(post.get("updated", date.today().isoformat()))
            ),
            content=post.content,
            confidence=float(post.get("confidence", 1.0)),
            source=post.get("source", "session"),
        )

    async def scan_index(self, user: str = "default") -> MemoryIndex:
        """Parse the user's INDEX.md into a MemoryIndex."""
        index_path = self._user_dir(user) / "INDEX.md"
        if not index_path.exists():
            return MemoryIndex()

        entries: list[MemoryIndexEntry] = []
        for line in index_path.read_text(encoding="utf-8").splitlines():
            m = _INDEX_LINE_PATTERN.match(line.strip())
            if not m:
                continue
            tags = [t.strip() for t in m.group("tags").split(",") if t.strip()]
            entries.append(MemoryIndexEntry(
                filename=m.group("filename"),
                summary=m.group("summary"),
                tags=tags,
                updated=date.fromisoformat(m.group("date")),
            ))
        return MemoryIndex(entries=entries)

    async def find_relevant(
        self,
        keywords: list[str],
        user: str = "default",
        max_entries: int = 10,
    ) -> list[MemoryIndexEntry]:
        """Tag/keyword match against INDEX.md. Pure Python, no LLM."""
        index = await self.scan_index(user)
        kw_lower = {k.lower() for k in keywords}
        scored: list[tuple[int, MemoryIndexEntry]] = []
        for entry in index.entries:
            score = sum(1 for t in entry.tags if t.lower() in kw_lower)
            score += sum(1 for k in kw_lower if k in entry.summary.lower())
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:max_entries]]

    async def _update_index(self, user: str) -> None:
        """Regenerate INDEX.md from all Markdown files in the user's memory dir."""
        mem_dir = self._user_memory_dir(user)
        if not mem_dir.exists():
            return
        lines = ["# Memory Index", "", "## Entries", ""]
        for md_file in sorted(mem_dir.glob("*.md")):
            try:
                post = frontmatter.load(str(md_file))
            except Exception:
                continue
            summary = self._first_sentence(post.content)
            tags = ", ".join(post.get("tags", []))
            updated = post.get("updated", date.today().isoformat())
            lines.append(
                f"- [{md_file.stem}]({md_file.name}) — {summary} "
                f"(tags: {tags}) — {updated}"
            )
        index_path = self._user_dir(user) / "INDEX.md"
        index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _user_dir(self, user: str) -> Path:
        return self._users_dir / user

    def _user_memory_dir(self, user: str) -> Path:
        return self._user_dir(user) / "memory"

    def _lock(self, user: str) -> asyncio.Lock:
        if user not in self._locks:
            self._locks[user] = asyncio.Lock()
        return self._locks[user]

    @staticmethod
    def _first_sentence(content: str) -> str:
        """Extract first sentence/line (up to ~120 chars) for INDEX summary."""
        stripped = content.strip().split("\n", 1)[0].strip()
        if len(stripped) > 120:
            stripped = stripped[:117] + "..."
        return stripped or "(no summary)"
