from os import path
from yaml import load as yaml_load
from boto3 import client as boto3_client

class CertificateUnusableError(Exception):
    def __init__(self):
        Exception.__init__(self)

__dir__ = path.abspath(path.dirname(__file__))
KEY_DIR = path.join(__dir__, 'keys')
CERT_DIR = path.join(__dir__, 'certs')
ACCOUNT_KEY_FILE = path.join(KEY_DIR, '__account__.pem')
ACCOUNT_DATA_FILE = path.join(CERT_DIR, '__account__.pem')

config = None
with open(path.join(path.dirname(__file__), '../config.yml'), 'r') as f:
    config = yaml_load(f)

osconfig = config['objectStorage']
s3_client = boto3_client('s3',
    aws_access_key_id=osconfig['accessKeyID'],
    aws_secret_access_key=osconfig['secretAccessKey']
)
