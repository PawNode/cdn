from os import path
from yaml import safe_load as yaml_load
from base64 import b64decode, b64encode
from Cryptodome.Cipher import AES

__dir__ = path.abspath(path.dirname(__file__))

def __readf(fn):
    fh = open(fn, 'rb')
    data = fh.read()
    fh.close()
    return data

AES_KEY = b64decode(__readf('/opt/cdn-key'))
serverId = __readf('/opt/cdn-id')

def decryptString(encryptedStr):
    if not isinstance(encryptedStr, str):
        encryptedStr = encryptedStr.decode('utf-8')
    split = encryptedStr.split('.')
    mode = split[0]
    if mode != '2':
        raise ValueError(f'Unknown mode {mode}')

    nonce = b64decode(split[1])
    tag = b64decode(split[2])
    encryptedStr = b64decode(split[3])

    aes = AES.new(AES_KEY, AES.MODE_GCM, nonce=nonce)
    plaintextStr = aes.decrypt_and_verify(encryptedStr, tag)
    return plaintextStr

def encryptString(plaintextStr):
    if isinstance(plaintextStr, str):
        plaintextStr = plaintextStr.encode('utf-8')
    aes = AES.new(AES_KEY, AES.MODE_GCM)
    encryptedStr, tag = aes.encrypt_and_digest(plaintextStr)
    return "2.%s.%s.%s" % (b64encode(aes.nonce).decode('utf-8'), b64encode(tag).decode('utf-8'), b64encode(encryptedStr).decode('utf-8'))

config = None
with open(path.join(__dir__, './config.yml'), 'r') as f:
    config = yaml_load(f)

config['serverId'] = serverId

if __name__ == '__main__':
    from sys import argv
    from Crypto.Random import get_random_bytes

    if argv[1] == 'encrypt':
        print(encryptString(argv[2]))
    elif argv[1] == 'newkey':
        print(b64encode(get_random_bytes(16)))
