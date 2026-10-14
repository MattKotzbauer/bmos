#!/usr/bin/env bash
# Local private-lab layout: LAB/bmos/tools/run.sh. No shell/profile installation.
set -euo pipefail
bmos_tools="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
export BMOS_LAB="${BMOS_LAB:-$(cd "$bmos_tools/../.." && pwd)}"
exec python "$bmos_tools/launch.py"
