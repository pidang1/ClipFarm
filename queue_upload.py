import os
import sys
import time
import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError
from moviepy.editor import VideoFileClip
from queue import Queue
import threading

# loads environment
load_dotenv()

# gets AWS credentials
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')  # Default to us-east-1 if not specified
S3_BUCKET_NAME = 'uploaded-clips'

s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

#uploads a file to S3 bucket
def upload_clip_to_s3(file_path, object_name=None):
    if object_name is None:
        object_name = os.path.basename(file_path)
    
    try:
        print(f"Uploading {file_path} to S3 bucket {S3_BUCKET_NAME}...")
        s3_client.upload_file(file_path, S3_BUCKET_NAME, object_name)
        print(f"Successfully uploaded {object_name} to S3")
        return True
    except ClientError as e:
        print(f"Error uploading {file_path} to S3: {e}")
        return False

# processes file from queue and uploads to S3
def upload_worker(queue):
    while True:
        file_info = queue.get()
        
        if file_info is None:
            queue.task_done()
            break
            
        file_path = file_info['file']
        segment_index = file_info.get('segment_index', 0)
        video_id = file_info.get('video_id', 'unknown')
        
        object_name = f"{video_id}/segment_{segment_index:03d}.mp4"
        
        # uploads the file
        upload_clip_to_s3(file_path, object_name)
        queue.task_done()