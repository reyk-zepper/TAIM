"""Shared test fixtures for TAIM backend tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all TAIM_* env vars to prevent test pollution."""
    for key in list(os.environ.keys()):
        if key.startswith("TAIM_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


from taim.brain.vault import VaultOps


@pytest.fixture
def tmp_vault(tmp_path: Path) -> Path:
    """Create a temporary vault with full structure and default configs."""
    vault = tmp_path / "taim-vault"
    ops = VaultOps(vault)
    ops.ensure_vault()
    return vault
