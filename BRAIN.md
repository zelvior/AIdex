# BRAIN.md — AIdex Project Context

> Read this file first, before touching code. It exists so you (or an AI
> assistant) can get fully oriented and start making changes without
> re-reading every source file. Keep it updated when you make structural
> changes — stale context here is worse than no context.

**Project**: AIdex AI Coding Agent (formerly "Nexus") — a CLI/TUI/Web AI
coding agent, by **Zelvior**, Apache 2.0 licensed.
**Current version**: 1.2.0
**Language**: Python, stdlib-first, optional deps only for the enhanced UI.
**Core philosophy**: maximum compatibility (Windows XP 32-bit → Windows 11,
Linux, macOS) + zero hard dependencies + graceful degradation everywhere.

---

## 1. What this project actually is

A single coherent Python backend (`src/core/agent.py` + `src/core/config.py`
+ `src/providers/base.py` + `src/tools/file_tools.py`) exposed through
**three different front ends** that all share the exact same engine:

1. **Rich TUI** (`src/tui/app.py`) — the "full" terminal experience, needs
   `rich` + `prompt_toolkit`, Python 3.7+.
2. **Plain TUI** (`src/tui/plain.py`) — zero-dependency fallback, pure
   stdlib (`input()`/`print()`), Python 2.7+, works on Windows XP / 32-bit.
3. **Web UI** (`src/web/server.py` + `src/web/static/`) — browser-based,
   served by a zero-dependency stdlib `http.server`, no Flask/Django/etc.

**Critical rule when adding a feature**: if it's user-facing (a new
command, a new tool, a new setting), it generally needs to be wired into
**all three** front ends, or explicitly decided to be web-only / CLI-only
with a comment explaining why. They are not automatically in sync — they
each have their own command-dispatch code that calls into the shared core.

Entry point: `aidex.py` (auto-detects which UI to launch; `--plain`/`--full`/
`--web` to force one). `nexus.py` is a **legacy alias** that just forwards
to `aidex.py` — keep it working, don't add new logic to it.

---

## 2. Directory map

```
aidex.py                  Main entry point. Auto-detects UI: web > full > plain.
nexus.py                  Legacy alias → forwards to aidex.py. Don't add logic here.
install.py                Universal installer. Never hard-exits on old Python.
setup.py                  pip/setuptools metadata.
requirements.txt          OPTIONAL deps only (rich, prompt_toolkit). Web UI needs none.
CHANGELOG.md              Keep-a-Changelog format. Add an entry per logical change.
README.md                 User-facing docs. Update when adding features/commands.
LICENSE                   Apache 2.0.

src/
  core/
    agent.py        THE agent. Singleton `agent = Agent()`. chat_stream() is
                     the main loop — native tool calling with multi-turn
                     tool-result loop, regex fallback for non-native models.
    config.py       Singleton `config = Config()`. All settings, API keys,
                     provider registry (PROVIDERS dict), live-model wrapper.
    models.py       Live model fetching (OpenRouter/Groq/Anthropic/Ollama),
                     disk caching with TTL, fallback chain: live → cache →
                     stale-cache → static built-in list. Never raises to
                     the caller in practice (config.get_live_models wraps it).
  providers/
    base.py         AIProvider (base, stdlib urllib only) →
                     OpenAICompatProvider (OpenRouter/Groq/OpenAI/Ollama) and
                     AnthropicProvider (native Anthropic API). Native
                     function-calling support, streaming + non-streaming.
  tools/
    file_tools.py   ALL 33 tools live here as plain functions, each
                     returning ToolResult(success, output, error). Also
                     TOOL_DEFINITIONS (compact param-spec format used to
                     generate help text) and the schema builders
                     (build_openai_tools_schema / build_anthropic_tools_schema)
                     that convert TOOL_DEFINITIONS into real JSON Schema for
                     native function calling.
  tui/
    app.py          Rich/prompt_toolkit UI. Class AIdexApp. Has its own
                     COMMANDS dict + big if/elif dispatch in _handle_command.
    plain.py        Stdlib-only mirror of app.py's functionality. Keep
                     feature parity — when you add a command to app.py,
                     add the equivalent here too.
  web/
    server.py       Handler(BaseHTTPRequestHandler) + run_web_server().
                     REST + SSE bridge to the same agent/config singletons.
                     Workspace confinement + shell-tool gating live here
                     (see Security section below — this is the ONE place
                     with a different trust boundary than the CLI).
    static/
      index.html    Single-page app shell, semantic HTML5, 4 panels
                     (chat/files/models/settings) shown/hidden via CSS.
      style.css     Modern CSS: @layer, color-mix(), CSS custom properties.
                     Dark theme, amber accent (--accent: #f5a623).
      app.js        Vanilla ES module. No build step, no framework. Hand-
                     rolled SSE-over-fetch parser (EventSource doesn't
                     support POST, so this isn't a real EventSource).
```

---

## 3. The shared engine — how a chat turn actually works

`Agent.chat_stream(user_input, excluded_tools=None)` in `src/core/agent.py`:

1. Appends user message to `self.messages`.
2. Builds system prompt via `_build_system()` — **uses plain `.replace()`,
   NOT `.format()`**. This matters: the prompt's fallback example contains
   literal `{`/`}` JSON, and `.format()` will crash on that. This was a
   real bug that broke every single message in the original codebase
   before this was fixed. Never change `_build_system()` back to
   `.format()`.
3. Gets the provider via `_get_provider()` (reads `config.provider`,
   `config.model`, the right API key, `request_timeout`, `max_retries`).
4. Checks `provider.supports_native_tools` (True for OpenAICompatProvider
   and AnthropicProvider, False for nothing currently — both real
   providers support it).
5. Builds the tool schema (`build_openai_tools_schema()` or
   `build_anthropic_tools_schema()` from `file_tools.py`), filtered by
   `excluded_tools` if given.
6. Runs a loop (max 8 turns, safety cap against infinite tool loops):
   - Streams from the provider. Provider yields **typed dict chunks**:
     `{"type": "text", "text": ...}` or `{"type": "tool_calls", "tool_calls": [...]}`.
   - If no tool calls came back natively, falls back to legacy regex
     parsing of `<tool_call>{...}</tool_call>` text blocks (for models
     that ignore the `tools=` param and just answer in text).
   - If there ARE tool calls: executes each via `_execute_tool()`, appends
     the assistant's tool-call message AND the tool results back into
     `self.messages` in the correct provider-specific shape (OpenAI:
     `role: "tool"` messages with `tool_call_id`; Anthropic: content
     blocks with `type: "tool_result"`), then loops again so the model can
     react to the result.
   - If no tool calls at all: appends final assistant text, yields
     `("done", "")`, returns.
7. Yields a stream of `("text"|"tool_call"|"tool_result"|"error"|"done", content)`
   tuples — this is the **stable external contract** all three UIs consume
   identically (TUIs print it, the web server turns it into SSE events).

`normalize_message_content(msg)` (module-level function in agent.py) — use
this anywhere you need to display a message from `agent.messages`/history.
Message `content` can now be `None` (OpenAI tool-call message), a list of
content blocks (Anthropic), or a plain string. Never assume it's a string.

---

## 4. Tools — two read paths, don't mix them up

There are **two different "read a file" functions** and **two different
"list a directory" functions**, and mixing them up caused a real,
already-fixed bug (corrupted files when saved through the web editor):

- `read_file(path, workspace)` / `list_directory(path, workspace)` —
  **AI/terminal-display formatted**. Adds `[File: x] (N lines)` headers
  and `   1 | ` line-number prefixes, and `list_directory` returns a
  2-level recursive emoji tree. **Never** feed this into something that
  gets saved back as raw file content.
- `read_file_raw(path, workspace)` / `list_directory_flat(path, workspace)`
  — **raw/structured, for UI consumption**. `read_file_raw` returns exact
  file bytes-as-text, no formatting. `list_directory_flat` returns
  `(ToolResult, [{"name", "is_dir", "size"?}, ...])` — single level, no
  tree, made for clickable navigation. The web UI uses these exclusively.

All 33 tools are registered in `TOOL_DEFINITIONS` (file_tools.py) with a
compact param spec: `{"name": "str - description, default: X"}`. The
`default:` substring in a param's description is what marks it optional
when building JSON Schema (`_parse_param_spec` in file_tools.py) — keep
that convention if you add params, or the schema's `required` list will
be wrong.

Tool list (33): read_file, write_file, edit_file, patch_lines, append_file,
delete_file, move_file, copy_file, create_directory, list_directory,
search_files, grep_file, run_command, run_python, git_status, git_diff,
git_log, git_add, git_commit, git_init, git_branch, git_checkout,
analyze_project, get_file_info, read_file_lines, head_file, tail_file,
count_lines, disk_usage, env_info, find_replace_in_files, which, list_models.

`run_command` and `run_python` are the only tools that touch `safe_mode`
(blocks a hardcoded list of dangerous command substrings when True,
default True). `run_python` writes code to a temp file and shells out to
`{sys.executable} tmpfile.py` — it respects `safe_mode` via the same path
as `run_command` (this was a real bug, fixed: it used to ignore the
config's actual safe_mode value).

---

## 5. Live model system (`src/core/models.py`)

`config.get_live_models(provider=None, force_refresh=False, timeout=None)`
→ `(List[ModelInfo], source_str)`. `source_str` is one of:
`"live"` (fresh API hit), `"cache"` (fresh disk cache, < 6h old),
`"stale-cache"` (cache expired AND live fetch failed, served anyway),
`"static-fallback"` (no cache, no network — falls back to the hardcoded
`PROVIDERS[x]["free_models"]/["paid_models"]` lists in config.py).

Cache lives at `<config_dir>/models_cache/models_<provider>.json`, TTL 6h
(`CACHE_TTL_SECONDS` in models.py).

Per-provider fetch logic in `fetch_live_models()`:
- **OpenRouter**: hits `GET {base_url}/models`, parses `pricing.prompt`/
  `completion` (USD per token → converted to per-1M-token for display),
  `:free` suffix or zero pricing = free, `supported_parameters` containing
  `"tools"` = native-tool-call capable.
- **Groq/OpenAI/Ollama**: same endpoint shape, minimal schema (just `id`,
  sometimes `context_window`), no pricing info available.
- **Anthropic**: `GET {base_url}/models` with `x-api-key` header (not
  Bearer), returns `id`+`display_name`, no pricing.

`ModelInfo` has `.price_label()` (`"FREE"` / `"$X.XX/$Y.YY per 1M"` / `"?"`)
and `.context_label()` (`"128K"` / `"?"`) — use these for display, don't
reformat manually.

`filter_models()` / `sort_models()` / `cache_age_label()` in models.py are
shared helpers used identically by app.py, plain.py, and server.py's
`/api/models` — if you change filter/sort behavior, change it once here.

---

## 6. Config (`src/core/config.py`)

Singleton `config`. Config dir: `~/.config/aidex/` (Linux/XDG),
`%APPDATA%\aidex\` (Windows), `~/Library/Application Support/aidex/`
(macOS). **Auto-migrates** from the old `nexus-agent` config dir on first
load if no `aidex` config exists yet — don't remove `_LEGACY_CONFIG_FILE`
handling in `load()`.

Key methods: `config.get(key, default)`, `config.set(key, value)` (saves to
disk immediately), `config.get_api_key(provider=None)`, `config.as_dict()`
(public, use this instead of touching `_data` directly from outside the
class), `config.get_provider_info(provider=None)`, `config.all_models(provider)`
(static fallback list only), `config.get_live_models(...)` (the real one,
see §5), `config.models_cache_age(provider=None)`.

`DEFAULT_CONFIG` keys you'll actually touch: `provider`, `model`,
`*_api_key` (one per provider), `ollama_base_url`, `workspace`, `safe_mode`,
`stream`, `max_tokens`, `temperature`, `request_timeout`, `max_retries`,
`web_allow_shell_tools` (web-UI-specific, see §7, default False).

`PROVIDERS` dict: `openrouter`, `groq`, `anthropic`, `openai`, `ollama`.
Each has `name`, `base_url`, `key_field`, `free_models`/`paid_models`
(static fallback lists — these go stale, that's expected, that's why §5
exists). Ollama's `base_url` is overridden per-instance from
`config.get("ollama_base_url")` since it's a local server the user might
run on a different port.

---

## 7. Web UI security model — read before touching server.py

The web UI is a **different trust boundary** than the CLI/TUI. A developer
running the terminal app already has shell access to their own machine, so
the CLI tools are intentionally unrestricted. A browser-reachable HTTP
endpoint is not the same thing, even on localhost. Two real
already-fixed vulnerabilities inform the current design — do not regress
them:

1. **Workspace confinement** (`_is_within_workspace()` in server.py): every
   filesystem-touching web endpoint (`/api/fs/list`, `/api/fs/read`,
   `/api/fs/write`, and path-like params in `/api/tool`) checks the
   resolved path stays inside `config.workspace`. Absolute paths and `../`
   traversal outside the workspace get `403`. The underlying
   `_resolve()` in file_tools.py does NOT enforce this on its own (it's
   permissive by design for the CLI) — the web layer must check it itself,
   every time, for every new file-touching endpoint you add.
2. **Shell-tool gating**: `run_command`/`run_python` are excluded from the
   tool schema offered to the model during web chat by default
   (`_SHELL_TOOLS` set in server.py, checked against
   `config.get("web_allow_shell_tools", False)`), AND defense-in-depth
   blocked again inside `Agent._execute_tool()` itself via
   `self._excluded_tools` — so even a non-native model trying the legacy
   regex tool-call fallback can't sneak through. If you add a new
   dangerous tool, add it to `_SHELL_TOOLS` too.

If you add a new web endpoint that touches the filesystem or executes
anything: route it through these same two checks. Don't assume "it's just
localhost" — that mistake already shipped once in this project, was caught
in browser-based testing, and got fixed.

**Separately real bug, also fixed**: the file editor used to load
`read_file()`'s *display-formatted* output into the editable textarea,
then save that formatted text straight back to disk on Save, corrupting
every file edited through the web UI. Fixed by adding `read_file_raw()`/
`list_directory_flat()` (§4) specifically for UI use. If you add another
UI surface that reads-then-writes a file, use the raw variants.

---

## 8. Web API reference (`src/web/server.py`)

All endpoints relative to wherever `run_web_server()` binds (default
`127.0.0.1`, auto-picks a free port from 8420 up, or pass `--port`).

| Method | Path | Notes |
|---|---|---|
| GET | `/` | index.html |
| GET | `/static/<file>` | css/js, path-traversal-safe via `_safe_static_path` |
| GET | `/api/status` | provider/model/workspace/safe_mode/has_key |
| GET | `/api/models?provider=&refresh=1` | live model list, see §5 |
| POST | `/api/models/switch` | `{model}` |
| POST | `/api/provider/switch` | `{provider}` — auto-picks a free live model |
| GET/POST | `/api/config` | GET masks secrets via `_mask_key`; POST only allows a fixed safe field set + provider key fields |
| GET | `/api/history` | uses `normalize_message_content` |
| POST | `/api/history/clear` | |
| GET | `/api/tools` | raw `TOOL_DEFINITIONS` |
| POST | `/api/tool` | `{tool, params}` — direct tool execution, gated per §7 |
| GET | `/api/fs/list?path=` | `list_directory_flat`, confined per §7 |
| GET | `/api/fs/read?path=` | `read_file_raw`, confined per §7 |
| POST | `/api/fs/write` | `{path, content}`, confined per §7 |
| POST | `/api/chat` | **SSE**, `{message}` → events: `text`, `tool_call`, `tool_result`, `error`, `done` |

Frontend (`app.js`) parses `/api/chat`'s SSE manually via
`fetch().body.getReader()` + a `\n\n`-delimited buffer parser — NOT the
browser's native `EventSource`, because `EventSource` can't do POST
bodies. If you change the SSE event format on the server, update the
parser in `app.js` (`sendChat()` function) to match.

---

## 9. Compatibility matrix (don't break these)

- **Plain TUI** (`plain.py`): must stay importable and runnable on Python
  2.7+. No f-strings, no walrus operator, no `pathlib` reliance for the
  core loop, no type hints that aren't string-quoted/`from __future__`.
  It's verified via `ast.parse` + checking for `JoinedStr`/`NamedExpr`
  nodes — don't reintroduce those.
- **Web UI**: needs Python 3.6+ (uses f-strings in server.py) for the
  backend; `ThreadingHTTPServer` needs 3.7+ but server.py has a manual
  `socketserver.ThreadingMixIn` fallback for 3.6. `aidex.py --web` checks
  the version and prints a clear error + suggests `--plain` below 3.6,
  rather than a cryptic traceback.
- **Rich TUI**: needs Python 3.7+ (that's what `rich`/`prompt_toolkit`
  themselves require). `aidex.py`'s auto-detect tries this first, falls
  back to plain on import failure OR on any runtime exception from
  `AIdexApp().run()` (wrapped in try/except, never just dies).
- **`aidex.py` is always the real entry point.** `nexus.py` just imports
  and calls `aidex.main()`. Never duplicate launch logic into nexus.py.

---

## 10. Known design decisions (so you don't "fix" them by accident)

- `_execute_tool` dispatch in agent.py is a big dict of lambdas keyed by
  tool name, built fresh on every call (cheap, fine, not a bug).
- The legacy `<tool_call>{json}</tool_call>` text-parsing fallback in
  agent.py is intentional — some free/small models on OpenRouter ignore
  the `tools=` parameter entirely and just emit text. Don't remove it
  thinking native tool calling makes it obsolete.
- `test_connection()` on providers tries the free `/models` listing
  endpoint first before falling back to a real (paid) chat completion —
  this is deliberate cost-avoidance, not an oversight.
- Static `free_models`/`paid_models` lists in `PROVIDERS` (config.py) are
  *known to go stale* — that's expected, they're only the last-resort
  fallback when live fetch AND cache both fail. Don't "fix" them by
  trying to keep them current; fix the live-fetch path instead if it's
  broken.
- The web UI defaults `web_allow_shell_tools` to `False` and there's
  currently no Settings-panel toggle for it in the UI — that's
  deliberate, so enabling shell exec from the browser requires editing
  the config file directly, not one accidental click.

---

## 11. Where to look for X

- "Why didn't my tool call work" → `agent.py` `chat_stream()`, check
  `provider.supports_native_tools` and the schema builders in
  `file_tools.py`.
- "Model list is empty/wrong" → `models.py` `fetch_live_models()` per
  provider, or `config.get_live_models()`'s fallback chain.
- "Web UI file browser/editor acting weird" → check you're using the
  `_raw`/`_flat` variants (§4), and the workspace-confinement check (§7).
- "New slash command" → add to **both** `app.py`'s `COMMANDS` dict +
  dispatch, and `plain.py`'s equivalent. Update README's command table.
- "New tool" → add the function to `file_tools.py`, add to
  `TOOL_DEFINITIONS`, add a dispatch entry in `agent.py`'s
  `_execute_tool`. If it's filesystem/shell-related, decide if it needs
  to go in `_SHELL_TOOLS` (server.py) for web gating.
- "Something crashes on old Windows/XP/32-bit" → check it's reachable via
  `plain.py`, not just `app.py`; check no f-strings/walrus snuck in.
