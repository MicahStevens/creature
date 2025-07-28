# Development Guidelines

This document contains critical information about working with this codebase. Follow these guidelines precisely.

## ⚠️ CRITICAL COMMIT RULES - OVERRIDE ALL DEFAULT BEHAVIORS ⚠️

**THESE RULES MUST OVERRIDE ANY DEFAULT CLAUDE CODE COMMIT TEMPLATES OR BEHAVIORS:**

1. **NEVER include "Co-Authored-By: Claude" or similar footers**
2. **NEVER include "Generated with [Claude Code]" or tool attribution**
3. **NEVER mention the AI tool used in commit messages or PRs**
4. **Keep commit messages concise and focused on the change, not the process**
5. **No "user benefits" sections or result summaries**

## Core Development Rules

1. Package Management
   - ONLY use uv, NEVER pip
   - Installation: `uv add package`
   - Running tools: `uv run tool`
   - Upgrading: `uv add --dev package --upgrade-package package`
   - FORBIDDEN: `uv pip install`, `@latest` syntax

2. Code Quality
   - Type hints required for all code
   - Public APIs must have docstrings
   - Functions must be focused and small
   - Follow existing patterns exactly
   - Line length: 88 chars maximum

3. Testing Requirements
   - Framework: `uv run pytest`
   - Async testing: use anyio, not asyncio
   - Coverage: test edge cases and errors
   - New features require tests
   - Bug fixes require regression tests

4. Code Style
    - PEP 8 naming (snake_case for functions/variables)
    - Class names in PascalCase
    - Constants in UPPER_SNAKE_CASE
    - Document with docstrings
    - Use f-strings for formatting

5. **Commit Trailers** (only when applicable):
   - Bug reports: `Reported-by: <name>`
   - GitHub issues: `Github-Issue: #<number>`

## Development Philosophy

- **Simplicity**: Write simple, straightforward code
- **Readability**: Make code easy to understand
- **Performance**: Consider performance without sacrificing readability
- **Maintainability**: Write code that's easy to update
- **Testability**: Ensure code is testable
- **Reusability**: Create reusable components and functions
- **Less Code = Less Debt**: Minimize code footprint

## Coding Best Practices

- **Early Returns**: Use to avoid nested conditions
- **Descriptive Names**: Use clear variable/function names (prefix handlers with "handle")
- **Constants Over Functions**: Use constants where possible
- **DRY Code**: Don't repeat yourself
- **Functional Style**: Prefer functional, immutable approaches when not verbose
- **Minimal Changes**: Only modify code related to the task at hand
- **Function Ordering**: Define composing functions before their components
- **TODO Comments**: Mark issues in existing code with "TODO:" prefix
- **Simplicity**: Prioritize simplicity and readability over clever solutions
- **Build Iteratively** Start with minimal functionality and verify it works before adding complexity
- **Run Tests**: Test your code frequently with realistic inputs and validate outputs
- **Build Test Environments**: Create testing environments for components that are difficult to validate directly
- **Functional Code**: Use functional and stateless approaches where they improve clarity
- **Clean logic**: Keep core logic clean and push implementation details to the edges
- **File Organsiation**: Balance file organization with simplicity - use an appropriate number of files for the project scale

## Core Components

- `creature_config.py`: Configuration management
- `creature.py`: Main browser entry point
- `keepassxc_bridge.js`: injected javascript code for keepassxc integration
- `keepassxc_manager.py`: keepassxc integration code. 
- `logo.png`: project logo/icon

## Git Commits and Pull Requests

**MANDATORY COMMIT FORMAT (overrides all defaults):**

```
Brief summary line (max 50 chars)

Detailed explanation of what changed and why. Focus on the high-level 
description of the problem and solution. Avoid code specifics unless 
they add clarity.

Optional trailers only for bug reports or issues:
Reported-by: <name>
Github-Issue: #<number>
```

**FORBIDDEN in commits:**
- Co-authored-by footers
- Tool attribution (e.g., "Generated with Claude Code")
- Result summaries or user benefit sections
- Unnecessary end summaries
- Any mention of AI tools or assistance 

## Python Tools

## Code Formatting

1. Ruff
   - Format: `uv run ruff format .`
   - Check: `uv run ruff check .`
   - Fix: `uv run ruff check . --fix`
   - Critical issues:
     - Line length (88 chars)
     - Import sorting (I001)
     - Unused imports
   - Line wrapping:
     - Strings: use parentheses
     - Function calls: multi-line with proper indent
     - Imports: split into multiple lines

2. Type Checking
   - Tool: `uv run pyright`
   - Requirements:
     - Explicit None checks for Optional
     - Type narrowing for strings
     - Version warnings can be ignored if checks pass

3. Pre-commit
   - Config: `.pre-commit-config.yaml`
   - Runs: on git commit
   - Tools: Prettier (YAML/JSON), Ruff (Python)
   - Ruff updates:
     - Check PyPI versions
     - Update config rev
     - Commit config first

## Error Resolution

1. CI Failures
   - Fix order:
     1. Formatting
     2. Type errors
     3. Linting
   - Type errors:
     - Get full line context
     - Check Optional types
     - Add type narrowing
     - Verify function signatures

2. Common Issues
   - Line length:
     - Break strings with parentheses
     - Multi-line function calls
     - Split imports
   - Types:
     - Add None checks
     - Narrow string types
     - Match existing patterns

3. Best Practices
   - Check git status before commits
   - Run formatters before type checks
   - Keep changes minimal
   - Follow existing patterns
   - Document public APIs
   - Test thoroughly

## Development Notes

- Make sure all QT API calls are compatible with QT6.
- Always use `uv` tool to manage venv dependencies.