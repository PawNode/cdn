from os import path

__dir__ = path.abspath(path.dirname(__file__))
KEY_DIR = path.join(__dir__, 'keys')
CERT_DIR = path.join(__dir__, 'certs')
ACCOUNT_KEY_FILE = path.join(KEY_DIR, "__account__.pem")
ACCOUNT_DATA_FILE = path.join(CERT_DIR, "__account__.json")