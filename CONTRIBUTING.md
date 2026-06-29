# Contributing Guide

## Quick Start

```bash
# Clone and setup
git clone <repo-url>
cd agentic-playwright-mcp
make dev          # install deps + playwright browsers

# Run checks before committing
make test         # run pytest (475 tests)
make lint         # check code style
make format       # auto-fix style issues
```

## Project Structure

```
src/
├── server.py              # MCP tool registration — keep thin, delegate to layers
├── cli.py                 # CLI entry point (serve/run/doctor)
├── config.py              # Environment / .env loading
├── logging.py             # Structured logging
├── core/
│   ├── agent_loop.py      # Agent loop (OBSERVE→PLAN→ACT)
│   ├── script_engine.py   # Sandboxed script execution
│   ├── browser_manager.py # Playwright / CloakBrowser dual engine
│   ├── event_bus.py       # Event hooks system
│   └── vision.py          # Multimodal LLM page analysis
├── layer_1/
│   └── actions.py         # Atomic actions (goto, click, fill, screenshot)
├── layer_2/
│   └── controls.py        # High-level controls (smart_login, smart_search, etc.)
├── layer_3/
│   ├── domain_loader.py   # YAML load + Pydantic validation
│   └── config_updater.py  # Self-healing selector write-back
└── skill_library/
    ├── skill_base.py      # SkillBase abstract class
    ├── skills.yaml        # Declarative skill config
    ├── registry.py        # Skill registration and lookup
    ├── domains/           # Site adapters
    ├── interactions/      # Generic interaction templates
    └── guides/            # Markdown documentation
tests/
├── conftest.py            # Shared fixtures
└── test_*.py              # One test file per source module
domains/
└── *.yaml                 # Per-site locator configs
skills/
└── *.yaml                 # Declarative skill metadata
docs/
├── index.md               # Project overview
├── quickstart.md          # 5-minute guide
├── architecture.md        # Architecture deep dive
├── skills.md              # Skill library guide
├── api.md                 # API reference
└── adr/                   # Architecture Decision Records
examples/
└── *.py                   # Runnable example scripts
```

## Code Conventions

- **Language**: Python 3.11+, type hints required for public functions
- **Docstrings**: Google style (Chinese or English, be consistent within a file)
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes
- **Imports**: `from __future__ import annotations` at top of every module
- **Selectors**: Never hardcode selectors in Python — always load from YAML via Layer 3

## Layer Rules

| Layer | Responsibility | Rule |
|-------|---------------|------|
| Layer 1 | Atomic actions | No selectors hardcoded; receive via args |
| Layer 2 | Composite skills | Combines Layer 1 atoms; no direct Playwright calls |
| Layer 3 | Domain config | YAML parse + validate; self-heal write-back |
| server.py | MCP registration | Thin wrapper — logic goes in layers |
| cli.py | CLI commands | Thin wrapper — delegates to core modules |

## Adding a New Tool

1. Write the core logic in the appropriate layer (`layer_1/`, `layer_2/`, `layer_3/`)
2. Add tests in `tests/test_<module>.py`
3. Register in `server.py` with `@mcp.tool()`
4. Update `README.md` tool table

## Adding a New Skill (Plugin System)

### Option 1: Declarative YAML (Simple)

1. Create `skills/<name>.yaml` with metadata (triggers, url_patterns, etc.)
2. Create `src/skill_library/<category>/<name>.py` with a `run()` function
3. Skills are auto-discovered from `skills.yaml`

### Option 2: SkillBase Class (Advanced)

1. Create a class inheriting from `SkillBase` in `src/skill_library/search/`
2. Implement `execute(self, page, context) -> SkillResult`
3. Register in `skills.yaml` with `entry: MySkillClass`

## Adding a New Domain (YAML Config)

1. Create `domains/<site>.yaml` following the schema in `domains/example_baidu.yaml`
2. Add at least 2 selectors per element (CSS preferred, XPath as fallback)
3. Test with `smart_click` tool against the live site

## Git Workflow

1. Branch from `main`: `git checkout -b feat/<short-description>`
2. Make commits with clear messages
3. Run `make test && make lint` before pushing
4. Open PR — CI must pass
5. Squash merge into `main`

## Commit Messages

```
<type>: <short summary>

# Types: feat, fix, refactor, test, docs, chore
# Example:
feat: add smart_fill tool with domain config support
fix: handle timeout in do_click fallback chain
docs: update architecture diagram
test: add agent loop integration tests
```

## Documentation

```bash
# Install docs dependencies
pip install -e ".[docs]"

# Local docs server
make docs

# Build static docs
make docs-build

# Deploy to GitHub Pages
make docs-deploy
```

## ADR (Architecture Decision Records)

When making significant architectural decisions, create an ADR in `docs/adr/`:

```bash
# Template
cp docs/adr/001-three-layer-architecture.md docs/adr/004-your-decision.md
```

ADR format:
- **Title**: What was decided
- **Status**: Accepted / Superseded / Deprecated
- **Context**: Why this decision was needed
- **Decision**: What was decided
- **Consequences**: What are the implications
