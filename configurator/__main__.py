from datetime import timezone, datetime
from io import BytesIO
from jinja2 import Environment, FileSystemLoader, select_autoescape
from os import chdir, listdir, path, unlink, rename, system, mkdir, stat
from sys import path as sys_path
from requests import get as http_get
from shutil import rmtree
from yaml import safe_load as yaml_load, dump as yaml_dump
from zipfile import ZipFile
from socket import getfqdn
from subprocess import PIPE, run

__dir__ = path.abspath(path.dirname(__file__))
chdir(__dir__)
sys_path.append(path.dirname(__dir__))

from config import config, decryptString

SITECONFIGDIR = path.abspath(path.join(__dir__, '../sites'))
def getGitTime(fn):
    res = run(['git', 'log', '-1', '--format="%ad"', '--date=iso8601', '--', fn], stdout=PIPE, encoding='ascii').stdout
    res = res.strip(' \'"\t\r\n')
    return datetime.strptime(res, '%Y-%m-%d %H:%M:%S %z')

def getGitRevision():
    res = run(['git', 'rev-parse', 'HEAD'], stdout=PIPE, encoding='ascii').stdout
    res = res.strip(' \'"\t\r\n')
    return res

def loadSite(name):
    fn = path.join(SITECONFIGDIR, name)
    fh = open(fn, 'r')
    data = fh.read()
    fh.close()
    return yaml_load(data), getGitTime(fn)

dynConfig, _ = loadSite('__main__.yml')

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
    if 'inherit' not in cfg:
        return

    subTags = cfg['inherit']
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
dynConfig['_self']['_gitrev'] = getGitRevision()
dynConfig['_find'] = dynConfigFindClosest

SITEDIR = config['siteDir']

DIR = path.abspath(path.join(__dir__, 'sites'))
OUTDIR = path.abspath(path.join(__dir__, 'out'))
OLDDIR = path.abspath(path.join(OUTDIR, 'sites'))
CERTIFIER_DIR = path.abspath(path.join(__dir__, '../certifier'))
DNSSECDIR = '/etc/powerdns/dnssec'
CERTIFIER_DEFFS_DIR = '/mnt/certifier'

dynConfig['_self']['dnssecDir'] = DNSSECDIR
dynConfig['_self']['certDir'] = path.abspath(path.join(CERTIFIER_DEFFS_DIR, 'certs'))
dynConfig['_self']['keyDir'] = path.abspath(path.join(CERTIFIER_DEFFS_DIR, 'keys'))

j2env = Environment(
    loader=FileSystemLoader(path.join(__dir__, 'templates')),
    autoescape=select_autoescape([])
)

RECORD_MAX_LEN = 240
def j2_escape_txt_record(value):
    escaped = value.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'

def j2_format_txt_record(value):
    value_len = len(value)
    if value_len <= RECORD_MAX_LEN:
        return j2_escape_txt_record(value)
    
    result = []
    for i in range(0, value_len, RECORD_MAX_LEN):
        result.append(j2_escape_txt_record(value[i:i+RECORD_MAX_LEN]))
    return ' '.join(result)

j2env.filters['format_txt_record'] = j2_format_txt_record

nginxSiteTemplate = j2env.get_template('nginx/site.conf.j2')
nginxMainTemplate = j2env.get_template('nginx/main.conf.j2')
bindZoneTemplate = j2env.get_template('bind/zone.j2')

zoneTplLastModified = getGitTime(path.join(__dir__, 'templates', 'bind', 'zone.j2'))

zones = {}

def decryptStringAscii(encryptedStr):
    return decryptString(encryptedStr).decode('ascii')

def writeGlobalTpl(name, target):
    tpl = j2env.get_template(name)
    data = tpl.render(zones=zones, config=config, dynConfig=dynConfig, tags=tags, decrypt=decryptStringAscii)
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

SITE_LOADERS = {
    'none': loadSiteNoop,
    'empty': loadSiteNoop,
    'redirect': loadSiteNoop,
    'directproxy': loadSiteNoop,
    'zip': loadSiteZIP
}

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

def __main__():
    allnodes = []

    for node in dynConfig.keys():
        if node[0] == '_' or 'noServer' in dynConfig[node]:
            continue
        allnodes.append(node)

    nginxConfig = [nginxMainTemplate.render(config=config, dynConfig=dynConfig, tags=tags)]
    certifierConfig = {
        'sites': [],
        'zones': [],
        'siteips4': dynConfigFindClosest('siteips4'),
        'siteips6': dynConfigFindClosest('siteips6'),
        'sitecname': dynConfigFindClosest('sitecname'),
        'allnodes': allnodes,
        'gitrev': dynConfig['_self']['_gitrev'],
    }
    loadedSites = {}
    reloadDNS = False

    sites = []
    for fn in listdir(SITECONFIGDIR):
        if fn[0] == '.' or fn[-4:] != '.yml' or fn == '__main__.yml':
            continue
        sites.append(fn)

    print('Found sites: %s' % ', '.join(sites))

    for site_name_raw in sorted(sites):
        oldName = path.join(OLDDIR, site_name_raw)
        site_name = site_name_raw[:-4]

        print('[%s] Processing...' % site_name)

        site, lastModified = loadSite(site_name_raw)
        if zoneTplLastModified > lastModified:
            lastModified = zoneTplLastModified
        
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

        domains = site['domains']
        allDomains = domains

        if site['type'] != 'none':
            domainsChanged = oldSite['domains'] != domains
            if domainsChanged:
                print('[%s] Domains changed from %s to %s' % (site_name, ','.join(oldSite['domains']), ','.join(domains)))

            redirectDomains = []
            if 'redirectDomains' in site:
                redirectDomains = site['redirectDomains']
            else:
                site['redirectDomains'] = redirectDomains

            if 'redirectWWW' in site and site['redirectWWW']:
                newDomains = []
                for domain in sorted(domains):
                    if domain[0:4] != 'www.':
                        newDomains.append(domain)
                        continue
                    redirectDomains.append({
                        'from': domain,
                        'to': domain[4:],
                    })
                domains = newDomains

            if len(redirectDomains) > 0:
                domSet = set(domains)
                for rdom in redirectDomains:
                    dom = rdom['from']
                    if dom in domSet:
                        domSet.remove(dom)
                domains = list(domSet)

            site['domains'] = domains                    

            allDomains = domains + [val['from'] for val in redirectDomains]

            certSite = {
                'name': site_name,
                'domains': allDomains
            }
            certifierConfig['sites'].append(certSite)
            nginxConfig.append(nginxSiteTemplate.render(site=site, config=config, dynConfig=dynConfig, tags=tags))
        else:
            print('[%s] Site is type none. Not rendering nginx or certifier config' % site_name)

        for domain in allDomains:
            addZoneFor(domain, site)

    for zone_name in sorted(zones):
        zone = zones[zone_name]
        certifierConfig['zones'].append({
            'name': zone_name,
            'domains': zone['domains'],
        })

        zoneFile = '/etc/powerdns/sites/db.%s' % zone_name

        zoneConfig = bindZoneTemplate.render(zone=zone, config=config, dynConfig=dynConfig, tags=tags)
        if swapFile(zoneFile, zoneConfig):
            reloadDNS = True

        signedFile = '%s.signed' % zoneFile
        try:
            stat(signedFile)
        except FileNotFoundError:
            fh = open(signedFile, 'w')
            fh.close()
            reloadDNS = True

    certifierConfStr = yaml_dump(certifierConfig)
    nginxConfStr = '\n'.join(nginxConfig)

    swapFile(path.join(CERTIFIER_DIR, 'config.yml'), certifierConfStr)

    if writeGlobalTpl('ips.sh.j2', path.join(OUTDIR, 'ips.sh')):
        system('bash \'%s\'' % path.join(OUTDIR, 'ips.sh'))

    if writeGlobalTpl('bird/main4.conf.j2', '/etc/bird/bird.conf'):
        system('service bird reload')

    if writeGlobalTpl('bird/main6.conf.j2', '/etc/bird/bird6.conf'):
        system('service bird6 reload')

    if writeGlobalTpl('bind/named.conf.j2', '/etc/powerdns/named.conf') or reloadDNS:
        system('pdns_control rediscover && pdns_control reload')

    if writeGlobalTpl('chrony/chrony.conf.j2', '/etc/chrony/chrony.conf'):
        system('service chrony restart')

    if writeNginxInclude('hsts') | \
        writeNginxInclude('proxy') | \
        writeNginxInclude('varnish') | \
        writeNginxInclude('wellknown') | \
        writeNginxInclude('securitytxt') | \
        writeNginxInclude('headers') | \
        writeGlobalTpl('nginx/security.txt.j2', path.join(SITEDIR, 'security.txt')) | \
        swapFile('/etc/nginx/conf.d/cdn.conf', nginxConfStr) | \
        writeGlobalTpl('nginx/nginx.conf.j2', '/etc/nginx/nginx.conf'):
        system('docker exec nginx killall -HUP nginx')

    for name in loadedSites:
        oldName = path.join(OLDDIR, '%s.yml' % name)
        site = loadedSites[name]

        fh = open(oldName, 'w')
        fh.write(yaml_dump(site))
        fh.close()

if __name__ == '__main__':
    __main__()
