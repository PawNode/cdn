from io import BytesIO
from jinja2 import Environment, FileSystemLoader, select_autoescape
from os import listdir, path, unlink, rename, system, mkdir, symlink
from requests import get as http_get
from shutil import rmtree
from yaml import load as yaml_load, dump as yaml_dump
from zipfile import ZipFile
from azure.storage.blob import BlockBlobService
from socket import getfqdn

__dir__ = path.dirname(__file__)

config = None
with open(path.join(__dir__, '../config.yml'), 'r') as f:
    config = yaml_load(f)

osconfig = config['objectStorage']
blob_client = BlockBlobService(account_name=osconfig['accountName'], account_key=osconfig['accessKey'])

dynConfig = yaml_load(blob_client.get_blob_to_text('config', 'config.yml').content)

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
        recurseTags(tag)

recurseTags(getfqdn())
recurseTags("all")

print("My tags are: %s" % ', '.join(tags))

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
        print("DynConf: Using %s as closest for %s" % (tag, grp))
        dc = cfg[grp]
        __closest_grp[grp] = dc
        return dc

dynConfig['_self'] = dynConfig[tags[0]] # 0 = FQDN
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

dynConfig['_self']['certDir'] = CERTDIR
dynConfig['_self']['keyDir'] = KEYDIR

j2env = Environment(
    loader=FileSystemLoader(path.join(__dir__, 'templates')),
    autoescape=select_autoescape([])
)
nginxSiteTemplate = j2env.get_template('nginx/site.conf.j2')
nginxMainTemplate = j2env.get_template('nginx/main.conf.j2')
birdMainTemplate = j2env.get_template('bird/main4.conf.j2')
bird6MainTemplate = j2env.get_template('bird/main6.conf.j2')
ipTemplate = j2env.get_template('ips.sh.j2')
bindZoneTemplate = j2env.get_template('bind/zone.j2')
bindSiteTemplate = j2env.get_template('bind/site.conf.j2')

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
    'zip': loadSiteZIP
}

def run():
    nginxConfig = [nginxMainTemplate.render(config=config, dynConfig=dynConfig, tags=tags)]
    zoneListConfig = []
    certifierConfig = []
    loadedSites = {}
    reloadBind = False
    reloadNginx = False
    reloadCertifier = False

    files = listdir(DIR)

    print('Found site files: %s' % ', '.join(files))

    for file in files:
        if file[0] == '.' or file[-4:] != '.yml':
            continue

        site_name = file[:-4]

        curName = path.join(DIR, file)
        oldName = path.join(OLDDIR, file)

        print('[%s] Processing...' % site_name)

        fh = open(curName, 'r')
        site = yaml_load(fh)
        fh.close()

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
            reloadNginx = True
            reloadCertifier = True
        
        oldSite['name'] = site_name

        symlinkCert(site_name)

        typeChanged = site['type'] != oldSite['type']
        if typeChanged:
            print('[%s] Type changed from %s to %s' % (site_name, oldSite['type'], site['type']))
            reloadNginx = True
            reloadCertifier = True

        try:
            loader = SITE_LOADERS[site['type']]
            loader(site, oldSite, typeChanged)
            print('[%s] Loaded site' % site_name)
        except Exception as e:
            print('[%s] Error loading site:' % site_name, e)
            pass

        domainsChanged = oldSite['domains'] != site['domains']
        if domainsChanged:
            print('[%s] Domains changed from %s to %s' % (site_name, ','.join(oldSite['domains']), ','.join(site['domains'])))
            reloadNginx = True
            reloadCertifier = True

        certifierConfig.append(site)
        nginxConfig.append(nginxSiteTemplate.render(site=site, config=config, dynConfig=dynConfig, tags=tags))

        zoneListConfig.append(bindSiteTemplate.render(site=site, config=config, dynConfig=dynConfig, tags=tags))
        zoneConfig = bindZoneTemplate.render(site=site, config=config, dynConfig=dynConfig, tags=tags)
        if swapFile('/etc/bind/sites/db.%s' % site_name, zoneConfig):
            reloadBind = True

    certifierConfStr = yaml_dump(certifierConfig)
    nginxConfStr = '\n'.join(nginxConfig)
    zoneListConfigStr = '\n'.join(zoneListConfig)

    if swapFile('/etc/nginx/conf.d/cdn.conf', nginxConfStr):
        reloadNginx = True

    if swapFile(path.join(CERTIFIER_DIR, 'sites.yml'), certifierConfStr):
        reloadCertifier = True

    birdConfStr = birdMainTemplate.render(config=config, dynConfig=dynConfig, tags=tags)
    bird6ConfStr = bird6MainTemplate.render(config=config, dynConfig=dynConfig, tags=tags)

    if swapFile('/etc/bird/bird.conf', birdConfStr):
        system('service bird reload')

    if swapFile('/etc/bird/bird6.conf', bird6ConfStr):
        system('service bird6 reload')

    if swapFile('/etc/bind/sites.conf', zoneListConfigStr):
        reloadBind = True

    ipConfStr = ipTemplate.render(config=config, dynConfig=dynConfig, tags=tags)
    if swapFile(path.join(OUTDIR, 'ips.sh'), ipConfStr):
        system('bash "%s"' % path.join(OUTDIR, 'ips.sh'))

    if reloadBind:
        system('service bind9 reload')

    if reloadCertifier:
        system('python3 %s' % path.join(__dir__, '../certifier'))

    if reloadNginx:
        system('service nginx reload')

    for name in loadedSites:
        oldName = path.join(OLDDIR, '%s.yml' % name)
        site = loadedSites[name]

        fh = open(oldName, 'w')
        fh.write(yaml_dump(site))
        fh.close()

run()
