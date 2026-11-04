#!/usr/bin/env bash
# Roll back a build run using its per-step snapshots.
#
#   ./rollback.sh --list                    list every run and its steps
#   ./rollback.sh <run_id>                  restore every file that run touched
#   ./rollback.sh <run_id> --step N         restore one step (N = the step number)
#   ./rollback.sh <run_id> --dry-run        show what would be restored
#
# This restores files from the run's snapshot directories. It does NOT touch
# git history — git remains the coarse-grained, whole-project revert.
#
# Files that did not exist before a step are deleted on rollback, because the
# step created them.
set -euo pipefail
cd "$(dirname "$0")"

exec python3 .rollback_steps.py "$@"
