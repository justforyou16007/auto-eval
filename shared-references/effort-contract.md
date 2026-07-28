# Effort Contract

_Adapted from ARIS patterns for the eval-wiki context._

## Difficulty Axis

Tasks are classified along a difficulty axis with five levels:

| Level | Label | Characteristics | Max Turns | Tools | Error Injection |
|-------|-------|----------------|-----------|-------|-----------------|
| Lite | `lite` | Trivial, single-turn | 1 | 1 | No |
| Easy | `easy` | Simple, single-turn | 1 | 2+ | No |
| Medium | `medium` | Moderate, multi-turn | 2-5 | Chain | No |
| Hard | `hard` | Complex, multi-turn | 2-5 | Chain | Yes |
| Beast | `beast` | Extreme, long context | 5+ | Multi | Yes |

## Hard Invariants

1. **Difficulty is never changed mid-run**: Once a task is created with a
   difficulty level, that level is fixed. The difficulty determines the
   resource budget and evaluation criteria.
2. **Cost is a ceiling, not a target**: The actual resource usage should not
   exceed the cost budget. A `lite` task with `cost: 5.0` should not use all
   5.0 units — it's a maximum.
3. **Difficulty and cost are independent**: A `lite` task can have a high cost
   for extensive verification, and a `beast` task can have a low cost for
   minimal smoke testing.
4. **Cross-model review always on**: ACQUIT evaluations must use a different
   model family than DRIVE generation, regardless of difficulty level.

## Implementation

In eval-wiki, difficulty and cost are stored in task frontmatter:

```yaml
difficulty: "medium"
cost_budget: 1.0
```

Stage skills accept `--difficulty` and `--cost` parameters. See each skill's
SKILL.md for details.

## Cross-Reference

- `difficulty-cost-contract.md` — Original contract
- `assurance-contract.md` — Draft vs submission
- Each stage skill's SKILL.md argument-hint