# Reviewer Routing

_Adapted from ARIS patterns for the eval-wiki context._

## Cross-Model Reviewer Backend Routing

ACQUIT evaluations must use a different model family than the generating
model. Reviewer routing defines how to select the appropriate reviewer
backend.

## Routing Rules

| Generating Model | Reviewer Model | Reason |
|-----------------|----------------|--------|
| Claude (Anthropic) | GPT-4, Gemini, or other non-Anthropic | Different family |
| GPT-4 (OpenAI) | Claude, Gemini, or other non-OpenAI | Different family |
| Gemini (Google) | Claude, GPT-4, or other non-Google | Different family |
| Local model | Any cloud model | Different backend |

## Implementation

```bash
# Determine generating model family
case "$GENERATING_MODEL" in
    claude*|anthropic*)
        REVIEWER_MODEL="gpt-4"
        REVIEWER_ENDPOINT="https://api.openai.com/v1"
        ;;
    gpt*|openai*)
        REVIEWER_MODEL="claude-3-opus"
        REVIEWER_ENDPOINT="https://api.anthropic.com/v1"
        ;;
    gemini*)
        REVIEWER_MODEL="gpt-4"
        REVIEWER_ENDPOINT="https://api.openai.com/v1"
        ;;
    *)
        REVIEWER_MODEL="gpt-4"
        REVIEWER_ENDPOINT="https://api.openai.com/v1"
        ;;
esac

# Route to the reviewer backend
python3 eval-wiki.py add-run eval-wiki/ \
    --model "$REVIEWER_MODEL" \
    --endpoint "$REVIEWER_ENDPOINT"
```

## Verification

The `run-state.py` accept command includes a reviewer name check. If the
reviewer name contains "claude" and the generating model was also Claude,
the accept is rejected (self-acquit guard).

## Cross-Reference

- `acceptance-gate.md` — DRIVE vs ACQUIT roles
- `reviewer-independence.md` — LLM judge isolation
- `run-state.py` — Self-acquit guard
- `injection-hygiene.md` — Cross-agent injection prevention