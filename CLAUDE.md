# Claude Agent Guidelines

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
