from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, ed25519
from cryptography.hazmat.primitives import serialization
import josepy as jose
import OpenSSL
import dns.resolver
import requests
from acme import challenges, client, crypto_util, errors, messages, standalone
from os import path, unlink
from myglobals import KEY_DIR, CERT_DIR, ACCOUNT_KEY_FILE, ACCOUNT_DATA_FILE, NoLockError
from loader import loadCertAndKey, storeCertAndKey, loadFile, storeFile
from wellknown import uploadWellknown
from config import config

DIRECTORY_URL = 'https://acme-v02.api.letsencrypt.org/directory'
USER_AGENT = 'python-acme-pawnode'
KEY_BITS = 4096

dns_resolver = dns.resolver.Resolver(configure=False)
dns_resolver.nameservers = ['8.8.8.8', '2001:4860:4860::8888',
                            '8.8.4.4', '2001:4860:4860::8844' ]

def new_csr_comp(domain_names, pkey_pem):
    '''Create certificate signing request.'''

    if not pkey_pem:
        pkey = OpenSSL.crypto.PKey()
        pkey.generate_key(OpenSSL.crypto.TYPE_RSA, KEY_BITS)
        pkey_pem = OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM,
                                                  pkey)

    csr_pem = crypto_util.make_csr(pkey_pem, domain_names)
    return pkey_pem, csr_pem

def select_http01_chall(orderr):
    '''Extract authorization resource from within order resource.'''
    # Authorization Resource: authz.
    # This object holds the offered challenges by the server and their status.
    authz_list = orderr.authorizations

    challenge_list = []
    for authz in authz_list:
        # Choosing challenge.
        # authz.body.challenges is a set of ChallengeBody objects.
        for i in authz.body.challenges:
            # Find the supported challenge.
            if isinstance(i.chall, challenges.HTTP01):
                challenge_list.append(i)

    return challenge_list

# /.well-known/
# 1234567890123

def perform_http01(client_acme, challbs, orderr):
    for challb in challbs:
        response, validation = challb.response_and_validation(client_acme.net.key)

        if challb.chall.path[:13] != '/.well-known/':
            raise Exception('Sorry, challenge does not begin with /.well-known/')
        uploadWellknown(challb.chall.path[13:], validation.encode())

        # Let the CA server know that we are ready for the challenge.
        client_acme.answer_challenge(challb, response)

    # Wait for challenge status and then issue a certificate.
    finalized_orderr = client_acme.poll_and_finalize(orderr)

    return finalized_orderr.fullchain_pem

__cached_client_acme = None
def get_client():
    global __cached_client_acme

    if __cached_client_acme:
        return __cached_client_acme

    account_pkey = loadFile("le/account.pem")
    account_data = None
    if account_pkey:
        account_data = loadFile("le/account.json")
    acc_key_pkey = None

    if account_pkey:
        acc_key_pkey = serialization.load_pem_private_key(
            data=account_pkey,
            password=None,
            backend=default_backend()
        )
    else:
        acc_key_pkey = rsa.generate_private_key(
            public_exponent=65537,
            key_size=KEY_BITS,
            backend=default_backend()
        )
        account_pkey = acc_key_pkey.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

    acc_key = jose.JWKRSA(key=acc_key_pkey)
    net = client.ClientNetwork(acc_key, user_agent=USER_AGENT)
    directory = messages.Directory.from_json(net.get(DIRECTORY_URL).json())
    client_acme = client.ClientV2(directory, net=net)

    if account_data != None:
        client_acme.net.account = messages.RegistrationResource.json_loads(account_data)

    try:
        if not client_acme.net.account:
            email = ('ssl@pawnode.com')
            regr = client_acme.new_account(
                messages.NewRegistration.from_data(
                    email=email, terms_of_service_agreed=True))

            storeFile("le/account.json", regr.json_dumps().encode())
            storeFile("le/account.pem", account_pkey)
    except errors.ConflictError:
        raise # TODO: Maybe handle? This happens when an account has been made with a key already

    __cached_client_acme = client_acme
    return client_acme

# https://github.com/certbot/certbot/blob/07abe7a8d68961042ee301039dd4da87306cb1a0/acme/acme/crypto_util.py#L189
def pawnode_make_csr(private_key_pem, domains):
    """Generate a CSR containing a list of domains as subjectAltNames.
    :param buffer private_key_pem: Private key, in PEM PKCS#8 format.
    :param list domains: List of DNS names to include in subjectAltNames of CSR.
    :returns: buffer PEM-encoded Certificate Signing Request.
    """
    private_key = OpenSSL.crypto.load_privatekey(
        OpenSSL.crypto.FILETYPE_PEM, private_key_pem)
    csr = OpenSSL.crypto.X509Req()
    extensions = [
        OpenSSL.crypto.X509Extension(
            b'subjectAltName',
            critical=False,
            value=', '.join('DNS:' + d for d in domains).encode('ascii')
        ),
    ]
    csr.add_extensions(extensions)
    csr.set_pubkey(private_key)
    csr.set_version(2)
    csr.sign(private_key, '')
    return OpenSSL.crypto.dump_certificate_request(
        OpenSSL.crypto.FILETYPE_PEM, csr)

def get_ssl_for_site(site, use_acme, acme_mutex, ccConfig):
    domains = site['domains']
    site_name = site['name']

    print("[%s] Processing domains %s" % (site_name, ', '.join(domains)))

    pkey_pem, fullchain_pem, from_local = loadCertAndKey(site_name, domains)
    if fullchain_pem:
        return not from_local

    if not use_acme:
        print("[%s] Ignoring missing SSL because ACME is off" % site_name)
        return False

    sitecname = ccConfig['sitecname']
    siteips4 = ccConfig['siteips4']
    siteips6 = ccConfig['siteips6']
    allnodes = ccConfig['allnodes']
    gitrev = ccConfig['gitrev']

    siteips4.sort()
    siteips6.sort()

    for node in allnodes:
        r = requests.get('http://%s:9080/gitrev.txt' % node)
        if r.status_code == 200 and r.text.strip() == gitrev:
            continue

        print("[%s] Git revision mismatch with node (%s)" % (site_name, node))
        return False

    for domain in domains:
        try:
            r = dns_resolver.query(domain, 'cname')
            if len(r) == 1 and r[0].target == sitecname:
                continue
        except dns.resolver.NoAnswer:
            pass

        try:
            def _to_text(o):
                return o.to_text()

            ra = dns_resolver.query(domain, 'a')
            ra = list(map(_to_text, ra))
            ra.sort()

            raaaa = dns_resolver.query(domain, 'aaaa')
            raaaa = list(map(_to_text, raaaa))
            raaaa.sort()

            if ra == siteips4 and raaaa == siteips6:
                continue
        except dns.resolver.NoAnswer:
            pass

        print("[%s] Public DNS mismatch, skipping site (%s)" % (site_name, domain))
        return False

    if not acme_mutex.locked:
        print("[%s] Site requires ACME. Acquiring SSL mutex..." % site_name)
        if not acme_mutex.lock():
            print("[%s] Could not acquire lock. Continuing without ACME!" % site_name)
            raise NoLockError()
        print("[%s] Acquired ACME lock! (kept until process exit)" % site_name)
    else:
        print("[%s] Site requires ACME. Already have SSL mutex." % site_name)

    if not pkey_pem:
        pkey = ed25519.Ed25519PrivateKey.generate()
        pkey_pem = pkey.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

    client_acme = get_client()
    csr_pem = pawnode_make_csr(pkey_pem, domains)
    # Issue certificate
    orderr = client_acme.new_order(csr_pem)
    # Select HTTP-01 within offered challenges by the CA server
    challbs = select_http01_chall(orderr)
    # The certificate is ready to be used in the variable 'fullchain_pem'.
    fullchain_pem = perform_http01(client_acme, challbs, orderr).encode()
    storeCertAndKey(site_name, pkey_pem, fullchain_pem)

    print("[%s] Obtained new certificate" % site_name)
    return True
