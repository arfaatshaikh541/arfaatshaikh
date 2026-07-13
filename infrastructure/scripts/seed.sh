#!/usr/bin/env bash
# Populate the platform super admin + Rafana Advisory Demo tenant.
# Safe to run multiple times (idempotent) - see apps/api/app/seed.py.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../../apps/api"
python -m app.seed
