#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

python3 configurator
python3 certifier
#python3 wg
