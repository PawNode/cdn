from os import path, unlink
from myglobals import KEY_DIR, CERT_DIR, ACCOUNT_KEY_FILE, CertificateUnusableError, config, __dir__, s3_client
import OpenSSL
from datetime import datetime, timedelta
from Cryptodome.Cipher import AES
from base64 import b64decode, b64encode

from config import encryptString, decryptString

certconfig = config['crypto']
BUCKET_NAME = certconfig['bucketName']
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

    fh = open(path.join(KEY_DIR, name), 'rb')
    key_pem = fh.read()
    fh.close()

    fh = open(path.join(CERT_DIR, name), 'rb')
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

def downloadAndDecrypt(fn):
    blob = s3_client.get_object(
        Bucket=BUCKET_NAME,
        Key=fn
    )
    pem = decryptString(blob['Body'].read())
    return pem

def uploadAndEncrypt(fn, data):
    if not data:
        return

    encryptedData = encryptString(data)
    s3_client.put_object(Bucket=BUCKET_NAME, Key=fn, Body=encryptedData)

def loadCertAndKeyRemote(name):
    key_pem = None
    cert_pem = None
    try:
        key_pem = downloadAndDecrypt('keys/%s.pem' % name)
        cert_pem = downloadAndDecrypt('certs/%s.pem' % name)
    except s3_client.exceptions.NoSuchKey:
        pass
    return key_pem, cert_pem

def storeCertAndKeyRemote(name, key_pem, cert_pem):
    uploadAndEncrypt('certs/%s.pem' % name, cert_pem)
    uploadAndEncrypt('keys/%s.pem' % name, key_pem)

def loadFile(name):
    if path.exists(name):
        fh = open(path.join(__dir__, name), 'rb')
        fd = fh.read()
        fh.close()
        return fd
    try:
        data = downloadAndDecrypt(name)
        if data:
            storeFile(name, data, True)
        return data
    except s3_client.exceptions.NoSuchKey:
        return None

def storeFile(name, fd, localOnly=False):
    if not localOnly:
        uploadAndEncrypt(name, fd)
    fh = open(path.join(__dir__, name), 'wb')
    fh.write(fd)
    fh.close()

def loadCertAndKey(name, domains):
    try:
        pkey, crt = loadCertAndKeyLocal(name)
        if not checkCertPEM(crt, domains):
            raise CertificateUnusableError()
        print("[%s] Found from local storage: key=%d, cert=%d" % (name, pkey != None, crt != None))
        return pkey, crt, True
    except (FileNotFoundError, CertificateUnusableError, OpenSSL.crypto.Error):
        pkey, crt = loadCertAndKeyRemote(name)
        storeCertAndKeyLocal(name, pkey, crt)
        if not checkCertPEM(crt, domains):
            crt = None
        print("[%s] Found from object storage: key=%d, cert=%d" % (name, pkey != None, crt != None))
        return pkey, crt, False

def storeCertAndKey(name, key_pem, cert_pem):
    storeCertAndKeyRemote(name, key_pem, cert_pem)
    storeCertAndKeyLocal(name, key_pem, cert_pem)
