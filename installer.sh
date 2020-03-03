#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

addIfMissing() {
    if ! grep -q "$1" "$2"
    then
        echo "$1" >> "$2"
    fi
}

mkdir -p /var/www/empty /var/www/sites /etc/bind/sites

addIfMissing /etc/bind/named.conf.local 'include "/etc/bind/sites.conf";'

if [ ! -f /etc/ssl/default.crt ]
then
    openssl req -newkey rsa:4096 -nodes -keyout /etc/ssl/default.key -x509 -days 1 -out /etc/ssl/default.crt
fi

python3 ./configurator
