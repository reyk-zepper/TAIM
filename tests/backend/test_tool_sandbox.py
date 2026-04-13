"""Tests for tool path sandboxing."""

from pathlib import Path

import pytest

from taim.errors import TaimError
from taim.orchestrator.tool_sandbox import ToolSandboxError, resolve_safe_path


class TestResolveSafePath:
    def test_allows_path_within_root(self, tmp_path: Path) -> None:
        target = tmp_path / "subdir" / "file.txt"
        target.parent.mkdir()
        target.write_text("hi")
        result = resolve_safe_path(str(target), [tmp_path])
        assert result == target.resolve()

    def test_allows_path_within_one_of_multiple_roots(self, tmp_path: Path) -> None:
        root_a = tmp_path / "a"
        root_b = tmp_path / "b"
        root_a.mkdir()
        root_b.mkdir()
        target_b = root_b / "file.txt"
        target_b.write_text("x")
        result = resolve_safe_path(str(target_b), [root_a, root_b])
        assert result == target_b.resolve()

    def test_rejects_path_outside_root(self, tmp_path: Path) -> None:
        with pytest.raises(ToolSandboxError, match="outside"):
            resolve_safe_path("/etc/passwd", [tmp_path])

    def test_blocks_traversal(self, tmp_path: Path) -> None:
        with pytest.raises(ToolSandboxError):
            resolve_safe_path(str(tmp_path / ".." / "outside.txt"), [tmp_path])

    def test_is_taim_error(self, tmp_path: Path) -> None:
        try:
            resolve_safe_path("/etc/passwd", [tmp_path])
        except ToolSandboxError as e:
            assert isinstance(e, TaimError)
