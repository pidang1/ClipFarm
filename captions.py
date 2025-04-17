import boto3
import time
import json
import urllib.request
import os
from dotenv import load_dotenv
import re
import datetime 
import subprocess
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import math
from transcribe import transcribe_video

# Load .env variables
load_dotenv()

AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

def generate_srt_from_transcript(transcript_data, output_file):
    """
    Generate an SRT file from the transcript data
    """
    items = transcript_data['results']['items']
    
    srt_lines = []
    current_caption = []
    caption_index = 1
    start_time = None
    
    for item in items:
        # Skip non-speech elements like punctuation which don't have start_time
        if 'start_time' not in item:
            if current_caption:  # Append punctuation to the current word if there is one
                current_caption[-1] += item['alternatives'][0]['content']
            continue
            
        # If this is the first word in a caption, record the start time
        if not current_caption:
            start_time = float(item['start_time'])
        
        # Add the word to the current caption
        current_caption.append(item['alternatives'][0]['content'])
        
        # If we've reached ~10 words or there's a natural break (e.g., end of sentence),
        # or if this is the last word, then complete this caption
        end_time = float(item['end_time'])
        is_end_of_sentence = item['type'] == 'pronunciation' and item.get('alternatives')[0].get('content', '').endswith(('.', '!', '?'))
        
        if len(current_caption) >= 10 or is_end_of_sentence or item == items[-1]:
            # Format the times as required by SRT
            start_str = format_srt_time(start_time)
            end_str = format_srt_time(end_time)
            
            # Join the words into a caption text
            caption_text = ' '.join(current_caption)
            
            # Add the caption to our SRT content
            srt_lines.append(f"{caption_index}")
            srt_lines.append(f"{start_str} --> {end_str}")
            srt_lines.append(caption_text)
            srt_lines.append("")  # Empty line between captions
            
            # Reset for the next caption
            current_caption = []
            caption_index += 1
            start_time = None
    
    # Write the SRT file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(srt_lines))
    
    return output_file

def format_srt_time(seconds):
    """
    Convert seconds to SRT time format: HH:MM:SS,MS
    """
    ms = int((seconds - int(seconds)) * 1000)
    seconds = int(seconds)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"

def burn_subtitles_into_video(video_path, srt_path, output_path):
    """
    Burn SRT subtitles directly into the video using FFmpeg with proper path handling
    """
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Convert Windows paths to properly escaped paths for FFmpeg
    video_path_fixed = video_path.replace('\\', '/')
    srt_path_fixed = srt_path.replace('\\', '/')
    output_path_fixed = output_path.replace('\\', '/')
    
    # Print debugging info
    print(f"Video path: {os.path.abspath(video_path)}")
    print(f"SRT path: {os.path.abspath(srt_path)}")
    print(f"Output path: {os.path.abspath(output_path)}")
    
    # FFmpeg command with proper path escaping
    cmd = [
        'ffmpeg',
        '-i', video_path_fixed,
        '-vf', f"subtitles='{srt_path_fixed}':force_style='FontName=Arial,FontSize=20,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H50000000,BackColour=&H50000000,BorderStyle=1,Outline=1,Shadow=1,Alignment=10'",
        '-c:a', 'copy',
        '-y',
        output_path_fixed
    ]
    
    print("Running FFmpeg command:", ' '.join(cmd))
    
    # Run the command
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Print FFmpeg output for debugging
        if result.stdout:
            print("FFmpeg stdout:", result.stdout)
        if result.stderr:
            print("FFmpeg stderr:", result.stderr)
            
        if result.returncode != 0:
            print(f"FFmpeg process returned non-zero exit code: {result.returncode}")
            return None
            
        print(f"Successfully added captions to the video. Output saved to {output_path}")
        return output_path
    except Exception as e:
        print(f"Error running FFmpeg: {e}")
        return None

def add_captions_to_video(video_path, transcript_data):
    """
    Main function to add captions to a video using FFmpeg only
    """
    # Verify the video file exists
    if not os.path.exists(video_path):
        print(f"ERROR: Video file not found at {video_path}")
        print(f"Current working directory: {os.getcwd()}")
        return {
            "error": f"Video file not found at {video_path}",
            "video_path_provided": video_path
        }
    
    # Create output paths
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    output_dir = "captioned_videos"
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    srt_path = os.path.join("transcripts", f"{base_name}_{timestamp}.srt")
    output_video_path = os.path.join(output_dir, f"{base_name}_captioned_{timestamp}.mp4")
    
    # Generate subtitle file
    generate_srt_from_transcript(transcript_data, srt_path)
    print(f"Generated SRT file: {srt_path}")
    
    # Burn subtitles with FFmpeg
    result = burn_subtitles_into_video(video_path, srt_path, output_video_path)
    
    if result:
        return {
            "captioned_video": output_video_path,
            "srt_file": srt_path
        }
    else:
        return {
            "error": "Failed to create captioned video with FFmpeg",
            "srt_file": srt_path
        }

# Example usage
# if __name__ == "__main__":
#     # Download the video from S3 (you'll need to implement this)
#     s3_uri = "s3://clip-farm-results/clips/segment_000_clip_1_117.95-123.59.mp4"
#     local_video_path = f"downloaded_videos/captioned_clip_{s3_uri.split('/')[-1]}"
    
#     # Ensure the directory exists
#     os.makedirs(os.path.dirname(local_video_path), exist_ok=True)
    
#     s3_client = boto3.client('s3', 
#                           aws_access_key_id=AWS_ACCESS_KEY, 
#                           aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
#     bucket_name = s3_uri.split("/")[2]
#     object_key = "/".join(s3_uri.split("/")[3:])
    
#     try:
#         s3_client.download_file(bucket_name, object_key, local_video_path)
#         print(f"Downloaded video to {local_video_path}")
#     except Exception as e:
#         print(f"Error downloading video: {e}")
#         # If you already have the video locally, you can skip this
    
#     # Transcribe the video
#     transcript_data = transcribe_video(s3_uri)
    
#     if transcript_data:
#         # Add captions to the video
#         result = add_captions_to_video(local_video_path, transcript_data)
#         print("Caption process complete!")
#         print(result)