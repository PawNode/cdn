from os import path
from config import KEY_DIR, CERT_DIR, ACCOUNT_KEY_FILE
import OpenSSL

def loadCertAndKey(name):
    name = "%s.pem" % name

    fh = open(path.join(KEY_DIR, name), 'r')
    pkey_openssl = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM,
                fh.read())
    fh.close()

    fh = open(path.join(CERT_DIR, name), 'r')
    cert_openssl = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM,
                fh.read())
    fh.close()

    return pkey_openssl, cert_openssl

def storeCertAndKey(name, pkey_pem, cert_pem):
    name = "%s.pem" % name

    fh = open(path.join(KEY_DIR, name), 'w')
    fh.write(pkey_pem)
    fh.close()

    fh = open(path.join(CERT_DIR, name), 'w')
    fh.write(cert_pem)
    fh.close()
