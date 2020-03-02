from os import path
from config import KEY_DIR, CERT_DIR, ACCOUNT_KEY_FILE, CertificateUnusableError
import OpenSSL

def checkCertExpiry(cert_pem):
    # TODO: This
    return True


def checkCertDomains(cert_pem, domains):
    return True

def loadCertAndKeyLocal(name):
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

def storeCertAndKeyLocal(name, pkey_pem, cert_pem):
    name = "%s.pem" % name

    fh = open(path.join(KEY_DIR, name), 'w')
    fh.write(pkey_pem)
    fh.close()

    fh = open(path.join(CERT_DIR, name), 'w')
    fh.write(cert_pem)
    fh.close()

def loadCertAndKeyRemote(name):
    key_pem = None
    cert_pem = None
    # TODO: This
    return key_pem, cert_pem

def storeCertAndKeyRemote(name, pkey_pem, cert_pem):
    # TODO: This
    return

def loadCertAndKey(name, domains):
    try:
        pkey, crt = loadCertAndKeyLocal(name)
        if not checkCertExpiry(crt) or not checkCertDomains(crt, domains):
            raise CertificateUnusableError()
        return pkey, crt
    except FileNotFoundError | CertificateUnusableError:
        pkey, crt = loadCertAndKeyRemote(name)
        storeCertAndKeyLocal(name, pkey, crt)
        if not checkCertExpiry(crt) or not checkCertDomains(crt, domains):
            crt = None
        return pkey, crt

def storeCertAndKey(name, pkey_pem, cert_pem):
    storeCertAndKeyRemote(name, pkey_pem, cert_pem)
    storeCertAndKeyLocal(name, pkey_pem, cert_pem)