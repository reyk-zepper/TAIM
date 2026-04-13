"""VaultOps — tAIm Vault filesystem operations."""

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
# tAIm — Main Configuration
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
# tAIm — LLM Provider Configuration
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
# tAIm — Smart Defaults
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

_DEFAULT_INTENT_CLASSIFIER_PROMPT = """\
name: intent-classifier
version: 1
description: "Stage 1 — classify user message into intent category"
model_tier: tier3_economy
variables:
  - user_message
  - recent_context
template: |
  You are tAIm's intent classifier. Classify the user's message into ONE category.

  Recent context (last few messages):
  {{ recent_context }}

  User message: "{{ user_message }}"

  Categories:
  - new_task: User wants to start a new task or project
  - confirmation: User confirms or approves something ("yes", "go ahead", "do it")
  - follow_up: User adds to or modifies an existing task
  - status_query: User asks about current status ("what's happening?", "status?")
  - configuration: User wants to change settings or preferences
  - stop_command: User wants to stop ("stop", "cancel", "halt")
  - onboarding_response: User answers an onboarding question

  Respond with JSON only, no markdown:
  {
    "category": "<one of the categories above>",
    "confidence": <0.0 to 1.0>,
    "needs_deep_analysis": <true if message is complex/ambiguous, false if clear>
  }
"""

_DEFAULT_INTENT_INTERPRETER_PROMPT = """\
name: intent-interpreter
version: 1
description: "Stage 2 — extract structured task command from user message"
model_tier: tier2_standard
variables:
  - user_message
  - recent_context
  - user_preferences
template: |
  You are tAIm's intent interpreter. Extract a structured task command from the user's message.

  User preferences (from memory):
  {{ user_preferences }}

  Recent context:
  {{ recent_context }}

  User message: "{{ user_message }}"

  Extract:
  - task_type: short label (e.g., "research", "code_review", "content_creation")
  - objective: one-sentence description of what the user wants achieved
  - parameters: dict of specific values (URLs, names, file paths) mentioned
  - constraints: time/budget limits if mentioned
  - missing_info: list of critical info NOT in the message but needed
  - suggested_team: optional list of agent role names that fit the task

  If anything critical is missing, include it in missing_info — do NOT guess.

  Respond with JSON only, no markdown:
  {
    "task_type": "<string>",
    "objective": "<string>",
    "parameters": {},
    "constraints": {
      "time_limit_seconds": null,
      "budget_eur": null
    },
    "missing_info": [],
    "suggested_team": []
  }
"""

_DEFAULT_SESSION_SUMMARIZER_PROMPT = """\
name: session-summarizer
version: 1
description: "Summarize an older chat transcript into a compact warm-memory entry"
model_tier: tier3_economy
variables:
  - transcript
template: |
  You are tAIm's session summarizer. Compress the following chat transcript
  into a concise summary (3-5 sentences max).

  Focus on:
  - What the user was trying to achieve
  - Key decisions made
  - Outcomes or partial results
  - Anything the user will need to remember later

  Do NOT include trivial exchanges (greetings, confirmations).

  Transcript:
  {{ transcript }}

  Respond with plain text (no markdown, no JSON, no headers).
"""

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

_DEFAULT_AGENT_CODER = """\
name: coder
description: Writes, edits, and explains code
model_preference:
  - tier1_premium
  - tier2_standard
skills:
  - code_generation
  - refactoring
  - code_explanation
tools:
  - file_read
  - file_write
max_iterations: 3
requires_approval_for:
  - file_deletion
  - external_communication
"""

_DEFAULT_AGENT_REVIEWER = """\
name: reviewer
description: Reviews work products for quality, completeness, and correctness
model_preference:
  - tier1_premium
skills:
  - code_review
  - quality_assessment
  - content_review
tools:
  - file_read
max_iterations: 2
requires_approval_for: []
"""

_DEFAULT_AGENT_WRITER = """\
name: writer
description: Creates written content — articles, emails, documentation
model_preference:
  - tier2_standard
skills:
  - content_writing
  - editing
  - tone_adaptation
tools:
  - file_read
  - file_write
  - vault_memory_read
max_iterations: 3
requires_approval_for:
  - external_communication
"""

_DEFAULT_AGENT_ANALYST = """\
name: analyst
description: Analyzes data and synthesizes insights
model_preference:
  - tier1_premium
  - tier2_standard
skills:
  - data_analysis
  - pattern_recognition
  - insight_synthesis
tools:
  - file_read
  - vault_memory_read
max_iterations: 3
requires_approval_for: []
"""

_DEFAULT_STATE_PROMPT_PLANNING = """\
name: agents/default/planning
version: 1
description: Default PLANNING prompt — agent analyzes task and proposes an approach
model_tier: tier2_standard
variables:
  - task_description
  - agent_description
  - user_preferences
template: |
  You are a {{ agent_description }}.

  Your task: {{ task_description }}

  User preferences:
  {{ user_preferences }}

  Think through how you will approach this task. Output a concise plan (3-6 bullet points).
  Do not execute yet. Just plan.
"""

_DEFAULT_STATE_PROMPT_EXECUTING = """\
name: agents/default/executing
version: 1
description: Default EXECUTING prompt — agent carries out the plan
model_tier: tier2_standard
variables:
  - task_description
  - agent_description
  - plan
  - iteration
  - user_preferences
template: |
  You are a {{ agent_description }}.

  Task: {{ task_description }}

  Your plan:
  {{ plan }}

  Iteration: {{ iteration }}

  User preferences:
  {{ user_preferences }}

  Execute the plan and produce the result.
"""

_DEFAULT_STATE_PROMPT_REVIEWING = """\
name: agents/default/reviewing
version: 1
description: Default REVIEWING prompt — agent self-assesses its output
model_tier: tier2_standard
variables:
  - task_description
  - current_result
template: |
  You are a critical reviewer. Assess the following result against the task.

  Task: {{ task_description }}

  Result:
  {{ current_result }}

  Respond with JSON only:
  {
    "quality_ok": <true | false>,
    "feedback": "<specific feedback — what is good, what needs improvement>"
  }

  quality_ok=true only if the result fully satisfies the task.
"""

_DEFAULT_STATE_PROMPT_ITERATING = """\
name: agents/default/iterating
version: 1
description: Default ITERATING prompt — agent improves based on review feedback
model_tier: tier2_standard
variables:
  - task_description
  - current_result
  - review_feedback
template: |
  Improve the following result based on the review feedback.

  Task: {{ task_description }}

  Previous result:
  {{ current_result }}

  Reviewer feedback:
  {{ review_feedback }}

  Produce an improved result that addresses the feedback.
"""

_RESEARCHER_EXECUTING_OVERRIDE = """\
name: agents/researcher/executing
version: 1
description: Researcher-specific EXECUTING prompt — emphasizes source verification
model_tier: tier2_standard
variables:
  - task_description
  - agent_description
  - plan
  - iteration
  - user_preferences
template: |
  You are a researcher. Verify sources, prefer primary data, and cite specifics.

  Task: {{ task_description }}

  Your plan:
  {{ plan }}

  Iteration: {{ iteration }}

  User preferences:
  {{ user_preferences }}

  Execute the plan. Cite sources. Avoid speculation.
"""

_DEFAULT_TOOL_FILE_READ = """\
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
"""

_DEFAULT_TOOL_FILE_WRITE = """\
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
"""

_DEFAULT_TOOL_VAULT_MEMORY_READ = """\
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
"""

_DEFAULT_TOOL_VAULT_MEMORY_WRITE = """\
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
"""

_DEFAULT_SKILL_WEB_RESEARCH = """\
name: web_research
description: Search the web, fetch pages, and synthesize findings from multiple sources
required_tools: [web_search, web_fetch, file_write]
output_format: markdown
prompt_template: |
  You are conducting web research on the task below.

  Approach:
  1. Use web_search to identify 3-5 high-quality sources
  2. Use web_fetch to retrieve full content from the most promising
  3. Cross-reference findings — never trust a single source
  4. Cite specific URLs and quote when possible

  Output a structured summary in markdown with:
  - Key findings (bullet points)
  - Sources (URL + 1-line description)
  - Open questions or contradictions found
"""

_DEFAULT_SKILL_CODE_GENERATION = """\
name: code_generation
description: Write, modify, and explain code with attention to existing conventions
required_tools: [file_read, file_write]
output_format: markdown
prompt_template: |
  You are writing code as part of an existing project.

  Approach:
  1. Read existing files (file_read) to understand conventions before writing
  2. Match the existing style — naming, indentation, idioms
  3. Write minimal, focused code — no speculative abstractions
  4. After writing, briefly explain what you did and why

  When writing files, use file_write with clear file paths.
"""

_DEFAULT_SKILL_CODE_REVIEW = """\
name: code_review
description: Review code for correctness, security, performance, and maintainability
required_tools: [file_read]
output_format: markdown
prompt_template: |
  You are reviewing code. Be specific and constructive.

  Focus areas (in order):
  1. Correctness — does it do what it claims?
  2. Security — input validation, secret handling, injection risks
  3. Maintainability — clarity, naming, structure
  4. Performance — only if obviously problematic

  Output:
  - Critical issues (must fix)
  - Important suggestions (should consider)
  - Minor notes (nice to have)

  Reference specific file:line locations. Avoid vague feedback.
"""

_DEFAULT_SKILL_CONTENT_WRITING = """\
name: content_writing
description: Write structured documents — reports, articles, summaries, emails
required_tools: [file_write]
output_format: markdown
prompt_template: |
  You are writing content for a specific audience and purpose.

  Approach:
  1. Identify the target reader and the action you want them to take
  2. Lead with the most important information
  3. Use plain language — replace jargon with concrete terms
  4. Match the requested tone (formal, casual, technical, marketing)

  Structure: clear headings, short paragraphs, bullet points where lists help.
"""

_DEFAULT_SKILL_DATA_ANALYSIS = """\
name: data_analysis
description: Analyze structured data and synthesize insights with comparisons
required_tools: [file_read]
output_format: markdown
prompt_template: |
  You are analyzing data to produce insights.

  Approach:
  1. Read input data carefully — note structure, types, completeness
  2. Identify patterns, outliers, comparisons that matter for the question
  3. Quantify where possible — exact numbers beat vague claims
  4. Distinguish observations (what the data shows) from inferences (what you conclude)

  Output:
  - Summary (2-3 sentences)
  - Key findings (with numbers)
  - Notable patterns or anomalies
  - Caveats — what the data does NOT tell us
"""


class VaultOps:
    """Filesystem operations for the tAIm Vault."""

    def __init__(self, vault_path: Path) -> None:
        resolved = vault_path.resolve()
        if resolved.exists() and not resolved.is_dir():
            raise VaultError(
                user_message=f"The vault path '{vault_path}' points to a file, not a directory.",
                detail=f"Vault path {resolved} points to a file, not a directory",
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
                    "tAIm can't create its data directory. "
                    f"Please check file permissions for '{self.vault_config.vault_root}'."
                ),
                detail=f"PermissionError creating directory: {e}",
            ) from e

        index_path = self.vault_config.users_dir / "default" / "INDEX.md"
        if not index_path.exists():
            index_path.write_text("# Memory Index\n\n<!-- Entries added automatically -->\n")

        self._ensure_default_configs()
        self._ensure_default_prompts()
        self._ensure_default_agents()
        self._ensure_default_state_prompts()
        self._ensure_default_tools()
        self._ensure_default_skills()

    def load_raw_yaml(self, filename: str) -> dict:
        """Load a YAML file from the config directory."""
        path = self.vault_config.config_dir / filename
        if not path.exists():
            raise ConfigError(
                user_message=f"Configuration file '{filename}' is missing from the vault.",
                detail=f"Configuration file '{filename}' is missing from the vault: {path}",
            )
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise ConfigError(
                user_message=(
                    f"Configuration file '{filename}' has a syntax error. "
                    "Please check the file format."
                ),
                detail=f"Configuration file '{filename}' has a syntax error in {path}: {e}",
            ) from e

    def load_product_config(self) -> ProductConfig:
        """Load and validate all YAML config files into ProductConfig."""
        taim_cfg = self.load_raw_yaml("taim.yaml")
        providers_cfg = self.load_raw_yaml("providers.yaml")
        defaults_cfg = self.load_raw_yaml("defaults.yaml")

        providers = [ProviderConfig(**p) for p in providers_cfg.get("providers", [])]
        tiering = {
            name: TierConfig(**tier) for name, tier in providers_cfg.get("tiering", {}).items()
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

    def _ensure_default_prompts(self) -> None:
        """Write default prompt YAML files only if they don't exist."""
        defaults = {
            "intent-classifier.yaml": _DEFAULT_INTENT_CLASSIFIER_PROMPT,
            "intent-interpreter.yaml": _DEFAULT_INTENT_INTERPRETER_PROMPT,
            "session-summarizer.yaml": _DEFAULT_SESSION_SUMMARIZER_PROMPT,
        }
        for filename, content in defaults.items():
            path = self.vault_config.prompts_dir / filename
            if not path.exists():
                path.write_text(content, encoding="utf-8")

    def _ensure_default_agents(self) -> None:
        """Write default agent YAML files only if they don't exist."""
        defaults = {
            "researcher.yaml": _DEFAULT_AGENT_RESEARCHER,
            "coder.yaml": _DEFAULT_AGENT_CODER,
            "reviewer.yaml": _DEFAULT_AGENT_REVIEWER,
            "writer.yaml": _DEFAULT_AGENT_WRITER,
            "analyst.yaml": _DEFAULT_AGENT_ANALYST,
        }
        for filename, content in defaults.items():
            path = self.vault_config.agents_dir / filename
            if not path.exists():
                path.write_text(content, encoding="utf-8")

    def _ensure_default_state_prompts(self) -> None:
        """Seed default per-state prompts and researcher override."""
        default_dir = self.vault_config.prompts_dir / "agents" / "default"
        researcher_dir = self.vault_config.prompts_dir / "agents" / "researcher"
        default_dir.mkdir(parents=True, exist_ok=True)
        researcher_dir.mkdir(parents=True, exist_ok=True)

        defaults = {
            default_dir / "planning.yaml": _DEFAULT_STATE_PROMPT_PLANNING,
            default_dir / "executing.yaml": _DEFAULT_STATE_PROMPT_EXECUTING,
            default_dir / "reviewing.yaml": _DEFAULT_STATE_PROMPT_REVIEWING,
            default_dir / "iterating.yaml": _DEFAULT_STATE_PROMPT_ITERATING,
            researcher_dir / "executing.yaml": _RESEARCHER_EXECUTING_OVERRIDE,
        }
        for path, content in defaults.items():
            if not path.exists():
                path.write_text(content, encoding="utf-8")

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

    def _ensure_default_skills(self) -> None:
        """Seed default skill YAML definitions."""
        skills_dir = self.vault_config.vault_root / "system" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        defaults = {
            "web_research.yaml": _DEFAULT_SKILL_WEB_RESEARCH,
            "code_generation.yaml": _DEFAULT_SKILL_CODE_GENERATION,
            "code_review.yaml": _DEFAULT_SKILL_CODE_REVIEW,
            "content_writing.yaml": _DEFAULT_SKILL_CONTENT_WRITING,
            "data_analysis.yaml": _DEFAULT_SKILL_DATA_ANALYSIS,
        }
        for filename, content in defaults.items():
            path = skills_dir / filename
            if not path.exists():
                path.write_text(content, encoding="utf-8")
