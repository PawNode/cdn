from myacme import get_ssl_for_site
from yaml import safe_load as yaml_load
from myglobals import __dir__, s3_client, config, DNSSEC_DIR, NoLockError
from os import chdir, path, system, stat, environ
from stat import ST_SIZE, ST_MTIME
from loader import loadFile, storeFile
from subprocess import run, PIPE
from argparse import ArgumentParser
from dyndbmutex.dyndbmutex import DynamoDbMutex
from socket import getfqdn

parser = ArgumentParser(description='PawNode CDN certifier')
parser.add_argument('--renew-dnssec', help='Re-sign DNSSEC signatures', action='store_true')
parser.add_argument('--no-ssl', help='Skip SSL/TLS certificate things', dest='ssl', action='store_false')
parser.add_argument('--no-acme', help='Skip ACME things', dest='acme', action='store_false')
parser.add_argument('--no-dnssec', help='Skip DNSSEC things', dest='dnssec', action='store_false')
args = parser.parse_args()

chdir(__dir__)

BUCKET_NAME = config['crypto']['bucketName']

sites = []
zones = []
keyFiles = {}
ccConfig = None
with open(path.join(__dir__, 'config.yml'), 'r') as f:
    ccConfig = yaml_load(f.read())
    sites = ccConfig['sites']
    zones = ccConfig['zones']

paginator = s3_client.get_paginator('list_objects_v2')
for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix='dnssec'):
    if not 'Contents' in page:
        continue

    for obj in page['Contents']:
        loadFile(obj['Key'])
        k = obj['Key'][7:].split('+')[0]
        if k in keyFiles:
            keyFiles[k] += 1
        else:
            keyFiles[k] = 1

reloadDNS = False
reloadNginx = False

if args.dnssec:
    for zone in zones:
        zone_name = zone['name']
        k = 'K%s.' % zone_name
        if k in keyFiles and keyFiles[k] >= 4:
            continue
        print('[%s] Generating DNSSEC keys for zone' % zone_name)
        files = []
        res = run(['dnssec-keygen', '-K', DNSSEC_DIR, '-a', 'ECDSAP256SHA256', zone_name], stdout=PIPE, encoding='ascii').stdout.strip()
        files.append("%s.key" % res)
        files.append("%s.private" % res)
        res = run(['dnssec-keygen', '-K', DNSSEC_DIR, '-fk', '-a', 'ECDSAP256SHA256', zone_name], stdout=PIPE, encoding='ascii').stdout.strip()
        files.append("%s.key" % res)
        files.append("%s.private" % res)
        for fn in files:
            fh = open(path.join(DNSSEC_DIR, fn), 'rb')
            fd = fh.read()
            fh.close()
            storeFile('dnssec/%s' % fn, fd)
        reloadDNS = True

    for zone in zones:
        zone_name = zone['name']
        zoneFile = '/etc/powerdns/sites/db.%s' % zone_name
        signedZoneFile = '%s.signed' % zoneFile

        if not args.renew_dnssec:
            zoneStat = stat(zoneFile)
            zoneMtime = zoneStat[ST_MTIME]

            signedZoneSize = 0
            signedZoneMtime = 0
            try:
                signedZoneStat = stat(signedZoneFile)
                signedZoneSize = signedZoneStat[ST_SIZE]
                signedZoneMtime = signedZoneStat[ST_MTIME]
            except FileNotFoundError:
                pass

            if signedZoneSize > 0 and signedZoneMtime >= zoneMtime:
                continue

        run(['dnssec-signzone', '-K', DNSSEC_DIR, '-o', zone_name, '-S', zoneFile])
        run(['pdnsutil', 'set-presigned', zone_name])
        reloadDNS = True

if args.ssl:
    mutex = DynamoDbMutex('pawnode-cdn-certifier-ssl', holder=getfqdn(), timeoutms=300 * 1000)

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

if reloadDNS:
    system('chown -R pdns:pdns %s' % DNSSEC_DIR)
    system('pdns_control reload')

if reloadNginx:
    system('service nginx reload')
