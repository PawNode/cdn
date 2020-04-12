#!/bin/bash

set -euo pipefail

s() {
	IP="$1"
	shift 1
	echo "Running on $IP ($@)"
	ssh "$IP.pawnode.com" "sudo $@"
#	ssh "$IP" "sudo $@"
}

sa() {
	s fra01 "$@"
	s sea01 "$@"
#	s van01 "$@"
	s nyc01 "$@"
#	s 95.179.240.248 "$@"
#	s 108.61.78.245 "$@"
#	s 66.42.79.223 "$@"
}

sa 'sudo add-apt-repository ppa:wireguard/wireguard && sudo apt -y install wireguard'

#sa 'git -C /opt/cdn pull -r; sudo rm -f /etc/powerdns/sites/*.signed'
#sa 'sudo rm -f /var/lib/powerdns/bind-dnssec.db*; sudo pdnsutil create-bind-db /var/lib/powerdns/bind-dnssec.db; sudo chown pdns:pdns /var/lib/powerdns/bind-dnssec.db; sudo systemctl restart pdns'
#sa 'sudo python3 /opt/cdn/configurator; sudo python3 /opt/cdn/certifier; sudo cp /opt/cdn/files/pdns.conf /etc/powerdns/pdns.d/custom.conf'

#sa 'cp /opt/cdn/files/pdns.conf /etc/powerdns/pdns.d/custom.conf'
#sa 'systemctl restart pdns'

#sa 'mkdir -p /etc/nginx/includes'
#sa 'rm /etc/bind/sites/*'
#sa 'curl https://repo.powerdns.com/FD380FBB-pub.asc | sudo apt-key add; sudo cp /opt/cdn/files/apt/pdns.list /etc/apt/sources.list.d/; sudo cp /opt/cdn/files/apt/pdns.conf /etc/apt/preferences.d/; sudo apt update; sudo apt remove bind9; sudo apt install pdns-server pdns-backend-lua2; sudo cp /opt/cdn/files/pdns.conf /etc/powerdns/pdns.d/custom.conf; sudo systemctl restart pdns'
#sa 'rm -f /opt/cdn/certifier/dnssec; sudo ln -sf /etc/powerdns/dnssec /opt/cdn/certifier/dnssec; sudo mkdir -p  /etc/powerdns/dnssec; sudo chown pdns:pdns /etc/powerdns/dnssec /opt/cdn/certifier/dnssec; sudo chmod 700 /etc/powerdns/dnssec'
#sa 'mkdir -p /etc/powerdns/sites'
#sa 'rm -f /etc/apt/preferences.d/pdns.conf'
#sa 'cp /opt/cdn/files/apt/pdns /etc/apt/preferences.d/pdns'
#sa 'cp /opt/cdn/files/backend.lua /etc/powerdns/backend.lua'
#sa 'apt install pdns-backend-bind pdns-backend-lua2'
#sa 'python3 /opt/cdn/configurator'
