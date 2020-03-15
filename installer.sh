#!/bin/bash
set -euo pipefail

ID="$1"

cd "$(dirname "$0")"

addIfMissing() {
    if ! grep -q "$2" "$1"
    then
        echo "$2" >> "$1"
    fi
}

apt update
apt -y install bind9 nginx python3 python3-acme python3-boto3 python3-josepy python3-jinja2 python3-crypto bird apparmor-utils sudo
aa-complain /usr/sbin/named

enableStart() {
    systemctl enable "$1"
    systemctl start "$1"
}

printf "$ID * * * * python3 /opt/cdn/certifier\n@reboot bash /opt/cdn/configurator/out/ips.sh\n" | crontab

rm -rf certifier/dnssec
ln -s /etc/bind/dnssec certifier/dnssec
mkdir -p /var/www/empty /var/www/sites /etc/bind/sites /etc/bind/dnssec /etc/nginx/includes
chown bind:bind /etc/bind/sites /etc/bind/dnssec
chmod 700 /etc/bind/dnssec
chmod 700 /opt/cdn

cp files/named.conf.options /etc/bind/named.conf.options


addIfMissing /etc/bind/named.conf.local 'include "/etc/bind/sites.conf";'

enableStart bird
enableStart bird6
enableStart bind9
enableStart nginx

if [ ! -f /etc/ssl/default.crt ]
then
    openssl req -newkey rsa:4096 -nodes -keyout /etc/ssl/default.key -x509 -days 1 -out /etc/ssl/default.crt
fi

useradd deployer
cp files/deployer-sudo /etc/sudoers.d/
mkdir -p /home/deployer/.ssh
cp files/deployer-authorized-keys /home/deployer/.ssh/authorized_keys
chown -R deployer:deployer /home/deployer
chmod 600 /home/deployer/.ssh/authorized_keys
chmod 700 /home/deployer/.ssh

python3 configurator
python3 certifier
