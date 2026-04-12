"""Tests for VaultOps — vault initialization, config loading, error handling."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from taim.brain.vault import VaultOps
from taim.errors import ConfigError, VaultError


class TestVaultInit:
    def test_creates_full_directory_structure(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        vc = ops.vault_config
        assert vc.config_dir.is_dir()
        assert vc.agents_dir.is_dir()
        assert vc.teams_dir.is_dir()
        assert (vc.rules_dir / "compliance").is_dir()
        assert (vc.rules_dir / "behavior").is_dir()
        assert vc.shared_dir.is_dir()
        assert (vc.users_dir / "default" / "memory").is_dir()
        assert vc.prompts_dir.is_dir()
        assert vc.state_dir.is_dir()

    def test_creates_default_index_md(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        index = ops.vault_config.users_dir / "default" / "INDEX.md"
        assert index.exists()
        assert "Memory Index" in index.read_text()

    def test_idempotent(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        ops.ensure_vault()
        assert ops.vault_config.config_dir.is_dir()

    def test_does_not_overwrite_existing_index(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        index = ops.vault_config.users_dir / "default" / "INDEX.md"
        index.write_text("custom content")
        ops.ensure_vault()
        assert index.read_text() == "custom content"

    def test_creates_default_config_files(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        assert (ops.vault_config.config_dir / "taim.yaml").exists()
        assert (ops.vault_config.config_dir / "providers.yaml").exists()
        assert (ops.vault_config.config_dir / "defaults.yaml").exists()

    def test_does_not_overwrite_existing_configs(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        config_path = ops.vault_config.config_dir / "taim.yaml"
        config_path.write_text("custom: true\n")
        ops.ensure_vault()
        assert config_path.read_text() == "custom: true\n"


class TestVaultPathValidation:
    def test_rejects_file_as_vault_path(self, tmp_path: Path) -> None:
        file_path = tmp_path / "not-a-dir"
        file_path.write_text("i am a file")
        with pytest.raises(VaultError, match="points to a file"):
            VaultOps(file_path)

    def test_accepts_nonexistent_path(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "new-vault")
        assert ops.vault_config.vault_root == (tmp_path / "new-vault").resolve()


class TestLoadRawYaml:
    def test_loads_valid_yaml(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        (ops.vault_config.config_dir / "test.yaml").write_text("key: value\n")
        result = ops.load_raw_yaml("test.yaml")
        assert result == {"key": "value"}

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        with pytest.raises(ConfigError, match="missing from the vault"):
            ops.load_raw_yaml("nonexistent.yaml")

    def test_raises_on_invalid_yaml(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        (ops.vault_config.config_dir / "bad.yaml").write_text(":\n  :\n  bad: [")
        with pytest.raises(ConfigError, match="syntax error"):
            ops.load_raw_yaml("bad.yaml")

    def test_returns_empty_dict_for_empty_file(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        (ops.vault_config.config_dir / "empty.yaml").write_text("")
        result = ops.load_raw_yaml("empty.yaml")
        assert result == {}


class TestLoadProductConfig:
    def test_loads_from_real_vault_configs(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        src = Path("/Users/reykz/repositorys/TAIM/taim-vault/config")
        shutil.copytree(src, vault / "config")
        ops = VaultOps(vault)
        ops.ensure_vault()
        config = ops.load_product_config()
        assert len(config.providers) > 0
        assert config.providers[0].name == "anthropic"
        assert "tier1_premium" in config.tiering
        assert config.conversation_verbosity == "normal"
        assert config.usd_to_eur_rate == 0.92
