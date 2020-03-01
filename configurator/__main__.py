from io import BytesIO
from jinja2 import Environment, FileSystemLoader, select_autoescape
from os import listdir, path, unlink, rename, system, mkdir, symlink
from requests import get as http_get
from shutil import rmtree
from sys import exc_info
from yaml import load as yaml_load, dump as yaml_dump
from zipfile import ZipFile

__dir__ = path.dirname(__file__)

DIR = path.abspath(path.join(__dir__, "sites"))
OUTDIR = path.abspath(path.join(__dir__, "out"))
OLDDIR = path.abspath(path.join(OUTDIR, "sites"))
SITEDIR = '/var/www/sites'
CERTIFIER_DIR = path.abspath(path.join(__dir__, "../certifier"))
CERTDIR = path.abspath(path.join(CERTIFIER_DIR, "certs"))
KEYDIR = path.abspath(path.join(CERTIFIER_DIR, "keys"))
DEFAULT_CERT_AND_KEY = "/etc/ssl/default.pem"

j2env = Environment(
    loader=FileSystemLoader(path.join(__dir__, 'configs')),
    autoescape=select_autoescape([])
)
nginxSiteTemplate = j2env.get_template('nginx/site.conf.j2')
nginxMainTemplate = j2env.get_template('nginx/main.conf.j2')

def loadSiteNoop(site, oldSite, force):
    return

def loadSiteZIP(site, oldSite, force):
    if oldSite and not force and site['src'] == oldSite['src']:
        return

    outDir = path.join(SITEDIR, site['name'])
    site['dir'] = outDir

    newDir = "%s___new" % outDir
    oldDir = "%s___old" % outDir
    
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


def swapFile(file, content):
    newfile = "%s.new" % file
    fh = open(newfile, "w")
    fh.write(content)
    fh.close()

    try:
        unlink(file)
    except FileNotFoundError:
        pass
    rename(newfile, file)

    return False # TODO: Return if changed

def symlinkCert(name):
    name = "%s.pem" % name
    certName = path.join(CERTDIR, name)
    keyName = path.join(KEYDIR, name)
    if not path.lexists(certName):
        symlink(DEFAULT_CERT_AND_KEY, certName)
    if not path.lexists(keyName):
        symlink(DEFAULT_CERT_AND_KEY, keyName)

SITE_LOADERS = {
    'redirect': loadSiteNoop,
    'none': loadSiteNoop,
    'zip': loadSiteZIP
}

def run():
    nginxConfig = [nginxMainTemplate.render()]
    certifierConfig = []
    loadedSites = {}
    reloadNginx = False
    reloadCertifier = False

    files = listdir(DIR)

    for file in files:
        if file[0] == '.' or file[-4:] != '.yml':
            continue

        curName = path.join(DIR, file)
        oldName = path.join(OLDDIR, file)

        fh = open(curName, 'r')
        site = yaml_load(fh)
        fh.close()

        site['name'] = file[:-4]

        loadedSites[site['name']] = site

        oldSite = None
        try:
            fh = open(oldName, 'r')
            oldSite = yaml_load(fh)
            fh.close()
        except:
            pass

        if not oldSite:
            oldSite = {
                'domains': [],
                'type': 'none',
            }
            reloadNginx = True
            reloadCertifier = True
        
        oldSite['name'] = site['name']

        symlinkCert(site['name'])

        typeChanged = site['type'] != oldSite['type']
        reloadNginx |= typeChanged
        reloadCertifier |= typeChanged

        try:
            loader = SITE_LOADERS[site['type']]
            loader(site, oldSite, typeChanged)
        except Exception:
            print("Error loading site", site['name'], exc_info()[0])
            pass

        reloadCertifier |= oldSite['domains'] != site['domains']

        certifierConfig.append(site)
        nginxConfig.append(nginxSiteTemplate.render(site=site))

    certifierConfStr = yaml_dump(certifierConfig)
    nginxConfStr = '\n'.join(nginxConfig)

    if swapFile("/etc/nginx/conf.d/cdn.conf", nginxConfStr):
        reloadNginx = True

    if swapFile(path.join(CERTIFIER_DIR, "config.yml"), certifierConfStr):
        reloadCertifier = True

    if reloadNginx:
        system('service nginx reload')

    #if reloadCertifier:
    #    system('service certifier restart')

    for name in loadedSites:
        oldName = path.join(OLDDIR, "%s.yml" % name)
        site = loadedSites[name]

        fh = open(oldName, 'w')
        fh.write(yaml_dump(site))
        fh.close()

run()
