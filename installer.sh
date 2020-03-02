#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"
git pull
if [ ! -f /etc/ssl/default.crt ]
then
    openssl req -newkey rsa:4096 -nodes -keyout /etc/ssl/default.key -x509 -days 1 -out /etc/ssl/default.crt
fi
