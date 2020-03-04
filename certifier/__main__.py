from myacme import get_ssl_for_site
from yaml import load as yaml_load
from myglobals import __dir__
from os import path, system
from loader import loadFile, storeFile

sites = []
with open(path.join(__dir__, 'sites.yml'), 'r') as f:
    sites = yaml_load(f.read())

reloadNginx = False
for site in sites:
    reloadNginx |= get_ssl_for_site(site)

loadFile("dnssec/Kcdn.pawnode.com.+013+27208.key")
loadFile("dnssec/Kcdn.pawnode.com.+013+27208.private")
loadFile("dnssec/Kcdn.pawnode.com.+013+51197.key")
loadFile("dnssec/Kcdn.pawnode.com.+013+51197.private")

if reloadNginx:
    system('service nginx reload')

