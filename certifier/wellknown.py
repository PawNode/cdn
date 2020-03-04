from myglobals import config, s3_client

BUCKET_NAME = config['wellknown']['bucketName']

def uploadWellknown(path, data):
    s3_client.put_object(Bucket=BUCKET_NAME, Key=path, Body=data)
