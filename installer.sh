#!/bin/bash
set -euo pipefail

# MAKE SURE LOCAL HOSTNAME IS BOTH SET VIA hostnamectl AND PRESENT AS 127.0.1.1 IN /etc/hosts
# MAKE SURE TO dpkg-reconfigure locales to en-US.UTF-8!

ID="$(cat /opt/cdn-id)"
printf "$ID * * * * python3 /opt/cdn/certifier --renew-dnssec --no-ssl\n* * * * * python3 /opt/cdn/certifier\n@reboot bash /opt/cdn/configurator/out/ips.sh\n" | crontab

cd "$(dirname "$0")"

addIfMissing() {
    if ! grep -qF "$2" "$1"
    then
        echo "$2" >> "$1"
    fi
}

apt-get -y install pdns-server pdns-backend-bind python3 python3-acme python3-boto3 python3-josepy python3-jinja2 python3-pycryptodome bird apparmor-utils sudo git gcc libfuse-dev fuse bind9utils software-properties-common at python3-dnspython python3-requests python3-pip docker.io
pip3 install dyndbmutex

enableStart() {
    systemctl enable "$1"
    systemctl restart "$1"
}

rm -rf certifier/dnssec
ln -sf /etc/powerdns/dnssec certifier/dnssec
mkdir -p /etc/powerdns/sites /var/www/empty /var/www/sites /etc/powerdns/dnssec /etc/nginx/includes /mnt/certifier/keys /mnt/certifier/certs
chown pdns:pdns /etc/powerdns/dnssec /opt/cdn/certifier/dnssec
chmod 700 /etc/powerdns/dnssec /opt/cdn /mnt/certifier /mnt/certifier/* || true
chmod 600 /opt/cdn/config.yml

if [ ! -f /var/lib/powerdns/bind-dnssec.db ]
then
    pdnsutil create-bind-db /var/lib/powerdns/bind-dnssec.db
fi
chown pdns:pdns /var/lib/powerdns/bind-dnssec.db /var/lib/powerdns

cp files/pdns.conf /etc/powerdns/pdns.d/custom.conf

enableStart bird
enableStart bird6
enableStart pdns || true
#enableStart nginx

if [ ! -f /etc/ssl/default.crt ]
then
    openssl req -newkey rsa:4096 -nodes -keyout /etc/ssl/default.key -x509 -days 1 -out /etc/ssl/default.crt -subj '/CN=invalid.pawnode.com'
fi

# FALLBACKFS
if [ ! -d /opt/deffs ]
then
    git clone https://github.com/Doridian/deffs /opt/deffs
fi
gcc -O2 -D_FILE_OFFSET_BITS=64 /opt/deffs/main.c -lfuse -o /usr/bin/deffs

addIfMissing /etc/fstab 'deffs#/opt/cdn/certifier/certs /mnt/certifier/certs fuse defaults,nonempty,deffile=/etc/ssl/default.crt 0 0'
addIfMissing /etc/fstab 'deffs#/opt/cdn/certifier/keys /mnt/certifier/keys fuse defaults,nonempty,deffile=/etc/ssl/default.key 0 0'
mount -a
# END FALLBACKS

# SET UP NTP
apt-get -y install chrony
enableStart chrony
# END NTP

exec ./deploy_run.sh
echo 'Could not exec deploy_run.sh'
exit 1
