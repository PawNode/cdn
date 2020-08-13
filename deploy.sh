#!/bin/bash
set -euo pipefail

DEPLOY_TMP=/tmp/deploy.sh
if [ "$0" != "$DEPLOY_TMP" ]
then
    cd "$(dirname "$0")"

    cp "$0" "$DEPLOY_TMP"
    exec "$DEPLOY_TMP"

    echo 'Could not re-execute self... :('
    exit 1
fi

for keyfile in `ls files/trusted_keys`
do
    gpg --import "files/trusted_keys/$keyfile"
done

git fetch
git verify-commit origin/master
git reset --hard origin/master

exec ./deploy_run.sh
echo 'Could not exec deploy_run.sh'
exit 1
