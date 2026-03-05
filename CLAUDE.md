# Claude Agent Guidelines

## Package Manager

This project uses **uv** as its package manager. All commands should use `uv`, not `poetry` or `pip`.

- `uv sync` - Install all dependencies
- `uv run <cmd>` - Run a command in the project environment
- `uv build` - Build sdist and wheel
- `uv add <pkg>` - Add a dependency
- `uv add --group dev <pkg>` - Add a dev dependency

## Commit Convention

This project uses **Conventional Commits**. All commits MUST follow this format:

```
<type>(<optional scope>): <description>

[optional body]

[optional footer(s)]
```

### Allowed types (from cliff.toml):

- `feat`: New features
- `fix`: Bug fixes
- `doc`: Documentation changes
- `perf`: Performance improvements
- `refactor`: Code refactoring
- `style`: Code style changes
- `test`: Adding or updating tests
- `ci`: CI/CD changes
- `build`: Build system changes
- `chore`: Maintenance tasks (excluded from changelog)

### Examples:

```
feat(container): add support for async bindings
fix(scopes): resolve thread-safety issue in singleton scope
doc: update getting-started guide
test: add coverage for collection injection
```

## PR Workflow: No Fix Commits

When working on a PR and discovering issues with previous commits:

**DO NOT** create separate "fix" commits to address problems introduced in earlier commits on the same PR.

**INSTEAD**, use interactive rebase to amend the original commit:

```bash
# Amend the most recent commit
git add .
git commit --amend --no-edit

# Or for older commits, use autosquash rebase
git commit --fixup <digest of commit with issue>
git rebase --autosquash <digest of commit with issue>~1
```

### Rationale:

- Keeps the commit history clean and meaningful
- Each commit should represent a complete, working change
- Makes code review easier by avoiding "fix typo" or "oops" commits
- The PR should contain only the final, polished commits before merging

## One Commit Per Logical Change

When working on multiple features or fixes, split them into separate commits:

- Each commit should address **one** logical change
- Don't bundle unrelated changes in a single commit
- If a PR contains multiple features/fixes, each should have its own commit(s)

### Example:

```bash
# Good: separate commits for separate concerns
git commit -m "feat(container): add lazy binding support"
git commit -m "fix(scopes): handle edge case in request scope"
git commit -m "doc: document lazy bindings"

# Bad: mixing unrelated changes
git commit -m "feat(container): add lazy binding and fix scope bug and update docs"
```

This makes it easier to:

- Review changes independently
- Revert specific changes if needed
- Understand the history of the codebase

## Design Philosophy

The type system serves as the configuration language for dependency injection. Classes declare dependencies through Python type annotations and remain completely unaware of the DI container — they are plain objects usable without the framework. Around this foundation, the library layers real encapsulation (private-by-default module bindings), pluggable lifecycle management (scopes as interchangeable strategies rather than a fixed hierarchy), and layered safety guarantees (static and runtime circular dependency detection, container freezing, and typed exceptions) — all while maintaining dual sync/async support. The result is a framework that combines zero-configuration autowiring with the structural guardrails needed for complex applications, without ever coupling application code to the container.
