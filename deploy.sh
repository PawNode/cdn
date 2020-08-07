#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

git pull -r

python3 configurator
python3 certifier
#python3 wg
