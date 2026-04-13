# Step 6a: Tool Framework + Local Tools — Implementation Plan

> **For agentic workers:** Follow superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Tool execution framework, 4 local built-in tools, AgentStateMachine integration with tool-calling loop, sandboxing, WebSocket event format.

**Architecture:** ToolExecutor + sandboxed builtins. AgentStateMachine EXECUTING state runs tool loop. Design: `docs/plans/2026-04-13-step6a-tool-framework-design.md`.

**Tech Stack:** Python 3.11+, jsonschema, LiteLLM via Router, asyncio.

---

## File Structure

### Files to Create
```
backend/src/taim/models/tool.py
backend/src/taim/orchestrator/__init__.py
backend/src/taim/orchestrator/tools.py
backend/src/taim/orchestrator/tool_sandbox.py
backend/src/taim/orchestrator/tool_registry.py
backend/src/taim/orchestrator/builtin_tools/__init__.py
backend/src/taim/orchestrator/builtin_tools/file_io.py
backend/src/taim/orchestrator/builtin_tools/memory_tools.py
taim-vault/system/tools/{file_read,file_write,vault_memory_read,vault_memory_write}.yaml
tests/backend/test_tool_models.py
tests/backend/test_tool_sandbox.py
tests/backend/test_tool_registry.py
tests/backend/test_tool_executor.py
tests/backend/test_builtin_tools.py
tests/backend/test_router_tools.py
tests/backend/test_agent_state_machine_tools.py
```

### Files to Modify
```
backend/pyproject.toml              # Add jsonschema explicit dep
backend/src/taim/models/router.py   # Add tool_calls to LLMResponse
backend/src/taim/router/router.py   # tools param
backend/src/taim/router/transport.py # tools param + tool_calls extraction
backend/src/taim/brain/agent_state_machine.py  # tool loop in EXECUTING
backend/src/taim/brain/vault.py     # Seed tool YAMLs + update agent YAMLs
backend/src/taim/main.py            # ToolExecutor + ToolRegistry in lifespan
backend/src/taim/api/deps.py        # get_tool_executor()
tests/backend/test_vault.py         # Verify tool YAMLs seeded
```

Note: existing seeded agent YAMLs in `taim-vault/agents/` are idempotent — won't auto-update tool fields. Manually delete + re-seed during dev (one-time migration documented in PR).

---

## Task 1: Tool Data Models + Add jsonschema dep

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/src/taim/models/tool.py`
- Create: `tests/backend/test_tool_models.py`

- [ ] **Step 1: Add jsonschema to pyproject.toml dependencies**

```toml
"jsonschema>=4.20.0",
```

Run: `cd backend && uv sync --all-extras` to refresh lockfile.

- [ ] **Step 2: Write tests**

```python
"""Tests for tool data models."""

from taim.models.tool import Tool, ToolCall, ToolResult, ToolExecutionEvent


class TestTool:
    def test_minimal(self) -> None:
        t = Tool(
            name="file_read",
            description="Read a file",
            parameters={"type": "object", "properties": {}, "required": []},
        )
        assert t.requires_approval is False
        assert t.source == "builtin"


class TestToolCall:
    def test_minimal(self) -> None:
        c = ToolCall(id="call-1", name="file_read", arguments={"path": "/tmp/x"})
        assert c.arguments["path"] == "/tmp/x"


class TestToolResult:
    def test_success(self) -> None:
        r = ToolResult(call_id="c1", tool_name="file_read", success=True, output="hello", duration_ms=12.0)
        assert r.error == ""

    def test_failure(self) -> None:
        r = ToolResult(call_id="c1", tool_name="file_read", success=False, error="not found")
        assert r.output == ""


class TestToolExecutionEvent:
    def test_minimal(self) -> None:
        e = ToolExecutionEvent(agent_name="researcher", run_id="r1", tool_name="file_read", status="running")
        assert e.duration_ms == 0.0
        assert e.error == ""
```

- [ ] **Step 3: Run → FAIL**

- [ ] **Step 4: Implement models/tool.py**

```python
"""Data models for tool execution."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Tool(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
    requires_approval: bool = False
    source: str = "builtin"


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    call_id: str
    tool_name: str
    success: bool
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0


class ToolExecutionEvent(BaseModel):
    agent_name: str
    run_id: str
    tool_name: str
    status: str
    duration_ms: float = 0.0
    error: str = ""
    summary: str = ""
```

- [ ] **Step 5: Run → PASS** (5 tests)
- [ ] **Step 6: Commit**

```bash
cd /Users/reykz/repositorys/TAIM && git add backend/pyproject.toml backend/src/taim/models/tool.py tests/backend/test_tool_models.py backend/uv.lock
git commit -m "feat: add tool data models and jsonschema dependency"
```

---

## Task 2: Tool Sandbox

**Files:** `backend/src/taim/orchestrator/__init__.py`, `backend/src/taim/orchestrator/tool_sandbox.py`, `tests/backend/test_tool_sandbox.py`

- [ ] **Step 1: Create empty package init**

```python
# backend/src/taim/orchestrator/__init__.py
"""tAIm Orchestrator — tool execution and (Step 7) team coordination."""
```

- [ ] **Step 2: Write tests**

```python
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
        # Even though string contains "..", resolve normalizes
        with pytest.raises(ToolSandboxError):
            resolve_safe_path(str(tmp_path / ".." / "outside.txt"), [tmp_path])

    def test_is_taim_error(self, tmp_path: Path) -> None:
        try:
            resolve_safe_path("/etc/passwd", [tmp_path])
        except ToolSandboxError as e:
            assert isinstance(e, TaimError)
```

- [ ] **Step 3: Run → FAIL**

- [ ] **Step 4: Implement tool_sandbox.py**

```python
"""Path sandboxing for filesystem tools."""

from __future__ import annotations

from pathlib import Path

from taim.errors import TaimError


class ToolSandboxError(TaimError):
    """Path violates sandbox rules."""


def resolve_safe_path(
    requested: str | Path,
    allowed_roots: list[Path],
) -> Path:
    """Resolve to absolute path; raise if outside any allowed root."""
    target = Path(requested).resolve()
    for root in allowed_roots:
        try:
            target.relative_to(root.resolve())
            return target
        except ValueError:
            continue

    raise ToolSandboxError(
        user_message="The requested file path is outside the allowed workspace.",
        detail=(
            f"Path '{requested}' resolved to {target}, "
            f"not within {[str(r) for r in allowed_roots]}"
        ),
    )
```

- [ ] **Step 5: Run → PASS** (5 tests)

- [ ] **Step 6: Commit**

```bash
cd /Users/reykz/repositorys/TAIM && git add backend/src/taim/orchestrator/__init__.py backend/src/taim/orchestrator/tool_sandbox.py tests/backend/test_tool_sandbox.py
git commit -m "feat: add tool path sandbox to block traversal"
```

---

## Task 3: ToolRegistry + Tool YAML files

**Files:**
- Create: `backend/src/taim/orchestrator/tool_registry.py`
- Create: 4 YAML files in `taim-vault/system/tools/`
- Modify: `backend/src/taim/brain/vault.py` (seed tool YAMLs)
- Create: `tests/backend/test_tool_registry.py`

- [ ] **Step 1: Create tool YAML files**

`taim-vault/system/tools/file_read.yaml`:
```yaml
name: file_read
description: Read the contents of a text file from the vault or workspace
requires_approval: false
source: builtin
parameters:
  type: object
  properties:
    path:
      type: string
      description: Absolute or relative path within vault/workspace
  required: [path]
```

`taim-vault/system/tools/file_write.yaml`:
```yaml
name: file_write
description: Write or append text content to a file in the vault or workspace
requires_approval: true
source: builtin
parameters:
  type: object
  properties:
    path:
      type: string
      description: Path within vault/workspace
    content:
      type: string
      description: Text content to write
    mode:
      type: string
      enum: [overwrite, append]
      default: overwrite
  required: [path, content]
```

`taim-vault/system/tools/vault_memory_read.yaml`:
```yaml
name: vault_memory_read
description: Read a memory entry from the user's persistent vault memory
requires_approval: false
source: builtin
parameters:
  type: object
  properties:
    filename:
      type: string
      description: Memory file name (e.g., "preferences.md")
    user:
      type: string
      default: default
  required: [filename]
```

`taim-vault/system/tools/vault_memory_write.yaml`:
```yaml
name: vault_memory_write
description: Save a new memory entry to the user's persistent vault memory
requires_approval: false
source: builtin
parameters:
  type: object
  properties:
    title:
      type: string
    content:
      type: string
    tags:
      type: array
      items: { type: string }
    category:
      type: string
      default: agent-output
    user:
      type: string
      default: default
  required: [title, content]
```

- [ ] **Step 2: Add `_ensure_default_tools()` to vault.py**

Add 4 module constants with the YAML content (triple-quoted strings). Add method:

```python
    def _ensure_default_tools(self) -> None:
        """Seed default tool YAML schema definitions."""
        tools_dir = self.vault_config.vault_root / "system" / "tools"
        tools_dir.mkdir(parents=True, exist_ok=True)
        defaults = {
            "file_read.yaml": _DEFAULT_TOOL_FILE_READ,
            "file_write.yaml": _DEFAULT_TOOL_FILE_WRITE,
            "vault_memory_read.yaml": _DEFAULT_TOOL_VAULT_MEMORY_READ,
            "vault_memory_write.yaml": _DEFAULT_TOOL_VAULT_MEMORY_WRITE,
        }
        for filename, content in defaults.items():
            path = tools_dir / filename
            if not path.exists():
                path.write_text(content, encoding="utf-8")
```

In `ensure_vault()`, after `self._ensure_default_state_prompts()`, add:
```python
        self._ensure_default_tools()
```

- [ ] **Step 3: Write tests**

```python
"""Tests for ToolRegistry."""

from pathlib import Path

from taim.orchestrator.tool_registry import ToolRegistry


class TestLoad:
    def test_loads_valid_schemas(self, tmp_path: Path) -> None:
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "t1.yaml").write_text(
            "name: t1\ndescription: Test\nparameters:\n  type: object\n  properties: {}\n  required: []\n"
        )
        registry = ToolRegistry(tools_dir)
        registry.load()
        assert registry.get_schema("t1") is not None
        assert len(registry.list_schemas()) == 1

    def test_skips_invalid_yaml(self, tmp_path: Path) -> None:
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "bad.yaml").write_text("not: valid: [")
        (tools_dir / "good.yaml").write_text(
            "name: good\ndescription: G\nparameters: {type: object, properties: {}, required: []}\n"
        )
        registry = ToolRegistry(tools_dir)
        registry.load()
        assert registry.get_schema("good") is not None
        assert registry.get_schema("bad") is None

    def test_missing_dir(self, tmp_path: Path) -> None:
        registry = ToolRegistry(tmp_path / "nonexistent")
        registry.load()
        assert registry.list_schemas() == []
```

- [ ] **Step 4: Implement tool_registry.py**

```python
"""ToolRegistry — loads tool schema definitions from vault YAMLs."""

from __future__ import annotations

from pathlib import Path

import structlog
import yaml
from pydantic import ValidationError

from taim.models.tool import Tool

logger = structlog.get_logger()


class ToolRegistry:
    """Loads tool schema definitions from taim-vault/system/tools/."""

    def __init__(self, tools_dir: Path) -> None:
        self._dir = tools_dir
        self._schemas: dict[str, Tool] = {}

    def load(self) -> None:
        self._schemas.clear()
        if not self._dir.exists():
            logger.warning("tool_registry.dir_missing", path=str(self._dir))
            return

        for yaml_file in sorted(self._dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
                tool = Tool(**data)
                self._schemas[tool.name] = tool
            except (yaml.YAMLError, ValidationError) as e:
                logger.warning(
                    "tool_registry.invalid_schema",
                    file=yaml_file.name,
                    error=str(e),
                )
        logger.info("tool_registry.loaded", count=len(self._schemas))

    def get_schema(self, name: str) -> Tool | None:
        return self._schemas.get(name)

    def list_schemas(self) -> list[Tool]:
        return list(self._schemas.values())
```

- [ ] **Step 5: Add test_vault.py extension**

```python
class TestDefaultTools:
    def test_creates_four_tool_schemas(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        tools_dir = ops.vault_config.vault_root / "system" / "tools"
        for name in ["file_read", "file_write", "vault_memory_read", "vault_memory_write"]:
            assert (tools_dir / f"{name}.yaml").exists()
```

- [ ] **Step 6: Run + Commit**

```bash
cd /Users/reykz/repositorys/TAIM && git add backend/src/taim/orchestrator/tool_registry.py backend/src/taim/brain/vault.py taim-vault/system/tools/ tests/backend/test_tool_registry.py tests/backend/test_vault.py
git commit -m "feat: add ToolRegistry and seed 4 tool schema YAMLs"
```

---

## Task 4: ToolExecutor + Built-in Tools

**Files:**
- Create: `backend/src/taim/orchestrator/tools.py`
- Create: `backend/src/taim/orchestrator/builtin_tools/__init__.py`
- Create: `backend/src/taim/orchestrator/builtin_tools/file_io.py`
- Create: `backend/src/taim/orchestrator/builtin_tools/memory_tools.py`
- Create: `tests/backend/test_tool_executor.py`
- Create: `tests/backend/test_builtin_tools.py`

- [ ] **Step 1: Implement file_io.py**

(From design Section 7.1)

- [ ] **Step 2: Implement memory_tools.py**

(From design Section 7.2)

- [ ] **Step 3: Create empty `builtin_tools/__init__.py`**

- [ ] **Step 4: Implement tools.py (ToolExecutor)**

(From design Section 6 — full code)

- [ ] **Step 5: Write test_tool_executor.py**

```python
"""Tests for ToolExecutor."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.models.tool import Tool, ToolCall
from taim.orchestrator.tool_registry import ToolRegistry
from taim.orchestrator.tools import ToolExecutor


@pytest.fixture
def registry(tmp_path: Path) -> ToolRegistry:
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "echo.yaml").write_text(
        "name: echo\ndescription: Echo back\nparameters:\n"
        "  type: object\n  properties:\n    msg: {type: string}\n  required: [msg]\n"
    )
    r = ToolRegistry(tools_dir)
    r.load()
    return r


@pytest.fixture
def executor(registry: ToolRegistry) -> ToolExecutor:
    e = ToolExecutor(registry=registry)

    async def echo_fn(args, ctx):
        return f"echoed: {args['msg']}"

    e.register("echo", echo_fn)
    return e


@pytest.mark.asyncio
class TestExecute:
    async def test_success(self, executor: ToolExecutor) -> None:
        result = await executor.execute(ToolCall(id="c1", name="echo", arguments={"msg": "hi"}))
        assert result.success is True
        assert result.output == "echoed: hi"
        assert result.duration_ms >= 0

    async def test_invalid_arguments(self, executor: ToolExecutor) -> None:
        result = await executor.execute(ToolCall(id="c1", name="echo", arguments={}))
        assert result.success is False
        assert "msg" in result.error.lower() or "required" in result.error.lower()

    async def test_unknown_tool(self, executor: ToolExecutor) -> None:
        result = await executor.execute(ToolCall(id="c1", name="nonexistent", arguments={}))
        assert result.success is False
        assert "not available" in result.error.lower() or "not registered" in result.error.lower()

    async def test_executor_exception_swallowed(self, executor: ToolExecutor, registry: ToolRegistry) -> None:
        async def crashy(args, ctx):
            raise RuntimeError("boom")
        executor.register("echo", crashy)
        result = await executor.execute(ToolCall(id="c1", name="echo", arguments={"msg": "x"}))
        assert result.success is False
        assert "boom" in result.error


@pytest.mark.asyncio
class TestDenylist:
    async def test_denied_tool_returns_error(self, registry: ToolRegistry) -> None:
        e = ToolExecutor(registry=registry, global_denylist=["echo"])

        async def echo_fn(args, ctx):
            return "ok"

        e.register("echo", echo_fn)
        result = await e.execute(ToolCall(id="c1", name="echo", arguments={"msg": "x"}))
        assert result.success is False
        assert "denylist" in result.error.lower() or "disabled" in result.error.lower()


class TestGetToolsForAgent:
    def test_returns_litellm_format(self, executor: ToolExecutor) -> None:
        tools = executor.get_tools_for_agent(["echo"])
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "echo"

    def test_filters_by_agent_allowed(self, executor: ToolExecutor) -> None:
        tools = executor.get_tools_for_agent(["nonexistent"])
        assert tools == []
```

- [ ] **Step 6: Write test_builtin_tools.py**

```python
"""Tests for built-in tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.memory import MemoryManager
from taim.orchestrator.builtin_tools.file_io import file_read, file_write
from taim.orchestrator.builtin_tools.memory_tools import (
    vault_memory_read,
    vault_memory_write,
)
from taim.orchestrator.tool_sandbox import ToolSandboxError


@pytest.mark.asyncio
class TestFileIO:
    async def test_file_write_then_read(self, tmp_path: Path) -> None:
        ctx = {"allowed_roots": [tmp_path]}
        target = tmp_path / "test.txt"
        write_result = await file_write({"path": str(target), "content": "hello"}, ctx)
        assert "Wrote" in write_result
        read_result = await file_read({"path": str(target)}, ctx)
        assert read_result == "hello"

    async def test_file_read_missing(self, tmp_path: Path) -> None:
        ctx = {"allowed_roots": [tmp_path]}
        result = await file_read({"path": str(tmp_path / "missing.txt")}, ctx)
        assert "not found" in result.lower()

    async def test_sandbox_blocks_outside(self, tmp_path: Path) -> None:
        ctx = {"allowed_roots": [tmp_path]}
        with pytest.raises(ToolSandboxError):
            await file_read({"path": "/etc/passwd"}, ctx)

    async def test_file_write_append(self, tmp_path: Path) -> None:
        ctx = {"allowed_roots": [tmp_path]}
        target = tmp_path / "log.txt"
        await file_write({"path": str(target), "content": "line1\n"}, ctx)
        await file_write({"path": str(target), "content": "line2\n", "mode": "append"}, ctx)
        result = await file_read({"path": str(target)}, ctx)
        assert "line1" in result and "line2" in result


@pytest.mark.asyncio
class TestMemoryTools:
    async def test_write_then_read(self, tmp_path: Path) -> None:
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        memory = MemoryManager(users_dir)
        ctx = {"memory_manager": memory}

        write_msg = await vault_memory_write(
            {"title": "Test Pref", "content": "concise outputs", "tags": ["preferences"]},
            ctx,
        )
        assert "Saved" in write_msg

        # Filename derived from title
        read_result = await vault_memory_read({"filename": "agent-test-pref.md"}, ctx)
        assert "concise outputs" in read_result

    async def test_read_missing_returns_friendly(self, tmp_path: Path) -> None:
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        ctx = {"memory_manager": MemoryManager(users_dir)}
        result = await vault_memory_read({"filename": "nonexistent.md"}, ctx)
        assert "not found" in result.lower()
```

- [ ] **Step 7: Run all → PASS**

- [ ] **Step 8: Commit**

```bash
cd /Users/reykz/repositorys/TAIM && git add backend/src/taim/orchestrator/tools.py backend/src/taim/orchestrator/builtin_tools/ tests/backend/test_tool_executor.py tests/backend/test_builtin_tools.py
git commit -m "feat: add ToolExecutor and 4 built-in tools (file_io, memory_tools)"
```

---

## Task 5: LLMRouter Tool Support

**Files:**
- Modify: `backend/src/taim/models/router.py` (LLMResponse adds tool_calls)
- Modify: `backend/src/taim/router/transport.py` (tools param + tool_calls extraction)
- Modify: `backend/src/taim/router/router.py` (tools param passthrough)
- Create: `tests/backend/test_router_tools.py`

- [ ] **Step 1: Update LLMResponse**

In `backend/src/taim/models/router.py`, add field:
```python
class LLMResponse(BaseModel):
    ...existing fields...
    tool_calls: list[dict] = []
```

- [ ] **Step 2: Update Transport**

In `backend/src/taim/router/transport.py`:

Add `tools: list[dict] | None = None` to `complete()` signature.

Add to kwargs construction:
```python
if tools:
    kwargs["tools"] = tools
    kwargs["tool_choice"] = "auto"
```

After receiving response, extract tool_calls:
```python
msg = response.choices[0].message
tool_calls_raw: list[dict] = []
if hasattr(msg, "tool_calls") and msg.tool_calls:
    for tc in msg.tool_calls:
        tool_calls_raw.append({
            "id": tc.id,
            "name": tc.function.name,
            "arguments": tc.function.arguments,
        })

return LLMResponse(
    content=msg.content or "",
    ...
    tool_calls=tool_calls_raw,
)
```

- [ ] **Step 3: Update Router**

In `backend/src/taim/router/router.py`, add `tools` param to `complete()`:

```python
async def complete(
    self,
    messages: list[dict[str, str]],
    tier: ModelTierEnum,
    expected_format: str | None = None,
    tools: list[dict] | None = None,            # NEW
    task_id: str | None = None,
    agent_run_id: str | None = None,
    session_id: str | None = None,
) -> LLMResponse:
```

Pass `tools=tools` to `self._transport.complete()`.

Skip JSON validation when tools are present:
```python
# Format validation (only if no tools)
if expected_format == "json" and not tools:
    try:
        json.loads(response.content)
    except json.JSONDecodeError:
        raise LLMTransportError(...)
```

- [ ] **Step 4: Write tests**

```python
"""Tests for Router tool support."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.database import init_database
from taim.models.config import ProductConfig, ProviderConfig, TierConfig
from taim.models.router import LLMResponse, ModelTierEnum
from taim.router.router import LLMRouter
from taim.router.tiering import TierResolver
from taim.router.tracking import TokenTracker

from conftest import MockTransport, make_response


def _config() -> ProductConfig:
    return ProductConfig(
        providers=[
            ProviderConfig(name="primary", api_key_env="PRIMARY_KEY", models=["m1"], priority=1),
        ],
        tiering={"tier2_standard": TierConfig(description="S", models=["m1"])},
        defaults={},
    )


@pytest_asyncio.fixture
async def db(tmp_path: Path):
    conn = await init_database(tmp_path / "taim.db")
    yield conn
    await conn.close()


@pytest.mark.asyncio
class TestToolsParameter:
    async def test_tools_passed_to_transport(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "k")
        transport = MockTransport([make_response("ok")])
        router = LLMRouter(
            transport=transport,
            tier_resolver=TierResolver(_config()),
            tracker=TokenTracker(db),
            product_config=_config(),
        )
        my_tools = [{"type": "function", "function": {"name": "echo"}}]
        await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            tier=ModelTierEnum.TIER2_STANDARD,
            tools=my_tools,
        )
        assert transport.calls[0]["tools"] == my_tools

    async def test_no_json_validation_when_tools(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "k")
        transport = MockTransport([make_response("not json at all")])
        router = LLMRouter(
            transport=transport,
            tier_resolver=TierResolver(_config()),
            tracker=TokenTracker(db),
            product_config=_config(),
        )
        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            tier=ModelTierEnum.TIER2_STANDARD,
            expected_format="json",
            tools=[{"type": "function", "function": {"name": "x"}}],
        )
        assert result.content == "not json at all"


class TestLLMResponseToolCalls:
    def test_default_empty(self) -> None:
        r = LLMResponse(
            content="x", model="m", provider="p",
            prompt_tokens=1, completion_tokens=1, cost_usd=0.0, latency_ms=10.0,
        )
        assert r.tool_calls == []
```

For testing the actual transport extraction of tool_calls from litellm response, mock litellm with a response that has tool_calls. Here's a test for the transport layer:

```python
@pytest.mark.asyncio
class TestTransportToolExtraction:
    @patch("taim.router.transport.litellm")
    async def test_extracts_tool_calls(self, mock_litellm) -> None:
        from unittest.mock import AsyncMock, MagicMock
        from taim.router.transport import LLMTransport

        # Build mock response with tool_calls
        mock_tool_call = MagicMock()
        mock_tool_call.id = "tc-1"
        mock_tool_call.function.name = "echo"
        mock_tool_call.function.arguments = '{"msg": "hi"}'

        mock_msg = MagicMock()
        mock_msg.content = ""
        mock_msg.tool_calls = [mock_tool_call]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=mock_msg)]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        mock_litellm.completion_cost = MagicMock(return_value=0.001)

        transport = LLMTransport()
        result = await transport.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="m", provider="p", api_key="k",
            tools=[{"type": "function", "function": {"name": "echo"}}],
        )
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "echo"
        assert result.tool_calls[0]["id"] == "tc-1"
```

- [ ] **Step 5: Run all + verify no regressions**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest -v
```

- [ ] **Step 6: Commit**

```bash
cd /Users/reykz/repositorys/TAIM && git add backend/src/taim/models/router.py backend/src/taim/router/router.py backend/src/taim/router/transport.py tests/backend/test_router_tools.py
git commit -m "feat: add tools parameter to LLMRouter and tool_calls extraction in Transport"
```

---

## Task 6: AgentStateMachine Tool Loop

**Files:**
- Modify: `backend/src/taim/brain/agent_state_machine.py`
- Create: `tests/backend/test_agent_state_machine_tools.py`

- [ ] **Step 1: Update AgentStateMachine**

Add to constructor:
```python
def __init__(
    self,
    ...
    tool_executor: "ToolExecutor | None" = None,
    tool_context: dict | None = None,
    on_tool_event: "Callable[[ToolExecutionEvent], Awaitable[None]] | None" = None,
):
    ...
    self._tool_executor = tool_executor
    self._tool_context = tool_context
    self._on_tool_event = on_tool_event
```

Replace `_do_executing` with the tool-loop version (from design Section 9.2).

Add helpers `_summarize_call`, `_summarize_result`, `_emit_tool_event`.

Update `_call_llm` to accept `tools` parameter.

- [ ] **Step 2: Write tests**

```python
"""Tests for AgentStateMachine tool calling loop."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.agent_run_store import AgentRunStore
from taim.brain.agent_state_machine import AgentStateMachine
from taim.brain.database import init_database
from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.models.agent import Agent, AgentStateEnum
from taim.models.router import LLMResponse
from taim.models.tool import Tool, ToolExecutionEvent
from taim.orchestrator.tool_registry import ToolRegistry
from taim.orchestrator.tools import ToolExecutor

from conftest import MockRouter, make_response


def _make_response_with_tool_calls(tool_name: str, arguments: dict, call_id: str = "tc-1") -> LLMResponse:
    return LLMResponse(
        content="",
        model="m", provider="p",
        prompt_tokens=10, completion_tokens=5, cost_usd=0.001, latency_ms=50.0,
        tool_calls=[{
            "id": call_id,
            "name": tool_name,
            "arguments": json.dumps(arguments),
        }],
    )


@pytest_asyncio.fixture
async def setup(tmp_vault: Path):
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    db = await init_database(ops.vault_config.db_path)
    store = AgentRunStore(db)

    # Build a simple registry + executor with one test tool
    tools_dir = tmp_vault / "test-tools"
    tools_dir.mkdir()
    (tools_dir / "echo.yaml").write_text(
        "name: echo\ndescription: Echo\nparameters: {type: object, properties: {msg: {type: string}}, required: [msg]}\n"
    )
    registry = ToolRegistry(tools_dir)
    registry.load()
    executor = ToolExecutor(registry=registry)

    async def echo_fn(args, ctx):
        return f"echoed:{args['msg']}"

    executor.register("echo", echo_fn)

    yield ops, loader, store, executor
    await db.close()


def _make_agent(tools: list[str] | None = None) -> Agent:
    return Agent(
        name="researcher", description="Test",
        model_preference=["tier2_standard"], skills=[],
        tools=tools or [],
    )


@pytest.mark.asyncio
class TestToolLoop:
    async def test_executes_tool_then_returns(self, setup) -> None:
        _, loader, store, executor = setup
        router = MockRouter([
            make_response("plan"),                              # PLANNING
            _make_response_with_tool_calls("echo", {"msg": "hi"}),  # EXEC: tool call
            make_response("Done with tools, here's result"),    # EXEC: continuation after tool
            make_response('{"quality_ok": true, "feedback": "ok"}'),  # REVIEWING
        ])
        agent = _make_agent(tools=["echo"])
        sm = AgentStateMachine(
            agent=agent,
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
            tool_executor=executor,
            tool_context={},
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE
        assert "result" in run.result_content.lower()

    async def test_no_tools_falls_back_to_normal_flow(self, setup) -> None:
        _, loader, store, executor = setup
        router = MockRouter([
            make_response("plan"),
            make_response("normal result"),
            make_response('{"quality_ok": true, "feedback": ""}'),
        ])
        agent = _make_agent(tools=[])  # No tools allowed
        sm = AgentStateMachine(
            agent=agent,
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
            tool_executor=executor,
            tool_context={},
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE
        assert run.result_content == "normal result"

    async def test_tool_event_emitted(self, setup) -> None:
        _, loader, store, executor = setup
        events: list[ToolExecutionEvent] = []
        async def capture(e: ToolExecutionEvent) -> None:
            events.append(e)
        router = MockRouter([
            make_response("plan"),
            _make_response_with_tool_calls("echo", {"msg": "hi"}),
            make_response("done"),
            make_response('{"quality_ok": true, "feedback": ""}'),
        ])
        agent = _make_agent(tools=["echo"])
        sm = AgentStateMachine(
            agent=agent,
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
            tool_executor=executor,
            tool_context={},
            on_tool_event=capture,
        )
        await sm.run()
        statuses = [e.status for e in events]
        assert "running" in statuses
        assert "completed" in statuses

    async def test_tool_error_continues(self, setup) -> None:
        _, loader, store, executor = setup
        # Register a tool that raises
        executor.register("echo", _crashing_fn)
        router = MockRouter([
            make_response("plan"),
            _make_response_with_tool_calls("echo", {"msg": "hi"}),
            make_response("recovered after error"),
            make_response('{"quality_ok": true, "feedback": ""}'),
        ])
        agent = _make_agent(tools=["echo"])
        sm = AgentStateMachine(
            agent=agent,
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
            tool_executor=executor,
            tool_context={},
        )
        run = await sm.run()
        # Agent recovered — DONE not FAILED
        assert run.final_state == AgentStateEnum.DONE


async def _crashing_fn(args, ctx):
    raise RuntimeError("intentional test failure")
```

- [ ] **Step 3: Run → PASS**

- [ ] **Step 4: Commit**

```bash
cd /Users/reykz/repositorys/TAIM && git add backend/src/taim/brain/agent_state_machine.py tests/backend/test_agent_state_machine_tools.py
git commit -m "feat: add tool calling loop in AgentStateMachine EXECUTING state"
```

---

## Task 7: Lifespan Integration + Agent YAML Updates + /api/tools

**Files:**
- Modify: `backend/src/taim/main.py` (lifespan)
- Modify: `backend/src/taim/api/deps.py` (get_tool_executor)
- Modify: `backend/src/taim/brain/vault.py` (update agent YAML constants)
- Manual: delete + re-seed `taim-vault/agents/*.yaml`
- Modify: `backend/src/taim/api/agents.py` OR create `backend/src/taim/api/tools.py` for `GET /api/tools`

- [ ] **Step 1: Update agent YAML constants in vault.py**

Update each `_DEFAULT_AGENT_*` constant to include the `tools:` field:

```python
_DEFAULT_AGENT_RESEARCHER = """\
name: researcher
description: Researches topics using web sources and summarizes findings
model_preference:
  - tier2_standard
  - tier3_economy
skills:
  - web_research
  - summarization
  - source_evaluation
tools:
  - vault_memory_write
max_iterations: 3
requires_approval_for: []
"""
```

(Similar updates for coder, reviewer, writer, analyst — see design Section 12.)

- [ ] **Step 2: Re-seed dev vault agents**

```bash
cd /Users/reykz/repositorys/TAIM && rm -f taim-vault/agents/*.yaml
# Server-side re-seeding would happen on next start; for tests we use tmp_vault which always re-seeds
```

For the dev vault, just delete and let next server start re-seed. Or manually edit. Document in PR.

- [ ] **Step 3: Update main.py lifespan**

After agent registry init, add:
```python
    # 11. Tool System
    from taim.orchestrator.builtin_tools.file_io import file_read, file_write
    from taim.orchestrator.builtin_tools.memory_tools import (
        vault_memory_read, vault_memory_write,
    )
    from taim.orchestrator.tool_registry import ToolRegistry
    from taim.orchestrator.tools import ToolExecutor

    tool_registry = ToolRegistry(
        system_config.vault.vault_root / "system" / "tools"
    )
    tool_registry.load()
    tool_executor = ToolExecutor(
        registry=tool_registry,
        global_denylist=product_config.defaults.get("tools", {}).get("global_denylist", []),
    )
    tool_executor.register("file_read", file_read)
    tool_executor.register("file_write", file_write)
    tool_executor.register("vault_memory_read", vault_memory_read)
    tool_executor.register("vault_memory_write", vault_memory_write)

    app.state.tool_registry = tool_registry
    app.state.tool_executor = tool_executor
    app.state.tool_context = {
        "allowed_roots": [system_config.vault.vault_root],
        "memory_manager": memory_manager,
    }

    logger.info("tools.loaded", count=len(tool_executor.list_tools()))
```

- [ ] **Step 4: Add `get_tool_executor()` to deps.py**

```python
from taim.orchestrator.tools import ToolExecutor

def get_tool_executor(request: Request) -> ToolExecutor:
    return request.app.state.tool_executor
```

- [ ] **Step 5: Add `GET /api/tools` endpoint**

Either extend `api/agents.py` or create `api/tools.py`. Suggest `api/tools.py`:

```python
"""Tool REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from taim.api.deps import get_tool_executor
from taim.orchestrator.tools import ToolExecutor

router = APIRouter(prefix="/api/tools")


@router.get("")
async def list_tools(executor: ToolExecutor = Depends(get_tool_executor)) -> dict:
    tools = executor.list_tools()
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "source": t.source,
                "requires_approval": t.requires_approval,
            }
            for t in tools
        ],
        "count": len(tools),
    }
```

In `create_app()`:
```python
from taim.api.tools import router as tools_router
app.include_router(tools_router)
```

- [ ] **Step 6: Run all tests + lint**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest -v
cd /Users/reykz/repositorys/TAIM/backend && uv run ruff check src/ && uv run ruff format src/
```

- [ ] **Step 7: Manual smoke test**

```bash
cd /Users/reykz/repositorys/TAIM && rm -f taim-vault/agents/*.yaml
cd /Users/reykz/repositorys/TAIM/backend && uv run uvicorn taim.main:app --host localhost --port 8004 > /tmp/taim-step6a.log 2>&1 &
sleep 3
curl -s http://localhost:8004/api/tools | python3 -m json.tool
curl -s http://localhost:8004/api/agents/researcher | python3 -m json.tool
kill %1 2>/dev/null
cat /tmp/taim-step6a.log | head -10
```

Expected: `tools.loaded count=4`, `/api/tools` returns 4 built-in tools, researcher agent shows `tools: [vault_memory_write]`.

- [ ] **Step 8: Commit**

```bash
cd /Users/reykz/repositorys/TAIM && git add backend/src/taim/main.py backend/src/taim/api/deps.py backend/src/taim/api/tools.py backend/src/taim/brain/vault.py taim-vault/agents/
git commit -m "feat: wire ToolExecutor into lifespan, add /api/tools, populate agent tool lists"
```

---

## Task 8: Final Verification

- [ ] Run full suite + coverage
- [ ] Lint check
- [ ] Commit any cleanup

---

## Summary

| Task | Module | Tests | Steps |
|------|--------|-------|-------|
| 1 | models/tool.py + jsonschema dep | test_tool_models.py | 6 |
| 2 | tool_sandbox.py | test_tool_sandbox.py | 6 |
| 3 | tool_registry.py + 4 YAMLs | test_tool_registry.py + test_vault | 6 |
| 4 | tools.py + builtin_tools/* | test_tool_executor.py + test_builtin_tools.py | 8 |
| 5 | router/transport+router (modify) | test_router_tools.py | 6 |
| 6 | agent_state_machine.py (modify) | test_agent_state_machine_tools.py | 4 |
| 7 | main.py + agent YAMLs + /api/tools | (smoke) | 8 |
| 8 | Verification | — | 3 |
| **Total** | **6 new modules + 4 vault YAMLs** | **7 test files** | **47 steps** |
