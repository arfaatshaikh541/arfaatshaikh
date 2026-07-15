#!/usr/bin/env bash
# Seeds the platform catalogue (safe for every environment) and, unless
# GRIDKEEP_SKIP_DEMO_SEED is set, the fictional demo tenant used for local
# development and product demonstrations.
set -euo pipefail
cd "$(dirname "$0")/../../apps/api"

python -m seed.bootstrap

if [ -z "${GRIDKEEP_SKIP_DEMO_SEED:-}" ]; then
  python -m seed.demo
fi
