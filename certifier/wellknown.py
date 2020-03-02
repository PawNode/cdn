from azure.storage.blob import BlockBlobService
from myglobals import config

osconfig = config['objectStorage']
blob_client = BlockBlobService(account_name=osconfig['accountName'], account_key=osconfig['accessKey'])

def uploadWellknown(path, data):
    blob_client.create_blob_from_bytes('wellknown', path, data)
