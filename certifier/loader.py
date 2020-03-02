from os import path, unlink, urandom
from myglobals import KEY_DIR, CERT_DIR, ACCOUNT_KEY_FILE, CertificateUnusableError
import OpenSSL
from datetime import datetime, timedelta
from azure.storage.blob import BlockBlobService
from azure.common import AzureMissingResourceHttpError
from myglobals import config
from Crypto.Cipher import AES
from base64 import b64decode, b64encode

certconfig = config['certs']
blob_client = BlockBlobService(account_name=certconfig['accountName'], account_key=certconfig['accessKey'])

AES_KEY = b64decode(certconfig['encryptionKey'])
CERT_MIN_VALID_DAYS = certconfig['minValidDays']

def checkCertPEM(cert_pem, domains):
    if not cert_pem:
        return False
    if not domains:
        return True

    cert_openssl = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert_pem)
    if not cert_openssl:
        return False
    return checkCertExpiry(cert_openssl) and checkCertDomains(cert_openssl, domains)

def getCertSAN(cert_openssl):
    ext_count = cert_openssl.get_extension_count()
    for i in range(0, ext_count):
        ext = cert_openssl.get_extension(i)
        if ext.get_short_name() == b'subjectAltName':
            return ext.__str__()

def checkCertExpiry(cert_openssl):
    expiryDate = datetime.strptime(cert_openssl.get_notAfter().decode('ascii'), '%Y%m%d%H%M%SZ')
    minExpiryDate = datetime.now() + timedelta(days=CERT_MIN_VALID_DAYS)

    return expiryDate > minExpiryDate

def checkCertDomains(cert_openssl, domains):
    sans = getCertSAN(cert_openssl).split(',')
    validDomains = set()

    for san in sans:
        san = san.strip()
        if san[0:4] != 'DNS:':
            continue
        validDomains.add(san[4:])
    
    return set(domains) == validDomains

def loadCertAndKeyLocal(name):
    name = '%s.pem' % name

    fh = open(path.join(KEY_DIR, name), 'r')
    key_pem = fh.read()
    fh.close()

    fh = open(path.join(CERT_DIR, name), 'r')
    cert_pem = fh.read()
    fh.close()

    return key_pem, cert_pem

def storeCertAndKeyLocal(name, pkey_pem, cert_pem):
    name = '%s.pem' % name

    if not pkey_pem or not cert_pem:
        return

    fn = path.join(KEY_DIR, name)
    try:
        unlink(fn)
    except FileNotFoundError:
        pass
    fh = open(fn, 'wb')
    fh.write(pkey_pem)
    fh.close()

    fn = path.join(CERT_DIR, name)
    try:
        unlink(fn)
    except FileNotFoundError:
        pass
    fh = open(fn, 'wb')
    fh.write(cert_pem)
    fh.close()

def _downloadAndDecrypt(fn):
    blob = blob_client.get_blob_to_bytes('ssl', fn)
    iv = b64decode(blob.metadata['crypto_iv'])
    aes = AES.new(AES_KEY, AES.MODE_CFB, iv)
    pem = aes.decrypt(blob.content)
    return pem

def _uploadAndEncrypt(fn, data):
    if not data:
        return

    iv = urandom(16)
    aes = AES.new(AES_KEY, AES.MODE_CFB, iv)
    data = aes.encrypt(data)
    blob_client.create_blob_from_bytes('ssl', fn, data, metadata={
        'crypto_version': '1',
        'crypto_iv': b64encode(iv).decode('ascii'),
    })

def loadCertAndKeyRemote(name):
    key_pem = None
    cert_pem = None
    try:
        key_pem = _downloadAndDecrypt('keys/%s.pem' % name)
        cert_pem = _downloadAndDecrypt('certs/%s.pem' % name)
    except AzureMissingResourceHttpError:
        pass
    return key_pem, cert_pem

def storeCertAndKeyRemote(name, key_pem, cert_pem):
    _uploadAndEncrypt('certs/%s.pem' % name, cert_pem)
    _uploadAndEncrypt('keys/%s.pem' % name, key_pem)

def loadCertAndKey(name, domains):
    try:
        pkey, crt = loadCertAndKeyLocal(name)
        if not checkCertPEM(crt, domains):
            raise CertificateUnusableError()
        print("[%s] Found from local storage: key=%d, cert=%d" % (name, pkey != None, crt != None))
        return pkey, crt
    except (FileNotFoundError, CertificateUnusableError, OpenSSL.crypto.Error):
        pkey, crt = loadCertAndKeyRemote(name)
        storeCertAndKeyLocal(name, pkey, crt)
        if not checkCertPEM(crt, domains):
            crt = None
        print("[%s] Found from object storage: key=%d, cert=%d" % (name, pkey != None, crt != None))
        return pkey, crt

def storeCertAndKey(name, key_pem, cert_pem):
    storeCertAndKeyRemote(name, key_pem, cert_pem)
    storeCertAndKeyLocal(name, key_pem, cert_pem)
