# Step 6a: Tool Framework + Local Tools — Implementation Design

> Version: 1.0
> Date: 2026-04-13
> Status: Reviewed — partition of Step 6 (6b Skills, 6c MCP, 6d Web Tools to follow)
> Scope: US-12.1 (Tool Framework), US-12.2 (4 local built-in tools), US-12.5 (Sandboxing, Denylist), US-12.6 (WebSocket event)

---

## 1. Overview

Step 6a builds the foundation that lets agents take **real actions** instead of just producing text:

```
Agent EXECUTING state
    ↓ LLM call with tools=[...]
LLM responds with tool_calls
    ↓
ToolExecutor validates + executes (sandboxed)
    ↓
Results fed back to LLM
    ↓ loop until no more tool_calls
Final result → REVIEWING state
```

**Deliverables:**
1. `models/tool.py` — Tool, ToolCall, ToolResult, ToolExecutionEvent
2. `orchestrator/tools.py` — ToolExecutor (registration, validation, execution)
3. `orchestrator/tool_sandbox.py` — Path sandboxing for file I/O
4. `orchestrator/builtin_tools/` — 4 built-in tools (file_read, file_write, vault_memory_read, vault_memory_write)
5. `taim-vault/system/tools/*.yaml` — JSON Schema definitions for the 4 tools
6. `router/transport.py` + `router/router.py` — `tools` parameter support, tool_calls in LLMResponse
7. `brain/agent_state_machine.py` — Tool-calling loop in EXECUTING state
8. `api/chat.py` — `tool_execution` WebSocket event forwarding
9. `main.py` — ToolExecutor in lifespan, register built-in tools, populate agent YAMLs with `tools`

**Out of scope (deferred):**
- Skills layer → Step 6b
- MCP integration → Step 6c
- Web tools (web_search, web_fetch) → Step 6d (require user API key)
- Approval gate execution flow → Step 7 (Orchestrator coordinates with WebSocket)

---

## 2. Module Architecture

### 2.1 File Layout

```
backend/src/taim/
├── orchestrator/                              # NEW package
│   ├── __init__.py
│   ├── tools.py                               # ToolExecutor
│   ├── tool_sandbox.py                        # Path validation
│   ├── tool_registry.py                       # Schema loading from vault YAML
│   └── builtin_tools/
│       ├── __init__.py
│       ├── file_io.py                         # file_read, file_write
│       └── memory_tools.py                    # vault_memory_read, vault_memory_write
├── models/
│   └── tool.py                                # Tool models
├── brain/
│   └── agent_state_machine.py                 # MODIFIED: tool loop
├── router/
│   ├── router.py                              # MODIFIED: tools param
│   └── transport.py                           # MODIFIED: pass tools to litellm
├── api/
│   └── chat.py                                # MODIFIED: forward tool_execution
└── main.py                                    # MODIFIED: ToolExecutor in lifespan

taim-vault/
├── system/tools/                              # NEW
│   ├── file_read.yaml
│   ├── file_write.yaml
│   ├── vault_memory_read.yaml
│   └── vault_memory_write.yaml
└── agents/                                    # MODIFIED: tools field populated
    ├── researcher.yaml                        # tools: [vault_memory_write]
    ├── coder.yaml                             # tools: [file_read, file_write]
    ├── reviewer.yaml                          # tools: [file_read]
    ├── writer.yaml                            # tools: [file_read, file_write, vault_memory_read]
    └── analyst.yaml                           # tools: [file_read, vault_memory_read]
```

### 2.2 Dependency Graph

```
models/tool.py                          (no TAIM deps)
    ↓
orchestrator/tool_sandbox.py            (depends on: models/tool, errors)
orchestrator/tool_registry.py           (depends on: models/tool, errors, yaml)
orchestrator/builtin_tools/*            (depends on: models/tool, sandbox, MemoryManager)
orchestrator/tools.py                   (depends on: all above)
    ↓
router/transport.py                     (MODIFIED: tools param)
router/router.py                        (MODIFIED: tools param)
    ↓
brain/agent_state_machine.py            (MODIFIED: tool loop using ToolExecutor + Router)
    ↓
api/chat.py                             (MODIFIED: forward tool_execution events)
main.py                                 (lifespan registers tools, injects ToolExecutor)
```

---

## 3. Data Models (`models/tool.py`)

```python
from __future__ import annotations
from typing import Any
from pydantic import BaseModel


class Tool(BaseModel):
    """Tool definition — schema + executor reference."""
    name: str                                   # "file_read"
    description: str                            # Human + LLM-readable
    parameters: dict[str, Any]                  # JSON Schema (object type)
    requires_approval: bool = False             # Hint for Step 7 approval gate
    source: str = "builtin"                     # "builtin", "mcp", "user" (Step 6c+)


class ToolCall(BaseModel):
    """Request from LLM to execute a tool."""
    id: str                                     # LiteLLM-provided call ID
    name: str
    arguments: dict[str, Any]                   # Already JSON-decoded


class ToolResult(BaseModel):
    """Result of executing a tool."""
    call_id: str
    tool_name: str
    success: bool
    output: str = ""                            # String content (for LLM consumption)
    error: str = ""                             # Error message if success=False
    duration_ms: float = 0.0


class ToolExecutionEvent(BaseModel):
    """Emitted before/after tool execution for observers."""
    agent_name: str
    run_id: str
    tool_name: str
    status: str                                 # "running", "completed", "failed"
    duration_ms: float = 0.0
    error: str = ""
    summary: str = ""                           # Human-readable activity description
```

---

## 4. Tool Sandboxing (`orchestrator/tool_sandbox.py`)

**Responsibility:** Validate paths against allowed sandbox roots. Path traversal blocked.

```python
from pathlib import Path

from taim.errors import TaimError


class ToolSandboxError(TaimError):
    """Path violates sandbox rules."""


def resolve_safe_path(
    requested: str | Path,
    allowed_roots: list[Path],
) -> Path:
    """Resolve to absolute path; raise if outside any allowed root.

    Blocks path traversal (../) and symlink escapes (since we resolve symlinks).
    """
    target = Path(requested).resolve()
    for root in allowed_roots:
        try:
            target.relative_to(root.resolve())
            return target
        except ValueError:
            continue

    raise ToolSandboxError(
        user_message="The requested file path is outside the allowed workspace.",
        detail=f"Path '{requested}' resolved to {target}, not within {[str(r) for r in allowed_roots]}",
    )
```

**Threat modelled:** `../../etc/passwd`, absolute paths outside vault, symlink escape. **Not modelled:** TOCTOU race conditions (low risk for single-user MVP, file-level locking not needed).

---

## 5. Tool Registry (`orchestrator/tool_registry.py`)

**Responsibility:** Load tool YAML schemas from vault.

```python
from pathlib import Path
import yaml
import structlog
from taim.errors import ConfigError
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
            except Exception as e:
                logger.warning("tool_registry.invalid_schema", file=yaml_file.name, error=str(e))
        logger.info("tool_registry.loaded", count=len(self._schemas))

    def get_schema(self, name: str) -> Tool | None:
        return self._schemas.get(name)

    def list_schemas(self) -> list[Tool]:
        return list(self._schemas.values())
```

YAML format example (`taim-vault/system/tools/file_read.yaml`):
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

---

## 6. ToolExecutor (`orchestrator/tools.py`)

**Responsibility:** Register Python executor functions, validate calls, execute with sandboxing, log to agent state.

```python
import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import jsonschema
import structlog
from taim.errors import TaimError
from taim.models.tool import Tool, ToolCall, ToolResult

logger = structlog.get_logger()

# Executor signature: takes parameters dict + context (e.g., user_id), returns string output
ToolFn = Callable[[dict[str, Any], dict[str, Any]], Awaitable[str]]


class ToolError(TaimError):
    """Generic tool execution error."""


class ToolExecutor:
    """Registers and executes tools. Returns errors to LLM, never crashes the agent."""

    def __init__(
        self,
        registry: ToolRegistry,
        global_denylist: list[str] | None = None,
    ) -> None:
        self._registry = registry
        self._executors: dict[str, ToolFn] = {}
        self._denylist = set(global_denylist or [])

    def register(self, name: str, fn: ToolFn) -> None:
        """Register a Python function as the executor for a tool name."""
        if self._registry.get_schema(name) is None:
            logger.warning("tool_executor.no_schema", name=name)
        self._executors[name] = fn

    def list_tools(self) -> list[Tool]:
        """All registered + schema-known tools that aren't denylisted."""
        return [
            t for t in self._registry.list_schemas()
            if t.name in self._executors and t.name not in self._denylist
        ]

    def get_tools_for_agent(self, allowed_names: list[str]) -> list[dict]:
        """Return litellm-format tool definitions for the agent's allowed tools."""
        result = []
        for tool in self.list_tools():
            if tool.name in allowed_names:
                result.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                })
        return result

    async def execute(
        self,
        call: ToolCall,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Execute one tool call. Always returns a ToolResult (success or error)."""
        if call.name in self._denylist:
            return ToolResult(
                call_id=call.id, tool_name=call.name, success=False,
                error=f"Tool '{call.name}' is disabled by global denylist.",
            )

        schema = self._registry.get_schema(call.name)
        executor = self._executors.get(call.name)
        if schema is None or executor is None:
            return ToolResult(
                call_id=call.id, tool_name=call.name, success=False,
                error=f"Tool '{call.name}' is not available.",
            )

        # Validate against JSON schema
        try:
            jsonschema.validate(call.arguments, schema.parameters)
        except jsonschema.ValidationError as e:
            return ToolResult(
                call_id=call.id, tool_name=call.name, success=False,
                error=f"Invalid arguments: {e.message}",
            )

        # Execute
        start = time.monotonic()
        try:
            output = await executor(call.arguments, context or {})
            return ToolResult(
                call_id=call.id, tool_name=call.name, success=True,
                output=output, duration_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as e:  # noqa: BLE001 — tool errors must not crash agent
            logger.exception("tool_executor.error", tool=call.name)
            return ToolResult(
                call_id=call.id, tool_name=call.name, success=False,
                error=str(e), duration_ms=(time.monotonic() - start) * 1000,
            )
```

**Why catch all exceptions?** US-12.1 AC6: Tool errors must not crash the agent — they're returned to the LLM as text so it can adapt. This is the entire point of the wide except clause.

---

## 7. Built-in Tools

### 7.1 `orchestrator/builtin_tools/file_io.py`

```python
from pathlib import Path
from typing import Any

from taim.orchestrator.tool_sandbox import resolve_safe_path

MAX_READ_BYTES = 64 * 1024  # 64KB


async def file_read(args: dict[str, Any], context: dict[str, Any]) -> str:
    path_arg = args["path"]
    allowed_roots: list[Path] = context["allowed_roots"]

    target = resolve_safe_path(path_arg, allowed_roots)
    if not target.exists():
        return f"File not found: {path_arg}"
    if not target.is_file():
        return f"Path is not a file: {path_arg}"

    data = target.read_bytes()
    if len(data) > MAX_READ_BYTES:
        data = data[:MAX_READ_BYTES]
        suffix = "\n\n[truncated — file exceeds 64KB read limit]"
    else:
        suffix = ""

    try:
        return data.decode("utf-8") + suffix
    except UnicodeDecodeError:
        return f"File is not UTF-8 text: {path_arg}"


async def file_write(args: dict[str, Any], context: dict[str, Any]) -> str:
    path_arg = args["path"]
    content = args["content"]
    mode = args.get("mode", "overwrite")  # "overwrite" or "append"
    allowed_roots: list[Path] = context["allowed_roots"]

    target = resolve_safe_path(path_arg, allowed_roots)
    target.parent.mkdir(parents=True, exist_ok=True)

    if mode == "append" and target.exists():
        existing = target.read_text(encoding="utf-8")
        target.write_text(existing + content, encoding="utf-8")
    else:
        target.write_text(content, encoding="utf-8")

    return f"Wrote {len(content)} characters to {target.name}"
```

### 7.2 `orchestrator/builtin_tools/memory_tools.py`

```python
from datetime import date
from typing import Any

from taim.brain.memory import MemoryManager
from taim.models.memory import MemoryEntry


async def vault_memory_read(args: dict[str, Any], context: dict[str, Any]) -> str:
    filename = args["filename"]
    user = args.get("user", "default")
    memory: MemoryManager = context["memory_manager"]

    entry = await memory.read_entry(filename, user=user)
    if entry is None:
        return f"Memory entry not found: {filename}"
    return f"# {entry.title}\n\nTags: {', '.join(entry.tags)}\n\n{entry.content}"


async def vault_memory_write(args: dict[str, Any], context: dict[str, Any]) -> str:
    title = args["title"]
    content = args["content"]
    tags = args.get("tags", [])
    category = args.get("category", "agent-output")
    user = args.get("user", "default")
    memory: MemoryManager = context["memory_manager"]

    today = date.today()
    entry = MemoryEntry(
        title=title, category=category, tags=tags,
        created=today, updated=today,
        content=content, source="agent",
    )
    # Filename derived from title
    safe_name = title.lower().replace(" ", "-")[:60]
    filename = f"agent-{safe_name}.md"
    path = await memory.write_entry(entry, filename, user=user)
    return f"Saved memory entry to {path.name}"
```

### 7.3 Tool YAML Definitions

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

VaultOps gets `_ensure_default_tools()` to seed these.

---

## 8. LLMRouter Tool Support

### 8.1 `LLMResponse` adds `tool_calls`

```python
class LLMResponse(BaseModel):
    content: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: float
    failover_occurred: bool = False
    attempts: int = 1
    tool_calls: list[dict] = []                 # NEW: raw tool_calls from litellm
```

### 8.2 Transport changes

```python
async def complete(
    self,
    messages: list[dict[str, Any]],             # widened — tool messages have list types
    model: str,
    provider: str,
    api_key: str | None = None,
    api_base: str | None = None,
    timeout: float = 30.0,
    tools: list[dict] | None = None,            # NEW
) -> LLMResponse:
    ...
    kwargs = { ... existing ..., }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    response = await litellm.acompletion(**kwargs)
    ...
    msg = response.choices[0].message
    tool_calls_raw = []
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        for tc in msg.tool_calls:
            tool_calls_raw.append({
                "id": tc.id,
                "name": tc.function.name,
                "arguments": tc.function.arguments,  # JSON string from LiteLLM
            })

    return LLMResponse(
        content=msg.content or "",
        ...
        tool_calls=tool_calls_raw,
    )
```

### 8.3 Router changes

`LLMRouter.complete()` adds `tools` param and passes through to transport. JSON validation is skipped if `tools` is set (tool calls are the structured output).

---

## 9. AgentStateMachine — Tool Calling Loop

### 9.1 New constructor parameter

```python
def __init__(
    self,
    ...
    tool_executor: ToolExecutor | None = None,    # NEW, optional
    tool_context: dict[str, Any] | None = None,   # NEW: passed to tool fns
    on_tool_event: Callable[[ToolExecutionEvent], Awaitable[None]] | None = None,  # NEW
):
```

### 9.2 EXECUTING state rewrite

```python
async def _do_executing(self) -> None:
    base_prompt = await self._load_state_prompt(AgentStateEnum.EXECUTING, {
        "task_description": self._task_description,
        "agent_description": self._agent.description,
        "plan": self._state.plan,
        "iteration": str(self._state.iteration),
        "user_preferences": self._user_preferences,
    })

    tools = None
    if self._tool_executor and self._agent.tools:
        tools = self._tool_executor.get_tools_for_agent(self._agent.tools)

    messages: list[dict] = [{"role": "system", "content": base_prompt}]

    MAX_TOOL_LOOPS = 10
    for loop_idx in range(MAX_TOOL_LOOPS):
        response = await self._call_llm(messages, tools=tools)
        self._accumulate_cost(response)

        if not response.tool_calls:
            self._state.current_result = response.content
            break

        # Execute each tool call
        messages.append({
            "role": "assistant",
            "content": response.content or "",
            "tool_calls": [
                {"id": tc["id"], "type": "function",
                 "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in response.tool_calls
            ],
        })

        for tc_raw in response.tool_calls:
            try:
                args = json.loads(tc_raw["arguments"]) if isinstance(tc_raw["arguments"], str) else tc_raw["arguments"]
            except json.JSONDecodeError:
                args = {}
            call = ToolCall(id=tc_raw["id"], name=tc_raw["name"], arguments=args)

            await self._emit_tool_event(call.name, "running", summary=self._summarize_call(call))
            result = await self._tool_executor.execute(call, self._tool_context or {})
            await self._emit_tool_event(
                call.name,
                "completed" if result.success else "failed",
                duration_ms=result.duration_ms,
                error=result.error,
                summary=self._summarize_result(result),
            )

            # Append tool result for LLM
            tool_message_content = result.output if result.success else f"Error: {result.error}"
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": tool_message_content,
            })

            # Track in state history (lightweight audit)
            self._state.state_history.append(StateTransition(
                from_state=AgentStateEnum.EXECUTING,
                to_state=AgentStateEnum.EXECUTING,
                timestamp=datetime.now(timezone.utc),
                reason=f"tool:{call.name}:{'ok' if result.success else 'err'}",
            ))
    else:
        # Loop exhausted — accept whatever last response had as content
        logger.warning("agent.tool_loop_exhausted", run_id=self._state.run_id)
        self._state.current_result = self._state.current_result or "(tool loop exhausted)"

    await self._transition(AgentStateEnum.REVIEWING, "execution_complete")


def _summarize_call(self, call: ToolCall) -> str:
    """Human-readable single-line description of a tool call."""
    if call.name == "file_read":
        return f"Reading file {call.arguments.get('path', '?')}"
    if call.name == "file_write":
        return f"Writing to {call.arguments.get('path', '?')}"
    if call.name == "vault_memory_read":
        return f"Reading memory: {call.arguments.get('filename', '?')}"
    if call.name == "vault_memory_write":
        return f"Saving memory: {call.arguments.get('title', '?')}"
    return f"Running {call.name}"


def _summarize_result(self, result: ToolResult) -> str:
    if not result.success:
        return f"Failed: {result.error[:80]}"
    snippet = result.output[:80].replace("\n", " ")
    return snippet


async def _emit_tool_event(self, tool_name: str, status: str, **kwargs) -> None:
    if self._on_tool_event is None:
        return
    try:
        await self._on_tool_event(ToolExecutionEvent(
            agent_name=self._agent.name,
            run_id=self._state.run_id,
            tool_name=tool_name,
            status=status,
            duration_ms=kwargs.get("duration_ms", 0.0),
            error=kwargs.get("error", ""),
            summary=kwargs.get("summary", ""),
        ))
    except Exception:
        logger.exception("tool_event.emit_error", run_id=self._state.run_id)
```

### 9.3 `_call_llm` adds `tools`

```python
async def _call_llm(
    self,
    messages: list[dict],
    expected_format: str | None = None,
    tools: list[dict] | None = None,
):
    tier_str = self._agent.model_preference[0] if self._agent.model_preference else "tier2_standard"
    return await self._router.complete(
        messages=messages,
        tier=ModelTierEnum(tier_str),
        expected_format=expected_format,
        tools=tools,
        task_id=self._task_id,
        session_id=self._session_id,
        agent_run_id=self._state.run_id,
    )
```

The PLANNING/REVIEWING/ITERATING states use the existing single-prompt path. Only EXECUTING uses tool loop.

---

## 10. WebSocket Forwarding (`api/chat.py`)

The chat endpoint already wires the IntentInterpreter. Step 6a doesn't change the chat flow itself (the orchestrator that drives state machines is Step 7). Step 6a just defines the event format in models — actual forwarding is wired when the Orchestrator runs state machines.

For Step 6a, we expose `tool_execution` as a documented event type. The WebSocket handler accepts the event when the Orchestrator emits it (Step 7). For now the event format is finalized:

```json
{
  "type": "tool_execution",
  "content": "Researcher is reading file research/competitors.md",
  "session_id": "...",
  "metadata": {
    "agent_name": "researcher",
    "tool_name": "file_read",
    "tool_status": "running",
    "duration_ms": 0,
    "error": ""
  }
}
```

Step 7 will instantiate state machines with `on_tool_event=forward_to_websocket(session_id)`.

---

## 11. Lifespan Integration

In `main.py`, after AgentRegistry initialization:

```python
    # 11. Tool System
    from taim.orchestrator.tools import ToolExecutor
    from taim.orchestrator.tool_registry import ToolRegistry
    from taim.orchestrator.builtin_tools.file_io import file_read, file_write
    from taim.orchestrator.builtin_tools.memory_tools import vault_memory_read, vault_memory_write

    tool_registry = ToolRegistry(system_config.vault.vault_root / "system" / "tools")
    tool_registry.load()
    tool_executor = ToolExecutor(
        registry=tool_registry,
        global_denylist=product_config.defaults.get("tools", {}).get("global_denylist", []),
    )
    tool_executor.register("file_read", file_read)
    tool_executor.register("file_write", file_write)
    tool_executor.register("vault_memory_read", vault_memory_read)
    tool_executor.register("vault_memory_write", vault_memory_write)

    app.state.tool_executor = tool_executor
    app.state.tool_registry = tool_registry

    # Tool context shared across executions: vault paths + memory manager
    app.state.tool_context = {
        "allowed_roots": [system_config.vault.vault_root],   # workspace is Step 6c+
        "memory_manager": memory_manager,
    }

    logger.info("tools.loaded", count=len(tool_executor.list_tools()))
```

Add `get_tool_executor()` to `api/deps.py`. Add `GET /api/tools` endpoint (lightweight — lists registered tools).

---

## 12. Updated Agent YAMLs

```yaml
# researcher.yaml
tools: [vault_memory_write]                     # web tools come in 6d

# coder.yaml
tools: [file_read, file_write]

# reviewer.yaml
tools: [file_read]

# writer.yaml
tools: [file_read, file_write, vault_memory_read]

# analyst.yaml
tools: [file_read, vault_memory_read]
```

VaultOps `_ensure_default_agents()` constants get updated. Idempotent — won't overwrite existing user-edited agent files.

**Note:** Existing vaults won't get the updated tool lists automatically (idempotent — files exist). Document migration path: delete `taim-vault/agents/*.yaml` to re-seed, or manually edit. For our development vault, we'll delete + re-seed.

---

## 13. Critical Review Findings (Applied)

| # | Finding | Resolution |
|---|---------|------------|
| 1 | Tool errors must not crash the agent | Wide `except Exception` in ToolExecutor.execute; result returned as text to LLM (US-12.1 AC6) |
| 2 | Path traversal must be blocked | resolve() + relative_to() check in tool_sandbox; tested with `../` cases |
| 3 | Approval-required tools without handler? | For Step 6a: warn in log, proceed. Step 7 will register approval handler. (Documented in Expansion Stages) |
| 4 | Tool loop must terminate | MAX_TOOL_LOOPS=10. Exhaustion logged, current_result accepted as-is. |
| 5 | LLM tool_calls format varies (OpenAI vs Anthropic) | LiteLLM normalizes to OpenAI format. Transport extracts `.tool_calls` from response.choices[0].message |
| 6 | JSON validation conflict with tools | Router skips JSON validation when `tools` is set — tool calls are the structured output |
| 7 | Read size limit | 64KB cap on file_read to avoid context blow-up |
| 8 | Dead code: tool_executor=None case | Bootstrap pattern: agents without tools or executor work normally (single LLM call, no loop) |
| 9 | Existing agent YAMLs won't auto-update | Idempotent seeding by design. Migration documented; dev vault will be re-seeded manually. |

---

## 14. Expansion Stages (Deferred from Step 6a)

### Step 6b (Skills)
- Skill model + YAML loader (`taim-vault/system/skills/*.yaml`)
- 5 built-in skills (web-research, code-generation, code-review, content-writing, data-analysis)
- Agent skill resolution: when agent enters EXECUTING, skill prompts merge with base prompt
- Team Composer skill-aware selection (full effect in Step 7)

### Step 6c (MCP Integration)
- MCP client (stdio + SSE/HTTP transports)
- `taim-vault/config/mcp-servers.yaml` config
- Auto-discovery: tools from MCP servers register into the same ToolExecutor
- Graceful degradation when MCP server unavailable
- `mcp_tools` field on agent YAML

### Step 6d (Web Tools)
- `web_search` (Tavily/Serper/SearXNG, requires API key)
- `web_fetch` (HTML→text, max 8000 chars)
- Researcher agent gets these added to `tools`
- "Tool unavailable" graceful error if API key missing

### Step 7 (Orchestrator)
- Approval gate execution flow — wires `on_tool_event` to WebSocket and `requires_approval_for` to user confirmation
- Pass `on_tool_event` callback to state machines
- Workspace path config (`TAIM_WORKSPACE_PATH` env)

### Step 8 (Heartbeat)
- Tool execution timing in heartbeat metrics
- Tool usage in `agent_progress` event count

---

## 15. Test Strategy

| Test File | Module | Notable Tests |
|-----------|--------|---------------|
| `test_tool_models.py` | models/tool.py | Pydantic validation |
| `test_tool_sandbox.py` | tool_sandbox.py | Allow vault path, block traversal, block absolute outside |
| `test_tool_registry.py` | tool_registry.py | Load valid/invalid YAML schemas |
| `test_tool_executor.py` | tools.py | Register, denylist, schema validation, success, error swallowed-and-returned |
| `test_builtin_tools.py` | builtin_tools/* | file_read/write roundtrip, sandbox enforced, memory tool wraps MemoryManager correctly |
| `test_router_tools.py` | router/router.py + transport.py | tools param passed to litellm, tool_calls in LLMResponse |
| `test_agent_state_machine_tools.py` | brain/agent_state_machine.py | Tool loop happy path, no-tools fallback, tool error continues, max loops |
| `test_vault.py` (extend) | brain/vault.py | Seeds 4 tool YAMLs |

Coverage target: >85% on new modules.

---

*End of Step 6a Design.*
