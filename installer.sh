#!/bin/bash
set -euo pipefail

ID="$1"

cd "$(dirname "$0")"

addIfMissing() {
    if ! grep -qF "$2" "$1"
    then
        echo "$2" >> "$1"
    fi
}

curl https://repo.powerdns.com/FD380FBB-pub.asc | apt-key add -
cp files/apt/*.list /etc/apt/sources.list.d/
cp files/apt/*.conf /etc/apt/preferences.d/

apt update
apt -y install pdns-server pdns-backend-lua2 nginx python3 python3-acme python3-boto3 python3-josepy python3-jinja2 python3-crypto bird apparmor-utils sudo git gcc libfuse-dev
aa-complain /usr/sbin/named

enableStart() {
    systemctl enable "$1"
    systemctl start "$1"
}

printf "$ID * * * * python3 /opt/cdn/certifier\n@reboot bash /opt/cdn/configurator/out/ips.sh\n" | crontab

rm -rf certifier/dnssec
ln -s /etc/powerdns/dnssec certifier/dnssec
mkdir -p /var/www/empty /var/www/sites /etc/powerdns/dnssec /etc/nginx/includes /mnt/certifier/keys /mnt/certifier/certs
chown pdns:pdns /etc/powerdns/dnssec /opt/cdn/certifier/dnssec
chmod 700 /etc/powerdns/dnssec /opt/cdn /mnt/certifier /mnt/certifier/* || true
chmod 600 /opt/cdn/config.yml

cp files/pdns.conf /etc/powerdns/pdns.d/custom.conf

enableStart bird
enableStart bird6
enableStart pdns || true
enableStart nginx

if [ ! -f /etc/ssl/default.crt ]
then
    openssl req -newkey rsa:4096 -nodes -keyout /etc/ssl/default.key -x509 -days 1 -out /etc/ssl/default.crt
fi

# GITHUB DEPLOY
useradd deployer
cp files/deployer-sudo /etc/sudoers.d/
mkdir -p /home/deployer/.ssh
cp files/deployer-authorized-keys /home/deployer/.ssh/authorized_keys
chown -R deployer:deployer /home/deployer
chmod 600 /home/deployer/.ssh/authorized_keys
chmod 700 /home/deployer/.ssh
# END GITHUB DEPLOY

# FALLBACKFS
if [ ! -f /opt/deffs ]
then
    git clone https://github.com/Doridian/deffs /opt/deffs
fi
gcc -O2 -D_FILE_OFFSET_BITS=64 /opt/deffs/main.c -lfuse -o /usr/bin/deffs

addIfMissing /etc/fstab 'deffs#/opt/cdn/certifier/certs /mnt/certifier/certs fuse defaults,deffile=/etc/ssl/default.crt 0 0'
addIfMissing /etc/fstab 'deffs#/opt/cdn/certifier/keys /mnt/certifier/keys fuse defaults,deffile=/etc/ssl/default.key 0 0'
mount -a
# END FALLBACKS

python3 configurator
python3 certifier
