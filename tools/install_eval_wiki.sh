#!/bin/bash
# ARIS-style install_eval_wiki.sh
# Installs auto-eval skills and tools into a target project directory.
# Symlinks are created under .claude/skills/ (skills) and .eval/dist/tools/ (tool scripts).
#
# Usage:
#   bash /path/to/auto-eval/tools/install_eval_wiki.sh [project_path] [options]
#
# Options:
#   --reconcile     Reconcile existing symlinks (add missing, report extra)
#   --uninstall     Remove all installed symlinks
#   --dry-run       Show what would be done without doing it
#   --force         Overwrite existing non-symlink files/directories
#   --help          Show this help message

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: install_eval_wiki.sh [project_path] [options]

Install auto-eval skills and tools into a target project directory.

Arguments:
  project_path    Target project directory (default: current directory)

Options:
  --reconcile     Reconcile existing symlinks (add missing, report extra)
  --uninstall     Remove all installed symlinks
  --dry-run       Show what would be done without doing it
  --force         Overwrite existing non-symlink files/directories
  --help          Show this help message

Examples:
  # Install into current directory
  bash /path/to/auto-eval/tools/install_eval_wiki.sh

  # Install into a specific project
  bash /path/to/auto-eval/tools/install_eval_wiki.sh /path/to/my-project

  # Dry-run to see what would happen
  bash /path/to/auto-eval/tools/install_eval_wiki.sh --dry-run

  # Uninstall from a project
  bash /path/to/auto-eval/tools/install_eval_wiki.sh --uninstall

  # Reconcile (add missing, report extra)
  bash /path/to/auto-eval/tools/install_eval_wiki.sh --reconcile
EOF
    exit 0
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
PROJECT_PATH=""
ACTION="install"
DRY_RUN=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --reconcile) ACTION="reconcile"; shift ;;
        --uninstall) ACTION="uninstall"; shift ;;
        --dry-run)   DRY_RUN=true; shift ;;
        --force)     FORCE=true; shift ;;
        --help)      usage ;;
        -*)
            echo "Unknown option: $1" >&2
            echo "Use --help for usage information." >&2
            exit 1
            ;;
        *)
            if [ -z "$PROJECT_PATH" ]; then
                PROJECT_PATH="$1"
            else
                echo "Unexpected argument: $1" >&2
                echo "Use --help for usage information." >&2
                exit 1
            fi
            shift
            ;;
    esac
done

# Default project path to current directory
if [ -z "$PROJECT_PATH" ]; then
    PROJECT_PATH="$(pwd)"
fi

# Resolve to absolute path
PROJECT_PATH="$(cd "$PROJECT_PATH" 2>/dev/null && pwd)" || {
    echo "ERROR: Cannot access project path: $PROJECT_PATH" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Discover the auto-eval repository location
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AUTOEVAL_REPO="${AUTOEVAL_REPO:-}"

# 1. Check AUTOEVAL_REPO env var
if [ -n "$AUTOEVAL_REPO" ]; then
    if [ ! -f "$AUTOEVAL_REPO/src/tools/eval-wiki.py" ]; then
        echo "ERROR: AUTOEVAL_REPO is set to '$AUTOEVAL_REPO' but does not contain src/tools/eval-wiki.py" >&2
        exit 1
    fi
else
    # 2. Walk up from script directory to find the auto-eval repo root
    CANDIDATE="$SCRIPT_DIR"
    while [ "$CANDIDATE" != "/" ]; do
        if [ -f "$CANDIDATE/src/tools/eval-wiki.py" ]; then
            AUTOEVAL_REPO="$CANDIDATE"
            break
        fi
        CANDIDATE="$(dirname "$CANDIDATE")"
    done

    # 3. Check common locations
    if [ -z "$AUTOEVAL_REPO" ]; then
        for loc in "$HOME/auto-eval" "$HOME/repos/auto-eval" "$HOME/projects/auto-eval"; do
            if [ -f "$loc/src/tools/eval-wiki.py" ]; then
                AUTOEVAL_REPO="$loc"
                break
            fi
        done
    fi
fi

if [ -z "$AUTOEVAL_REPO" ] || [ ! -f "$AUTOEVAL_REPO/src/tools/eval-wiki.py" ]; then
    echo "ERROR: Cannot find auto-eval repository." >&2
    echo "" >&2
    echo "  Set the AUTOEVAL_REPO environment variable to the path of your auto-eval" >&2
    echo "  repository, or run this script from within the auto-eval repo." >&2
    echo "" >&2
    echo "  Example:" >&2
    echo "    AUTOEVAL_REPO=~/auto-eval bash /path/to/install_eval_wiki.sh" >&2
    echo "    bash /path/to/auto-eval/tools/install_eval_wiki.sh" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SKILLS=(
    "auto-eval-pipeline"
    "benchmark-compare"
    "benchmark-search"
    "benchmark2-evaluator"
    "env-component-manager"
    "env-gen"
    "env-audit"
    "eval-wiki"
    "feedback-align"
    "feedback-audit"
    "report-gen"
    "report-audit"
    "rubric-gen"
    "rubric-audit"
    "scorecard-evaluator"
    "setup"
    "task-gen"
    "task-audit"
)

TOOLS=(
    "capture-filter.py"
    "env-component-manager.py"
    "eval-wiki.py"
    "evidence-check.py"
    "iteration-log.py"
    "provenance.py"
    "run-state.py"
    "watchdog.py"
)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
LINKS_CREATED=()
LINKS_REMOVED=()
ERRORS=()

log_info()  { echo "  $1"; }
log_ok()    { echo "  ✓ $1"; }
log_add()   { echo "  + $1"; }
log_remove(){ echo "  - $1"; }
log_warn()  { echo "  ! $1" >&2; }
log_error() { echo "  ✗ $1" >&2; }

# Create a symlink with safety checks.
# Returns 0 on success, 1 on error.
create_symlink() {
    local target="$1"
    local link_path="$2"
    local label="$3"

    if [ -L "$link_path" ]; then
        # Already a symlink
        local existing_target
        existing_target="$(readlink "$link_path")"
        if [ "$existing_target" = "$target" ]; then
            log_ok "$label (already up-to-date)"
            return 0
        fi
        # Pointing elsewhere — replace
        log_info "$label: replacing symlink (was: $existing_target → $target)"
        if [ "$DRY_RUN" = false ]; then
            rm "$link_path"
        fi
    elif [ -e "$link_path" ]; then
        # Exists as a regular file or directory
        if [ "$FORCE" = true ]; then
            log_warn "$label: overwriting existing file/directory (--force)"
            if [ "$DRY_RUN" = false ]; then
                rm -rf "$link_path"
            fi
        else
            log_error "$label: exists and is not a symlink. Use --force to overwrite."
            ERRORS+=("$link_path")
            return 1
        fi
    fi

    log_add "$label → $target"
    LINKS_CREATED+=("$link_path")
    if [ "$DRY_RUN" = false ]; then
        mkdir -p "$(dirname "$link_path")"
        ln -sf "$target" "$link_path"
    fi
    return 0
}

# Remove a symlink.
remove_symlink() {
    local link_path="$1"
    local label="$2"

    if [ -L "$link_path" ]; then
        log_remove "$label"
        LINKS_REMOVED+=("$link_path")
        if [ "$DRY_RUN" = false ]; then
            rm "$link_path"
            # Clean up empty parent directories (non-critical)
            rmdir "$(dirname "$link_path")" 2>/dev/null || true
        fi
    elif [ -e "$link_path" ]; then
        log_warn "$label: not a symlink, skipping. Use --force to remove."
        ERRORS+=("$link_path")
    fi
}

# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

do_uninstall() {
    echo ""
    echo "Uninstalling from $PROJECT_PATH..."
    echo ""

    # Remove skill symlinks
    for skill in "${SKILLS[@]}"; do
        remove_symlink "$PROJECT_PATH/.claude/skills/$skill" ".claude/skills/$skill"
    done

    # Remove tool symlinks
    for tool in "${TOOLS[@]}"; do
        remove_symlink "$PROJECT_PATH/.eval/dist/tools/$tool" ".eval/dist/tools/$tool"
    done

    # Remove manifest
    local manifest="$PROJECT_PATH/.eval/installed-skills.txt"
    if [ -f "$manifest" ]; then
        log_remove ".eval/installed-skills.txt"
        if [ "$DRY_RUN" = false ]; then
            rm "$manifest"
            rmdir "$PROJECT_PATH/.eval" 2>/dev/null || true

    # Remove empty directories
    rmdir "$PROJECT_PATH/.claude/skills" 2>/dev/null || true
    rmdir "$PROJECT_PATH/.claude" 2>/dev/null || true
    rmdir "$PROJECT_PATH/.eval/dist/tools" 2>/dev/null || true
    rmdir "$PROJECT_PATH/.eval/dist" 2>/dev/null || true
        fi
    fi

    echo ""
    echo "Done. Removed ${#LINKS_REMOVED[@]} symlinks."
    if [ ${#ERRORS[@]} -gt 0 ]; then
        echo "WARNING: ${#ERRORS[@]} items could not be removed (use --force)." >&2
    fi
}

do_install() {
    echo ""
    echo "Auto-eval repo: $AUTOEVAL_REPO"
    echo "Target project: $PROJECT_PATH"
    echo ""

    # Create .claude/skills/ symlinks
    echo "Installing skills to .claude/skills/..."
    for skill in "${SKILLS[@]}"; do
        local skill_source="$AUTOEVAL_REPO/skills/$skill"
        if [ ! -d "$skill_source" ]; then
            log_warn "WARNING: skill directory not found: $skill_source"
            continue
        fi
        create_symlink "$skill_source" "$PROJECT_PATH/.claude/skills/$skill" ".claude/skills/$skill"
    done

    echo ""
    echo "Installing tools to .eval/dist/tools/..."
    for tool in "${TOOLS[@]}"; do
        local tool_source="$AUTOEVAL_REPO/src/tools/$tool"
        if [ ! -f "$tool_source" ]; then
            log_warn "WARNING: tool not found: $tool_source"
            continue
        fi
        create_symlink "$tool_source" "$PROJECT_PATH/.eval/dist/tools/$tool" ".eval/dist/tools/$tool"
    done

    # Write manifest
    local manifest="$PROJECT_PATH/.eval/installed-skills.txt"
    if [ "$DRY_RUN" = false ]; then
        mkdir -p "$(dirname "$manifest")"
        {
            echo "# auto-eval skills manifest"
            echo "# AUTOEVAL_REPO=$AUTOEVAL_REPO"
            echo "# Installed: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
            echo ""
            for link in "${LINKS_CREATED[@]}"; do
                echo "$link"
            done
        } > "$manifest"
    fi

    echo ""
    echo "Done. Created ${#LINKS_CREATED[@]} symlinks."
    echo "Manifest: $PROJECT_PATH/.eval/installed-skills.txt"
    if [ ${#ERRORS[@]} -gt 0 ]; then
        echo "WARNING: ${#ERRORS[@]} items could not be installed (use --force)." >&2
    fi
}

do_reconcile() {
    echo ""
    echo "Reconciling $PROJECT_PATH..."
    echo ""

    # Read existing symlinks from the manifest
    local manifest="$PROJECT_PATH/.eval/installed-skills.txt"
    local -A existing_links
    if [ -f "$manifest" ]; then
        while IFS= read -r line; do
            # Skip comment lines and blank lines
            if [[ "$line" =~ ^# ]] || [ -z "$line" ]; then
                continue
            fi
            existing_links["$line"]=1
        done < "$manifest"
    fi

    local expected_links=()
    local added=0
    local extra=0

    # Check expected skill symlinks
    for skill in "${SKILLS[@]}"; do
        local link_path="$PROJECT_PATH/.claude/skills/$skill"
        expected_links+=("$link_path")
        if [ ! -L "$link_path" ]; then
            local skill_source="$AUTOEVAL_REPO/skills/$skill"
            if [ -d "$skill_source" ]; then
                echo "  MISSING: .claude/skills/$skill — installing"
                create_symlink "$skill_source" "$link_path" ".claude/skills/$skill"
                added=$((added + 1))
            fi
        fi
    done

    # Check expected tool symlinks
    for tool in "${TOOLS[@]}"; do
        local link_path="$PROJECT_PATH/.eval/dist/tools/$tool"
        expected_links+=("$link_path")
        if [ ! -L "$link_path" ]; then
            local tool_source="$AUTOEVAL_REPO/src/tools/$tool"
            if [ -f "$tool_source" ]; then
                echo "  MISSING: .eval/dist/tools/$tool — installing"
                create_symlink "$tool_source" "$link_path" ".eval/dist/tools/$tool"
                added=$((added + 1))
            fi
        fi
    done

    # Check for extra symlinks (not in expected list)
    # Check .claude/skills/
    if [ -d "$PROJECT_PATH/.claude/skills" ]; then
        for entry in "$PROJECT_PATH/.claude/skills"/*; do
            if [ -L "$entry" ]; then
                if [[ ! " ${expected_links[*]} " =~ " $entry " ]]; then
                    echo "  EXTRA: $entry"
                    extra=$((extra + 1))
                fi
            fi
        done
    fi

    # Check .eval/dist/tools/
    if [ -d "$PROJECT_PATH/.eval/dist/tools" ]; then
        for entry in "$PROJECT_PATH/.eval/dist/tools"/*; do
            if [ -L "$entry" ]; then
                if [[ ! " ${expected_links[*]} " =~ " $entry " ]]; then
                    echo "  EXTRA: $entry"
                    extra=$((extra + 1))
                fi
            fi
        done
    fi

    # Update manifest
    if [ "$DRY_RUN" = false ] && [ ${#LINKS_CREATED[@]} -gt 0 ]; then
        mkdir -p "$(dirname "$manifest")"
        {
            echo "# auto-eval skills manifest"
            echo "# AUTOEVAL_REPO=$AUTOEVAL_REPO"
            echo "# Reconcile: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
            echo ""
            for link in "${expected_links[@]}"; do
                echo "$link"
            done
        } > "$manifest"
    fi

    echo ""
    echo "Reconcile complete. Added $added missing, found $extra extra."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
case "$ACTION" in
    uninstall)
        do_uninstall
        ;;
    reconcile)
        do_reconcile
        ;;
    install)
        do_install
        ;;
esac