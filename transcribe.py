import boto3
import time
import json
import urllib.request
import os
from dotenv import load_dotenv
import re
import datetime 

# Load .env variables
load_dotenv()

AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
transcribe = boto3.client('transcribe', region_name='us-east-1', aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

def transcribe_video(media_uri):
    # Create a job name from the file name
    original_name = media_uri.split("/")[-1].split(".")[0]
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    job_name = re.sub(r'[^0-9a-zA-Z._-]', '_', original_name) + '_' + timestamp
    
    # Start the transcription job
    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={'MediaFileUri': media_uri},
        MediaFormat='mp4',
        LanguageCode='en-US'
    )
    
    # Wait for the job to complete
    while True:
        status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
            break
        print("Transcription in progress...")
        # only query for every 5 seconds to check for the status
        time.sleep(5)
    
    if status['TranscriptionJob']['TranscriptionJobStatus'] == 'FAILED':
        print(f"Transcription failed: {status['TranscriptionJob'].get('FailureReason', 'Unknown reason')}")
        return None
    
    # Get the transcript URL and download the content
    transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
    response = urllib.request.urlopen(transcript_uri)
    transcript_data = json.loads(response.read().decode('utf-8'))
    
    print("Transcription completed successfully.")
    
    # The transcript text is nested within the results
    transcript_text = transcript_data['results']['transcripts'][0]['transcript']
    print(f"Transcript: {transcript_text[:100]}...")  
    
    # Store this data in a json file in a folder ./transcripts
    transcript_folder = "transcripts"
    if not os.path.exists(transcript_folder):
        os.makedirs(transcript_folder)
    
    # Save the full transcript data to a file
    output_file = os.path.join(transcript_folder, f"{original_name}_{timestamp}.json")
    with open(output_file, 'w') as f:
        json.dump(transcript_data, f, indent=4)
    
    print(f"Transcript saved to {output_file}")
    
    return transcript_data


transcribe_video("s3://uploaded-clips/A one minute TEDx Talk for the digital age _ Woody Roseland _ TEDxMileHigh.mp4")