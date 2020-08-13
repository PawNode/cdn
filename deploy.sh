#!/bin/bash
set -euo pipefail

if [ "${1-top}" != 'sub' ]
then
    DEPLOY_TMP="$(mktemp --suffix=.sh)"
    rm -f "$DEPLOY_TMP"

    cd "$(dirname "$0")"

    cp "$0" "$DEPLOY_TMP"
    exec "$DEPLOY_TMP" sub

    echo 'Could not re-execute self... :('
    exit 1
fi

rm -f "$0"

git pull --verify-signatures

exec ./deploy_run.sh
echo 'Could not exec deploy_run.sh'
exit 1
