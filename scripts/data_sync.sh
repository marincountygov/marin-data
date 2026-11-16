#!/usr/bin/env bash
# Brings a consumer up to date with marin-data and checks the result. It does not commit or push.
#
#   bash marin-data/scripts/data_sync.sh marin-links
#
# The consumer's folder and marin-data must sit side by side, and the consumer must have no uncommitted changes.
# 1. Runs the sync and build commands for the consumer from consumers.json.
# 2. If no file changed, stops. The consumer is already up to date.
# 3. Otherwise writes marin-data.lock, then runs the consumer's own check.sh. If the check fails, so does this.
# Writes changed=true or changed=false to $GITHUB_OUTPUT when it is set.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
CONSUMER=$(cd -- "${1:?usage: data_sync.sh <consumer folder>}" && pwd)
out() { [[ -z "${GITHUB_OUTPUT:-}" ]] || printf '%s\n' "$1" >> "$GITHUB_OUTPUT"; }

cd "$CONSUMER"
[[ -z "$(git status --porcelain)" ]] || { printf 'ERROR: %s has uncommitted changes. Commit or stash them first.\n' "$CONSUMER" >&2; exit 1; }

python3 "$HERE/scripts/sync_consumer.py" "$CONSUMER"

if [[ -z "$(git status --porcelain)" ]]; then
  printf 'No file changed. %s is up to date with marin-data.\n' "$(basename "$CONSUMER")"
  out "changed=false"
  exit 0
fi

bash "$HERE/scripts/lock.sh" "$CONSUMER"
bash scripts/check.sh
git status --short
out "changed=true"
