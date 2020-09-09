from myglobals import __dir__, s3_client, config, DNSSEC_DIR, NoLockError, BUCKET_NAME
from loader import loadFile, storeFile
from subprocess import run, PIPE
from os import path, stat
from stat import ST_MTIME, ST_SIZE

keyFiles = {}

def get_dnssec_keys():
    global keyFiles
    keyFiles = {}

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
    return keyFiles

def make_dnssec_keys(zone, mutex):
    global keyFiles

    zone_name = zone['name']
    k = 'K%s.' % zone_name
    if k in keyFiles and keyFiles[k] >= 4:
        return False

    if not mutex.locked:
        print('[%s] Can\'t find DNSSEC keys for zone. Acquiring lock.' % zone_name)
        if not mutex.lock():
            print('[%s] Can\'t acquire lock. Raising exception' % zone_name)
            raise NoLockError()
        print('[%s] Re-acquiring keyfiles...' % zone_name)
        get_dnssec_keys()
        if k in keyFiles and keyFiles[k] >= 4:
            return False

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
    return True

def sign_zone(zone, renew_dnssec):
    zone_name = zone['name']
    zoneFile = '/etc/powerdns/sites/db.%s' % zone_name
    signedZoneFile = '%s.signed' % zoneFile

    if not renew_dnssec:
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
            return False

    run(['dnssec-signzone', '-K', DNSSEC_DIR, '-o', zone_name, '-S', zoneFile])
    run(['pdnsutil', 'set-presigned', zone_name])
    return True