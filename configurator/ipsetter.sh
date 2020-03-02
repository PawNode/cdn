#!/bin/bash
cd "$(dirname "$0")" || exit 1

cat out/ips.txt | xargs -n 1 ip addr add dev lo
cat out/ip_rules.txt | xargs -n 1 ip rule add lookup 666 src
