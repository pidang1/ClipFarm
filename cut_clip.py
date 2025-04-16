import boto3
import os
import uuid
import json
from moviepy.editor import VideoFileClip
from dotenv import load_dotenv

load_dotenv()

AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
s3_client = boto3.client('s3', region_name='us-east-1', aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

def extract_clips_from_s3(clips, s3_key, bucket_name="uploaded-clips", output_bucket="clip-farm-results"):
    
    
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
    "start_time": 117.95,
    "end_time": 123.59,
    "duration": 5.64,
    "transcript": "I hate my grandma I genuinely wish nothing but the worst for her I think that's fucked",
    "confidence": 0.15
  },
  {
    "start_time": 189.67,
    "end_time": 200.65,
    "duration": 10.98,
    "transcript": "I was 6 years old and I covered my toilet walls and shit My mom asked if I needed help with pooping Keep in mind I was 6 and I said no mom I'm good I went to school and my mom found out about it when I got home The poop was under my",
    "confidence": 0.29
  },
  {
    "start_time": 235.88,
    "end_time": 281.19,
    "duration": 45.31,
    "transcript": "When I was younger I was in my room and one day asked my mom and dad something So I walked into the room and saw my mom sucking on my dad's da da da So they I feel like this is a video from 2014 So I'm so invested So they instantly froze and my mom sat up My dad said Sorry mommy's just sucking on my thumb That's how small it was because I got stung by a wasp And then I said I thought she was sucking on your This is traum this is trauma right Yeah I don't wanna read that one Yeah I don't wanna comment No comments What are you confessing though I'm gay I'm gay I pooped like y'all are lame I used to help out at a nursing home This old Russian lady would relate the same tale over and over",
    "confidence": 0.8
  }
]
    
    s3_key = "video_1744604377/segment_000.mp4"
    
    # Extract the clips
    extracted_clips = extract_clips_from_s3(clips_to_extract, s3_key)
    
    # Print the results
    print(json.dumps(extracted_clips, indent=2))