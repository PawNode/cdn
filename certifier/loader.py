from os import path, unlink
from myglobals import KEY_DIR, CERT_DIR, ACCOUNT_KEY_FILE, CertificateUnusableError
import OpenSSL
from datetime import datetime, timedelta

CERT_MIN_VALID_DAYS = 30

def getCertSAN(cert):
    ext_count = cert.get_extension_count()
    for i in range(0, ext_count):
        ext = cert.get_extension(i)
        if ext.get_short_name() == b'subjectAltName':
            return ext.__str__()

def checkCertExpiry(cert):
    if not cert:
        return False

    expiryDate = datetime.strptime(cert.get_notAfter().decode('ascii'), '%Y%m%d%H%M%SZ')
    minExpiryDate = datetime.now() + timedelta(days=CERT_MIN_VALID_DAYS)

    return expiryDate > minExpiryDate

def checkCertDomains(cert, domains):
    if not cert:
        return False

    sans = getCertSAN(cert).split('\n')
    validDomains = []

    for san in sans:
        san = san.strip()
        if san[0:4] != 'DNS:':
            continue
        validDomains.append(san[4:])
    
    return domains == validDomains

def loadCertAndKeyLocal(name):
    name = "%s.pem" % name

    fh = open(path.join(KEY_DIR, name), 'r')
    pkey_openssl = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, fh.read())
    fh.close()

    fh = open(path.join(CERT_DIR, name), 'r')
    cert_openssl = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, fh.read())
    fh.close()

    return pkey_openssl, cert_openssl

def storeCertAndKeyLocal(name, pkey_pem, cert_pem):
    name = "%s.pem" % name

    if not pkey_pem or not cert_pem:
        return

    fn = path.join(KEY_DIR, name)
    unlink(fn)
    fh = open(fn, 'w')
    fh.write(pkey_pem)
    fh.close()

    fn = path.join(CERT_DIR, name)
    unlink(fn)
    fh = open(fn, 'w')
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
    except (FileNotFoundError, CertificateUnusableError, OpenSSL.crypto.Error):
        pkey, crt = loadCertAndKeyRemote(name)
        storeCertAndKeyLocal(name, pkey, crt)
        if not checkCertExpiry(crt) or not checkCertDomains(crt, domains):
            crt = None
        return pkey, crt

def storeCertAndKey(name, pkey_pem, cert_pem):
    storeCertAndKeyRemote(name, pkey_pem, cert_pem)
    storeCertAndKeyLocal(name, pkey_pem, cert_pem)
