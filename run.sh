#!/usr/bin/env bash
# Logged build driver for the Skills_n_Agents library.
#
#   ./run.sh                run every step (build + verify)
#   ./run.sh --list         list the declared steps
#   ./run.sh --only NAME    run a single step
#   ./run.sh --skip NAME    skip a step (repeatable)
#
# Each step is snapshotted, logged and validated. Results land in
# logs/<run_id>/ — see README.md ("Rebuilding") and rollback.sh.
#
# Nothing is ever deleted from logs/ without asking.
set -euo pipefail
cd "$(dirname "$0")"

exec python3 .run_steps.py "$@"
