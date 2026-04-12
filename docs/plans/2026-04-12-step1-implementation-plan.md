# Step 1: Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the TAIM backend foundation — config loading, vault init, SQLite schema, PromptLoader, FastAPI skeleton with health endpoint.

**Architecture:** Two-layer config (ENV + YAML), VaultOps for filesystem, aiosqlite for state, Jinja2-based PromptLoader, FastAPI with lifespan DI. All decisions documented in `docs/plans/2026-04-12-step1-foundation-design.md`.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, pydantic-settings, aiosqlite, Jinja2, structlog, PyYAML, pytest

---

## File Structure

All paths relative to project root `/Users/reykz/repositorys/TAIM/`.

### Files to Create

```
backend/src/taim/__init__.py          (modify — add __version__)
backend/src/taim/errors.py            (create — error hierarchy)
backend/src/taim/settings.py          (create — TaimSettings)
backend/src/taim/models/config.py     (create — all config Pydantic models)
backend/src/taim/brain/vault.py       (create — VaultOps)
backend/src/taim/brain/database.py    (create — SQLite init + schema)
backend/src/taim/brain/prompts.py     (create — PromptLoader)
backend/src/taim/brain/logging.py     (create — structlog configuration)
backend/src/taim/api/deps.py          (create — DI functions)
backend/src/taim/api/health.py        (create — health endpoint)
backend/src/taim/api/chat.py          (create — WebSocket stub)
backend/src/taim/main.py              (create — FastAPI app + lifespan)
tests/backend/conftest.py             (create — shared fixtures, built incrementally)
tests/backend/test_errors.py          (create)
tests/backend/test_settings.py        (create)
tests/backend/test_config.py          (create)
tests/backend/test_vault.py           (create)
tests/backend/test_database.py        (create)
tests/backend/test_prompts.py         (create)
tests/backend/test_health.py          (create)
tests/backend/test_main.py            (create)
```

### Files to Modify

```
backend/pyproject.toml                (add dependencies)
taim-vault/config/taim.yaml           (already corrected — host: localhost, usd_to_eur_rate)
```

### Dependency Graph

```
Task 1 (setup) → Task 2 (errors) → Task 3 (settings) → Task 4 (config models)
                                                              ↓
                   Task 5 (vault) ← ← ← ← ← ← ← ← ← ← ← ←┘
                   Task 6 (database) — parallel with Task 5
                   Task 7 (prompts) — parallel with Task 5
                        ↓
                   Task 8 (logging) → Task 9 (API) → Task 10 (main app) → Task 11 (verify)
```

---

## Task 1: Project Setup & Dependencies

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/src/taim/__init__.py`
- Create: `tests/backend/__init__.py`
- Create: `tests/backend/conftest.py`

- [ ] **Step 1: Update pyproject.toml with new dependencies**

```toml
[project]
name = "taim"
version = "0.1.0"
description = "TAIM — Team AI Manager. AI team orchestration through natural language."
readme = "README.md"
license = "Apache-2.0"
requires-python = ">=3.11"
authors = [
    { name = "Reyk Zepper" },
]
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "litellm>=1.40.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "typer[all]>=0.12.0",
    "rich>=13.7.0",
    "aiofiles>=24.1.0",
    "websockets>=13.0",
    "pyyaml>=6.0.1",
    "aiosqlite>=0.20.0",
    "jinja2>=3.1.0",
    "structlog>=24.1.0",
    "python-frontmatter>=1.1.0",
    "tiktoken>=0.7.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "pytest-mock>=3.14.0",
    "httpx>=0.27.0",
    "ruff>=0.5.0",
]

[project.scripts]
taim = "taim.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/taim"]

[tool.pytest.ini_options]
testpaths = ["../tests/backend"]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
```

- [ ] **Step 2: Set package version in `__init__.py`**

File: `backend/src/taim/__init__.py`
```python
"""TAIM — Team AI Manager."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create test directory with initial conftest**

File: `tests/backend/__init__.py` — empty file.

File: `tests/backend/conftest.py`
```python
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
```

- [ ] **Step 4: Install dependencies**

Run: `cd backend && uv sync --all-extras`
Expected: Dependencies install without errors, including new ones (jinja2, structlog, etc.)

- [ ] **Step 5: Verify pytest discovers test directory**

Run: `cd backend && uv run pytest --collect-only 2>&1 | head -5`
Expected: `no tests ran` or `collected 0 items` (no errors about missing directories)

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/src/taim/__init__.py tests/backend/
git commit -m "feat: add Step 1 dependencies and test infrastructure"
```

---

## Task 2: Error System

**Files:**
- Create: `backend/src/taim/errors.py`
- Create: `tests/backend/test_errors.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/backend/test_errors.py`
```python
"""Tests for the TAIM error hierarchy."""

from pathlib import Path

from taim.errors import (
    ConfigError,
    DatabaseError,
    PromptNotFoundError,
    PromptVariableError,
    TaimError,
    VaultError,
)


class TestTaimError:
    def test_has_user_message_and_detail(self) -> None:
        err = TaimError(user_message="Something went wrong.", detail="NullPointerException at line 42")
        assert err.user_message == "Something went wrong."
        assert err.detail == "NullPointerException at line 42"

    def test_detail_defaults_to_user_message(self) -> None:
        err = TaimError(user_message="Oops")
        assert err.detail == "Oops"

    def test_str_returns_detail(self) -> None:
        err = TaimError(user_message="Friendly", detail="Technical")
        assert str(err) == "Technical"

    def test_is_exception(self) -> None:
        assert issubclass(TaimError, Exception)


class TestSubclasses:
    def test_vault_error_is_taim_error(self) -> None:
        err = VaultError(user_message="Vault broken")
        assert isinstance(err, TaimError)

    def test_config_error_is_taim_error(self) -> None:
        err = ConfigError(user_message="Config broken")
        assert isinstance(err, TaimError)

    def test_database_error_is_taim_error(self) -> None:
        err = DatabaseError(user_message="DB broken")
        assert isinstance(err, TaimError)


class TestPromptNotFoundError:
    def test_builds_messages_from_args(self) -> None:
        err = PromptNotFoundError("intent-classify", Path("/vault/prompts/intent-classify.yaml"))
        assert "intent-classify" in err.user_message
        assert "missing from the vault" in err.user_message
        assert "/vault/prompts/intent-classify.yaml" in err.detail
        assert isinstance(err, TaimError)


class TestPromptVariableError:
    def test_builds_messages_from_args(self) -> None:
        err = PromptVariableError("intent-classify", "user_message")
        assert "internal configuration error" in err.user_message.lower() or "check the logs" in err.user_message.lower()
        assert "user_message" in err.detail
        assert "intent-classify" in err.detail
        assert isinstance(err, TaimError)
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && uv run pytest ../tests/backend/test_errors.py -v`
Expected: `ModuleNotFoundError: No module named 'taim.errors'`

- [ ] **Step 3: Implement errors.py**

File: `backend/src/taim/errors.py`
```python
"""TAIM error hierarchy with dual personality: user-friendly + developer-detailed."""

from __future__ import annotations

from pathlib import Path


class TaimError(Exception):
    """Base error with user-facing and developer-facing messages."""

    def __init__(self, user_message: str, detail: str | None = None) -> None:
        self.user_message = user_message
        self.detail = detail or user_message
        super().__init__(self.detail)


class VaultError(TaimError):
    """Vault filesystem errors."""


class ConfigError(TaimError):
    """Configuration loading/validation errors."""


class DatabaseError(TaimError):
    """SQLite errors."""


class PromptNotFoundError(TaimError):
    """Requested prompt YAML file doesn't exist."""

    def __init__(self, prompt_name: str, path: Path) -> None:
        super().__init__(
            user_message=f"A required prompt template '{prompt_name}' is missing from the vault.",
            detail=f"Prompt file not found: {path}",
        )


class PromptVariableError(TaimError):
    """A template variable was required but not provided."""

    def __init__(self, prompt_name: str, variable: str) -> None:
        super().__init__(
            user_message="An internal configuration error occurred. Please check the logs.",
            detail=f"Missing variable '{variable}' in prompt '{prompt_name}'",
        )
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd backend && uv run pytest ../tests/backend/test_errors.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/errors.py tests/backend/test_errors.py
git commit -m "feat: add TAIM error hierarchy with dual personality messages"
```

---

## Task 3: Settings Module

**Files:**
- Create: `backend/src/taim/settings.py`
- Create: `tests/backend/test_settings.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/backend/test_settings.py`
```python
"""Tests for TaimSettings (ENV-based infrastructure config)."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.settings import TaimSettings


class TestDefaults:
    def test_default_vault_path(self) -> None:
        s = TaimSettings()
        assert s.vault_path == Path("./taim-vault")

    def test_default_env(self) -> None:
        s = TaimSettings()
        assert s.env == "development"

    def test_default_log_level(self) -> None:
        s = TaimSettings()
        assert s.log_level == "INFO"

    def test_default_log_format(self) -> None:
        s = TaimSettings()
        assert s.log_format == "dev"


class TestEnvOverride:
    def test_vault_path_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TAIM_VAULT_PATH", "/custom/vault")
        s = TaimSettings()
        assert s.vault_path == Path("/custom/vault")

    def test_env_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TAIM_ENV", "production")
        s = TaimSettings()
        assert s.env == "production"

    def test_log_level_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TAIM_LOG_LEVEL", "DEBUG")
        s = TaimSettings()
        assert s.log_level == "DEBUG"

    def test_log_format_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TAIM_LOG_FORMAT", "json")
        s = TaimSettings()
        assert s.log_format == "json"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && uv run pytest ../tests/backend/test_settings.py -v`
Expected: `ModuleNotFoundError: No module named 'taim.settings'`

- [ ] **Step 3: Implement settings.py**

File: `backend/src/taim/settings.py`
```python
"""TaimSettings — ENV-only infrastructure settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class TaimSettings(BaseSettings):
    """Pure infrastructure settings loaded from ENV + .env file.

    These have no YAML counterpart. Server host/port/CORS live in taim.yaml.
    """

    model_config = SettingsConfigDict(
        env_prefix="TAIM_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    vault_path: Path = Path("./taim-vault")
    env: str = "development"
    log_level: str = "INFO"
    log_format: str = "dev"
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd backend && uv run pytest ../tests/backend/test_settings.py -v`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/settings.py tests/backend/test_settings.py
git commit -m "feat: add TaimSettings for ENV-based infrastructure config"
```

---

## Task 4: Config Models

**Files:**
- Create: `backend/src/taim/models/config.py`
- Create: `tests/backend/test_config.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/backend/test_config.py`
```python
"""Tests for Pydantic config models."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from taim.models.config import (
    ProductConfig,
    ProviderConfig,
    ServerConfig,
    SystemConfig,
    TierConfig,
    VaultConfig,
)
from taim.settings import TaimSettings


class TestVaultConfig:
    def test_from_root_resolves_all_paths(self, tmp_path: Path) -> None:
        vc = VaultConfig.from_root(tmp_path / "vault")
        assert vc.vault_root == (tmp_path / "vault").resolve()
        assert vc.config_dir == vc.vault_root / "config"
        assert vc.agents_dir == vc.vault_root / "agents"
        assert vc.prompts_dir == vc.vault_root / "system" / "prompts"
        assert vc.db_path == vc.vault_root / "system" / "state" / "taim.db"

    def test_paths_are_absolute(self) -> None:
        vc = VaultConfig.from_root(Path("./relative"))
        assert vc.vault_root.is_absolute()


class TestServerConfig:
    def test_defaults(self) -> None:
        sc = ServerConfig()
        assert sc.host == "localhost"
        assert sc.port == 8000
        assert "http://localhost:5173" in sc.cors_origins

    def test_from_yaml_uses_yaml_values(self) -> None:
        sc = ServerConfig.from_yaml_and_env({"host": "0.0.0.0", "port": 9000})
        assert sc.host == "0.0.0.0"
        assert sc.port == 9000

    def test_env_overrides_yaml(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TAIM_HOST", "192.168.1.1")
        monkeypatch.setenv("TAIM_PORT", "3000")
        sc = ServerConfig.from_yaml_and_env({"host": "0.0.0.0", "port": 9000})
        assert sc.host == "192.168.1.1"
        assert sc.port == 3000

    def test_cors_from_yaml(self) -> None:
        sc = ServerConfig.from_yaml_and_env(
            {"cors_origins": ["http://example.com"]}
        )
        assert sc.cors_origins == ["http://example.com"]

    def test_cors_env_overrides_yaml(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TAIM_CORS_ORIGINS", "http://a.com,http://b.com")
        sc = ServerConfig.from_yaml_and_env(
            {"cors_origins": ["http://example.com"]}
        )
        assert sc.cors_origins == ["http://a.com", "http://b.com"]

    def test_falls_back_to_defaults_when_yaml_empty(self) -> None:
        sc = ServerConfig.from_yaml_and_env({})
        assert sc.host == "localhost"
        assert sc.port == 8000


class TestProviderConfig:
    def test_minimal(self) -> None:
        pc = ProviderConfig(name="anthropic", models=["claude-sonnet-4-20250514"])
        assert pc.name == "anthropic"
        assert pc.priority == 1
        assert pc.monthly_budget_eur is None

    def test_full(self) -> None:
        pc = ProviderConfig(
            name="openai",
            api_key_env="OPENAI_API_KEY",
            models=["gpt-4o"],
            priority=2,
            monthly_budget_eur=50.0,
        )
        assert pc.api_key_env == "OPENAI_API_KEY"
        assert pc.monthly_budget_eur == 50.0


class TestProductConfig:
    def test_defaults(self) -> None:
        pc = ProductConfig(
            providers=[],
            tiering={},
            defaults={},
        )
        assert pc.conversation_verbosity == "normal"
        assert pc.heartbeat_interval == 30
        assert pc.usd_to_eur_rate == 0.92


class TestSystemConfig:
    def test_composes_all_layers(self, tmp_path: Path) -> None:
        sc = SystemConfig(
            server=ServerConfig(),
            vault=VaultConfig.from_root(tmp_path),
            product=ProductConfig(providers=[], tiering={}, defaults={}),
            settings=TaimSettings(),
        )
        assert sc.server.host == "localhost"
        assert sc.vault.vault_root == tmp_path.resolve()
        assert sc.product.conversation_verbosity == "normal"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && uv run pytest ../tests/backend/test_config.py -v`
Expected: `ModuleNotFoundError: No module named 'taim.models.config'`

- [ ] **Step 3: Implement models/config.py**

File: `backend/src/taim/models/config.py`
```python
"""Pydantic models for TAIM configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from taim.settings import TaimSettings

_DEFAULT_CORS = ["http://localhost:5173", "http://localhost:3000"]


class ServerConfig(BaseModel):
    """Server settings — from taim.yaml, overridable by ENV."""

    host: str = "localhost"
    port: int = 8000
    cors_origins: list[str] = _DEFAULT_CORS.copy()

    @classmethod
    def from_yaml_and_env(cls, yaml_server: dict) -> ServerConfig:
        """Build from YAML baseline with ENV overrides."""
        cors_env = os.environ.get("TAIM_CORS_ORIGINS")
        return cls(
            host=os.environ.get("TAIM_HOST") or yaml_server.get("host", "localhost"),
            port=int(os.environ.get("TAIM_PORT") or yaml_server.get("port", 8000)),
            cors_origins=(
                [o.strip() for o in cors_env.split(",") if o.strip()]
                if cors_env
                else yaml_server.get("cors_origins", _DEFAULT_CORS.copy())
            ),
        )


class ProviderConfig(BaseModel):
    """LLM provider definition."""

    name: str
    api_key_env: str = ""
    host: str | None = None
    models: list[str]
    priority: int = 1
    monthly_budget_eur: float | None = None


class TierConfig(BaseModel):
    """Model tier definition."""

    description: str
    models: list[str]


class ProductConfig(BaseModel):
    """Product behavior — loaded from vault YAML files."""

    providers: list[ProviderConfig]
    tiering: dict[str, TierConfig]
    defaults: dict[str, Any]
    conversation_verbosity: str = "normal"
    conversation_language: str = "auto"
    heartbeat_interval: int = 30
    agent_timeout: int = 120
    default_iterations: int = 2
    usd_to_eur_rate: float = 0.92


class VaultConfig(BaseModel):
    """Resolved vault paths — computed once at startup."""

    vault_root: Path
    config_dir: Path
    agents_dir: Path
    teams_dir: Path
    rules_dir: Path
    shared_dir: Path
    users_dir: Path
    prompts_dir: Path
    state_dir: Path
    db_path: Path

    @classmethod
    def from_root(cls, vault_root: Path) -> VaultConfig:
        """Compute all sub-paths from vault root. Resolves to absolute."""
        root = vault_root.resolve()
        return cls(
            vault_root=root,
            config_dir=root / "config",
            agents_dir=root / "agents",
            teams_dir=root / "teams",
            rules_dir=root / "rules",
            shared_dir=root / "shared",
            users_dir=root / "users",
            prompts_dir=root / "system" / "prompts",
            state_dir=root / "system" / "state",
            db_path=root / "system" / "state" / "taim.db",
        )


class SystemConfig(BaseModel):
    """Complete runtime config — composed at startup, injected via DI."""

    model_config = {"arbitrary_types_allowed": True}

    server: ServerConfig
    vault: VaultConfig
    product: ProductConfig
    settings: TaimSettings
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd backend && uv run pytest ../tests/backend/test_config.py -v`
Expected: `12 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/models/config.py tests/backend/test_config.py
git commit -m "feat: add Pydantic config models with YAML+ENV precedence"
```

---

## Task 5: VaultOps

**Files:**
- Create: `backend/src/taim/brain/vault.py`
- Create: `tests/backend/test_vault.py`
- Modify: `tests/backend/conftest.py` (add `tmp_vault` fixture)

- [ ] **Step 1: Write the failing tests**

File: `tests/backend/test_vault.py`
```python
"""Tests for VaultOps — vault initialization, config loading, error handling."""

from __future__ import annotations

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
        ops.ensure_vault()  # Second call should not raise
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
    def test_loads_from_existing_vault(self, tmp_path: Path) -> None:
        """Use the real taim-vault configs to test loading."""
        import shutil
        vault = tmp_path / "vault"
        vault.mkdir()
        # Copy real configs
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
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && uv run pytest ../tests/backend/test_vault.py -v`
Expected: `ModuleNotFoundError: No module named 'taim.brain.vault'`

- [ ] **Step 3: Implement brain/vault.py**

File: `backend/src/taim/brain/vault.py`
```python
"""VaultOps — TAIM Vault filesystem operations."""

from __future__ import annotations

from pathlib import Path

import yaml

from taim.errors import ConfigError, VaultError
from taim.models.config import (
    ProductConfig,
    ProviderConfig,
    TierConfig,
    VaultConfig,
)

_DEFAULT_TAIM_YAML = """\
# TAIM — Main Configuration
version: "0.1.0"

server:
  host: "localhost"
  port: 8000
  cors_origins:
    - "http://localhost:5173"
    - "http://localhost:3000"

conversation:
  verbosity: normal
  language: auto

orchestrator:
  heartbeat_interval: 30
  agent_timeout: 120
  default_iterations: 2

tracking:
  currency: "EUR"
  usd_to_eur_rate: 0.92
"""

_DEFAULT_PROVIDERS_YAML = """\
# TAIM — LLM Provider Configuration
# API keys are loaded from environment variables (never stored here).
providers: []

tiering:
  tier1_premium:
    description: "Complex reasoning, architecture, strategy"
    models: []
  tier2_standard:
    description: "Code generation, text processing, analysis"
    models: []
  tier3_economy:
    description: "Classification, formatting, routing"
    models: []
"""

_DEFAULT_DEFAULTS_YAML = """\
# TAIM — Smart Defaults
team:
  time_budget: "2h"
  token_budget: 500000
  iteration_rounds: 2
  on_limit_reached: graceful_stop

agent:
  max_iterations: 10
  default_tier: tier2_standard
  approval_gates:
    - file_deletion
    - external_communication
    - budget_exceeded

output:
  format: markdown
  language: auto

costs:
  display_currency: true
  warning_threshold: 10.00
"""


class VaultOps:
    """Filesystem operations for the TAIM Vault."""

    def __init__(self, vault_path: Path) -> None:
        resolved = vault_path.resolve()
        if resolved.exists() and not resolved.is_dir():
            raise VaultError(
                user_message=f"The vault path '{vault_path}' points to a file, not a directory.",
                detail=f"Vault path {resolved} exists but is not a directory",
            )
        self.vault_config = VaultConfig.from_root(resolved)

    def ensure_vault(self) -> None:
        """Create vault directory structure if missing. Idempotent."""
        directories = [
            self.vault_config.config_dir,
            self.vault_config.agents_dir,
            self.vault_config.teams_dir,
            self.vault_config.rules_dir / "compliance",
            self.vault_config.rules_dir / "behavior",
            self.vault_config.shared_dir,
            self.vault_config.users_dir / "default" / "memory",
            self.vault_config.prompts_dir,
            self.vault_config.state_dir,
        ]
        try:
            for d in directories:
                d.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise VaultError(
                user_message=(
                    "TAIM can't create its data directory. "
                    f"Please check file permissions for '{self.vault_config.vault_root}'."
                ),
                detail=f"PermissionError creating directory: {e}",
            ) from e

        # Default INDEX.md
        index_path = self.vault_config.users_dir / "default" / "INDEX.md"
        if not index_path.exists():
            index_path.write_text("# Memory Index\n\n<!-- Entries added automatically -->\n")

        # Default config files (never overwrite existing)
        self._ensure_default_configs()

    def load_raw_yaml(self, filename: str) -> dict:
        """Load a YAML file from the config directory."""
        path = self.vault_config.config_dir / filename
        if not path.exists():
            raise ConfigError(
                user_message=f"Configuration file '{filename}' is missing from the vault.",
                detail=f"Expected config file not found: {path}",
            )
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise ConfigError(
                user_message=(
                    f"Configuration file '{filename}' has a syntax error. "
                    "Please check the file format."
                ),
                detail=f"YAML parse error in {path}: {e}",
            ) from e

    def load_product_config(self) -> ProductConfig:
        """Load and validate all YAML config files into ProductConfig."""
        taim_cfg = self.load_raw_yaml("taim.yaml")
        providers_cfg = self.load_raw_yaml("providers.yaml")
        defaults_cfg = self.load_raw_yaml("defaults.yaml")

        providers = [
            ProviderConfig(**p) for p in providers_cfg.get("providers", [])
        ]
        tiering = {
            name: TierConfig(**tier)
            for name, tier in providers_cfg.get("tiering", {}).items()
        }

        conversation = taim_cfg.get("conversation", {})
        orchestrator = taim_cfg.get("orchestrator", {})
        tracking = taim_cfg.get("tracking", {})

        return ProductConfig(
            providers=providers,
            tiering=tiering,
            defaults=defaults_cfg,
            conversation_verbosity=conversation.get("verbosity", "normal"),
            conversation_language=conversation.get("language", "auto"),
            heartbeat_interval=orchestrator.get("heartbeat_interval", 30),
            agent_timeout=orchestrator.get("agent_timeout", 120),
            default_iterations=orchestrator.get("default_iterations", 2),
            usd_to_eur_rate=tracking.get("usd_to_eur_rate", 0.92),
        )

    def _ensure_default_configs(self) -> None:
        """Write default config files only if they don't exist."""
        defaults = {
            "taim.yaml": _DEFAULT_TAIM_YAML,
            "providers.yaml": _DEFAULT_PROVIDERS_YAML,
            "defaults.yaml": _DEFAULT_DEFAULTS_YAML,
        }
        for filename, content in defaults.items():
            path = self.vault_config.config_dir / filename
            if not path.exists():
                path.write_text(content, encoding="utf-8")
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd backend && uv run pytest ../tests/backend/test_vault.py -v`
Expected: `12 passed`

- [ ] **Step 5: Add `tmp_vault` fixture to conftest**

Append to `tests/backend/conftest.py`:
```python
from taim.brain.vault import VaultOps


@pytest.fixture
def tmp_vault(tmp_path: Path) -> Path:
    """Create a temporary vault with full structure and default configs."""
    vault = tmp_path / "taim-vault"
    ops = VaultOps(vault)
    ops.ensure_vault()
    return vault
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/taim/brain/vault.py tests/backend/test_vault.py tests/backend/conftest.py
git commit -m "feat: add VaultOps with idempotent init, YAML loading, error handling"
```

---

## Task 6: Database Module

**Files:**
- Create: `backend/src/taim/brain/database.py`
- Create: `tests/backend/test_database.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/backend/test_database.py`
```python
"""Tests for SQLite database initialization and schema management."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from taim.brain.database import SCHEMA_VERSION, init_database


class TestDatabaseInit:
    async def test_creates_db_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "state" / "taim.db"
        db = await init_database(db_path)
        try:
            assert db_path.exists()
        finally:
            await db.close()

    async def test_creates_parent_directories(self, tmp_path: Path) -> None:
        db_path = tmp_path / "deep" / "nested" / "taim.db"
        db = await init_database(db_path)
        try:
            assert db_path.parent.is_dir()
        finally:
            await db.close()

    async def test_wal_mode_enabled(self, tmp_path: Path) -> None:
        db = await init_database(tmp_path / "taim.db")
        try:
            async with db.execute("PRAGMA journal_mode") as cursor:
                row = await cursor.fetchone()
                assert row[0] == "wal"
        finally:
            await db.close()

    async def test_foreign_keys_enabled(self, tmp_path: Path) -> None:
        db = await init_database(tmp_path / "taim.db")
        try:
            async with db.execute("PRAGMA foreign_keys") as cursor:
                row = await cursor.fetchone()
                assert row[0] == 1
        finally:
            await db.close()


class TestSchema:
    async def test_all_tables_created(self, tmp_path: Path) -> None:
        db = await init_database(tmp_path / "taim.db")
        try:
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ) as cursor:
                tables = [row[0] for row in await cursor.fetchall()]
            assert "schema_version" in tables
            assert "token_tracking" in tables
            assert "task_state" in tables
            assert "session_state" in tables
            assert "agent_runs" in tables
        finally:
            await db.close()

    async def test_schema_version_recorded(self, tmp_path: Path) -> None:
        db = await init_database(tmp_path / "taim.db")
        try:
            async with db.execute("SELECT MAX(version) FROM schema_version") as cursor:
                row = await cursor.fetchone()
                assert row[0] == SCHEMA_VERSION
        finally:
            await db.close()

    async def test_indexes_created(self, tmp_path: Path) -> None:
        db = await init_database(tmp_path / "taim.db")
        try:
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            ) as cursor:
                indexes = [row[0] for row in await cursor.fetchall()]
            assert "idx_token_tracking_task" in indexes
            assert "idx_token_tracking_session" in indexes
            assert "idx_agent_runs_task" in indexes
        finally:
            await db.close()


class TestMigrationIdempotency:
    async def test_second_init_does_not_fail(self, tmp_path: Path) -> None:
        db_path = tmp_path / "taim.db"
        db1 = await init_database(db_path)
        await db1.close()
        db2 = await init_database(db_path)
        try:
            async with db2.execute("SELECT MAX(version) FROM schema_version") as cursor:
                row = await cursor.fetchone()
                assert row[0] == SCHEMA_VERSION
        finally:
            await db2.close()
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && uv run pytest ../tests/backend/test_database.py -v`
Expected: `ModuleNotFoundError: No module named 'taim.brain.database'`

- [ ] **Step 3: Implement brain/database.py**

File: `backend/src/taim/brain/database.py`
```python
"""SQLite database initialization and schema management."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

SCHEMA_VERSION = 1

_SCHEMA_V1 = """\
CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS token_tracking (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id           TEXT UNIQUE NOT NULL,
    agent_run_id      TEXT,
    task_id           TEXT,
    session_id        TEXT,
    model             TEXT NOT NULL,
    provider          TEXT NOT NULL,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd          REAL NOT NULL DEFAULT 0.0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS task_state (
    task_id        TEXT PRIMARY KEY,
    team_id        TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending',
    objective      TEXT,
    agent_states   TEXT,
    token_total    INTEGER DEFAULT 0,
    cost_total_eur REAL DEFAULT 0.0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at   TEXT
);

CREATE TABLE IF NOT EXISTS session_state (
    session_id      TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL DEFAULT 'default',
    messages        TEXT,
    session_summary TEXT,
    has_summary     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_runs (
    run_id             TEXT PRIMARY KEY,
    agent_name         TEXT NOT NULL,
    task_id            TEXT NOT NULL,
    team_id            TEXT NOT NULL,
    session_id         TEXT,
    state_history      TEXT,
    final_state        TEXT NOT NULL,
    prompt_tokens      INTEGER DEFAULT 0,
    completion_tokens  INTEGER DEFAULT 0,
    cost_eur           REAL DEFAULT 0.0,
    provider           TEXT,
    model_used         TEXT,
    failover_occurred  INTEGER NOT NULL DEFAULT 0,
    started_at         TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_token_tracking_task ON token_tracking(task_id);
CREATE INDEX IF NOT EXISTS idx_token_tracking_session ON token_tracking(session_id);
CREATE INDEX IF NOT EXISTS idx_token_tracking_agent_run ON token_tracking(agent_run_id);
CREATE INDEX IF NOT EXISTS idx_token_tracking_created ON token_tracking(created_at);
CREATE INDEX IF NOT EXISTS idx_task_state_team ON task_state(team_id);
CREATE INDEX IF NOT EXISTS idx_task_state_status ON task_state(status);
CREATE INDEX IF NOT EXISTS idx_session_state_user ON session_state(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_task ON agent_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_team ON agent_runs(team_id);
"""

_MIGRATIONS = {
    1: _SCHEMA_V1,
}


async def init_database(db_path: Path) -> aiosqlite.Connection:
    """Initialize SQLite database with schema. Idempotent."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(db_path))

    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")

    current = await _get_schema_version(db)
    if current < SCHEMA_VERSION:
        await _apply_migrations(db, current)

    return db


async def _get_schema_version(db: aiosqlite.Connection) -> int:
    """Returns 0 if no schema exists yet."""
    try:
        async with db.execute("SELECT MAX(version) FROM schema_version") as cursor:
            row = await cursor.fetchone()
            return row[0] if row and row[0] else 0
    except aiosqlite.OperationalError:
        return 0


async def _apply_migrations(db: aiosqlite.Connection, from_version: int) -> None:
    """Apply all migrations from from_version to SCHEMA_VERSION."""
    for version in range(from_version + 1, SCHEMA_VERSION + 1):
        await db.executescript(_MIGRATIONS[version])
        await db.execute(
            "INSERT INTO schema_version (version) VALUES (?)", (version,)
        )
        await db.commit()
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd backend && uv run pytest ../tests/backend/test_database.py -v`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/brain/database.py tests/backend/test_database.py
git commit -m "feat: add SQLite schema init with WAL mode and versioned migrations"
```

---

## Task 7: PromptLoader

**Files:**
- Create: `backend/src/taim/brain/prompts.py`
- Create: `tests/backend/test_prompts.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/backend/test_prompts.py`
```python
"""Tests for PromptLoader with Jinja2 templating."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.prompts import PromptLoader
from taim.errors import PromptNotFoundError, PromptVariableError


@pytest.fixture
def prompts_dir(tmp_path: Path) -> Path:
    d = tmp_path / "prompts"
    d.mkdir()
    return d


@pytest.fixture
def loader(prompts_dir: Path) -> PromptLoader:
    return PromptLoader(prompts_dir)


def _write_prompt(prompts_dir: Path, name: str, template: str, **extra: str) -> None:
    """Helper to write a prompt YAML file."""
    import yaml
    data = {"name": name, "version": 1, "template": template, **extra}
    (prompts_dir / f"{name}.yaml").write_text(yaml.dump(data))


class TestLoad:
    def test_loads_template_without_variables(
        self, loader: PromptLoader, prompts_dir: Path
    ) -> None:
        _write_prompt(prompts_dir, "simple", "Hello world")
        result = loader.load("simple")
        assert result == "Hello world"

    def test_substitutes_variables(
        self, loader: PromptLoader, prompts_dir: Path
    ) -> None:
        _write_prompt(prompts_dir, "greeting", "Hello {{ name }}, you are {{ role }}")
        result = loader.load("greeting", {"name": "TAIM", "role": "manager"})
        assert result == "Hello TAIM, you are manager"

    def test_json_braces_not_interpreted(
        self, loader: PromptLoader, prompts_dir: Path
    ) -> None:
        _write_prompt(
            prompts_dir, "json-output",
            'Output: {"category": "{{ cat }}", "score": 0.9}'
        )
        result = loader.load("json-output", {"cat": "task"})
        assert result == 'Output: {"category": "task", "score": 0.9}'


class TestErrors:
    def test_missing_file_raises_prompt_not_found(self, loader: PromptLoader) -> None:
        with pytest.raises(PromptNotFoundError):
            loader.load("nonexistent")

    def test_missing_variable_raises_prompt_variable_error(
        self, loader: PromptLoader, prompts_dir: Path
    ) -> None:
        _write_prompt(prompts_dir, "needs-var", "Hello {{ name }}")
        with pytest.raises(PromptVariableError):
            loader.load("needs-var", {"wrong_key": "value"})

    def test_empty_template_raises(
        self, loader: PromptLoader, prompts_dir: Path
    ) -> None:
        import yaml
        (prompts_dir / "empty.yaml").write_text(yaml.dump({"name": "empty", "template": ""}))
        with pytest.raises(PromptNotFoundError):
            loader.load("empty")


class TestCache:
    def test_caches_after_first_load(
        self, loader: PromptLoader, prompts_dir: Path
    ) -> None:
        _write_prompt(prompts_dir, "cached", "original")
        assert loader.load("cached") == "original"
        # Modify file content but NOT mtime (same second)
        # Cache should still return original
        assert loader.load("cached") == "original"

    def test_invalidates_on_file_change(
        self, loader: PromptLoader, prompts_dir: Path
    ) -> None:
        _write_prompt(prompts_dir, "changing", "v1")
        assert loader.load("changing") == "v1"
        # Rewrite with new mtime
        import time
        time.sleep(0.05)  # Ensure mtime differs
        _write_prompt(prompts_dir, "changing", "v2")
        assert loader.load("changing") == "v2"


class TestGetMetadata:
    def test_returns_metadata_without_template(
        self, loader: PromptLoader, prompts_dir: Path
    ) -> None:
        _write_prompt(
            prompts_dir, "meta", "template body",
            description="A test prompt", model_tier="tier3_economy"
        )
        meta = loader.get_metadata("meta")
        assert meta["name"] == "meta"
        assert meta["description"] == "A test prompt"
        assert meta["model_tier"] == "tier3_economy"
        assert "template" not in meta
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && uv run pytest ../tests/backend/test_prompts.py -v`
Expected: `ModuleNotFoundError: No module named 'taim.brain.prompts'`

- [ ] **Step 3: Implement brain/prompts.py**

File: `backend/src/taim/brain/prompts.py`
```python
"""PromptLoader — loads prompt templates from vault YAML with Jinja2 rendering."""

from __future__ import annotations

from pathlib import Path

import yaml
from jinja2 import StrictUndefined, UndefinedError
from jinja2.sandbox import SandboxedEnvironment

from taim.errors import PromptNotFoundError, PromptVariableError


class PromptLoader:
    """Loads prompt templates from vault YAML files with Jinja2 rendering.

    Uses SandboxedEnvironment for defense-in-depth against non-string
    template variables that may be introduced in later steps.
    """

    def __init__(self, prompts_dir: Path) -> None:
        self._dir = prompts_dir
        self._cache: dict[str, tuple[float, dict]] = {}
        self._jinja = SandboxedEnvironment(undefined=StrictUndefined)

    def load(self, prompt_name: str, variables: dict[str, str] | None = None) -> str:
        """Load a prompt, substitute variables, return rendered string."""
        prompt_data = self._load_cached(prompt_name)
        template_str = prompt_data.get("template", "")

        if not template_str:
            raise PromptNotFoundError(prompt_name, self._dir / f"{prompt_name}.yaml")

        if variables:
            try:
                template = self._jinja.from_string(template_str)
                return template.render(variables)
            except UndefinedError as e:
                raise PromptVariableError(prompt_name, str(e)) from e

        return template_str

    def get_metadata(self, prompt_name: str) -> dict:
        """Return prompt metadata (name, description, model_tier, etc.) without template."""
        data = self._load_cached(prompt_name)
        return {k: v for k, v in data.items() if k != "template"}

    def _load_cached(self, prompt_name: str) -> dict:
        """Load prompt data with mtime-based cache invalidation."""
        path = self._dir / f"{prompt_name}.yaml"
        if not path.exists():
            raise PromptNotFoundError(prompt_name, path)

        mtime = path.stat().st_mtime
        if prompt_name in self._cache and self._cache[prompt_name][0] == mtime:
            return self._cache[prompt_name][1]

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self._cache[prompt_name] = (mtime, data)
        return data
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd backend && uv run pytest ../tests/backend/test_prompts.py -v`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/brain/prompts.py tests/backend/test_prompts.py
git commit -m "feat: add PromptLoader with Jinja2 sandboxed rendering and mtime cache"
```

---

## Task 8: Structured Logging

**Files:**
- Create: `backend/src/taim/brain/logging.py`

No separate test file — logging is tested via integration in Task 10.

- [ ] **Step 1: Implement logging.py**

File: `backend/src/taim/brain/logging.py`
```python
"""Structured logging configuration for TAIM."""

from __future__ import annotations

import logging

import structlog


def configure_logging(log_level: str = "INFO", log_format: str = "dev") -> None:
    """Configure structlog with dev (pretty) or json (structured) output."""
    shared_processors: list[structlog.types.Processor] = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.contextvars.merge_contextvars,
    ]

    if log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
    )
```

- [ ] **Step 2: Verify import works**

Run: `cd backend && uv run python -c "from taim.brain.logging import configure_logging; configure_logging(); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/taim/brain/logging.py
git commit -m "feat: add structured logging with dev/json output modes"
```

---

## Task 9: API Layer

**Files:**
- Create: `backend/src/taim/api/deps.py`
- Create: `backend/src/taim/api/health.py`
- Create: `backend/src/taim/api/chat.py`
- Create: `tests/backend/test_health.py`

- [ ] **Step 1: Implement api/deps.py**

File: `backend/src/taim/api/deps.py`
```python
"""FastAPI dependency injection functions."""

from __future__ import annotations

import aiosqlite
from fastapi import Request

from taim.brain.prompts import PromptLoader
from taim.models.config import SystemConfig


def get_config(request: Request) -> SystemConfig:
    """Inject the SystemConfig singleton."""
    return request.app.state.config


def get_db(request: Request) -> aiosqlite.Connection:
    """Inject the SQLite database connection."""
    return request.app.state.db


def get_prompt_loader(request: Request) -> PromptLoader:
    """Inject the PromptLoader singleton."""
    return request.app.state.prompt_loader
```

- [ ] **Step 2: Implement api/health.py**

File: `backend/src/taim/api/health.py`
```python
"""Health check endpoint."""

from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends

from taim.api.deps import get_config, get_db
from taim.models.config import SystemConfig

router = APIRouter()


@router.get("/health")
async def health(
    config: SystemConfig = Depends(get_config),
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    """Health check — reports vault, DB, and provider status."""
    provider_names = [p.name for p in config.product.providers]
    vault_ok = config.vault.vault_root.is_dir()

    try:
        async with db.execute("SELECT 1") as cursor:
            await cursor.fetchone()
        db_ok = True
    except Exception:
        db_ok = False

    all_ok = vault_ok and db_ok
    return {
        "status": "ok" if all_ok else "degraded",
        "vault_ok": vault_ok,
        "db_ok": db_ok,
        "providers": provider_names,
        "version": "0.1.0",
    }
```

- [ ] **Step 3: Implement api/chat.py (WebSocket stub)**

File: `backend/src/taim/api/chat.py`
```python
"""WebSocket chat endpoint — stub for Step 1."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """WebSocket stub — echoes connection confirmation. Full chat in Step 3."""
    await websocket.accept()
    try:
        while True:
            await websocket.receive_json()
            await websocket.send_json({
                "type": "system",
                "content": f"Connected to session {session_id}. Full chat in Step 3.",
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
    except WebSocketDisconnect:
        pass
```

- [ ] **Step 4: Write health endpoint tests**

File: `tests/backend/test_health.py`
```python
"""Tests for the health check endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from taim.brain.database import init_database
from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.models.config import ProductConfig, ServerConfig, SystemConfig, VaultConfig
from taim.settings import TaimSettings


def _build_test_app(vault_path: Path) -> "FastAPI":
    """Build a minimal FastAPI app with real dependencies for testing."""
    from fastapi import FastAPI

    from taim.api.health import router as health_router

    app = FastAPI()
    app.include_router(health_router)
    return app


@pytest.fixture
async def configured_app(tmp_vault: Path):
    """Create a FastAPI app with all state configured."""
    from fastapi import FastAPI

    from taim.api.health import router as health_router

    app = FastAPI()
    app.include_router(health_router)

    ops = VaultOps(tmp_vault)
    config = ops.load_product_config()
    taim_yaml = ops.load_raw_yaml("taim.yaml")

    app.state.config = SystemConfig(
        server=ServerConfig.from_yaml_and_env(taim_yaml.get("server", {})),
        vault=ops.vault_config,
        product=config,
        settings=TaimSettings(vault_path=tmp_vault),
    )
    app.state.db = await init_database(ops.vault_config.db_path)
    app.state.prompt_loader = PromptLoader(ops.vault_config.prompts_dir)

    yield app

    await app.state.db.close()


class TestHealthEndpoint:
    async def test_returns_ok(self, configured_app) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=configured_app), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["vault_ok"] is True
        assert data["db_ok"] is True
        assert data["version"] == "0.1.0"

    async def test_lists_providers(self, configured_app) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=configured_app), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
        data = resp.json()
        assert isinstance(data["providers"], list)
```

- [ ] **Step 5: Run tests — expect PASS**

Run: `cd backend && uv run pytest ../tests/backend/test_health.py -v`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/src/taim/api/deps.py backend/src/taim/api/health.py backend/src/taim/api/chat.py tests/backend/test_health.py
git commit -m "feat: add health endpoint with DB check and WebSocket stub"
```

---

## Task 10: Main Application

**Files:**
- Create: `backend/src/taim/main.py`
- Create: `tests/backend/test_main.py`

- [ ] **Step 1: Implement main.py**

File: `backend/src/taim/main.py`
```python
"""TAIM FastAPI application — entry point."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import structlog
import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from taim.api.chat import router as chat_router
from taim.api.health import router as health_router
from taim.brain.database import init_database
from taim.brain.logging import configure_logging
from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.models.config import ServerConfig, SystemConfig
from taim.settings import TaimSettings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: init vault, load config, init DB, init PromptLoader."""
    settings = TaimSettings()
    configure_logging(settings.log_level, settings.log_format)

    vault_ops = VaultOps(settings.vault_path)
    vault_ops.ensure_vault()

    taim_yaml = vault_ops.load_raw_yaml("taim.yaml")
    product_config = vault_ops.load_product_config()
    server_config = ServerConfig.from_yaml_and_env(taim_yaml.get("server", {}))

    system_config = SystemConfig(
        server=server_config,
        vault=vault_ops.vault_config,
        product=product_config,
        settings=settings,
    )

    db = await init_database(system_config.vault.db_path)
    prompt_loader = PromptLoader(system_config.vault.prompts_dir)

    app.state.config = system_config
    app.state.db = db
    app.state.prompt_loader = prompt_loader

    logger.info(
        "taim.started",
        vault=str(system_config.vault.vault_root),
        host=server_config.host,
        port=server_config.port,
        providers=[p.name for p in product_config.providers],
    )

    yield

    await db.close()
    logger.info("taim.stopped")


def _resolve_cors_origins(vault_path: Path) -> list[str]:
    """Resolve CORS origins: ENV > YAML > defaults."""
    default_cors = ["http://localhost:5173", "http://localhost:3000"]
    env_cors = os.environ.get("TAIM_CORS_ORIGINS")
    if env_cors:
        return [o.strip() for o in env_cors.split(",") if o.strip()]

    yaml_path = vault_path.resolve() / "config" / "taim.yaml"
    if yaml_path.exists():
        try:
            raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            return raw.get("server", {}).get("cors_origins", default_cors)
        except yaml.YAMLError:
            pass

    return default_cors


def create_app() -> FastAPI:
    """Create and configure the TAIM FastAPI application."""
    settings = TaimSettings()
    cors_origins = _resolve_cors_origins(settings.vault_path)

    app = FastAPI(
        title="TAIM",
        description="Team AI Manager — AI team orchestration through natural language",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(chat_router)

    return app


app = create_app()
```

- [ ] **Step 2: Write integration tests**

File: `tests/backend/test_main.py`
```python
"""Integration tests for the TAIM application."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from taim.main import create_app


@pytest.fixture
def app_with_vault(tmp_vault: Path, monkeypatch: pytest.MonkeyPatch):
    """Create a TAIM app pointing at a temporary vault."""
    monkeypatch.setenv("TAIM_VAULT_PATH", str(tmp_vault))
    return create_app()


class TestAppStartup:
    async def test_health_via_lifespan(self, app_with_vault) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app_with_vault), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["vault_ok"] is True
        assert data["db_ok"] is True

    async def test_openapi_docs_available(self, app_with_vault) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app_with_vault), base_url="http://test"
        ) as client:
            resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        assert resp.json()["info"]["title"] == "TAIM"


class TestCORS:
    async def test_cors_headers_for_allowed_origin(
        self, app_with_vault
    ) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app_with_vault), base_url="http://test"
        ) as client:
            resp = await client.options(
                "/health",
                headers={
                    "origin": "http://localhost:5173",
                    "access-control-request-method": "GET",
                },
            )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"

    async def test_cors_env_override(
        self, tmp_vault: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TAIM_VAULT_PATH", str(tmp_vault))
        monkeypatch.setenv("TAIM_CORS_ORIGINS", "http://custom.com")
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.options(
                "/health",
                headers={
                    "origin": "http://custom.com",
                    "access-control-request-method": "GET",
                },
            )
        assert resp.headers.get("access-control-allow-origin") == "http://custom.com"
```

- [ ] **Step 3: Run tests — expect PASS**

Run: `cd backend && uv run pytest ../tests/backend/test_main.py -v`
Expected: `4 passed`

- [ ] **Step 4: Commit**

```bash
git add backend/src/taim/main.py tests/backend/test_main.py
git commit -m "feat: add FastAPI app with lifespan, CORS, and factory function"
```

---

## Task 11: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `cd backend && uv run pytest -v`
Expected: All tests pass (approximately 45+ tests)

- [ ] **Step 2: Run with coverage**

Run: `cd backend && uv run pytest --cov=taim --cov-report=term-missing`
Expected: >80% coverage on `errors.py`, `settings.py`, `models/config.py`, `brain/vault.py`, `brain/database.py`, `brain/prompts.py`

- [ ] **Step 3: Run ruff lint**

Run: `cd backend && uv run ruff check src/ && uv run ruff format --check src/`
Expected: No violations. If there are, fix and re-run.

- [ ] **Step 4: Manual startup test**

Run: `cd backend && uv run uvicorn taim.main:app --host localhost --port 8000`
Expected: Server starts, logs show `taim.started` with vault path and providers.

Then in another terminal:
Run: `curl http://localhost:8000/health`
Expected: `{"status":"ok","vault_ok":true,"db_ok":true,"providers":["anthropic","openai","ollama"],"version":"0.1.0"}`

Stop the server with Ctrl+C.

- [ ] **Step 5: Final commit (if any fixes were needed)**

```bash
git add -A
git commit -m "fix: address lint and test issues from final verification"
```

---

## Summary

| Task | Module | Tests | Estimated Steps |
|------|--------|-------|-----------------|
| 1 | Project setup | - | 6 |
| 2 | errors.py | test_errors.py | 5 |
| 3 | settings.py | test_settings.py | 5 |
| 4 | models/config.py | test_config.py | 5 |
| 5 | brain/vault.py | test_vault.py | 6 |
| 6 | brain/database.py | test_database.py | 5 |
| 7 | brain/prompts.py | test_prompts.py | 5 |
| 8 | brain/logging.py | - | 3 |
| 9 | API layer | test_health.py | 6 |
| 10 | main.py | test_main.py | 4 |
| 11 | Verification | - | 5 |
| **Total** | **13 files** | **8 test files** | **55 steps** |

Parallelizable groups for SWAT Swarm:
- **Group A** (Task 2 + 3): errors.py and settings.py — zero interdependence
- **Group B** (Task 6 + 7): database.py and prompts.py — both depend on errors.py but not on each other
