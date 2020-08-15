from os import path
from yaml import safe_load as yaml_load
from boto3 import client as boto3_client
from .config import config, decryptString

class CertificateUnusableError(Exception):
    def __init__(self):
        Exception.__init__(self)

__dir__ = path.abspath(path.dirname(__file__))
KEY_DIR = path.join(__dir__, 'keys')
CERT_DIR = path.join(__dir__, 'certs')
DNSSEC_DIR = path.join('/etc/powerdns/dnssec')
ACCOUNT_KEY_FILE = path.join(KEY_DIR, '__account__.pem')
ACCOUNT_DATA_FILE = path.join(CERT_DIR, '__account__.pem')

osconfig = config['objectStorage']
s3_client = boto3_client('s3',
    aws_access_key_id=decryptString(osconfig['accessKeyID']),
    aws_secret_access_key=decryptString(osconfig['secretAccessKey'])
)
