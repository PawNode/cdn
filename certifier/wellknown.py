from azure.storage.blob import BlockBlobService
from myglobals import config

wkconfig = config['wellknown']

blob_client = BlockBlobService(account_name=wkconfig['accountName'], account_key=wkconfig['accessKey'])

def uploadWellknown(path, data):
    blob_client.create_blob_from_bytes(wkconfig['path'], path, data)
