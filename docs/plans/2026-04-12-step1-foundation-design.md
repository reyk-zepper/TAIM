# Step 1: Foundation — Implementation Design

> Version: 1.1
> Date: 2026-04-12
> Status: Reviewed — DA + Meta-Review applied
> Scope: US-7.1, US-11.1, US-11.2, US-11.3

---

## 1. Overview

Step 1 builds the foundation that every subsequent step depends on: config loading, vault initialization, database schema, prompt loading, and the FastAPI skeleton. No LLM calls, no agents, no frontend — pure infrastructure.

**Deliverables:**
1. Config system (ENV + YAML, two-layer architecture)
2. Vault initialization (idempotent, first-run safe)
3. SQLite database with schema versioning
4. PromptLoader with Jinja2 templating
5. FastAPI app with health endpoint and WebSocket stub
6. Error system with dual personality (user-friendly + developer-detailed)
7. Structured logging with structlog
8. Test suite with shared vault fixture

**Guiding Principle:** Every decision here serves the "Conversation First" and "AI Equalizer" vision. The config system must be human-readable. Errors must speak human. The vault structure must be transparent and explorable.

---

## 2. PRD Deviations & Corrections

Issues found during design that deviate from or correct the PRD:

| # | Issue | PRD Says | Design Says | Rationale |
|---|-------|----------|-------------|-----------|
| D-1 | DB path | `taim.yaml` has `tracking.db` | `taim.db` at `{vault}/system/state/taim.db` | AD-8 decided single DB. `tracking.db` name implies separate DB. |
| D-2 | Host default | `taim.yaml` says `0.0.0.0`, ENV table says `localhost` | Default `localhost`, YAML can override | `0.0.0.0` exposes to network — insecure default for a self-hosted tool |
| D-3 | Template syntax | PRD specifies `{variable}` | Jinja2 `{{ variable }}` | `{variable}` collides with JSON in prompt templates |
| D-4 | python-dotenv | PRD lists as "must add" | Not needed | `pydantic-settings` handles `.env` natively |
| D-5 | Config tracking.database key | Separate config key in `taim.yaml` | Remove — derive from vault path | DB path = `{vault_root}/system/state/taim.db`, always |
| D-6 | Jinja2 dependency | Not in PRD | Add explicitly | Required for D-3 template syntax |

---

## 3. Module Architecture

### 3.1 File Layout

```
backend/src/taim/
├── __init__.py              # Package version
├── main.py                  # FastAPI app, lifespan, CORS, startup logging
├── settings.py              # TaimSettings (pydantic-settings, ENV-only)
├── errors.py                # TaimError hierarchy (dual personality)
│
├── api/
│   ├── __init__.py
│   ├── health.py            # GET /health + GET /api/health
│   └── deps.py              # FastAPI Depends() functions
│
├── brain/
│   ├── __init__.py
│   ├── vault.py             # VaultOps (init, path resolution, YAML loading)
│   ├── database.py          # SQLite init, schema migrations, connection management
│   └── prompts.py           # PromptLoader (Jinja2-based, cached)
│
├── models/
│   ├── __init__.py
│   └── config.py            # VaultConfig, ProviderConfig, TierConfig, ProductConfig, SystemConfig
│
├── conversation/
│   └── __init__.py          # Empty (Step 3)
├── orchestrator/
│   └── __init__.py          # Empty (Step 5-7)
├── router/
│   └── __init__.py          # Empty (Step 2)
└── cli/
    └── __init__.py          # Empty (Step 11)
```

### 3.2 Dependency Graph (Step 1 only)

```
settings.py          (no TAIM deps — reads ENV)
errors.py            (no TAIM deps — base exceptions)
models/config.py     (no TAIM deps — pure Pydantic)
    ↓
brain/vault.py       (depends on: models/config, errors, settings)
brain/prompts.py     (depends on: errors)
brain/database.py    (depends on: errors)
    ↓
api/deps.py          (depends on: models/config, brain/*)
api/health.py        (depends on: api/deps, models/config)
    ↓
main.py              (composes everything via lifespan)
```

No circular dependencies. Each module is independently testable.

---

## 4. Config System

### 4.1 Architecture: YAML is canonical, ENV overrides

Config has three layers with clear precedence:

```
Pydantic defaults (lowest) → YAML values → ENV variables (highest)
```

**Key design decision:** `taim.yaml` is the canonical config source for ALL settings (including server host/port). ENV vars override when explicitly set. This serves the AI Equalizer principle: a user who opens `taim.yaml` and changes the port gets their change honored.

**Layer 1: ENV-only settings** — `settings.py`

Only settings that have NO YAML counterpart (pure infrastructure):

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class TaimSettings(BaseSettings):
    """Pure infrastructure settings — no YAML counterpart."""

    model_config = SettingsConfigDict(
        env_prefix="TAIM_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    vault_path: Path = Path("./taim-vault")
    env: str = "development"        # development | production
    log_level: str = "INFO"
    log_format: str = "dev"         # "dev" (pretty) or "json" (structured)
```

Deliberately slim — only 4 fields. Host, port, CORS live in YAML.

**Layer 2: Product + Server Config (YAML)** — loaded by `VaultOps`

```python
# models/config.py
import os

class ServerConfig(BaseModel):
    """Server settings — from taim.yaml, overridable by ENV."""
    host: str = "localhost"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    @classmethod
    def from_yaml_and_env(cls, yaml_server: dict) -> "ServerConfig":
        """YAML is baseline, ENV vars override when explicitly set."""
        return cls(
            host=os.environ.get("TAIM_HOST") or yaml_server.get("host", "localhost"),
            port=int(os.environ.get("TAIM_PORT") or yaml_server.get("port", 8000)),
            cors_origins=(
                os.environ.get("TAIM_CORS_ORIGINS", "").split(",")
                if os.environ.get("TAIM_CORS_ORIGINS")
                else yaml_server.get("cors_origins", ["http://localhost:5173", "http://localhost:3000"])
            ),
        )

class ProviderConfig(BaseModel):
    name: str
    api_key_env: str = ""           # ENV var name, not the key itself
    host: str | None = None         # For local providers (Ollama)
    models: list[str]
    priority: int = 1
    monthly_budget_eur: float | None = None

class TierConfig(BaseModel):
    description: str
    models: list[str]

class ProductConfig(BaseModel):
    """Product behavior — loaded from vault YAML files."""
    providers: list[ProviderConfig]
    tiering: dict[str, TierConfig]          # tier1_premium, tier2_standard, tier3_economy
    defaults: dict[str, Any]                # Raw defaults.yaml content
    conversation_verbosity: str = "normal"
    conversation_language: str = "auto"
    heartbeat_interval: int = 30
    agent_timeout: int = 120
    default_iterations: int = 2
    usd_to_eur_rate: float = 0.92           # For token cost conversion (PRD Section 6)
```

**Layer 3: Runtime Composition**

```python
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
    def from_root(cls, vault_root: Path) -> "VaultConfig":
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
    server: ServerConfig
    vault: VaultConfig
    product: ProductConfig
    settings: TaimSettings

    class Config:
        arbitrary_types_allowed = True
```

### 4.2 Why `os.environ.get() or yaml_value`?

pydantic-settings v2 cannot distinguish "value from ENV" vs "value is the default." A custom `PydanticBaseSettingsSource` would be correct but adds ~40 lines of boilerplate for 3 fields. The `os.environ.get()` pattern is explicit, debuggable, and achieves the same result in ~5 lines.

### 4.3 taim.yaml Corrections

The existing `taim.yaml` needs these changes for consistency:
- Remove `tracking.database` key (DB path is always `{vault_root}/system/state/taim.db`)
- Change `server.host` default from `0.0.0.0` to `localhost` (secure default)
- Add `tracking.usd_to_eur_rate: 0.92` (needed for cost conversion, PRD Section 6 note)

---

## 5. Vault Initialization

### 5.1 Directory Structure

```
taim-vault/
├── config/
│   ├── taim.yaml            # Main config (exists)
│   ├── providers.yaml       # Provider config (exists)
│   └── defaults.yaml        # Smart defaults (exists)
├── agents/                  # Built-in agent YAML definitions (Step 5)
├── teams/                   # Saved team configurations
├── rules/
│   ├── compliance/          # GDPR, HIPAA rules (from onboarding)
│   └── behavior/            # Style, brand rules (from onboarding)
├── shared/                  # Shared knowledge base
├── users/
│   └── default/
│       ├── INDEX.md          # Warm memory index (empty)
│       └── memory/           # Memory notes directory
└── system/
    ├── prompts/             # Prompt YAML files
    └── state/               # SQLite DB auto-created here
```

### 5.2 VaultOps Class

```python
class VaultOps:
    """Filesystem operations for the TAIM Vault.
    
    Handles vault initialization, config loading, and path resolution.
    All paths are resolved to absolute at construction time.
    """

    def __init__(self, vault_path: Path):
        resolved = vault_path.resolve()
        # Validate vault path is usable (Review Item #9)
        if resolved.exists() and not resolved.is_dir():
            raise VaultError(
                user_message=f"The vault path '{vault_path}' points to a file, not a directory.",
                detail=f"Vault path {resolved} exists but is not a directory",
            )
        self.vault_config = VaultConfig.from_root(resolved)

    def ensure_vault(self) -> None:
        """Create vault structure if it doesn't exist. Idempotent."""
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
            # Review Item #5: Human-friendly permission errors
            raise VaultError(
                user_message=f"TAIM can't create its data directory. Please check file permissions for '{self.vault_config.vault_root}'.",
                detail=f"PermissionError creating {e.filename}: {e}",
            ) from e

        # Create default INDEX.md if missing
        index_path = self.vault_config.users_dir / "default" / "INDEX.md"
        if not index_path.exists():
            index_path.write_text("# Memory Index\n\n<!-- Entries added automatically -->\n")

        # Write default config files only if missing (never overwrite)
        self._ensure_default_configs()

    def load_product_config(self) -> ProductConfig:
        """Load and validate all YAML config files into ProductConfig."""
        taim_cfg = self._load_yaml("taim.yaml")
        providers_cfg = self._load_yaml("providers.yaml")
        defaults_cfg = self._load_yaml("defaults.yaml")
        # ... merge into ProductConfig with validation

    def _load_yaml(self, filename: str) -> dict:
        """Load a YAML file from the config directory with error handling."""
        path = self.vault_config.config_dir / filename
        if not path.exists():
            raise ConfigError(
                user_message=f"Configuration file '{filename}' is missing from the vault.",
                detail=f"Expected config file not found: {path}",
            )
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            # Review Item #3: YAML parse errors as ConfigError
            raise ConfigError(
                user_message=f"Configuration file '{filename}' has a syntax error. Please check the file format.",
                detail=f"YAML parse error in {path}: {e}",
            ) from e
```

### 5.3 Idempotency Contract

- `mkdir(parents=True, exist_ok=True)` — directory creation is always safe
- Config files: check `if not path.exists()` before writing — never overwrite user edits
- INDEX.md: same check — never overwrite
- DB: handled by database.py (see Section 6)

### 5.4 Path Resolution

All paths are resolved to absolute at `VaultConfig.from_root()` time via `vault_path.resolve()`. This eliminates CWD-sensitivity: no matter where `uvicorn` is started from, if `TAIM_VAULT_PATH=/home/user/my-vault`, all paths are absolute and correct.

---

## 6. SQLite Schema

### 6.1 Configuration

Per AD-8 and NFR-04:
- Path: `{vault_root}/system/state/taim.db`
- WAL mode (better concurrent reads)
- Foreign keys ON
- busy_timeout 5000ms (prevents "database is locked" on concurrent writes)

### 6.2 Schema (Version 1)

```sql
-- Schema versioning
CREATE TABLE schema_version (
    version   INTEGER NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Per-LLM-call token tracking (NFR-20)
CREATE TABLE token_tracking (
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

-- Active and completed tasks
CREATE TABLE task_state (
    task_id        TEXT PRIMARY KEY,
    team_id        TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending',
    objective      TEXT,
    agent_states   TEXT,    -- JSON serialized dict
    token_total    INTEGER DEFAULT 0,
    cost_total_eur REAL DEFAULT 0.0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at   TEXT
);

-- Chat session persistence (hot memory rebuild on crash, NFR-06)
CREATE TABLE session_state (
    session_id      TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL DEFAULT 'default',
    messages        TEXT,    -- JSON array (last 20 messages for hot memory rebuild)
    session_summary TEXT,
    has_summary     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Agent execution log (audit trail, NFR-21)
CREATE TABLE agent_runs (
    run_id             TEXT PRIMARY KEY,
    agent_name         TEXT NOT NULL,
    task_id            TEXT NOT NULL,
    team_id            TEXT NOT NULL,
    session_id         TEXT,
    state_history      TEXT,    -- JSON array of state transitions
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
```

### 6.3 Indexes

```sql
-- Token aggregation queries (Stats view)
CREATE INDEX idx_token_tracking_task ON token_tracking(task_id);
CREATE INDEX idx_token_tracking_session ON token_tracking(session_id);
CREATE INDEX idx_token_tracking_agent_run ON token_tracking(agent_run_id);
CREATE INDEX idx_token_tracking_created ON token_tracking(created_at);

-- Task filtering
CREATE INDEX idx_task_state_team ON task_state(team_id);
CREATE INDEX idx_task_state_status ON task_state(status);

-- Session lookup
CREATE INDEX idx_session_state_user ON session_state(user_id);

-- Agent run aggregation
CREATE INDEX idx_agent_runs_task ON agent_runs(task_id);
CREATE INDEX idx_agent_runs_team ON agent_runs(team_id);
```

### 6.4 Migration Strategy

Simple integer versioning per PRD Section 8.3:

```python
SCHEMA_VERSION = 1

async def init_database(db_path: Path) -> aiosqlite.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(db_path))

    # Pragmas
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")

    # Check and apply migrations
    current_version = await _get_schema_version(db)
    if current_version < SCHEMA_VERSION:
        await _apply_migrations(db, current_version)

    return db

async def _get_schema_version(db: aiosqlite.Connection) -> int:
    """Returns 0 if no schema exists yet."""
    try:
        async with db.execute("SELECT MAX(version) FROM schema_version") as cursor:
            row = await cursor.fetchone()
            return row[0] if row and row[0] else 0
    except aiosqlite.OperationalError:
        return 0  # Table doesn't exist → fresh DB

async def _apply_migrations(db: aiosqlite.Connection, from_version: int) -> None:
    """Apply all migrations from from_version to SCHEMA_VERSION."""
    migrations = {
        1: SCHEMA_V1_SQL,
        # Future: 2: SCHEMA_V2_SQL, etc.
    }
    for version in range(from_version + 1, SCHEMA_VERSION + 1):
        await db.executescript(migrations[version])
        await db.execute(
            "INSERT INTO schema_version (version) VALUES (?)", (version,)
        )
        await db.commit()
```

### 6.5 Connection Management

The database connection is created once in the lifespan and stored in `app.state`. For Step 1 (single-user), this is sufficient. Phase 3 (multi-user) would introduce a connection pool.

`aiosqlite` connections are not thread-safe, but FastAPI with uvicorn uses a single event loop, so this is safe. With `--workers N`, each worker gets its own connection — WAL mode handles concurrent access.

---

## 7. PromptLoader

### 7.1 Design

```python
from pathlib import Path
from jinja2.sandbox import SandboxedEnvironment
from jinja2 import StrictUndefined, UndefinedError
import yaml

class PromptLoader:
    """Loads prompt templates from vault YAML files with Jinja2 rendering.

    Prompts are cached in memory with mtime-based invalidation.
    Uses SandboxedEnvironment for defense-in-depth — prevents template
    access to Python internals even if non-string variables are passed
    in future steps (memory objects, agent state, etc.).
    """

    def __init__(self, prompts_dir: Path):
        self._dir = prompts_dir
        self._cache: dict[str, tuple[float, dict]] = {}
        self._jinja = SandboxedEnvironment(undefined=StrictUndefined)

    def load(self, prompt_name: str, variables: dict[str, str] | None = None) -> str:
        """Load a prompt, substitute variables, return rendered string.

        Raises:
            PromptNotFoundError: Prompt YAML file doesn't exist.
            PromptVariableError: A required variable is missing.
        """
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
        """Return prompt metadata (name, description, model_tier, version) without rendering."""
        data = self._load_cached(prompt_name)
        return {k: v for k, v in data.items() if k != "template"}

    def _load_cached(self, prompt_name: str) -> dict:
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

### 7.2 Prompt YAML Format

Per AD-1, enriched with metadata:

```yaml
# taim-vault/system/prompts/intent-classify.yaml
name: intent-classify
version: 1
description: "Stage 1 — classify user message into intent category"
model_tier: tier3_economy
variables:
  - user_message
  - session_context
template: |
  You are TAIM's intent classifier.

  User message: {{ user_message }}
  Recent context: {{ session_context }}

  Classify into exactly one category:
  - new_task: User wants to start a new task
  - confirmation: User confirms or approves
  - follow_up: User adds to existing task
  - status_query: User asks what's happening
  - configuration: User changes settings
  - stop_command: User wants to stop
  - onboarding_response: User answers onboarding question

  Respond with JSON:
  {
    "category": "<category>",
    "confidence": <0.0-1.0>,
    "needs_deep_analysis": <true|false>
  }
```

Note: `{` in the JSON output instruction works perfectly — Jinja2 only interprets `{{ }}`, not bare `{ }`.

### 7.3 Prompt Files Created in Step 1

Step 1 does NOT create all 20+ prompts (those come in Steps 2-9 as needed). Step 1 creates:
- The `system/prompts/` directory
- One example prompt: `health-check.yaml` (used in integration tests to verify PromptLoader works end-to-end)

---

## 8. FastAPI Application

### 8.1 Lifespan (Startup / Shutdown)

```python
from contextlib import asynccontextmanager
import structlog

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # === STARTUP ===
    settings = TaimSettings()
    configure_logging(settings.log_level, settings.log_format)

    # 1. Vault init
    vault_ops = VaultOps(settings.vault_path)
    vault_ops.ensure_vault()

    # 2. Load product config + raw YAML for server config
    taim_yaml = vault_ops.load_raw_yaml("taim.yaml")
    product_config = vault_ops.load_product_config()

    # 3. Build server config (YAML baseline + ENV override)
    server_config = ServerConfig.from_yaml_and_env(taim_yaml.get("server", {}))

    # 4. Compose system config
    system_config = SystemConfig(
        server=server_config,
        vault=vault_ops.vault_config,
        product=product_config,
        settings=settings,
    )

    # 5. Database init
    db = await init_database(system_config.vault.db_path)

    # 6. PromptLoader init
    prompt_loader = PromptLoader(system_config.vault.prompts_dir)

    # Store in app.state for dependency injection
    app.state.config = system_config
    app.state.db = db
    app.state.prompt_loader = prompt_loader

    logger.info(
        "taim.started",
        vault=str(system_config.vault.vault_root),
        host=server_config.host,
        port=server_config.port,
        providers=[p.name for p in product_config.providers],
        db=str(system_config.vault.db_path),
    )

    yield  # App is running

    # === SHUTDOWN ===
    await db.close()
    logger.info("taim.stopped")
```

### 8.2 App Configuration

```python
app = FastAPI(
    title="TAIM",
    description="Team AI Manager — AI team orchestration through natural language",
    version="0.1.0",
    lifespan=lifespan,
)
```

**CORS timing:** `CORSMiddleware` must be added at module import time (before lifespan). But CORS origins now live in `taim.yaml` — which isn't loaded until the lifespan runs.

Solution: CORS is added inside the lifespan after config is loaded, using FastAPI's `app.add_middleware()`. This works because middleware is resolved on the first request, not at app creation time. Alternatively, a two-pass approach reads only the CORS origins from YAML at import time. The cleaner approach:

```python
# main.py — CORS added in lifespan after config is available
# Inside lifespan, after system_config is built:
app.add_middleware(
    CORSMiddleware,
    allow_origins=server_config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Note:** If this causes timing issues with FastAPI (middleware not taking effect), fallback is to read CORS from `taim.yaml` directly at module level with a minimal YAML parse — no full config loading needed.

### 8.3 Health Endpoint

```python
# api/health.py
@router.get("/health")
async def health(
    config: SystemConfig = Depends(get_config),
    db: aiosqlite.Connection = Depends(get_db),
):
    provider_names = [p.name for p in config.product.providers]
    vault_ok = config.vault.vault_root.exists()

    # Review Item #4: Verify DB connectivity
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

Mounted at both `/health` (infrastructure probes) and `/api/health` (API consumers).

### 8.4 WebSocket Stub

```python
# api/chat.py (minimal stub for Step 1)
@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            # Echo back with server timestamp — proves connection works
            await websocket.send_json({
                "type": "system",
                "content": f"Connected to session {session_id}. Full chat in Step 3.",
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
            })
    except WebSocketDisconnect:
        pass
```

This stub lets the frontend team verify WebSocket connectivity works before Step 3 implements real chat.

### 8.5 Dependency Injection

```python
# api/deps.py
from fastapi import Request

def get_config(request: Request) -> SystemConfig:
    return request.app.state.config

def get_db(request: Request) -> aiosqlite.Connection:
    return request.app.state.db

def get_prompt_loader(request: Request) -> PromptLoader:
    return request.app.state.prompt_loader
```

**Why `app.state` + `Depends()` and not a global?**
- Testable: in tests, create a test app with `app.state.config = MockConfig()`
- No module-level side effects
- FastAPI idiomatic

---

## 9. Error System

### 9.1 Dual Personality

Every TAIM error has two faces:
- `user_message`: What the user sees (friendly, actionable, no technical jargon)
- `detail`: What gets logged (specific, debuggable, includes paths/values)

This directly serves the AI Equalizer principle: a marketing manager sees "I couldn't find my configuration files" while the developer sees `FileNotFoundError: taim-vault/config/providers.yaml`.

### 9.2 Error Hierarchy

```python
# errors.py

class TaimError(Exception):
    """Base error with user-facing and developer-facing messages."""
    def __init__(self, user_message: str, detail: str | None = None):
        self.user_message = user_message
        self.detail = detail or user_message
        super().__init__(self.detail)

class VaultError(TaimError):
    """Vault filesystem errors."""
    pass

class ConfigError(TaimError):
    """Configuration loading/validation errors."""
    pass

class DatabaseError(TaimError):
    """SQLite errors."""
    pass

class PromptNotFoundError(TaimError):
    """Requested prompt YAML file doesn't exist."""
    def __init__(self, prompt_name: str, path: Path):
        super().__init__(
            user_message=f"A required prompt template '{prompt_name}' is missing from the vault.",
            detail=f"Prompt file not found: {path}",
        )

class PromptVariableError(TaimError):
    """A template variable was required but not provided."""
    def __init__(self, prompt_name: str, variable: str):
        super().__init__(
            user_message="An internal configuration error occurred. Please check the logs.",
            detail=f"Missing variable '{variable}' in prompt '{prompt_name}'",
        )
```

### 9.3 FastAPI Error Handler

```python
# main.py
@app.exception_handler(TaimError)
async def taim_error_handler(request: Request, exc: TaimError):
    logger.error("taim.error", detail=exc.detail, user_message=exc.user_message)
    return JSONResponse(
        status_code=500,
        content={"error": exc.user_message, "type": type(exc).__name__},
    )
```

---

## 10. Structured Logging

### 10.1 Configuration

```python
import structlog

def configure_logging(log_level: str, log_format: str) -> None:
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.contextvars.merge_contextvars,
    ]

    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
    )
```

### 10.2 Log Events for Step 1

| Event | Level | When |
|-------|-------|------|
| `taim.started` | INFO | Server startup complete |
| `taim.stopped` | INFO | Server shutdown |
| `vault.initialized` | INFO | Vault created on first run |
| `vault.exists` | DEBUG | Vault already existed |
| `db.initialized` | INFO | Database schema created |
| `db.migrated` | INFO | Schema migration applied |
| `config.loaded` | INFO | YAML configs parsed successfully |
| `config.error` | ERROR | YAML parse/validation failure |
| `prompt.loaded` | DEBUG | Prompt loaded from cache or disk |
| `prompt.cache_miss` | DEBUG | Prompt loaded from disk (cache miss or invalidated) |

---

## 11. Dependency Updates

### 11.1 pyproject.toml Changes

**Add to `dependencies`:**
```toml
"jinja2>=3.1.0",
"structlog>=24.1.0",
"python-frontmatter>=1.1.0",   # Needed from Step 4, add now
"tiktoken>=0.7.0",              # Needed from Step 2, add now
```

**Remove from PRD "must add" list:**
- `python-dotenv` — replaced by `pydantic-settings` built-in `.env` support

**Add to `dev` dependencies:**
```toml
"pytest-mock>=3.14.0",
```

**Note on `keyring`:** PRD UX spec mentions keyring for API key storage. This is a Step 9 (Onboarding) concern, not Step 1. We do NOT add it now.

### 11.2 Already Present (no changes needed)
- `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `pyyaml`, `aiosqlite`, `aiofiles` — all in current `pyproject.toml`

---

## 12. Test Strategy

### 12.1 Shared Fixtures

```python
# tests/backend/conftest.py

@pytest.fixture
def clean_env(monkeypatch):
    """Review Item #8: Isolate ENV variables between tests.
    Removes all TAIM_* env vars to prevent test pollution."""
    for key in list(os.environ.keys()):
        if key.startswith("TAIM_"):
            monkeypatch.delenv(key, raising=False)
    # Also clear provider key vars
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

@pytest.fixture
def tmp_vault(tmp_path: Path, clean_env) -> Path:
    """Create a temporary vault with default structure and test configs."""
    vault = tmp_path / "taim-vault"
    ops = VaultOps(vault)
    ops.ensure_vault()
    # Write test-specific configs
    _write_test_providers(vault / "config" / "providers.yaml")
    _write_test_defaults(vault / "config" / "defaults.yaml")
    _write_test_taim_yaml(vault / "config" / "taim.yaml")
    return vault

@pytest.fixture
async def test_db(tmp_vault: Path) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Initialize a test database with schema."""
    db_path = tmp_vault / "system" / "state" / "taim.db"
    db = await init_database(db_path)
    yield db
    await db.close()

@pytest.fixture
def prompt_loader(tmp_vault: Path) -> PromptLoader:
    """PromptLoader with test prompts directory."""
    prompts_dir = tmp_vault / "system" / "prompts"
    # Write a test prompt
    (prompts_dir / "test-prompt.yaml").write_text(
        'name: test-prompt\nversion: 1\ntemplate: "Hello {{ name }}"\n'
    )
    return PromptLoader(prompts_dir)
```

### 12.2 Test Files

| Test File | Tests | Target Module |
|-----------|-------|---------------|
| `test_settings.py` | ENV loading, defaults, .env file override | `settings.py` |
| `test_config.py` | YAML parsing, ProductConfig validation, VaultConfig paths | `models/config.py` |
| `test_vault.py` | Vault creation, idempotency, config loading, path resolution | `brain/vault.py` |
| `test_database.py` | Schema creation, WAL mode, migrations, version check | `brain/database.py` |
| `test_prompts.py` | Load, cache, Jinja2 rendering, missing var error, missing file error | `brain/prompts.py` |
| `test_errors.py` | Dual personality (user_message vs detail), hierarchy | `errors.py` |
| `test_health.py` | Health endpoint response, degraded state | `api/health.py` |
| `test_main.py` | App startup/shutdown, lifespan, CORS | `main.py` (integration) |

### 12.3 Coverage Target

Step 1 modules must hit >80% line coverage (NFR-16). The main gap will be error branches in config loading (malformed YAML etc.) — ensure those are tested.

---

## 13. Implementation Order

Within Step 1, build bottom-up following the dependency graph:

```
Phase A (parallel — no TAIM dependencies):
  ├── errors.py
  ├── settings.py
  └── models/config.py

Phase B (depends on Phase A):
  ├── brain/vault.py
  ├── brain/database.py
  └── brain/prompts.py

Phase C (depends on Phase B):
  ├── api/deps.py
  ├── api/health.py
  └── main.py

Phase D (depends on all above):
  └── tests/backend/*
```

Phases A can be fully parallelized (3 independent files). Phase B can be partially parallelized (vault.py depends on models, but database.py and prompts.py don't depend on each other). Phase C composes. Phase D validates.

---

## 14. Design Notes & Constraints

### 14.1 Sync I/O in Async Context (Review Item #7)

VaultOps uses synchronous file I/O (`Path.read_text()`, `mkdir()`) inside the async lifespan. This is deliberate for Step 1:

- **At startup:** Config YAML files are <2KB each. Sync reads take <1ms. Event loop blocking is negligible.
- **At request time:** Step 1 has no request-time file I/O. The PromptLoader reads files only on cache miss (startup or file change).
- **From Step 4 onward:** Memory writes during request handling MUST use `aiofiles`. When implementing Step 4 (Memory System), add async methods to VaultOps for request-time operations.

### 14.2 Vault Path from ENV vs YAML

The vault path (`TAIM_VAULT_PATH`) is deliberately ENV-only with no YAML counterpart. Reason: the vault path determines WHERE the YAML files are — it cannot be read FROM the YAML files (chicken-and-egg). This is the one setting where ENV is the only source of truth.

---

## Appendix: Review Log

Design reviewed via Devil's Advocate (full 6-dimension framework) and Meta-Review (challenging the DA output).

### Items Applied

| # | Item | Source | Section Modified |
|---|------|--------|------------------|
| 1 | YAML as canonical config, ENV overrides via `os.environ.get()` | DA + Meta-Review | §4 Config System |
| 2 | `SandboxedEnvironment` for future-proofing against non-string variables | DA (corrected reasoning) | §7 PromptLoader |
| 3 | YAML parse errors wrapped as `ConfigError` | DA | §5.2 VaultOps |
| 4 | DB health check in `/health` endpoint | DA | §8.3 Health Endpoint |
| 5 | `PermissionError` handling in vault init | DA | §5.2 VaultOps |
| 6 | `usd_to_eur_rate` in `taim.yaml` tracking section | DA (corrected placement) | §4.3 taim.yaml |
| 7 | Sync I/O documented as deliberate for Step 1, async from Step 4 | Meta-Review (DA missed) | §14.1 |
| 8 | ENV isolation fixture in test conftest | Meta-Review (DA missed) | §12.1 |
| 9 | Vault path validation (file-not-dir check) | Meta-Review (DA missed) | §5.2 VaultOps |

### Items Evaluated and Not Applied

| Item | Reason |
|------|--------|
| Dynaconf instead of pydantic-settings | Comparable but less Pydantic-idiomatic for our stack |
| SQLAlchemy + Alembic | Over-engineered for 4 tables in Phase 1 |
| Custom `PydanticBaseSettingsSource` for YAML | ~40 lines for 3 fields — `os.environ.get()` achieves the same in 5 lines |

---

*End of Step 1 Foundation Design.*
