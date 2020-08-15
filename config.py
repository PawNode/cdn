from os import path
from yaml import safe_load as yaml_load
from base64 import b64decode, b64encode
from Crypto.Cipher import AES

__dir__ = path.abspath(path.dirname(__file__))

def __readf(fn):
    fh = open(fn, 'rb')
    data = fh.read()
    fh.close()
    return data

AES_KEY = b64decode(__readf('/opt/cdn-key'))
AES_IV = b'\0'*16
serverId = __readf('/opt/cdn-id')

def decryptString(encryptedStr, iv=AES_IV):
    aes = AES.new(AES_KEY, AES.MODE_CFB, iv)
    plaintextStr = aes.decrypt(encryptedStr)
    return plaintextStr

def encryptString(plaintextStr, iv=AES_IV):
    aes = AES.new(AES_KEY, AES.MODE_CFB, iv)
    encryptedStr = aes.encrypt(plaintextStr)
    return encryptedStr

config = None
with open(path.join(__dir__, './config.yml'), 'r') as f:
    config = yaml_load(f)

config['serverId'] = serverId
