from io import BytesIO
from jinja2 import Environment, FileSystemLoader, select_autoescape
from os import listdir, path, unlink, rename, system, mkdir, symlink
from requests import get as http_get
from shutil import rmtree
from yaml import load as yaml_load, dump as yaml_dump
from zipfile import ZipFile

__dir__ = path.dirname(__file__)

config = None
with open(path.join(__dir__, '../config.yml'), 'r') as f:
    config = yaml_load(f)

SITEDIR = config['siteDir']
DEFAULT_KEY = config['defaultKey']
DEFAULT_CERT = config['defaultCert']

DIR = path.abspath(path.join(__dir__, 'sites'))
OUTDIR = path.abspath(path.join(__dir__, 'out'))
OLDDIR = path.abspath(path.join(OUTDIR, 'sites'))
CERTIFIER_DIR = path.abspath(path.join(__dir__, '../certifier'))
CERTDIR = path.abspath(path.join(CERTIFIER_DIR, 'certs'))
KEYDIR = path.abspath(path.join(CERTIFIER_DIR, 'keys'))

j2env = Environment(
    loader=FileSystemLoader(path.join(__dir__, 'configs')),
    autoescape=select_autoescape([])
)
nginxSiteTemplate = j2env.get_template('nginx/site.conf.j2')
nginxMainTemplate = j2env.get_template('nginx/main.conf.j2')

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
    nginxConfig = [nginxMainTemplate.render(config=config)]
    certifierConfig = []
    loadedSites = {}
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
        nginxConfig.append(nginxSiteTemplate.render(site=site, config=config))

    certifierConfStr = yaml_dump(certifierConfig)
    nginxConfStr = '\n'.join(nginxConfig)

    if swapFile('/etc/nginx/conf.d/cdn.conf', nginxConfStr):
        reloadNginx = True

    if swapFile(path.join(CERTIFIER_DIR, 'sites.yml'), certifierConfStr):
        reloadCertifier = True

    if reloadNginx:
        system('service nginx reload')

    if reloadCertifier:
        system('python3 %s' % path.join(__dir__, '../certifier'))

    for name in loadedSites:
        oldName = path.join(OLDDIR, '%s.yml' % name)
        site = loadedSites[name]

        fh = open(oldName, 'w')
        fh.write(yaml_dump(site))
        fh.close()

run()
