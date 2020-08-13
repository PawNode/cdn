#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

DEPLOY_TMP=/tmp/deploy.sh
if [ "$0" != "$DEPLOY_TMP" ]
then
    cp "$0" "$DEPLOY_TMP"
    exec "$DEPLOY_TMP"

    echo 'Could not re-execute self... :('
    exit 1
fi

git pull -r

# TODO: VERIFY

exec ./deploy_run.sh
echo 'Could not exec deploy_run.sh'
exit 1
