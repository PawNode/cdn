from azure.storage.blob import BlockBlobService
from myglobals import config
from boto3 import client as boto3_client

osconfig = config['objectStorage']
s3_client = boto3_client('s3',
    aws_access_key_id=osconfig['accessKeyID'],
    aws_secret_access_key=osconfig['secretAccessKey']
)

BUCKET_NAME = config['wellknown']['bucketName']

def uploadWellknown(path, data):
    s3_client.create_blob_from_bytes(Bucket=BUCKET_NAME, Key=path, Body=data)
