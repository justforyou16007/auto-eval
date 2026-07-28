#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
EVAL_DIR="$REPO_ROOT/.eval"
mkdir -p "$EVAL_DIR/dist/tools"
ln -sf "$SCRIPT_DIR/../src/tools/eval-wiki.py" "$EVAL_DIR/dist/tools/eval-wiki.py"
echo "repo_root	$SCRIPT_DIR/.." > "$EVAL_DIR/installed-skills.txt"
echo "eval-wiki installed to $EVAL_DIR/dist/tools/eval-wiki.py"