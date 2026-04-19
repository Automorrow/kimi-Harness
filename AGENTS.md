# Kimi Code CLI — Agent Guide

This file is the single source of truth for AI coding agents working on the Kimi Code CLI repository. If you are an agent, read this first before making any changes.

## Project Overview

Kimi Code CLI is a Python-based AI agent that runs in the terminal. It can read and edit code, execute shell commands, search and fetch web pages, and autonomously plan and adjust actions during execution.

Key capabilities:
- **Interactive shell UI** (default) with slash commands, shell command mode (`Ctrl-X`), and approvals.
- **ACP server mode** (`kimi acp`) for IDE integrations (Zed, JetBrains, etc.).
- **MCP tool loading** (`kimi mcp`) for external Model Context Protocol servers.
- **Web UI** and **Vis UI** — React frontends built into the Python package.
- **Subagents** — nested agent instances that can be created, resumed, and persisted.

The repository is a **Python monorepo** managed with `uv` workspaces. It also contains Node.js frontends and a VitePress documentation site.

## Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.12+ (runtime); tooling targets Python 3.14 (`.python-version`) |
| CLI framework | Typer |
| Async runtime | asyncio |
| LLM framework | kosong (workspace package) |
| MCP integration | fastmcp |
| Logging | loguru |
| Package / build | uv + uv_build |
| Standalone binaries | PyInstaller (`kimi.spec`) |
| Web frontends | React 19 + Vite + Tailwind CSS + shadcn/ui |
| Docs site | VitePress |
| Reproducible env | Nix flake (`flake.nix`) |
| Tests | pytest + pytest-asyncio |
| Lint / format | ruff |
| Type checking | pyright + ty (ty is non-blocking) |
| JS/TS lint | Biome (web), tsc |

## Repository Structure

```
.
├── pyproject.toml              # Root package "kimi-harness" (CLI + runtime)
├── uv.lock                     # Workspace lockfile
├── Makefile                    # Primary build / dev / test interface
├── flake.nix                   # Nix package definition
├── kimi.spec                   # PyInstaller spec (onefile + onedir)
├── src/kimi_cli/               # Main CLI source code
│   ├── cli/                    # Typer CLI entry points
│   ├── soul/                   # Core agent loop, context, compaction, approvals
│   ├── tools/                  # Built-in tools (shell, file, web, agent, etc.)
│   ├── ui/                     # UI frontends (shell, print, acp, wire)
│   ├── wire/                   # Event types and transport between soul and UI
│   ├── acp/                    # ACP server components
│   ├── web/                    # Web UI backend (FastAPI) + static assets
│   ├── vis/                    # Vis UI backend (FastAPI) + static assets
│   ├── agents/                 # Built-in agent YAML specs and system prompts
│   ├── prompts/                # Shared prompt templates
│   ├── skills/                 # Built-in skills (commit, debug, plan, review, ...)
│   └── deps/                   # Binary dependencies (ripgrep) + Makefile
├── packages/
│   ├── kosong/                 # LLM abstraction layer (OpenAI, Anthropic, Google, MCP)
│   ├── kaos/                   # OS abstraction layer (local + SSH)
│   └── kimi-code/              # Thin wrapper package depending on kimi-harness
├── sdks/kimi-sdk/              # Lightweight Python SDK for the Kimi API
├── web/                        # React web frontend source
├── vis/                        # React vis frontend source
├── docs/                       # VitePress documentation site
├── tests/                      # Unit / integration tests
├── tests_e2e/                  # Wire protocol end-to-end tests
├── tests_ai/                   # AI-driven test suite
├── examples/                   # Sample plugins and custom souls
├── scripts/                    # Build helpers (web, vis, version checks)
└── klips/                      # Kimi Code CLI Improvement Proposals
```

## Build and Test Commands

All routine tasks are exposed through `Makefile`. Use `make help` to list targets.

### Environment setup
```sh
make prepare          # Sync deps for all workspace packages + install prek git hooks
make prepare-build    # Like prepare, but without workspace sources (for releases)
```

### Running the CLI
```sh
uv run kimi           # Run Kimi Code CLI from source
```

### Formatting and checks
```sh
make format           # Format all Python + JS sources
make check            # Lint + type-check all packages
make format-kimi-cli  # Format only the root CLI package
make check-kimi-cli   # Check only the root CLI package
```

### Testing
```sh
make test             # Run all test suites
make test-kimi-cli    # Run tests/ + tests_e2e/
make test-kosong      # Run kosong tests (includes doctests)
make test-pykaos      # Run pykaos tests
make test-kimi-sdk    # Run kimi-sdk tests
make ai-test          # Run the AI-driven test suite
```

### Building frontends
```sh
make build-web        # Build web UI and sync into src/kimi_cli/web/static/
make build-vis        # Build vis UI and sync into src/kimi_cli/vis/static/
make web-back         # Start web backend (uvicorn reload on :5494)
make web-front        # Start web frontend Vite dev server
make vis-back         # Start vis backend (uvicorn reload on :5495)
make vis-front        # Start vis frontend Vite dev server
```

### Building packages and binaries
```sh
make build            # Build Python wheels/sdists for release
make build-bin        # Build standalone executable with PyInstaller (onefile)
make build-bin-onedir # Build standalone executable (onedir)
```

### Documentation
Run inside `docs/`:
```sh
npm install
npm run dev      # Dev server with live reload
npm run build    # Build to docs/.vitepress/dist
npm run preview  # Preview production build
npm run sync     # Sync root CHANGELOG.md into English docs
```

## Code Style Guidelines

- **Line length**: 100 characters.
- **Python formatter / linter**: ruff.
  - Selected rules: `E`, `F`, `UP`, `B`, `SIM`, `I`.
  - Per-file ignores:
    - `tests/**/*.py` and `tests_e2e/**/*.py` → `E501`
    - `src/kimi_cli/web/api/**/*.py` → `B008` (FastAPI `Depends()` is standard)
- **Type checking**:
  - pyright: `standard` mode for root, `strict` for `src/kimi_cli/**/*.py`.
  - ty: runs as a non-blocking check (`|| true`).
- **Python version target**: 3.14 for type checkers; runtime supports 3.12+.
- **JavaScript / TypeScript**:
  - `web/` uses Biome for linting and formatting.
  - `vis/` uses TypeScript compiler (`tsc`) for type checking; no separate linter.
- **Tool imports**: Tools in `src/kimi_cli/tools/` should **not** import from `kimi_cli/wire/` unless they explicitly bridge UI/runtime. Prefer `kosong.tooling` types.

## Testing Instructions

- **Framework**: pytest with `pytest-asyncio` (async mode is `auto` per `pytest.ini`).
- **Unit / integration tests**: `tests/`
- **End-to-end wire tests**: `tests_e2e/`
  - Test only `kimi --wire` JSON-RPC + wire messages; no Shell UI / Print / ACP.
  - Isolate `HOME`, `USERPROFILE`, and `KIMI_SHARE_DIR`; use a temporary `--work-dir`.
  - Use `inline_snapshot` for snapshot testing.
  - Some tests require a real LLM provider (W-10, W-12, W-30, W-33); the rest use `_scripted_echo`.
- **AI tests**: `tests_ai/` — run via `make ai-test`.
- **Package tests**: each workspace package has its own `tests/` directory and is executed with `uv run --project <pkg> --directory <pkg> pytest ...`.

## Architecture Overview

1. **CLI entry** (`src/kimi_cli/cli/__init__.py`) parses flags (UI mode, agent spec, config, MCP) and routes into `KimiCLI` (`src/kimi_cli/app.py`).
2. **App / runtime setup** (`KimiCLI.create`) loads config (`src/kimi_cli/config.py`), chooses a model / provider (`src/kimi_cli/llm.py`), builds a `Runtime` (`src/kimi_cli/soul/agent.py`), loads an agent spec, restores `Context`, then constructs `KimiSoul`.
3. **Agent specs**: YAML files under `src/kimi_cli/agents/` loaded by `src/kimi_cli/agentspec.py`. Specs can `extend` base agents, select tools by import path, and register builtin subagent types via the `subagents` field. Subagent instances are persisted separately under the session directory (`session/subagents/<agent_id>/`) and can be resumed by `agent_id`.
4. **Tooling**: `src/kimi_cli/soul/toolset.py` loads tools by import path, injects dependencies, and runs tool calls. Built-in tools live in `src/kimi_cli/tools/` (agent, shell, file, web, todo, background, dmail, think, plan). MCP tools are loaded via `fastmcp`; CLI management is in `src/kimi_cli/mcp.py` and stored in the share dir.
5. **Subagents**: `LaborMarket` in `src/kimi_cli/soul/agent.py` registers builtin subagent types. The `Agent` tool (`src/kimi_cli/tools/agent/`) creates or resumes subagent instances, while `SubagentStore` persists instance metadata, prompts, wire logs, and context.
6. **Core loop**: `src/kimi_cli/soul/kimisoul.py` is the main agent loop. It accepts user input, handles slash commands (`src/kimi_cli/soul/slash.py`), appends to `Context` (`src/kimi_cli/soul/context.py`), calls the LLM (kosong), runs tools, and performs compaction (`src/kimi_cli/soul/compaction.py`) when needed.
7. **Approvals**: `src/kimi_cli/soul/approval.py` is the tool-facing facade. `ApprovalRuntime` in `src/kimi_cli/approval_runtime/` is the session-level source of truth for pending approvals, and approval requests are projected onto the root wire stream for Shell / Web style UIs.
8. **UI / Wire**: `src/kimi_cli/soul/run_soul` connects `KimiSoul` to a `Wire` (`src/kimi_cli/wire/`) so UI loops can stream events. UIs live in `src/kimi_cli/ui/` (shell / print / acp / wire).
9. **Shell UI**: `src/kimi_cli/ui/shell/` handles interactive TUI input, shell command mode, and slash command autocomplete; it is the default interactive experience.
10. **ACP**: Two server modes exist:
    - Single-session (`KimiCLI.run_acp`) used with `--acp`.
    - Multi-session (`kimi acp` subcommand) exposing `ACPServer`.
    - See `src/kimi_cli/acp/AGENTS.md` for protocol details, capability advertisement, and session lifecycle.

## Workspace Packages

| Package | Path | Role |
|---------|------|------|
| `kimi-harness` | root `pyproject.toml` | Main CLI and runtime |
| `kosong` | `packages/kosong/` | LLM abstraction layer (Anthropic, Google GenAI, OpenAI, MCP) |
| `pykaos` | `packages/kaos/` | OS abstraction (local filesystem + SSH) |
| `kimi-code` | `packages/kimi-code/` | Thin wrapper that depends on `kimi-harness`; provides `kimi-code` entry point |
| `kimi-sdk` | `sdks/kimi-sdk/` | Lightweight Python SDK for the Kimi API |

All packages share the same ruff/pyright/ty configuration pattern, line length 100, and Python 3.14 type-check target.

## Frontends (Web / Vis)

- **Web** (`web/`): React 19, Vite, Tailwind CSS, shadcn/ui, Biome, `package.json` scripts: `dev`, `build`, `typecheck`, `format`, `lint`.
- **Vis** (`vis/`): React 19, Vite, Tailwind CSS, shadcn/ui, `package.json` scripts: `dev`, `build`, `typecheck`.
- Both are built and synced into `src/kimi_cli/web/static/` and `src/kimi_cli/vis/static/` via `scripts/build_web.py` and `scripts/build_vis.py`.
- `make build` and `make build-bin` automatically trigger `make build-web` and `make build-vis`.

## Documentation Conventions

- The docs site lives in `docs/` and uses VitePress.
- Locales: `docs/en/` and `docs/zh/` with mirrored paths and filenames.
- **Chinese docs are the source of truth** for all non-changelog pages. English translations may be AI-generated.
- **English changelog** (`docs/en/release-notes/changelog.md`) is auto-synced from root `CHANGELOG.md` via `docs/scripts/sync-changelog.mjs`.
- Strict naming, typography, and term-mapping rules apply (see `docs/AGENTS.md`).
- Do not edit the English changelog manually; edit `CHANGELOG.md` at the repo root and run `npm run sync`.

## Versioning and Release Workflow

### Versioning scheme
The project follows a **minor-bump-only** scheme (`MAJOR.MINOR.PATCH`):
- **Patch** is always `0`. Never bump it.
- **Minor** is bumped for any change (features, fixes, improvements).
- **Major** is changed only by explicit manual decision.

All packages in the repo (root, `packages/*`, `sdks/*`) align versions.

### Release steps
1. Ensure `main` is up to date.
2. Create a release branch (e.g., `bump-0.68`).
3. Update `CHANGELOG.md`: rename `[Unreleased]` to `[0.68] - YYYY-MM-DD`.
4. Update `pyproject.toml` version (and ensure `packages/kimi-code/pyproject.toml` pins `kimi-cli==<version>`).
5. Run `uv sync` to align `uv.lock`.
6. Commit, open a PR, and merge.
7. Tag and push: `git tag 0.68 && git push --tags`.
8. GitHub Actions handles the rest (build wheels, build binaries, publish to PyPI, create GitHub Release).

### CI / CD
- **CI** (`.github/workflows/ci-kimi-cli.yml`):
  - `check` job: ruff + pyright + ty on Ubuntu with Python 3.14.
  - `test` job: matrix across Python 3.12 / 3.13 / 3.14 on Ubuntu.
  - `build` job: multi-platform PyInstaller binary builds (Linux x64+arm, macOS arm, Windows x64).
  - `nix-test` job: validates the Nix flake builds and runs on supported platforms.
  - `release-validate` job: on PRs with version bumps, checks version alignment and dependency pins.
- **Release** (`.github/workflows/release-kimi-cli.yml`):
  - Triggered on tags matching `[0-9]*`.
  - Validates version tags, builds onefile + onedir binaries for all platforms (including Windows arm), signs and notarizes macOS binaries, packages archives, uploads artifacts, publishes to PyPI, and creates a GitHub Release with SHA256 checksums.
- Separate CI workflows also exist for `kosong`, `pykaos`, and `kimi-sdk`.

## Security Considerations

- Only the **latest version** receives security support.
- Report vulnerabilities via the [GitHub Security page](https://github.com/MoonshotAI/kimi-cli/security) or open a public issue if appropriate.
- **macOS signing / notarization**: Release builds use Apple Developer ID certificates and `xcrun notarytool`.
- **OAuth**: Platform OAuth flows are implemented in `src/kimi_cli/auth/`.
- **Sensitive data filtering**: `src/kimi_cli/utils/sensitive.py` provides utilities for redacting secrets from logs.
- User configuration, logs, sessions, and MCP config live in `~/.kimi/`.

## Development Conventions

- **Git hooks**: The repo uses [prek](https://github.com/j178/prek) to run formatting and checks. Install via `make prepare` (which runs `prek install`). Hooks run only on changed projects (workspace mode). Skip with `git commit --no-verify`.
- **Commit messages**: Follow Conventional Commits:
  ```
  <type>(<scope>): <subject>
  ```
  Allowed types: `feat`, `fix`, `test`, `refactor`, `chore`, `style`, `docs`, `perf`, `build`, `ci`, `revert`.
- **Binary dependencies**: `make prepare` invokes `download-deps`, which downloads a platform-specific `ripgrep` binary into `src/kimi_cli/deps/bin/`.
- **User config path**: `~/.kimi/config.toml`. The `KIMI_SHARE_DIR` environment variable can override the share directory location.
- **Agent environment variables injected into specs**:
  `KIMI_NOW`, `KIMI_WORK_DIR`, `KIMI_WORK_DIR_LS`, `KIMI_AGENTS_MD`, `KIMI_SKILLS`, `KIMI_OS`, `KIMI_SHELL`.

## Sub-Project Agent Guides

Several directories contain their own `AGENTS.md` with deeper conventions:

- `docs/AGENTS.md` — VitePress authoring, locale rules, term mapping, typography.
- `tests_e2e/AGENTS.md` — Wire E2E test goals, execution rules, test matrix.
- `src/kimi_cli/acp/AGENTS.md` — ACP protocol details, session lifecycle, content mapping.
- `src/kimi_cli/tools/AGENTS.md` — Tool authoring guidelines (import restrictions).

When modifying code in those areas, consult the corresponding guide.
