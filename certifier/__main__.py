from myacme import get_ssl_for_site
from yaml import load as yaml_load
from myglobals import __dir__, s3_client, config
from os import path, system
from loader import loadFile, storeFile

BUCKET_NAME = config['certs']['bucketName']

sites = []
with open(path.join(__dir__, 'sites.yml'), 'r') as f:
    sites = yaml_load(f.read())

paginator = s3_client.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix='dnssec'):
    for obj in page['Contents']:
        loadFile(obj['Key'])

reloadNginx = False
for site in sites:
    reloadNginx |= get_ssl_for_site(site)
    mainDomain = site['domains'][0]
    

if reloadNginx:
    system('service nginx reload')

