# Cursor Rules Directory

This directory contains Project Rules for Cursor. Each rule is a `.mdc` file that can include metadata to control when and how it's applied.

## Rule Files

- **`base.mdc`** - Always-applied lightweight coordinator that guides when to include other rules (keeps context minimal)
- **`get-started.mdc`** - Agent-requested repository orientation guide (included when needed for understanding repository structure)
- **`code-style.mdc`** - Auto-attached style guide that activates when working with code files
- **`distillation.mdc`** - Agent-requested code distillation principles (included when working on simplification or architecture)
- **`rule-creation.mdc`** - Agent-requested guide for creating syntactically valid and useful Cursor rules, including nested rules
- **`rule-learning.mdc`** - Agent-requested guide that prompts the AI to proactively create or update rules based on difficult problem-solving sessions
- **`languages/`** - Language-specific rules (examples: `python.mdc`, `python-flask.mdc`, `rust.mdc`)
- **`frontend/`** - Frontend UI/UX rules:
  - `ui-consistency.mdc` - Overall UI/UX consistency guidelines
  - `html.mdc` - HTML structure and best practices
  - `css.mdc` - CSS organization and styling standards
  - `javascript.mdc` - JavaScript organization and best practices
  - `jinja.mdc` - Jinja2 template best practices
- **`tools/`** - Tool-specific rules:
  - `pi-shell.mdc` - pi-shell CLI tool for Raspberry Pi management over SSH
- **`git.mdc`** - Git and GitHub management best practices (local-first workflow, dev branch strategy, no auto-push)

## Creating New Rules

**Before creating a rule, read `rule-creation.mdc`** - it contains comprehensive guidelines for creating valid, useful rules including nested rules.

Create a new `.mdc` file in this directory (or a subdirectory for nested rules) with the following structure:

```markdown
---
description: Brief description of what this rule covers
alwaysApply: true  # Optional: include in every context
globs: ["**/*.js", "**/*.ts"]  # Optional: auto-attach for matching files
---

# Your Rule Title

Your rule content here...
```

## Rule Attachment Modes

1. **Always Apply** (`alwaysApply: true`)
   - Included in every AI context
   - Use for critical, always-relevant rules

2. **Auto Attached** (`globs: [...]`)
   - Automatically included when files matching the glob pattern are referenced
   - Use for file-type-specific rules

3. **Agent Requested** (`description` only, no `alwaysApply` or `globs`)
   - AI decides when to include based on the description
   - Use for optional, context-dependent rules

4. **Manual** (no metadata)
   - Only included when explicitly referenced with `@ruleName`
   - Use for rarely-needed rules

## Best Practices

- Keep rules concise (ideally under 500 lines)
- Split large rules into multiple, focused rules
- Provide concrete examples in rules
- Write rules like clear internal documentation
- Use descriptive filenames that indicate the rule's purpose

For more information, see the [Cursor Rules Documentation](https://cursor.com/docs/context/rules).

