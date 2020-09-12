from myacme import get_ssl_for_site
from yaml import safe_load as yaml_load
from myglobals import __dir__, s3_client, config, DNSSEC_DIR, NoLockError, BUCKET_NAME
from os import chdir, path, system, environ
from argparse import ArgumentParser
from dyndbmutex.dyndbmutex import DynamoDbMutex
from socket import getfqdn
from mydnssec import get_dnssec_keys, make_dnssec_keys, sign_zone

parser = ArgumentParser(description='PawNode CDN certifier')
parser.add_argument('--renew-dnssec', help='Re-sign DNSSEC signatures', action='store_true')
parser.add_argument('--no-ssl', help='Skip SSL/TLS certificate things', dest='ssl', action='store_false')
parser.add_argument('--no-acme', help='Skip ACME things', dest='acme', action='store_false')
parser.add_argument('--no-dnssec', help='Skip DNSSEC things', dest='dnssec', action='store_false')
args = parser.parse_args()

chdir(__dir__)

sites = []
zones = []
ccConfig = None
with open(path.join(__dir__, 'config.yml'), 'r') as f:
    ccConfig = yaml_load(f.read())
    sites = ccConfig['sites']
    zones = ccConfig['zones']

reloadDNS = False
reloadNginx = False

if args.dnssec:
    mutex = DynamoDbMutex('pawnode-certifier-dnssec', holder=getfqdn(), timeoutms=300 * 1000)

    try:
        get_dnssec_keys()
        for zone in zones:
            reloadDNS |= make_dnssec_keys(zone, mutex)
            reloadDNS |= sign_zone(zone, args.renew_dnssec)
    except NoLockError:
        print('Skipping DNSSEC. Can\'t get lock.')
    finally:
        if mutex.locked:
            mutex.release()

if reloadDNS:
    system('chown -R pdns:pdns %s' % DNSSEC_DIR)
    system('pdns_control reload')

if args.ssl:
    mutex = DynamoDbMutex('pawnode-certifier-ssl', holder=getfqdn(), timeoutms=300 * 1000)

    try_acme = args.acme

    try:
        for site in sites:
            try:
                reloadNginx |= get_ssl_for_site(site, try_acme, mutex, ccConfig)
            except NoLockError:
                try_acme = False
    finally:
        if mutex.locked:
            mutex.release()

if reloadNginx:
    system('docker exec nginx killall -HUP nginx')
