import boto3
import os
import uuid
import json
from moviepy.editor import VideoFileClip
load_dotenv()

AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
s3_client = boto3.client('s3', region_name='us-east-1', aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

def extract_clips_from_s3(clips, s3_key, bucket_name="uploaded-clip", output_bucket="clip-farm-results"):
    
    
    # Create a unique temp directory for this extraction job
    job_id = str(uuid.uuid4())
    temp_dir = f"/tmp/clip_farm_{job_id}"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Download the source video
    video_filename = os.path.basename(s3_key)
    local_video_path = os.path.join(temp_dir, video_filename)
    
    print(f"Downloading video from s3://{bucket_name}/{s3_key}...")
    s3_client.download_file(bucket_name, s3_key, local_video_path)
    print(f"Downloaded video to {local_video_path}")
    
    # Load the video file
    try:
        video = VideoFileClip(local_video_path)
        print(f"Loaded video: {video.duration}s duration, {video.size} resolution")
    except Exception as e:
        print(f"Error loading video: {e}")
        return []
    
    # Process each clip
    extracted_clips = []
    
    for i, clip in enumerate(clips):
        start_time = clip["start_time"]
        end_time = clip["end_time"]
        duration = clip["duration"]
        transcript = clip["transcript"]
        
        # Create output filename
        clip_name = f"{os.path.splitext(video_filename)[0]}_clip_{i+1}_{start_time:.2f}-{end_time:.2f}.mp4"
        clip_path = os.path.join(temp_dir, clip_name)
        
        try:
            # Extract the subclip using MoviePy
            print(f"Extracting clip {i+1}: {start_time:.2f}s - {end_time:.2f}s...")
            subclip = video.subclip(start_time, end_time)
            
            # Write the clip to file
            subclip.write_videofile(
                clip_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=f"{temp_dir}/temp-audio.m4a",
                remove_temp=True,
                fps=video.fps,
                preset='fast'  # Options: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
            )
            
            print(f"Clip extracted to {clip_path}")
            
            # Upload clip to S3
            s3_clip_key = f"clips/{os.path.basename(clip_path)}"
            s3_client.upload_file(clip_path, output_bucket, s3_clip_key)
            print(f"Uploaded clip to s3://{output_bucket}/{s3_clip_key}")
            
            # Create metadata for the clip
            clip_info = {
                "source_video": s3_key,
                "clip_number": i + 1,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "transcript": transcript,
                "s3_uri": f"s3://{output_bucket}/{s3_clip_key}",
                "filename": clip_name
            }
            
            extracted_clips.append(clip_info)
            
            # Close the subclip to free memory
            subclip.close()
            
        except Exception as e:
            print(f"Error extracting clip {i+1}: {e}")
    
    # Close the video to free memory
    video.close()
    
    # Clean up temporary files
    try:
        for file in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, file))
        os.rmdir(temp_dir)
        print(f"Cleaned up temporary directory {temp_dir}")
    except Exception as e:
        print(f"Warning: Could not clean up temp directory {temp_dir}: {e}")
    
    return extracted_clips

# Example usage
if __name__ == "__main__":
    # This would typically come from your database or previous processing step
    clips_to_extract = [
        {
            "start_time": 0.11,
            "end_time": 11.57,
            "duration": 11.46,
            "transcript": "Gas or pass Amber you can get a pap smear right there What OGYN That's a woman's annual",
            "confidence": 0.31
        },
        {
            "start_time": 41.15,
            "end_time": 48.4,
            "duration": 7.25,
            "transcript": "it's like 20 degrees out so we're going to see who can warm up our bellies with the best food Who can eat the most Who can eat the most I know this guy's going to",
            "confidence": 0.19
        },
        {
            "start_time": 137.15,
            "end_time": 152.08,
            "duration": 14.93,
            "transcript": "this is a bargain for $5 and they're really juicy and I love the little lady who smiled and like and took my order She was just so cute I'll say service 10 out of 10 juiciness 10 out of 10 bang for your buck 10 out of 10 100 out of 10 Can't buy this at a store for",
            "confidence": 0.4
        }
    ]
    
    s3_key = "video_1744592340/segment_000.mp4"
    
    # Extract the clips
    extracted_clips = extract_clips_from_s3(clips_to_extract, s3_key)
    
    # Print the results
    print(json.dumps(extracted_clips, indent=2))