from datetime import timezone
from io import BytesIO
from jinja2 import Environment, FileSystemLoader, select_autoescape
from os import path, unlink, rename, system, mkdir, symlink
from requests import get as http_get
from shutil import rmtree
from yaml import load as yaml_load, dump as yaml_dump
from zipfile import ZipFile
from socket import getfqdn
from boto3 import client as boto3_client

__dir__ = path.dirname(__file__)

config = None
with open(path.join(__dir__, '../config.yml'), 'r') as f:
    config = yaml_load(f)

osconfig = config['objectStorage']
s3_client = boto3_client('s3',
    aws_access_key_id=osconfig['accessKeyID'],
    aws_secret_access_key=osconfig['secretAccessKey']
)

CFG_BUCKET_NAME = config['dynConfig']['bucketName']
def downloadSite(name, prefix='sites/'):
    obj = s3_client.get_object(
        Bucket=CFG_BUCKET_NAME,
        Key=('%s%s.yml' % (prefix, name))
    )
    return yaml_load(obj['Body']), obj

dynConfig, _ = downloadSite('main', '')

tags = []
def recurseTags(tag):
    global dynConfig
    global tags
    if tag in tags:
        return
    tags.append(tag)

    if tag not in dynConfig:
        return
    cfg = dynConfig[tag]
    if 'tags' not in cfg:
        return

    subTags = cfg['tags']
    for subTag in subTags:
        recurseTags(subTag)

recurseTags(getfqdn())
recurseTags('all')

print('My tags are: %s' % ', '.join(tags))

location_nodes = {}
ips = set()
for tag in dynConfig:
    val = dynConfig[tag]
    if 'primaryIp' in val:
        ips.add(val['primaryIp'])
    if 'location' in val:
        loc = val['location']
        if loc not in location_nodes:
            location_nodes[loc] = set()
        location_nodes[loc].add(tag)
dynConfig['_locations'] = location_nodes
dynConfig['_ips'] = ips

__closest_grp = {}
def dynConfigFindClosest(grp):
    global __closest_grp

    if grp in __closest_grp:
        return __closest_grp[grp]

    for tag in tags:
        if tag not in dynConfig:
            continue
        cfg = dynConfig[tag]
        if grp not in cfg:
            continue
        print('DynConf: Using %s as closest for %s' % (tag, grp))
        dc = cfg[grp]
        __closest_grp[grp] = dc
        return dc

dynConfig['_self'] = dynConfig[getfqdn()]
dynConfig['_self']['_name'] = getfqdn()
dynConfig['_find'] = dynConfigFindClosest

SITEDIR = config['siteDir']
DEFAULT_KEY = config['defaultKey']
DEFAULT_CERT = config['defaultCert']

DIR = path.abspath(path.join(__dir__, 'sites'))
OUTDIR = path.abspath(path.join(__dir__, 'out'))
OLDDIR = path.abspath(path.join(OUTDIR, 'sites'))
CERTIFIER_DIR = path.abspath(path.join(__dir__, '../certifier'))
CERTDIR = path.abspath(path.join(CERTIFIER_DIR, 'certs'))
KEYDIR = path.abspath(path.join(CERTIFIER_DIR, 'keys'))
DNSSECDIR = '/etc/bind/dnssec'

dynConfig['_self']['dnssecDir'] = DNSSECDIR
dynConfig['_self']['certDir'] = CERTDIR
dynConfig['_self']['keyDir'] = KEYDIR

j2env = Environment(
    loader=FileSystemLoader(path.join(__dir__, 'templates')),
    autoescape=select_autoescape([])
)
nginxSiteTemplate = j2env.get_template('nginx/site.conf.j2')
nginxMainTemplate = j2env.get_template('nginx/main.conf.j2')
bindZoneTemplate = j2env.get_template('bind/zone.j2')
bindSiteTemplate = j2env.get_template('bind/site.conf.j2')

def writeGlobalTpl(name, target):
    tpl = j2env.get_template(name)
    data = tpl.render(config=config,dynConfig=dynConfig,tags=tags)
    return swapFile(target, data)

def writeNginxInclude(name):
    return writeGlobalTpl('nginx/%s.conf.j2' % name, '/etc/nginx/includes/%s.conf' % name)

def loadSiteNoop(site, oldSite, force):
    return

def loadSiteZIP(site, oldSite, force):
    outDir = path.join(SITEDIR, site['name'])
    site['dir'] = outDir

    if oldSite and not force and site['src'] == oldSite['src']:
        return

    newDir = '%s___new' % outDir
    oldDir = '%s___old' % outDir
    
    rmtree(newDir, ignore_errors=True)
    rmtree(oldDir, ignore_errors=True)
    rmtree(newDir, ignore_errors=True)

    mkdir(newDir)
    
    r = http_get(site['src'], stream=True)
    z = ZipFile(BytesIO(r.content))
    z.extractall(newDir)

    try:
        rename(outDir, oldDir)
    except FileNotFoundError:
        pass

    rename(newDir, outDir)
    rmtree(oldDir, ignore_errors=True)


def swapFile(fn, content):
    newfile = '%s.new' % fn
    fh = open(newfile, 'w')
    fh.write(content)
    fh.close()

    try:
        fh = open(fn, 'r')
        oldcontent = fh.read()
        fh.close()
        if oldcontent == content:
            print('<%s> Old == New' % fn)
            unlink(newfile)
            return False

        unlink(fn)
    except FileNotFoundError:
        pass

    print('<%s> Old != New' % fn)
    rename(newfile, fn)

    return True

def symlinkCert(name):
    name = '%s.pem' % name
    certName = path.join(CERTDIR, name)
    keyName = path.join(KEYDIR, name)
    if not path.lexists(certName):
        symlink(DEFAULT_CERT, certName)
    if not path.lexists(keyName):
        symlink(DEFAULT_KEY, keyName)

SITE_LOADERS = {
    'redirect': loadSiteNoop,
    'none': loadSiteNoop,
    'directproxy': loadSiteNoop,
    'zip': loadSiteZIP
}

zones = {}
def addZoneFor(domain, site):
    if domain in zones:
        return

    spl = domain.split('.')
    for i in range(1, len(spl) + 1):
        out = '.'.join(spl[-i:])
        if out in zones:
            zone = zones[out]
            zone['domains'].add(domain)
            if site['zoneSerial'] > zone['serial']:
                zone['serial'] = site['zoneSerial']
            return

    zone = {
        'domains': set([domain]),
        'site': site,
        'serial': site['zoneSerial'],
        'name': domain
    }
    zones[domain] = zone

    dotted = '.%s' % domain
    todel = set()
    for zone_name in zones:
        if zone_name[-len(dotted):] == dotted:
            otherZone = zones[zone_name]
            if otherZone['serial'] > zone['serial']:
                zone['serial'] = otherZone['serial']
            zone['domains'].add(zone_name)
            todel.add(zone_name)
    for zone_name in todel:
        del zones[zone_name]

def run():
    nginxConfig = [nginxMainTemplate.render(config=config, dynConfig=dynConfig, tags=tags)]
    certifierConfig = []
    zoneListConfig = []
    loadedSites = {}
    reloadBind = False

    sites = []
    for tag in tags:
        if tag not in dynConfig:
            continue
        cfg = dynConfig[tag]
        if 'sites' in cfg:
            sites += cfg['sites']

    print('Found sites: %s' % ', '.join(sites))

    for site_name in sites:
        oldName = path.join(OLDDIR, '%s.yml' % site_name)

        print('[%s] Processing...' % site_name)

        site, obj = downloadSite(site_name)

        lastModified = obj['LastModified']
        
        site['zoneSerial'] = lastModified.replace(tzinfo=timezone.utc).timestamp()
        site['name'] = site_name

        loadedSites[site_name] = site

        oldSite = None
        try:
            fh = open(oldName, 'r')
            oldSite = yaml_load(fh)
            fh.close()
            print('[%s] Loaded old site data' % site_name)
        except:
            pass

        if not oldSite:
            print('[%s] No old site data' % site_name)
            oldSite = {
                'domains': [],
                'type': 'none',
            }
        
        oldSite['name'] = site_name

        symlinkCert(site_name)

        typeChanged = site['type'] != oldSite['type']
        if typeChanged:
            print('[%s] Type changed from %s to %s' % (site_name, oldSite['type'], site['type']))

        try:
            loader = SITE_LOADERS[site['type']]
            loader(site, oldSite, typeChanged)
            print('[%s] Loaded site' % site_name)
        except Exception as e:
            print('[%s] Error loading site:' % site_name, e)
            pass

        if site['type'] != 'none':
            domainsChanged = oldSite['domains'] != site['domains']
            if domainsChanged:
                print('[%s] Domains changed from %s to %s' % (site_name, ','.join(oldSite['domains']), ','.join(site['domains'])))
            certSite = {
                'name': site_name,
                'domains': site['domains']
            }
            certifierConfig.append(certSite)
            nginxConfig.append(nginxSiteTemplate.render(site=site, config=config, dynConfig=dynConfig, tags=tags))
        else:
            print('[%s] Site is type none. Not rendering nginx or certifier config' % site_name)

        for domain in site['domains']:
            addZoneFor(domain, site)

    for zone_name in zones:
        zone = zones[zone_name]
        zone['name'] = zone_name
        zoneListConfig.append(bindSiteTemplate.render(zone=zone, config=config, dynConfig=dynConfig, tags=tags))
        zoneConfig = bindZoneTemplate.render(zone=zone, config=config, dynConfig=dynConfig, tags=tags)
        if swapFile('/etc/bind/sites/db.%s' % zone_name, zoneConfig):
            reloadBind = True

    certifierConfStr = yaml_dump(certifierConfig)
    nginxConfStr = '\n'.join(nginxConfig)
    zoneListConfigStr = '\n'.join(zoneListConfig)

    if writeGlobalTpl('ips.sh.j2', path.join(OUTDIR, 'ips.sh')):
        system('bash \'%s\'' % path.join(OUTDIR, 'ips.sh'))

    if writeGlobalTpl('bird/main4.conf.j2', '/etc/bird/bird.conf'):
        system('service bird reload')

    if writeGlobalTpl('bird/main6.conf.j2', '/etc/bird/bird6.conf'):
        system('service bird6 reload')

    if swapFile('/etc/bind/sites.conf', zoneListConfigStr) or reloadBind:
        system('service bind9 reload')

    if writeNginxInclude('hsts') | \
        writeNginxInclude('proxy') | \
        writeNginxInclude('varnish') | \
        writeNginxInclude('wellknown') | \
        writeNginxInclude('headers') | \
        swapFile('/etc/nginx/conf.d/cdn.conf', nginxConfStr):
        system('service nginx reload')

    if swapFile(path.join(CERTIFIER_DIR, 'sites.yml'), certifierConfStr):
        system('python3 %s' % path.join(__dir__, '../certifier'))

    for name in loadedSites:
        oldName = path.join(OLDDIR, '%s.yml' % name)
        site = loadedSites[name]

        fh = open(oldName, 'w')
        fh.write(yaml_dump(site))
        fh.close()

run()
