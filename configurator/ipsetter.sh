#!/bin/bash
cd "$(dirname "$0")" || exit 1

cat out/ips.txt | xargs -n 1 ip addr add dev lo addr
