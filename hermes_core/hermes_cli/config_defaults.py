# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Default configuration tree for hermes_cli.

Extracted verbatim from ``hermes_cli/config.py`` to shrink that module. Pure
data, no logic; ``hermes_cli.config`` re-exports ``DEFAULT_CONFIG`` so existing
imports keep working.
"""

from __future__ import annotations

DEFAULT_CONFIG = {
    "model": "",
    "providers": {},
    "fallback_providers": [],
    "credential_pool_strategies": {},
    "toolsets": ["hermes-cli"],
    "agent": {
        "max_turns": 90,
        # Inactivity timeout for gateway agent execution (seconds).
        # The agent can run indefinitely as long as it's actively calling
        # tools or receiving API responses.  Only fires when the agent has
        # been completely idle for this duration.  0 = unlimited.
        "gateway_timeout": 1800,
        # Graceful drain timeout for gateway stop/restart (seconds).
        # The gateway stops accepting new work, waits for running agents
        # to finish, then interrupts any remaining runs after the timeout.
        # 0 = no drain, interrupt immediately.
        "restart_drain_timeout": 60,
        # Max app-level retry attempts for API errors (connection drops,
        # provider timeouts, 5xx, etc.) before the agent surfaces the
        # failure.  The OpenAI SDK already does its own low-level retries
        # (max_retries=2 default) for transient network errors; this is
        # the Hermes-level retry loop that wraps the whole call.  Lower
        # this to 1 if you use fallback providers and want fast failover
        # on flaky primaries; raise it if you prefer to tolerate longer
        # provider hiccups on a single provider.
        "api_max_retries": 3,
        "service_tier": "",
        # Reasoning effort for the main agent. First-run desktop onboarding
        # should start at high so cheaper/weaker models get stronger reasoning
        # on coding and math tasks. Users can lower this with /reasoning.
        "reasoning_effort": "high",
        # Tool-use enforcement: injects system prompt guidance that tells the
        # model to actually call tools instead of describing intended actions.
        # Values: "auto" (default — applies to GPT models), true/false
        # (force on/off for all models), or a list of model-name substrings
        # to match (e.g. ["gpt", "gemini", "qwen"]).
        "tool_use_enforcement": "auto",
        # Staged inactivity warning: send a warning to the user at this
        # threshold before escalating to a full timeout.  The warning fires
        # once per run and does not interrupt the agent.  0 = disable warning.
        "gateway_timeout_warning": 900,
        # Periodic "still working" notification interval (seconds).
        # Sends a status message every N seconds so the user knows the
        # agent hasn't died during long tasks.  0 = disable notifications.
        # Lower values mean faster feedback on slow tasks but more chat
        # noise; 180s is a compromise that catches spinning weak-model runs
        # (60+ tool iterations with tiny output) before users assume the
        # bot is dead and /restart.
        "gateway_notify_interval": 180,
        # Freshness window for the gateway auto-continue note (seconds).
        # After a gateway crash/restart/SIGTERM mid-run, the next user
        # message gets a "[System note: your previous turn was
        # interrupted — process the unfinished tool result(s) first]"
        # prepended so the model picks up where it left off.  That's the
        # right behaviour while the interruption is fresh, but stale
        # markers (transcript last touched hours or days ago) can revive
        # an unrelated old task when the user's next message starts new
        # work.  This window is the max age of the last persisted
        # transcript row for which we still inject the continue note.
        # Default 3600s comfortably covers a long turn (gateway_timeout
        # default is 1800s) plus runtime slack.  Set to 0 to disable the
        # gate and restore pre-fix behaviour (always inject).
        "gateway_auto_continue_freshness": 3600,
        # How user-attached images are presented to the main model on each turn.
        #   "auto"   — attach natively when the active model reports
        #              supports_vision=True AND the user hasn't explicitly
        #              configured auxiliary.vision.provider.  Otherwise fall
        #              back to text (vision_analyze pre-analysis).
        #   "native" — always attach natively; non-vision models will either
        #              error at the provider or get a last-chance text fallback
        #              (see run_agent._prepare_messages_for_api).
        #   "text"   — always pre-analyze with vision_analyze and prepend the
        #              description as text; the main model never sees pixels.
        # Affects gateway platforms, the TUI, and CLI /attach.  vision_analyze
        # remains available as a tool regardless of this setting — the routing
        # only controls how inbound user images are presented.
        "image_input_mode": "auto",
    },
    
    "terminal": {
        "backend": "local",
        "modal_mode": "auto",
        "cwd": ".",  # Use current directory
        "timeout": 180,
        # Environment variables to pass through to sandboxed execution
        # (terminal and execute_code).  Skill-declared required_environment_variables
        # are passed through automatically; this list is for non-skill use cases.
        "env_passthrough": [],
        # Extra files to source in the login shell when building the
        # per-session environment snapshot.  Use this when tools like nvm,
        # pyenv, asdf, or custom PATH entries are registered by files that
        # a bash login shell would skip — most commonly ``~/.bashrc``
        # (bash doesn't source bashrc in non-interactive login mode) or
        # zsh-specific files like ``~/.zshrc`` / ``~/.zprofile``.
        # Paths support ``~`` / ``${VAR}``. Missing files are silently
        # skipped. When empty, Hermes auto-sources ``~/.profile``,
        # ``~/.bash_profile``, and ``~/.bashrc`` (in that order) if the
        # snapshot shell is bash (this is the ``auto_source_bashrc``
        # behaviour — disable with that key if you want strict login-only
        # semantics).
        "shell_init_files": [],
        # When true (default), Hermes sources the user's shell rc files
        # (``~/.profile``, ``~/.bash_profile``, ``~/.bashrc``) in the
        # login shell used to build the environment snapshot. This
        # captures PATH additions, shell functions, and aliases — which a
        # plain ``bash -l -c`` would otherwise miss because bash skips
        # bashrc in non-interactive login mode, and because a default
        # Debian/Ubuntu ``~/.bashrc`` short-circuits on non-interactive
        # sources. ``~/.profile`` and ``~/.bash_profile`` are tried first
        # because ``n`` / ``nvm`` / ``asdf`` installers typically write
        # their PATH exports there without an interactivity guard. Turn
        # this off if your rc files misbehave when sourced
        # non-interactively (e.g. one that hard-exits on TTY checks).
        "auto_source_bashrc": True,
        "docker_image": "nikolaik/python-nodejs:python3.11-nodejs20",
        "docker_forward_env": [],
        # Explicit environment variables to set inside Docker containers.
        # Unlike docker_forward_env (which reads values from the host process),
        # docker_env lets you specify exact key-value pairs — useful when Hermes
        # runs as a systemd service without access to the user's shell environment.
        # Example: {"SSH_AUTH_SOCK": "/run/user/1000/ssh-agent.sock"}
        "docker_env": {},
        "singularity_image": "docker://nikolaik/python-nodejs:python3.11-nodejs20",
        "modal_image": "nikolaik/python-nodejs:python3.11-nodejs20",
        "daytona_image": "nikolaik/python-nodejs:python3.11-nodejs20",
        "vercel_runtime": "node24",
        # Container resource limits (docker, singularity, modal, daytona, vercel_sandbox — ignored for local/ssh)
        "container_cpu": 1,
        "container_memory": 5120,       # MB (default 5GB)
        "container_disk": 51200,        # MB (default 50GB)
        "container_persistent": True,   # Persist filesystem across sessions
        # Docker volume mounts — share host directories with the container.
        # Each entry is "host_path:container_path" (standard Docker -v syntax).
        # Example:
        # ["/home/user/projects:/workspace/projects",
        #  "/home/user/.hermes/cache/documents:/output"]
        # For gateway MEDIA delivery, write inside Docker to /output/... and emit
        # the host-visible path in MEDIA:, not the container path.
        "docker_volumes": [],
        # Explicit opt-in: mount the host cwd into /workspace for Docker sessions.
        # Default off because passing host directories into a sandbox weakens isolation.
        "docker_mount_cwd_to_workspace": False,
        # Explicit opt-in: run the Docker container as the host user's uid:gid
        # (via `--user`).  When enabled, files written into bind-mounted dirs
        # (docker_volumes, the persistent workspace, or the auto-mounted cwd)
        # are owned by your host user instead of root, which avoids needing
        # `sudo chown` after container runs. Default off to preserve behavior
        # for images whose entrypoints expect to start as root (e.g. the
        # bundled Hermes image, which drops to the `hermes` user via gosu).
        # When on, SETUID/SETGID caps are omitted from the container since
        # no privilege drop is needed.
        "docker_run_as_host_user": False,
        # Persistent shell — keep a long-lived bash shell across execute() calls
        # so cwd/env vars/shell variables survive between commands.
        # Enabled by default for non-local backends (SSH); local is always opt-in
        # via TERMINAL_LOCAL_PERSISTENT env var.
        "persistent_shell": True,
    },
    
    "browser": {
        "inactivity_timeout": 120,
        "command_timeout": 30,  # Timeout for browser commands in seconds (screenshot, navigate, etc.)
        "record_sessions": False,  # Auto-record browser sessions as WebM videos
        "allow_private_urls": False,  # Allow navigating to private/internal IPs (localhost, 192.168.x.x, etc.)
        "auto_local_for_private_urls": True,  # When a cloud provider is set, auto-spawn local Chromium for LAN/localhost URLs instead of sending them to the cloud
        "cdp_url": "",  # Optional persistent CDP endpoint for attaching to an existing Chromium/Chrome
        # CDP supervisor — dialog + frame detection via a persistent WebSocket.
        # Active only when a CDP-capable backend is attached (Browserbase or
        # local Chrome via /browser connect). See
        # website/docs/developer-guide/browser-supervisor.md.
        "dialog_policy": "must_respond",  # must_respond | auto_dismiss | auto_accept
        "dialog_timeout_s": 300,  # Safety auto-dismiss after N seconds under must_respond
        "camofox": {
            # When true, Hermes sends a stable profile-scoped userId to Camofox
            # so the server maps it to a persistent Firefox profile automatically.
            # When false (default), each session gets a random userId (ephemeral).
            "managed_persistence": False,
        },
    },

    # Filesystem checkpoints — automatic snapshots before destructive file ops.
    # When enabled, the agent takes a snapshot of the working directory once per
    # conversation turn (on first write_file/patch call).  Use /rollback to restore.
    "checkpoints": {
        "enabled": True,
        "max_snapshots": 50,  # Max checkpoints to keep per directory
        # Auto-maintenance: shadow repos accumulate forever under
        # ~/.hermes/checkpoints/ (one per cd'd working directory). Field
        # reports put the typical offender at 1000+ repos / ~12 GB. When
        # auto_prune is on, hermes sweeps at startup (at most once per
        # min_interval_hours) and deletes:
        #   * orphan repos: HERMES_WORKDIR no longer exists on disk
        #   * stale repos:  newest mtime older than retention_days
        # Opt-in so users who rely on /rollback against long-ago sessions
        # never lose data silently.
        "auto_prune": False,
        "retention_days": 7,
        "delete_orphans": True,
        "min_interval_hours": 24,
    },

    # Maximum characters returned by a single read_file call.  Reads that
    # exceed this are rejected with guidance to use offset+limit.
    # 100K chars ≈ 25–35K tokens across typical tokenisers.
    "file_read_max_chars": 100_000,

    # Tool-output truncation thresholds. When terminal output or a
    # single read_file page exceeds these limits, Hermes truncates the
    # payload sent to the model (keeping head + tail for terminal,
    # enforcing pagination for read_file). Tuning these trades context
    # footprint against how much raw output the model can see in one
    # shot. Ported from anomalyco/opencode PR #23770.
    #
    # - max_bytes:       terminal_tool output cap, in chars
    #                    (default 50_000 ≈ 12-15K tokens).
    # - max_lines:       read_file pagination cap — the maximum `limit`
    #                    a single read_file call can request before
    #                    being clamped (default 2000).
    # - max_line_length: per-line cap applied when read_file emits a
    #                    line-numbered view (default 2000 chars).
    "tool_output": {
        "max_bytes": 50_000,
        "max_lines": 2000,
        "max_line_length": 2000,
    },

    "compression": {
        "enabled": True,
        "threshold": 0.50,            # compress when context usage exceeds this ratio
        "target_ratio": 0.20,         # fraction of threshold to preserve as recent tail
        "protect_last_n": 20,         # minimum recent messages to keep uncompressed
        "hygiene_hard_message_limit": 400,  # gateway session-hygiene force-compress threshold by message count
    },

    # Anthropic prompt caching (Claude via OpenRouter or native Anthropic API).
    # cache_ttl must be "5m" or "1h" (Anthropic-supported tiers); other values are ignored.
    "prompt_caching": {
        "cache_ttl": "5m",
    },

    # Auxiliary model config — provider:model for each side task.
    # Format: provider is the provider name, model is the model slug.
    # "auto" for provider = auto-detect best available provider.
    # Empty model = use provider's default auxiliary model.
    # When ``provider: auto`` cannot satisfy a task, Hermes tries the auxiliary
    # client chain (see agent/auxiliary_client.py); document your preferred
    # fallbacks under auxiliary.* instead of relying on a single hardcoded slug.
    "auxiliary": {
        "vision": {
            "provider": "auto",    # auto | openrouter | nous | custom
            "model": "",           # e.g. "google/gemini-2.5-flash", "gpt-4o"
            "base_url": "",        # direct OpenAI-compatible endpoint (takes precedence over provider)
            "api_key": "",         # API key for base_url (falls back to OPENAI_API_KEY)
            "timeout": 120,        # seconds — LLM API call timeout; vision payloads need generous timeout
            "extra_body": {},      # OpenAI-compatible provider-specific request fields
            "download_timeout": 30,  # seconds — image HTTP download timeout; increase for slow connections
        },
        "web_extract": {
            "provider": "auto",
            "model": "",
            "base_url": "",
            "api_key": "",
            "timeout": 360,        # seconds (6min) — per-attempt LLM summarization timeout; increase for slow local models
            "extra_body": {},
        },
        "compression": {
            "provider": "auto",
            "model": "",
            "base_url": "",
            "api_key": "",
            "timeout": 120,        # seconds — compression summarises large contexts; increase for local models
            "extra_body": {},
        },
        "session_search": {
            "provider": "auto",
            "model": "",
            "base_url": "",
            "api_key": "",
            "timeout": 30,
            "extra_body": {},
            "max_concurrency": 3,  # Clamp parallel summaries to avoid request-burst 429s on small providers
        },
        "skills_hub": {
            "provider": "auto",
            "model": "",
            "base_url": "",
            "api_key": "",
            "timeout": 30,
            "extra_body": {},
        },
        "approval": {
            "provider": "auto",
            "model": "",           # fast/cheap model recommended (e.g. gemini-flash, haiku)
            "base_url": "",
            "api_key": "",
            "timeout": 30,
            "extra_body": {},
        },
        "mcp": {
            "provider": "auto",
            "model": "",
            "base_url": "",
            "api_key": "",
            "timeout": 30,
            "extra_body": {},
        },
        "title_generation": {
            "provider": "auto",
            "model": "",
            "base_url": "",
            "api_key": "",
            "timeout": 30,
            "extra_body": {},
        },
        # Curator — skill-usage review fork. Timeout is generous because the
        # review pass can take several minutes on reasoning models (umbrella
        # building over hundreds of candidate skills). "auto" = use main chat
        # model; override via `hermes model` → auxiliary → Curator to route
        # to a cheaper aux model (e.g. openrouter google/gemini-3-flash-preview).
        "curator": {
            "provider": "auto",
            "model": "",
            "base_url": "",
            "api_key": "",
            "timeout": 600,
            "extra_body": {},
        },
    },
    
    "display": {
        "compact": False,
        "personality": "kawaii",
        "resume_display": "full",
        "busy_input_mode": "interrupt",  # interrupt | queue | steer
        # When true, `hermes --tui` auto-resumes the most recent human-
        # facing session on launch instead of forging a fresh one.
        # Mirrors `hermes -c` muscle memory.  Default off so existing
        # users aren't surprised.  HERMES_TUI_RESUME=<id> always wins.
        "tui_auto_resume_recent": False,
        "bell_on_complete": False,
        "show_reasoning": False,
        "streaming": False,
        "final_response_markdown": "strip",  # render | strip | raw
        "inline_diffs": True,     # Show inline diff previews for write actions (write_file, patch, skill_manage)
        "show_cost": False,       # Show $ cost in the status bar (off by default)
        "skin": "default",
        # TUI busy indicator style: kaomoji (default), emoji, unicode (braille
        # spinner), or ascii.  Live-swappable via `/indicator <style>`.
        "tui_status_indicator": "kaomoji",
        "user_message_preview": {  # CLI: how many submitted user-message lines to echo back in scrollback
            "first_lines": 2,
            "last_lines": 2,
        },
        "interim_assistant_messages": True,  # Gateway: show natural mid-turn assistant status messages
        "tool_progress_command": False,  # Enable /verbose command in messaging gateway
        "tool_progress_overrides": {},  # DEPRECATED — use display.platforms instead
        "tool_preview_length": 0,  # Max chars for tool call previews (0 = no limit, show full paths/commands)
        "platforms": {},  # Per-platform display overrides: {"telegram": {"tool_progress": "all"}, "slack": {"tool_progress": "off"}}
        # Gateway runtime-metadata footer appended to the FINAL message of a turn
        # (disabled by default to keep replies minimal). When enabled, renders
        # e.g. `model · 68% · ~/projects/hermes`. Per-platform overrides go under
        # display.platforms.<platform>.runtime_footer.
        "runtime_footer": {
            "enabled": False,
            "fields": ["model", "context_pct", "cwd"],  # Order shown; drop any to hide
        },
    },

    # Web dashboard settings
    "dashboard": {
        "theme": "default",  # Dashboard visual theme: "default", "midnight", "ember", "mono", "cyberpunk", "rose"
    },

    # Privacy settings
    "privacy": {
        "redact_pii": False,  # When True, hash user IDs and strip phone numbers from LLM context
    },
    
    # Text-to-speech configuration
    # Each provider supports an optional `max_text_length:` override for the
    # per-request input-character cap. Omit it to use the provider's documented
    # limit (OpenAI 4096, xAI 15000, MiniMax 10000, ElevenLabs 5k-40k model-aware,
    # Gemini 5000, Edge 5000, Mistral 4000, NeuTTS/KittenTTS 2000).
    "tts": {
        "provider": "edge",  # "edge" (free) | "elevenlabs" (premium) | "openai" | "xai" | "minimax" | "mistral" | "gemini" | "neutts" (local) | "kittentts" (local) | "piper" (local)
        "edge": {
            "voice": "en-US-AriaNeural",
            # Popular: AriaNeural, JennyNeural, AndrewNeural, BrianNeural, SoniaNeural
        },
        "elevenlabs": {
            "voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam
            "model_id": "eleven_multilingual_v2",
        },
        "openai": {
            "model": "gpt-4o-mini-tts",
            "voice": "alloy",
            # Voices: alloy, echo, fable, onyx, nova, shimmer
        },
        "xai": {
            "voice_id": "eve",
            "language": "en",
            "sample_rate": 24000,
            "bit_rate": 128000,
        },
        "mistral": {
            "model": "voxtral-mini-tts-2603",
            "voice_id": "c69964a6-ab8b-4f8a-9465-ec0925096ec8",  # Paul - Neutral
        },
        "neutts": {
            "ref_audio": "",  # Path to reference voice audio (empty = bundled default)
            "ref_text": "",   # Path to reference voice transcript (empty = bundled default)
            "model": "neuphonic/neutts-air-q4-gguf",  # HuggingFace model repo
            "device": "cpu",  # cpu, cuda, or mps
        },
        "piper": {
            # Voice name (e.g. "en_US-lessac-medium") downloaded on first
            # use, OR an absolute path to a pre-downloaded .onnx file.
            # Full voice list: https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md
            "voice": "en_US-lessac-medium",
            # "voices_dir": "",        # Override voice cache dir; default = ~/.hermes/cache/piper-voices/
            # "use_cuda": False,       # Requires onnxruntime-gpu
            # "length_scale": 1.0,     # 2.0 = twice as slow
            # "noise_scale": 0.667,
            # "noise_w_scale": 0.8,
            # "volume": 1.0,
            # "normalize_audio": True,
        },
    },
    
    "stt": {
        "enabled": True,
        "provider": "local",  # "local" (free, faster-whisper) | "groq" | "openai" (Whisper API) | "mistral" (Voxtral Transcribe)
        "local": {
            "model": "base",  # tiny, base, small, medium, large-v3
            "language": "",  # auto-detect by default; set to "en", "es", "fr", etc. to force
        },
        "openai": {
            "model": "whisper-1",  # whisper-1, gpt-4o-mini-transcribe, gpt-4o-transcribe
        },
        "mistral": {
            "model": "voxtral-mini-latest",  # voxtral-mini-latest, voxtral-mini-2602
        },
    },

    "voice": {
        "record_key": "ctrl+b",
        "max_recording_seconds": 120,
        "auto_tts": False,
        "beep_enabled": True,         # Play record start/stop beeps in CLI voice mode
        "silence_threshold": 200,     # RMS below this = silence (0-32767)
        "silence_duration": 3.0,      # Seconds of silence before auto-stop
    },
    
    "human_delay": {
        "mode": "off",
        "min_ms": 800,
        "max_ms": 2500,
    },
    
    # Context engine -- controls how the context window is managed when
    # approaching the model's token limit.
    # "compressor" = built-in lossy summarization (default).
    # Set to a plugin name to activate an alternative engine (e.g. "lcm"
    # for Lossless Context Management).  The engine must be installed as
    # a plugin in plugins/context_engine/<name>/ or ~/.hermes/plugins/.
    "context": {
        "engine": "compressor",
    },

    # Persistent memory -- bounded curated memory injected into system prompt
    "memory": {
        "memory_enabled": True,
        "user_profile_enabled": True,
        "memory_char_limit": 2200,   # ~800 tokens at 2.75 chars/token
        "user_char_limit": 1375,     # ~500 tokens at 2.75 chars/token
        # External memory provider plugin (empty = built-in only).
        # Set to a provider name to activate: "openviking", "mem0",
        # "hindsight", "holographic", "retaindb", "byterover".
        # Only ONE external provider is allowed at a time.
        "provider": "",
    },

    # Subagent delegation — override the provider:model used by delegate_task
    # so child agents can run on a different (cheaper/faster) provider and model.
    # Uses the same runtime provider resolution as CLI/gateway startup, so all
    # configured providers (OpenRouter, Nous, Z.ai, Kimi, etc.) are supported.
    "delegation": {
        "model": "",       # e.g. "google/gemini-3-flash-preview" (empty = inherit parent model)
        "provider": "",    # e.g. "openrouter" (empty = inherit parent provider + credentials)
        "base_url": "",    # direct OpenAI-compatible endpoint for subagents
        "api_key": "",     # API key for delegation.base_url (falls back to OPENAI_API_KEY)
        # When delegate_task narrows child toolsets explicitly, preserve any
        # MCP toolsets the parent already has enabled. On by default so
        # narrowing (e.g. toolsets=["web","browser"]) expresses "I want these
        # extras" without silently stripping MCP tools the parent already has.
        # Set to false for strict intersection.
        "inherit_mcp_toolsets": True,
        "max_iterations": 50,  # per-subagent iteration cap (each subagent gets its own budget,
                               # independent of the parent's max_iterations)
        "child_timeout_seconds": 600,  # wall-clock timeout for each child agent (floor 30s,
                                       # no ceiling). High-reasoning models on large tasks
                                       # (e.g. gpt-5.5 xhigh, opus-4.6) need generous budgets;
                                       # raise if children time out before producing output.
        "reasoning_effort": "",  # reasoning effort for subagents: "xhigh", "high", "medium",
                                  # "low", "minimal", "none" (empty = inherit parent's level)
        "max_concurrent_children": 3,  # max parallel children per batch; floor of 1 enforced, no ceiling
        # Orchestrator role controls (see tools/delegate_tool.py:_get_max_spawn_depth
        # and _get_orchestrator_enabled).  Values are clamped to [1, 3] with a
        # warning log if out of range.
        "max_spawn_depth": 1,        # depth cap (1 = flat [default], 2 = orchestrator→leaf, 3 = three-level)
        "orchestrator_enabled": True,  # kill switch for role="orchestrator"
        # When a subagent hits a dangerous-command approval prompt, the parent's
        # prompt_toolkit TUI owns stdin — a thread-local input() call from the
        # subagent worker would deadlock the parent UI. To avoid the deadlock,
        # subagent threads ALWAYS resolve approvals non-interactively:
        #   false (default) → auto-deny with a logger.warning audit line (safe)
        #   true             → auto-approve "once" with a logger.warning audit line
        # Flip to true only if you trust delegated work to run dangerous cmds
        # without human review (cron pipelines, batch automation, etc.).
        "subagent_auto_approve": False,
    },

    # Ephemeral prefill messages file — JSON list of {role, content} dicts
    # injected at the start of every API call for few-shot priming.
    # Never saved to sessions, logs, or trajectories.
    "prefill_messages_file": "",
    
    # Skills — external skill directories for sharing skills across tools/agents.
    # Each path is expanded (~, ${VAR}) and resolved.  Read-only — skill creation
    # always goes to ~/.hermes/skills/.
    "skills": {
        "external_dirs": [],   # e.g. ["~/.agents/skills", "/shared/team-skills"]
        # Substitute ${HERMES_SKILL_DIR} and ${HERMES_SESSION_ID} in SKILL.md
        # content with the absolute skill directory and the active session id
        # before the agent sees it.  Lets skill authors reference bundled
        # scripts without the agent having to join paths.
        "template_vars": True,
        # Pre-execute inline shell snippets written as !`cmd` in SKILL.md
        # body.  Their stdout is inlined into the skill message before the
        # agent reads it, so skills can inject dynamic context (dates, git
        # state, detected tool versions, …).  Off by default because any
        # content from the skill author runs on the host without approval;
        # only enable for skill sources you trust.
        "inline_shell": False,
        # Timeout (seconds) for each !`cmd` snippet when inline_shell is on.
        "inline_shell_timeout": 10,
        # Run the keyword/pattern security scanner on skills the agent
        # writes via skill_manage (create/edit/patch).  Off by default
        # because the agent can already execute the same code paths via
        # terminal() with no gate, so the scan adds friction (blocks
        # skills that mention risky keywords in prose) without meaningful
        # security.  Turn on if you want the belt-and-suspenders — a
        # dangerous verdict will then surface as a tool error to the
        # agent, which can retry with the flagged content removed.
        # External hub installs (trusted/community sources) are always
        # scanned regardless of this setting.
        "guard_agent_created": False,
    },

    # Curator — background skill maintenance.
    #
    # Periodically reviews AGENT-CREATED skills (never bundled or
    # hub-installed) and keeps the collection tidy: marks long-unused skills
    # as stale, archives genuinely obsolete ones (archive only, never
    # deletes), and spawns a forked aux-model agent to consolidate overlaps
    # and patch drift. Runs inactivity-triggered from session start — no
    # cron daemon.
    #
    # See `hermes curator status` for the last run summary.
    "curator": {
        "enabled": True,
        # How long to wait between curator runs (hours).  Default: 7 days.
        "interval_hours": 24 * 7,
        # Only run when the agent has been idle at least this long (hours).
        "min_idle_hours": 2,
        # Mark a skill as "stale" after this many days without use.
        "stale_after_days": 30,
        # Archive a skill (move to skills/.archive/) after this many days
        # without use. Archived skills are recoverable — no auto-deletion.
        "archive_after_days": 90,
    },

    # Honcho AI-native memory -- reads ~/.honcho/config.json as single source of truth.
    # This section is only needed for hermes-specific overrides; everything else
    # (apiKey, workspace, peerName, sessions, enabled) comes from the global config.
    "honcho": {},

    # IANA timezone (e.g. "Asia/Kolkata", "America/New_York").
    # Empty string means use server-local time.
    "timezone": "",

    # Discord platform settings (gateway mode)
    "discord": {
        "require_mention": True,       # Require @mention to respond in server channels
        "free_response_channels": "",  # Comma-separated channel IDs where bot responds without mention
        "allowed_channels": "",        # If set, bot ONLY responds in these channel IDs (whitelist)
        "auto_thread": True,           # Auto-create threads on @mention in channels (like Slack)
        "reactions": True,             # Add 👀/✅/❌ reactions to messages during processing
        "channel_prompts": {},         # Per-channel ephemeral system prompts (forum parents apply to child threads)
        # discord / discord_admin tools: restrict which actions the agent may call.
        # Default (empty) = all actions allowed (subject to bot privileged intents).
        # Accepts comma-separated string ("list_guilds,list_channels,fetch_messages")
        # or YAML list. Unknown names are dropped with a warning at load time.
        # Actions: list_guilds, server_info, list_channels, channel_info,
        # list_roles, member_info, search_members, fetch_messages, list_pins,
        # pin_message, unpin_message, create_thread, add_role, remove_role.
        "server_actions": "",
    },

    # WhatsApp platform settings (gateway mode)
    "whatsapp": {
        # Reply prefix prepended to every outgoing WhatsApp message.
        # Default (None) uses the built-in "⚕ *Hermes Agent*" header.
        # Set to "" (empty string) to disable the header entirely.
        # Supports \n for newlines, e.g. "🤖 *My Bot*\n──────\n"
    },

    # Telegram platform settings (gateway mode)
    "telegram": {
        "reactions": False,            # Add 👀/✅/❌ reactions to messages during processing
        "channel_prompts": {},         # Per-chat/topic ephemeral system prompts (topics inherit from parent group)
    },

    # Slack platform settings (gateway mode)
    "slack": {
        "channel_prompts": {},         # Per-channel ephemeral system prompts
    },

    # Mattermost platform settings (gateway mode)
    "mattermost": {
        "channel_prompts": {},         # Per-channel ephemeral system prompts
    },

    # Approval mode for dangerous commands:
    #   manual — always prompt the user (default)
    #   smart  — use auxiliary LLM to auto-approve low-risk commands, prompt for high-risk
    #   off    — skip all approval prompts (equivalent to --yolo)
    #
    # cron_mode — what to do when a cron job hits a dangerous command:
    #   deny    — block the command and let the agent find another way (default, safe)
    #   approve — auto-approve all dangerous commands in cron jobs
    "approvals": {
        "mode": "manual",
        "timeout": 60,
        "cron_mode": "deny",
        # When true, /reload-mcp asks the user to confirm before rebuilding
        # the MCP tool set for the active session.  Reloading invalidates
        # the provider prompt cache (tool schemas are baked into the system
        # prompt), so the next message re-sends full input tokens — this can
        # be expensive on long-context or high-reasoning models.  Users click
        # "Always Approve" to silence the prompt permanently; that flips
        # this key to false.
        "mcp_reload_confirm": True,
    },

    # Permanently allowed dangerous command patterns (added via "always" approval)
    "command_allowlist": [],
    # User-defined quick commands that bypass the agent loop (type: exec only)
    "quick_commands": {},

    # Shell-script hooks — declarative bridge that invokes shell scripts
    # on plugin-hook events (pre_tool_call, post_tool_call, pre_llm_call,
    # subagent_stop, etc.).  Each entry maps an event name to a list of
    # {matcher, command, timeout} dicts.  First registration of a new
    # command prompts the user for consent; subsequent runs reuse the
    # stored approval from ~/.hermes/shell-hooks-allowlist.json.
    # See `website/docs/user-guide/features/hooks.md` for schema + examples.
    "hooks": {},

    # Auto-accept shell-hook registrations without a TTY prompt.  Also
    # toggleable per-invocation via --accept-hooks or HERMES_ACCEPT_HOOKS=1.
    # Gateway / cron / non-interactive runs need this (or one of the other
    # channels) to pick up newly-added hooks.
    "hooks_auto_accept": False,
    # Custom personalities — add your own entries here
    # Supports string format: {"name": "system prompt"}
    # Or dict format: {"name": {"description": "...", "system_prompt": "...", "tone": "...", "style": "..."}}
    "personalities": {},

    # Pre-exec security scanning via tirith
    "security": {
        "allow_private_urls": False,  # Allow requests to private/internal IPs (for OpenWrt, proxies, VPNs)
        "redact_secrets": False,
        "tirith_enabled": True,
        "tirith_path": "tirith",
        "tirith_timeout": 5,
        "tirith_fail_open": True,
        "website_blocklist": {
            "enabled": False,
            "domains": [],
            "shared_files": [],
        },
    },

    "cron": {
        # Wrap delivered cron responses with a header (task name) and footer
        # ("The agent cannot see this message").  Set to false for clean output.
        "wrap_response": True,
        # Maximum number of due jobs to run in parallel per tick.
        # null/0 = unbounded (limited only by thread count).
        # 1 = serial (pre-v0.9 behaviour).
        # Also overridable via HERMES_CRON_MAX_PARALLEL env var.
        "max_parallel_jobs": None,
    },

    # execute_code settings — controls the tool used for programmatic tool calls.
    "code_execution": {
        # Execution mode:
        #   project (default) — scripts run in the session's working directory
        #     with the active virtualenv/conda env's python, so project deps
        #     (pandas, torch, project packages) and relative paths resolve.
        #   strict            — scripts run in an isolated temp directory with
        #     hermes-agent's own python (sys.executable). Maximum isolation
        #     and reproducibility; project deps and relative paths won't work.
        # Env scrubbing (strips *_API_KEY, *_TOKEN, *_SECRET, ...) and the
        # tool whitelist apply identically in both modes.
        "mode": "project",
    },

    # Logging — controls file logging to ~/.hermes/logs/.
    # agent.log captures INFO+ (all agent activity); errors.log captures WARNING+.
    "logging": {
        "level": "INFO",       # Minimum level for agent.log: DEBUG, INFO, WARNING
        "max_size_mb": 5,      # Max size per log file before rotation
        "backup_count": 3,     # Number of rotated backup files to keep
    },

    # Remotely-hosted model catalog manifest.  When enabled, the CLI fetches
    # curated model lists for OpenRouter and Nous Portal from this URL,
    # falling back to the in-repo snapshot on network failure.  Lets us
    # update model picker lists without shipping a hermes-agent release.
    # The default URL is served by the docs site GitHub Pages deploy.
    "model_catalog": {
        "enabled": True,
        "url": "https://hermes-agent.nousresearch.com/docs/api/model-catalog.json",
        # Disk cache TTL in hours.  Beyond this, the CLI refetches on the
        # next /model or `hermes model` invocation; network failures
        # silently fall back to the stale cache.
        "ttl_hours": 24,
        # Optional per-provider override URLs for third parties that want
        # to self-host their own curation list using the same schema.
        # Example:
        #   providers:
        #     openrouter:
        #       url: https://example.com/my-curation.json
        "providers": {},
    },

    # Network settings — workarounds for connectivity issues.
    "network": {
        # Force IPv4 connections.  On servers with broken or unreachable IPv6,
        # Python tries AAAA records first and hangs for the full TCP timeout
        # before falling back to IPv4.  Set to true to skip IPv6 entirely.
        "force_ipv4": False,
    },

    # Session storage — controls automatic cleanup of ~/.hermes/state.db.
    # state.db accumulates every session, message, tool call, and FTS5 index
    # entry forever.  Without auto-pruning, a heavy user (gateway + cron)
    # reports 384MB+ databases with 68K+ messages, which slows down FTS5
    # inserts, /resume listing, and insights queries.
    "sessions": {
        # When true, prune ended sessions older than retention_days once
        # per (roughly) min_interval_hours at CLI/gateway/cron startup.
        # Only touches ended sessions — active sessions are always preserved.
        # Default false: session history is valuable for search recall, and
        # silently deleting it could surprise users.  Opt in explicitly.
        "auto_prune": False,
        # How many days of ended-session history to keep.  Matches the
        # default of ``hermes sessions prune``.
        "retention_days": 90,
        # VACUUM after a prune that actually deleted rows.  SQLite does not
        # reclaim disk space on DELETE — freed pages are just reused on
        # subsequent INSERTs — so without VACUUM the file stays bloated
        # even after pruning.  VACUUM blocks writes for a few seconds per
        # 100MB, so it only runs at startup, and only when prune deleted
        # ≥1 session.
        "vacuum_after_prune": True,
        # Minimum hours between auto-maintenance runs (avoids repeating
        # the sweep on every CLI invocation).  Tracked via state_meta in
        # state.db itself, so it's shared across all processes.
        "min_interval_hours": 24,
    },

    # Contextual first-touch onboarding hints (see agent/onboarding.py).
    # Each hint is shown once per install and then latched here so it
    # never fires again.  Users can wipe the section to re-see all hints.
    "onboarding": {
        "seen": {},
    },

    # ``hermes update`` behaviour.
    "updates": {
        # Run a full ``hermes backup``-style zip of HERMES_HOME before every
        # ``hermes update``.  Backups land in ``<HERMES_HOME>/backups/`` and
        # can be restored with ``hermes import <path>``.  Off by default —
        # on large HERMES_HOME directories the zip can add minutes to every
        # update.  Set to true to re-enable, or pass ``--backup`` to opt in
        # for a single update run.
        "pre_update_backup": False,
        # How many pre-update backup zips to retain.  Older ones are pruned
        # automatically after each successful backup.
        "backup_keep": 5,
    },

    # Config schema version - bump this when adding new required fields
    "_config_version": 23,
}
