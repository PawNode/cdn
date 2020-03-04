from myacme import get_ssl_for_site
from yaml import load as yaml_load
from myglobals import __dir__, s3_client, config, DNSSEC_DIR
from os import path, system
from loader import loadFile, storeFile
from subprocess import run, PIPE

BUCKET_NAME = config['certs']['bucketName']

sites = []
zones = []
keyFiles = {}
with open(path.join(__dir__, 'sites.yml'), 'r') as f:
    sites = yaml_load(f.read())

paginator = s3_client.get_paginator('list_objects_v2')
for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix='dnssec'):
    for obj in page['Contents']:
        loadFile(obj['Key'])
        k = obj['Key'][7:].split('+')[0]
        if k in keyFiles:
            keyFiles[k] += 1
        else:
            keyFiles[k] = 1

reloadBind = False
reloadNginx = False
for site in sites:
    reloadNginx |= get_ssl_for_site(site)
    zones.append(site['domains'][0])

for zone in zones:
    k = 'K%s.' % zone
    if k in keyFiles and keyFiles[k] >= 4:
        continue
    print('[%s] Generating DNSSEC keys for zone' % zone)
    files = []
    res = run(['dnssec-keygen', '-K', DNSSEC_DIR, '-a', 'ECDSAP256SHA256', zone], stdout=PIPE, encoding='ascii').stdout.strip()
    files.append("%s.key" % res)
    files.append("%s.private" % res)
    res = run(['dnssec-keygen', '-K', DNSSEC_DIR, '-fk', '-a', 'ECDSAP256SHA256', zone], stdout=PIPE, encoding='ascii').stdout.strip()
    files.append("%s.key" % res)
    files.append("%s.private" % res)
    for fn in files:
        fh = open(path.join(DNSSEC_DIR, fn), 'rb')
        fd = fh.read()
        fh.close()
        storeFile('dnssec/%s' % fn, fd)
    reloadBind = True

if reloadBind:
    system('chown -R bind:bind %s' % DNSSEC_DIR)
    system('service bind9 reload')

if reloadNginx:
    system('service nginx reload')

