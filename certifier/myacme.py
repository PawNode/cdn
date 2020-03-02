from contextlib import contextmanager

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import josepy as jose
import OpenSSL
from acme import challenges, client, crypto_util, errors, messages, standalone
from os import path, unlink
from config import KEY_DIR, CERT_DIR, ACCOUNT_KEY_FILE, ACCOUNT_DATA_FILE

DIRECTORY_URL = 'https://acme-staging-v02.api.letsencrypt.org/directory'
USER_AGENT = 'python-acme-pawnode-cdn'
KEY_BITS = 4096

def new_csr_comp(domain_names, site_name):
    '''Create certificate signing request.'''

    pkey_pem = None
    try:
        pkey_pem = loadCertAndKey(site_name)
    except FileNotFoundError:
        pass
    except:
        # TODO: Print error here
        pass

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

    for authz in authz_list:
        # Choosing challenge.
        # authz.body.challenges is a set of ChallengeBody objects.
        for i in authz.body.challenges:
            # Find the supported challenge.
            if isinstance(i.chall, challenges.HTTP01):
                return i

    raise Exception('HTTP-01 challenge was not offered by the CA server.')

def perform_http01(client_acme, challb, orderr):
    '''Set up standalone webserver and perform HTTP-01 challenge.'''

    response, validation = challb.response_and_validation(client_acme.net.key)

    resource = standalone.HTTP01RequestHandler.HTTP01Resource(
        chall=challb.chall, response=response, validation=validation)
    # TODO: Upload challenge to blob

    # Let the CA server know that we are ready for the challenge.
    client_acme.answer_challenge(challb, response)

    # Wait for challenge status and then issue a certificate.
    # It is possible to set a deadline time.
    finalized_orderr = client_acme.poll_and_finalize(orderr)

    return finalized_orderr.fullchain_pem

def get_client():
    if path.exists(ACCOUNT_KEY_FILE):
        fh = open(ACCOUNT_KEY_FILE, 'rb')
        acc_key_pkey = serialization.load_pem_private_key(
            data=fh.read(),
            password=None,
            backend=default_backend()
        )
        fh.close()
    else:
        acc_key_pkey = rsa.generate_private_key(
            public_exponent=65537,
            key_size=KEY_BITS,
            backend=default_backend()
        )
        fh = open(ACCOUNT_KEY_FILE, 'wb')
        fh.write(acc_key_pkey.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
        fh.close()

    acc_key = jose.JWKRSA(key=acc_key_pkey)
    net = client.ClientNetwork(acc_key, user_agent=USER_AGENT)
    directory = messages.Directory.from_json(net.get(DIRECTORY_URL).json())
    client_acme = client.ClientV2(directory, net=net)

    regr = None

    try:
        fh = open(ACCOUNT_DATA_FILE, 'r')
        regr = messages.RegistrationResource.json_loads(fh.read())
        client_acme.net.account = regr
        fh.close()
    except FileNotFoundError:
        pass

    try:
        if regr is None:
            email = ('ssl@pawnode.com')
            regr = client_acme.new_account(
                messages.NewRegistration.from_data(
                    email=email, terms_of_service_agreed=True))
            
            fh = open(ACCOUNT_DATA_FILE, 'w')
            fh.write(regr.json_dumps())
            fh.close()
    except errors.ConflictError:
        unlink(ACCOUNT_KEY_FILE)
        return get_client()

    return client_acme

def get_ssl_for_site(site):
    domains = site['domains']
    site_name = site['name']

    client_acme = get_client()

    # Register account and accept TOS

    # Terms of Service URL is in client_acme.directory.meta.terms_of_service
    # Registration Resource: regr
    # Creates account with contact information.

    # Create domain private key and CSR
    pkey_pem, csr_pem = new_csr_comp(domains, site_name)

    # Issue certificate

    orderr = client_acme.new_order(csr_pem)

    # Select HTTP-01 within offered challenges by the CA server
    challb = select_http01_chall(orderr)

    # The certificate is ready to be used in the variable 'fullchain_pem'.
    fullchain_pem = perform_http01(client_acme, challb, orderr)

    print(fullchain_pem)
