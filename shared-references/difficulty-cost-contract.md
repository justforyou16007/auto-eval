# Difficulty and Cost Contract

Adapted from ARIS `effort-contract.md`.

## Two Independent Axes

Task generation and evaluation use two independent dimensions:

### Difficulty (controls task complexity)

| Level | Description | Characteristics |
|-------|-------------|-----------------|
| `lite` | Trivial | Single-turn, single-tool, no error injection |
| `easy` | Simple | Single-turn, multi-tool, basic tool chaining |
| `medium` | Moderate | Multi-turn, tool chains, state persistence |
| `hard` | Complex | Multi-turn + error injection + adversarial scenarios |
| `beast` | Extreme | Long context + multi-tool + error + adversarial combined |

### Cost (controls resource budget)

| Value | Budget | Use Case |
|-------|--------|----------|
| `0.1` | Minimal | Quick smoke tests, lite tasks |
| `0.5` | Low | Single-turn verification |
| `1.0` | Standard | Multi-turn evaluation |
| `5.0` | High | Extended evaluation, beast tasks |
| `unlimited` | No limit | Research, deep analysis |

## Hard Invariants

1. **Cross-model review always on**: Any ACQUIT evaluation must use a
   different model family than the DRIVE generation.
2. **Reviewer independence always on**: The evaluating model must not have
   been involved in the original generation.
3. **Difficulty and cost are independent**: A `lite` task can have
   `cost: 5.0` for extensive verification, and a `beast` task can have
   `cost: 0.1` for minimal smoke testing.
4. **Cost is a ceiling, not a target**: The actual resource usage should
   not exceed the cost budget.

## Usage

In SKILL.md frontmatter:

```yaml
argument-hint: "[difficulty: lite|easy|medium|hard|beast] [cost: 0.1-unlimited]"
```

In task files:

```yaml
difficulty: "medium"
cost: 1.0
```