from os import path, environ
from sys import path as sys_path
from yaml import safe_load as yaml_load
from boto3 import client as boto3_client

__dir__ = path.abspath(path.dirname(__file__))
sys_path.append(path.dirname(__dir__))

from config import config, decryptString

class CertificateUnusableError(Exception):
    def __init__(self):
        Exception.__init__(self)

class NoLockError(Exception):
    def __init__(self):
        Exception.__init__(self)

KEY_DIR = path.join(__dir__, 'keys')
CERT_DIR = path.join(__dir__, 'certs')
DNSSEC_DIR = path.join('/etc/powerdns/dnssec')
ACCOUNT_KEY_FILE = path.join(KEY_DIR, '__account__.pem')
ACCOUNT_DATA_FILE = path.join(CERT_DIR, '__account__.pem')

osconfig = config['objectStorage']

environ['AWS_ACCESS_KEY_ID'] = decryptString(osconfig['accessKeyID']).decode('ascii')
environ['AWS_SECRET_ACCESS_KEY'] = decryptString(osconfig['secretAccessKey']).decode('ascii')
environ['DD_MUTEX_TABLE_NAME'] = 'doridian-cdn-mutex'

s3_client = boto3_client('s3')
