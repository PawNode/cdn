#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

for keyfile in `ls files/trusted_keys/*.asc`
do
    gpg --import "$keyfile"
done
gpg --import-ownertrust 'files/trusted_keys/ownertrust.txt'

python3 configurator
python3 certifier --no-acme
