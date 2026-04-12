"""Tests for PromptLoader with Jinja2 templating."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
import yaml

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
    data: dict = {"name": name, "version": 1, "template": template, **extra}
    (prompts_dir / f"{name}.yaml").write_text(yaml.dump(data))


class TestLoad:
    def test_loads_template_without_variables(self, loader: PromptLoader, prompts_dir: Path) -> None:
        _write_prompt(prompts_dir, "simple", "Hello world")
        result = loader.load("simple")
        assert result == "Hello world"

    def test_substitutes_variables(self, loader: PromptLoader, prompts_dir: Path) -> None:
        _write_prompt(prompts_dir, "greeting", "Hello {{ name }}, you are {{ role }}")
        result = loader.load("greeting", {"name": "TAIM", "role": "manager"})
        assert result == "Hello TAIM, you are manager"

    def test_json_braces_not_interpreted(self, loader: PromptLoader, prompts_dir: Path) -> None:
        _write_prompt(prompts_dir, "json-output", 'Output: {"category": "{{ cat }}", "score": 0.9}')
        result = loader.load("json-output", {"cat": "task"})
        assert result == 'Output: {"category": "task", "score": 0.9}'


class TestErrors:
    def test_missing_file_raises_prompt_not_found(self, loader: PromptLoader) -> None:
        with pytest.raises(PromptNotFoundError):
            loader.load("nonexistent")

    def test_missing_variable_raises_prompt_variable_error(self, loader: PromptLoader, prompts_dir: Path) -> None:
        _write_prompt(prompts_dir, "needs-var", "Hello {{ name }}")
        with pytest.raises(PromptVariableError):
            loader.load("needs-var", {"wrong_key": "value"})

    def test_empty_template_raises(self, loader: PromptLoader, prompts_dir: Path) -> None:
        (prompts_dir / "empty.yaml").write_text(yaml.dump({"name": "empty", "template": ""}))
        with pytest.raises(PromptNotFoundError):
            loader.load("empty")


class TestCache:
    def test_caches_after_first_load(self, loader: PromptLoader, prompts_dir: Path) -> None:
        _write_prompt(prompts_dir, "cached", "original")
        assert loader.load("cached") == "original"
        assert loader.load("cached") == "original"

    def test_invalidates_on_file_change(self, loader: PromptLoader, prompts_dir: Path) -> None:
        _write_prompt(prompts_dir, "changing", "v1")
        assert loader.load("changing") == "v1"
        time.sleep(0.05)
        _write_prompt(prompts_dir, "changing", "v2")
        assert loader.load("changing") == "v2"


class TestGetMetadata:
    def test_returns_metadata_without_template(self, loader: PromptLoader, prompts_dir: Path) -> None:
        _write_prompt(prompts_dir, "meta", "template body", description="A test prompt", model_tier="tier3_economy")
        meta = loader.get_metadata("meta")
        assert meta["name"] == "meta"
        assert meta["description"] == "A test prompt"
        assert meta["model_tier"] == "tier3_economy"
        assert "template" not in meta
