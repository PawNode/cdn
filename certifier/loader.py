from os import path
from config import KEY_DIR, CERT_DIR, ACCOUNT_KEY_FILE
import OpenSSL

def loadCertAndKey(name):
    fh = open(path.join(KEY_DIR, "%s.pem" % name), 'r')
    pkey_pem = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM,
                fh.read())
    fh.close()
    return pkey_pem

def storeCertAndKey(name):
    return
