import streamlit as st
import time
import datetime
import pandas as pd
from preprocess import cut_video
from queue_upload import upload_worker
from queue import Queue
import threading
import os
import uuid
import boto3
import json
import io
from dotenv import load_dotenv
import tempfile
from cut_clip import extract_clips_from_s3
from captions import add_captions_to_video, generate_srt_from_transcript, format_srt_time
import subprocess


load_dotenv()

# Set page configuration
st.set_page_config(
    page_title="Clip Farm - Video Processing",
    page_icon="🎬",
    layout="wide"
)

def process_best_segments_json(json_data):
    """Extract relevant information from the best-segments JSON data"""
    try:
        # Parse the JSON data
        data = json.loads(json_data) if isinstance(json_data, str) else json_data
        
        # Extract the source information
        source_transcript = data.get('source_transcript', '')
        source_video = data.get('source_video', '')
        
        # Extract the segments
        segments = data.get('segments', [])
        
        # Return structured data
        return {
            'source_transcript': source_transcript,
            'source_video': source_video,
            'segments': segments,
            'segment_count': len(segments)
        }
    except Exception as e:
        print(f"Error processing best segments JSON: {str(e)}")
        return {
            'source_transcript': '',
            'source_video': '',
            'segments': [],
            'segment_count': 0,
            'error': str(e)
        }
        
def process_transcript_json(json_data):
    """Extract relevant transcript information from the JSON data"""
    try:
        # Parse the JSON data
        data = json.loads(json_data) if isinstance(json_data, str) else json_data
        
        # Extract the transcript text from the results
        transcript_text = data.get('results', {}).get('transcripts', [{}])[0].get('transcript', '')
        
        # Get the original video URI
        original_video_uri = data.get('original_video_uri', '')
        
        # Extract job name and status
        job_name = data.get('jobName', '')
        status = data.get('status', '')
        
        # Get audio segments for timing information
        audio_segments = data.get('results', {}).get('audio_segments', [])
        
        start_time = 0
        end_time = 0
        
        if audio_segments and len(audio_segments) > 0:
            start_time = float(audio_segments[0].get('start_time', 0))
            end_time = float(audio_segments[0].get('end_time', 0))
        
        # Return structured transcript data
        return {
            'transcript': transcript_text,
            'original_video_uri': original_video_uri,
            'job_name': job_name,
            'status': status,
            'start_time': start_time,
            'end_time': end_time,
            'duration': end_time - start_time
        }
    except Exception as e:
        print(f"Error processing transcript JSON: {str(e)}")
        return {
            'transcript': "Error processing transcript",
            'original_video_uri': "",
            'job_name': "",
            'status': "ERROR",
            'start_time': 0,
            'end_time': 0,
            'duration': 0
        }
        
# Initialize session state variables
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'current_video' not in st.session_state:
    st.session_state.current_video = None
if 'clip_suggestions' not in st.session_state:
    st.session_state.clip_suggestions = []
if 's3_contents' not in st.session_state:
    st.session_state.s3_contents = []
if 'fetch_scheduled' not in st.session_state:
    st.session_state.fetch_scheduled = False
if 'video_generation_progress' not in st.session_state:
    st.session_state.video_generation_progress = {}
if 'generated_videos' not in st.session_state:
    st.session_state.generated_videos = {}

# Initialize S3 client
# gets AWS credentials
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

def generate_video_for_best_segment(segment_data, source_video_uri, segment_index):
    """Generate a video for a specific segment using the original video"""
    # Create a unique key for this generation task
    if source_video_uri not in st.session_state.video_generation_progress:
        st.session_state.video_generation_progress[source_video_uri] = 0
    
    # Extract segment information
    start_time = segment_data.get('start_time', 0)
    end_time = segment_data.get('end_time', 0)
    duration = segment_data.get('duration', 0)
    transcript = segment_data.get('transcript', '')
    
    # Progress placeholders
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    download_placeholder = st.empty()
    
    # Initialize progress
    progress_placeholder.progress(0)
    
    # Parse the S3 URI
    s3_parts = source_video_uri.split('://')
    if len(s3_parts) != 2:
        status_placeholder.error(f"Invalid S3 URI format: {source_video_uri}")
        return
    
    s3_path = s3_parts[1].split('/', 1)
    if len(s3_path) != 2:
        status_placeholder.error(f"Invalid S3 path format: {source_video_uri}")
        return
    
    s3_bucket = s3_path[0]
    s3_key = s3_path[1]
    
    status_placeholder.info(f"Processing video segment from S3: {s3_bucket}/{s3_key}")
    
    try:
        # Create a list with the single segment we want to extract
        clips_to_extract = [{
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "transcript": transcript,
            "confidence": segment_data.get('confidence', 0)
        }]
        
        # Update progress to indicate we're starting extraction
        progress = 0.1  # 10%
        st.session_state.video_generation_progress[source_video_uri] = progress
        progress_placeholder.progress(progress)
        
        # First, download the original video
        temp_dir = tempfile.gettempdir()
        video_id = os.path.basename(s3_key).split('.')[0]
        original_video_path = os.path.join(temp_dir, f"{video_id}.mp4")
        
        status_placeholder.info(f"Downloading original video from S3: {s3_bucket}/{s3_key}")
        s3_client.download_file(
            Bucket=s3_bucket,
            Key=s3_key,
            Filename=original_video_path
        )
        
        # Update progress after download
        progress = 0.3  # 30%
        st.session_state.video_generation_progress[source_video_uri] = progress
        progress_placeholder.progress(progress)
        
        # Extract clip using MoviePy
        status_placeholder.info(f"Extracting clip from {start_time:.2f}s to {end_time:.2f}s...")
        
        # Generate unique filenames
        clip_filename = f"{video_id}_clip_{segment_index}_{start_time:.2f}-{end_time:.2f}.mp4"
        clip_path = os.path.join(temp_dir, clip_filename)
        
        from moviepy.editor import VideoFileClip
        try:
            # Load the video
            video = VideoFileClip(original_video_path)
            
            # Extract the subclip
            subclip = video.subclip(start_time, end_time)
            
            # Write the clip to file
            subclip.write_videofile(
                clip_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=os.path.join(temp_dir, "temp-audio.m4a"),
                remove_temp=True,
                fps=video.fps,
                preset='fast'
            )
            
            # Close clips to free memory
            subclip.close()
            video.close()
            
            # Update progress after extraction
            progress = 0.5  # 50%
            st.session_state.video_generation_progress[source_video_uri] = progress
            progress_placeholder.progress(progress)
            
            # Upload extracted clip to S3
            status_placeholder.info(f"Uploading extracted clip to S3...")
            
            clip_s3_key = clip_filename
            s3_client.upload_file(
                clip_path,
                "clip-farm-results",
                clip_s3_key
            )
            
            # Create clip info like what would be returned by extract_clips_from_s3
            clip_info = {
                "source_video": s3_key,
                "clip_number": segment_index,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "transcript": transcript,
                "s3_uri": f"s3://clip-farm-results/{clip_s3_key}",
                "filename": clip_filename
            }
            
            # Update progress after upload
            progress = 0.6  # 60%
            st.session_state.video_generation_progress[source_video_uri] = progress
            progress_placeholder.progress(progress)
            
            # Now proceed with captioning
            status_placeholder.info("Creating caption file...")
            
            # Create directories if they don't exist
            os.makedirs("transcripts", exist_ok=True)
            os.makedirs("captioned_videos", exist_ok=True)
            
            # Create a simplified SRT file directly from the transcript text
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            base_name = os.path.splitext(os.path.basename(clip_path))[0]
            srt_path = os.path.join("transcripts", f"{base_name}_{timestamp}.srt")
            
            # Create a simplified SRT file manually
            with open(srt_path, 'w', encoding='utf-8') as f:
                # Split transcript into approximately 10-word chunks
                words = transcript.split()
                chunks = []
                chunk = []
                
                for word in words:
                    chunk.append(word)
                    if len(chunk) >= 10 or word.endswith(('.', '!', '?')):
                        chunks.append(' '.join(chunk))
                        chunk = []
                
                # Add any remaining words as a chunk
                if chunk:
                    chunks.append(' '.join(chunk))
                
                # Calculate time per chunk
                if len(chunks) > 0:
                    time_per_chunk = duration / len(chunks)
                else:
                    time_per_chunk = duration
                    chunks = [transcript]  # Use full transcript as one chunk
                
                # Write SRT format
                for i, chunk_text in enumerate(chunks):
                    chunk_start = i * time_per_chunk
                    chunk_end = (i + 1) * time_per_chunk
                    
                    start_str = format_srt_time(chunk_start)
                    end_str = format_srt_time(chunk_end)
                    
                    f.write(f"{i+1}\n")
                    f.write(f"{start_str} --> {end_str}\n")
                    f.write(f"{chunk_text}\n\n")
            
            # Update progress
            progress = 0.7  # 70%
            st.session_state.video_generation_progress[source_video_uri] = progress
            progress_placeholder.progress(progress)
            
            # Add captions to the video using FFmpeg
            status_placeholder.info("Adding captions to the video...")
            output_dir = "captioned_videos"
            output_video_path = os.path.join(output_dir, f"{base_name}_captioned_{timestamp}.mp4")
            
            
            
            # Convert Windows paths to properly escaped paths for FFmpeg
            clip_path_fixed = clip_path.replace('\\', '/')
            srt_path_fixed = srt_path.replace('\\', '/')
            output_video_path_fixed = output_video_path.replace('\\', '/')
            
            # FFmpeg command with proper path escaping
            cmd = [
                'ffmpeg',
                '-i', clip_path_fixed,
                '-vf', f"subtitles='{srt_path_fixed}':force_style='FontName=Arial,FontSize=20,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H50000000,BackColour=&H50000000,BorderStyle=1,Outline=1,Shadow=1,Alignment=10'",
                '-c:a', 'copy',
                '-y',
                output_video_path_fixed
            ]
            
            # Run the command
            try:
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                if result.returncode != 0:
                    status_placeholder.warning(f"Warning: FFmpeg error when adding captions. Using original clip instead.")
                    captioned_video_path = clip_path
                else:
                    captioned_video_path = output_video_path
                    
            except Exception as e:
                status_placeholder.warning(f"Warning: Could not add captions: {str(e)}. Using original clip instead.")
                captioned_video_path = clip_path
            
            # Update progress
            progress = 0.9  # 90%
            st.session_state.video_generation_progress[source_video_uri] = progress
            progress_placeholder.progress(progress)
            
            # Upload the captioned video back to S3
            captioned_filename = os.path.basename(captioned_video_path)
            captioned_s3_key = f"captioned/{captioned_filename}"
            
            s3_client.upload_file(
                captioned_video_path,
                "clip-farm-results",
                captioned_s3_key
            )
            
            # Create S3 URI for the captioned video
            captioned_s3_uri = f"s3://clip-farm-results/{captioned_s3_key}"
            s3_clip_uri = f"s3://clip-farm-results/{clip_s3_key}"
            
            # Mark as complete
            st.session_state.video_generation_progress[source_video_uri] = 1.0
            progress_placeholder.progress(1.0)
            
            # Store in session state that this video has been generated
            video_id = os.path.basename(s3_key).split('.')[0]
            if video_id not in st.session_state.generated_videos:
                st.session_state.generated_videos[video_id] = []
            
            # Add to generated videos
            st.session_state.generated_videos[video_id].append({
                'segment_index': segment_index,
                'start_time': start_time,
                'end_time': end_time,
                'transcript': transcript,
                'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'filename': captioned_filename,
                's3_uri': captioned_s3_uri,
                'uncaptioned_s3_uri': s3_clip_uri
            })
            
            status_placeholder.success(f"Video segment ({duration:.2f}s) successfully generated with captions!")
            
            # Provide both S3 URLs for reference
            st.write(f"Original clip: {s3_clip_uri}")
            st.write(f"Captioned clip: {captioned_s3_uri}")
            
            # Provide download button for the captioned video
            try:
                with open(captioned_video_path, 'rb') as f:
                    video_bytes = f.read()
                    download_placeholder.download_button(
                        label="Download Captioned Clip",
                        data=io.BytesIO(video_bytes),
                        file_name=captioned_filename,
                        mime="video/mp4",
                        key=f"download_captioned_segment_{segment_index}_{start_time:.2f}"
                    )
                    
                # Clean up the temporary files
                if os.path.exists(original_video_path):
                    os.remove(original_video_path)
                if os.path.exists(clip_path) and clip_path != captioned_video_path:
                    os.remove(clip_path)
                if os.path.exists(srt_path):
                    os.remove(srt_path)
                if os.path.exists(captioned_video_path):
                    os.remove(captioned_video_path)
                
            except Exception as e:
                download_placeholder.error(f"Could not prepare download: {str(e)}")
                download_placeholder.info(f"Access the captioned clip directly from S3: {captioned_s3_uri}")
                
        except Exception as e:
            status_placeholder.error(f"Error processing video: {str(e)}")
            if os.path.exists(original_video_path):
                os.remove(original_video_path)
            raise e
            
    except Exception as e:
        status_placeholder.error(f"Error generating video: {str(e)}")
        progress_placeholder.progress(0)
        st.exception(e)

def delete_best_segment(segment_data, source_video_uri, segment_index, json_key):
    """Delete a segment from the best segments list"""
    # Progress placeholders
    status_placeholder = st.empty()
    
    # Parse the S3 URI
    s3_parts = source_video_uri.split('://')
    if len(s3_parts) != 2:
        status_placeholder.error(f"Invalid S3 URI format: {source_video_uri}")
        return
    
    s3_path = s3_parts[1].split('/', 1)
    if len(s3_path) != 2:
        status_placeholder.error(f"Invalid S3 path format: {source_video_uri}")
        return
    
    s3_bucket = s3_path[0]
    s3_key = s3_path[1]
    
    # Extract a readable video ID from the source video URI
    video_id = s3_key.split('.')[0]
    
    try:
        status_placeholder.info(f"Deleting segment {segment_index+1} for video {video_id}...")
        
        # Fetch the existing JSON
        try:
            response = s3_client.get_object(
                Bucket="best-segments",
                Key=json_key
            )
            
            # Parse the existing JSON
            best_segments = json.loads(response['Body'].read().decode('utf-8'))
            
            # Remove the segment at the specified index
            if 'segments' in best_segments and len(best_segments['segments']) > segment_index:
                # Store the segment info before deletion for confirmation message
                deleted_segment = best_segments['segments'][segment_index]
                
                # Remove the segment
                best_segments['segments'].pop(segment_index)
                
                # Check if the segments list is now empty
                if len(best_segments['segments']) == 0:
                    # Delete the entire JSON object since there are no more segments
                    s3_client.delete_object(
                        Bucket="best-segments",
                        Key=json_key
                    )
                    status_placeholder.success(f"Deleted the last segment and removed the best segments object: {json_key}")
                else:
                    # Upload the updated JSON back to S3
                    s3_client.put_object(
                        Bucket="best-segments",
                        Key=json_key,
                        Body=json.dumps(best_segments, indent=2),
                        ContentType='application/json'
                    )
                    status_placeholder.success(f"Successfully deleted segment {segment_index+1}: {deleted_segment['start_time']:.2f}s - {deleted_segment['end_time']:.2f}s")
                
                # If any generated videos exist for this segment, delete them too
                if video_id in st.session_state.generated_videos:
                    # Filter generated videos to exclude the deleted segment
                    st.session_state.generated_videos[video_id] = [
                        video for video in st.session_state.generated_videos[video_id]
                        if video.get('segment_index') != segment_index
                    ]
                
                # Force refresh of S3 contents
                fetch_s3_contents()
                
            else:
                status_placeholder.error(f"Segment index {segment_index} not found in the segments list.")
            
        except Exception as e:
            status_placeholder.error(f"Error fetching or updating segments JSON: {str(e)}")
            st.exception(e)
            
    except Exception as e:
        status_placeholder.error(f"Error deleting segment: {str(e)}")
        st.exception(e)

def generate_video_from_segment(segment_key):
    """Generate video from a segment and provide download"""
    # Create a unique key for this generation task
    if segment_key not in st.session_state.video_generation_progress:
        st.session_state.video_generation_progress[segment_key] = 0
    
    # Get video ID from segment key
    video_id = segment_key.split('/')[0] if '/' in segment_key else segment_key.split('_')[0]
    
    # Progress placeholders
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    download_placeholder = st.empty()
    
    # Initialize progress
    progress_placeholder.progress(0)
    status_placeholder.info("Fetching original video from S3...")
    
    # In a real implementation, this would:
    # 1. Parse the JSON to get the original video URI (S3 path)
    # 2. Download the video file from S3
    # 3. Process it as needed
    # 4. Generate the final video and make it available for download
    
    # Simulate fetching the original video
    for i in range(0, 30):
        progress = i / 100
        st.session_state.video_generation_progress[segment_key] = progress
        progress_placeholder.progress(progress)
        time.sleep(0.05)
    
    status_placeholder.info("Processing video content...")
    
    # Simulate video processing
    for i in range(30, 70):
        progress = i / 100
        st.session_state.video_generation_progress[segment_key] = progress
        progress_placeholder.progress(progress)
        time.sleep(0.05)
    
    status_placeholder.info("Finalizing video for download...")
    
    # Simulate finalizing
    for i in range(70, 101):
        progress = i / 100
        st.session_state.video_generation_progress[segment_key] = progress
        progress_placeholder.progress(progress)
        time.sleep(0.05)
    
    # Mark as complete
    st.session_state.video_generation_progress[segment_key] = 1.0
    progress_placeholder.progress(1.0)
    
    # Store in session state that this video has been generated
    if video_id not in st.session_state.generated_videos:
        st.session_state.generated_videos[video_id] = []
    
    # Create a mock download URL
    download_url = f"https://example.com/download/{uuid.uuid4()}"
    
    # Add to generated videos
    st.session_state.generated_videos[video_id].append({
        'segment_key': segment_key,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'download_url': download_url
    })
    
    status_placeholder.success("Video generation complete! Ready for download.")
    
    # In a real implementation, you would:
    # 1. Generate an actual video file
    # 2. Provide it for download using st.download_button with the real file content
    
    # Provide a download button (in a real app, this would link to the actual file)
    download_placeholder.download_button(
        label="Download Generated Video",
        data=io.BytesIO(b"This would be the actual video file content"),
        file_name=f"generated_clip_{segment_key.replace('/', '_').replace('.json', '')}.mp4",
        mime="video/mp4",
        key=f"download_{segment_key.replace('/', '_').replace('.', '_')}"
    )

def fetch_s3_contents():
    """Fetch contents of the S3 bucket"""
    try:
        # List objects in the bucket
        response = s3_client.list_objects_v2(
            Bucket="best-segments",
        )
        
        contents = []
        if 'Contents' in response:
            for obj in response['Contents']:
                contents.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S')
                })
        
        # Update session state with the fetched contents
        st.session_state.s3_contents = contents
        st.session_state.last_fetch_time = datetime.now()
        
        # Force Streamlit to rerun to update the UI
        st.rerun()
        
    except Exception as e:
        print(f"Error fetching S3 contents: {str(e)}")

def schedule_s3_fetch(delay_seconds=45):
    """Schedule a fetch of S3 contents after the specified delay"""
    if st.session_state.fetch_scheduled:
        return
    
    st.session_state.fetch_scheduled = True
    
    def delayed_fetch():
        print(f"Waiting {delay_seconds} seconds before fetching S3 contents...")
        time.sleep(delay_seconds)
        fetch_s3_contents()
        st.session_state.fetch_scheduled = False
    
    # Start a thread for the delayed fetch
    fetch_thread = threading.Thread(target=delayed_fetch)
    fetch_thread.daemon = True
    fetch_thread.start()

# Uploads the given file to s3 bucket
def preprocess_and_upload(file):
    # create an upload queue
    upload_queue = Queue()
    
    # start the upload worker thread
    upload_thread = threading.Thread(target=upload_worker, args=(upload_queue,))
    upload_thread.start()
    
    # generate a video ID
    video_id = f"{uuid.uuid4()}"
    
    # create 5-minute segments and add them to the upload queue
    segments = cut_video(
        file, 
        segment_length=300, 
        upload_queue=upload_queue,
        video_id=video_id
    )
    
    print(f"\nCreated {len(segments)} segments:")
    for i, segment in enumerate(segments):
        print(f"Segment {i}: {segment['file']} (Start: {segment['start_time']}s, Duration: {segment['duration']}s)")
    
    print("\nWaiting for uploads to complete...")
    upload_queue.join()
    
    upload_queue.put(None)
    upload_thread.join()
    
    print("\nAll segments have been uploaded to S3!")
    
    # Schedule S3 fetch 45 seconds after upload completes
    schedule_s3_fetch(45)
    
    
    return None, None

# UI Layout
st.title("🎬 Clip Farm")
st.subheader("Automated Video Clip Generator")

tab1, tab2 = st.tabs(["Upload Video", "S3 Contents"])

with tab1:
    st.write("Upload your video file here to generate engaging clips.")
    
    # File uploader widget
    uploaded_file = st.file_uploader("Choose a video file", type=["mp4"])
    
    if uploaded_file is not None and not st.session_state.processing_complete:
        # Show processing indicators
        with st.spinner("Processing your video..."):
            # Create a progress bar
            progress_bar = st.progress(0)
            video_data, clip_suggestions = preprocess_and_upload(uploaded_file)
            
            # Store in session state
            st.session_state.current_video = video_data
            st.session_state.clip_suggestions = clip_suggestions
            
            # Simulate (for now) transcription
            st.info("Generating transcript...")
            for i in range(25, 76, 5):
                time.sleep(0.1)  # Simulate processing time
                progress_bar.progress(i)
            
            # Simulate (for now) clip identification
            st.info("Identifying engaging clips...")
            for i in range(76, 101, 5):
                time.sleep(0.1) 
                progress_bar.progress(i)
            st.session_state.processing_complete = True
            
        st.success("Processing complete! 🎉 Check the suggested clips below.")
        
        # Notification about S3 fetch
        st.info("S3 contents will be fetched automatically 45 seconds after upload.")
    
    # Display results if processing is complete
    if st.session_state.processing_complete and st.session_state.current_video is not None:
        st.subheader("Transcript")
        transcript_df = pd.DataFrame([
            {"Time": f"{seg['start_time']:.1f}s - {seg['end_time']:.1f}s", "Text": seg['text']} 
            for seg in st.session_state.current_video["transcript"]
        ])
        st.dataframe(transcript_df, use_container_width=True)
        
        st.subheader("Suggested Clips")
        for i, clip in enumerate(st.session_state.clip_suggestions):
            with st.expander(f"Clip {i+1}: {clip['duration']}s (Confidence: {clip['confidence']:.0%})"):
                st.write(f"**Timeframe:** {clip['start_time']:.1f}s - {clip['end_time']:.1f}s")
                st.write(f"**Content:** {clip['transcript']}")
                
                if st.button(f"Generate Clip {i+1}", key=f"gen_clip_{i}"):
                    with st.spinner("Generating clip..."):
                        time.sleep(1) 
                        st.success("Clip generated! Download link would appear here.")

# The tab that displays S3 bucket contents
with tab2:
    st.subheader("Best Video Segments")
    
    # Add manual refresh button
    if st.button("Refresh RDS Contents"):
        fetch_s3_contents()
    
    # Show last fetch time if available
    if 'last_fetch_time' in st.session_state:
        st.write(f"Last updated: {st.session_state.last_fetch_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Display processed segments with transcripts
    if st.session_state.s3_contents:
        # Filter for best-segments JSON files
        # In a real implementation, you would identify these files by a naming pattern or content
        
        # Create a list to store best segment data
        best_segments_data = []
        
        for obj in st.session_state.s3_contents:
            key = obj['key']
            
            # Skip non-JSON files
            if not key.endswith('.json'):
                continue
                
            # For simulation purposes, we'll assume all JSON files are best-segment files
            # In production, you would need to fetch and check the content
            
            # Create a sample best-segments object for demonstration
            # In production, you would fetch this from S3
            response = s3_client.get_object(
            Bucket="best-segments",
            Key=key
            )
            
            # Parse the JSON content
            best_segments = json.loads(response['Body'].read().decode('utf-8'))
            
            
            # Process and add to our list
            best_segments_data.append({
                'key': key,
                'data': best_segments,
                'processed': process_best_segments_json(best_segments)
            })
            
            
        
        # Display best segments
        if best_segments_data:
            for item in best_segments_data:
                processed = item['processed']
                source_video = processed['source_video']
                segments = processed['segments']
                json_key = item['key']  # Get the actual JSON key
                
                # Extract a readable video ID from the source video URI
                video_id = source_video.split('/')[-1].split('.')[0]
                
                with st.expander(f"Video: {video_id} - {len(segments)} best segments"):
                    st.write(f"**Source Video:** {source_video}")
                    st.write(f"**Source Transcript:** {processed['source_transcript']}")
                    
                    # Display each segment with controls
                    for i, segment in enumerate(segments):
                        with st.container():
                            # Create columns for better layout
                            col1, col2, col3 = st.columns([3, 1, 1])
                            
                            with col1:
                                st.subheader(f"Segment {i+1}")
                                st.write(f"**Time Range:** {segment['start_time']:.2f}s - {segment['end_time']:.2f}s (Duration: {segment['duration']:.2f}s)")
                                st.write(f"**Transcript:** {segment['transcript']}")
                                st.write(f"**Confidence:** {segment['confidence']:.2%}")
                            
                            with col2:
                                # Generate Video button
                                if st.button(f"Generate Video", key=f"gen_video_{video_id}_{i}"):
                                    generate_video_for_best_segment(segment, source_video, i)
                            
                            with col3:
                                # Delete Segment button (new)
                                if st.button(f"Delete Segment", key=f"del_segment_{video_id}_{i}"):
                                    delete_best_segment(segment, source_video, i, json_key)
                            
                            st.markdown("---")
        else:
            st.info("No best-segments data found in the expected format.")
        
        # Display count of objects
        st.write(f"Total objects in RDS: {len(st.session_state.s3_contents)}")
    else:
        st.info("No objects found in RDS or contents haven't been fetched yet.")

# Footer
st.markdown("---")
st.caption("Clip Farm - With Delayed RDS Fetch | Automatically fetches RDS contents 45 seconds after upload")