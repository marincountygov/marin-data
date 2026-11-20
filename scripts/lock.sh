#!/usr/bin/env bash
# Records which marin-data commit a consumer has synced, in <consumer>/marin-data.lock.
# The consumer's CI checks out exactly that commit, so a later change to marin-data cannot turn it red.
#
#   bash scripts/lock.sh ../marin-pulse
#
# Refuses if marin-data has uncommitted changes or its commit is not on origin/main yet: the CI could not fetch it.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ -d "${1:?usage: lock.sh <consumer folder>}" ]] || { printf 'ERROR: %s is not a folder.\n' "$1" >&2; exit 1; }
CONSUMER=$(cd -- "$1" && pwd)   # an absolute path, because this script changes folder below
cd "$ROOT"
[[ -z "$(git status --porcelain)" ]] || { printf 'ERROR: marin-data has uncommitted changes. Commit them, then lock.\n' >&2; exit 1; }
SHA=$(git rev-parse HEAD)
git fetch --quiet origin main
git merge-base --is-ancestor "$SHA" origin/main || { printf 'ERROR: %s is not on origin/main yet. Push marin-data first.\n' "$SHA" >&2; exit 1; }
printf '%s\n' "$SHA" > "$CONSUMER/marin-data.lock"
printf 'Locked %s to marin-data %s\n' "$(basename "$(cd "$CONSUMER" && pwd)")" "${SHA:0:12}"
