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
        """Return prompt metadata without template."""
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
