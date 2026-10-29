#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec node e2e/stack.mjs
