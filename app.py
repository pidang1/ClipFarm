import streamlit as st
import time
from datetime import datetime
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
    
    s3_parts = source_video_uri.split('://')
    if len(s3_parts) != 2:
        status_placeholder = st.empty()
        status_placeholder.error(f"Invalid S3 URI format: {source_video_uri}")
        return
    
    s3_path = s3_parts[1].split('/', 1)
    if len(s3_path) != 2:
        status_placeholder = st.empty()
        status_placeholder.error(f"Invalid S3 path format: {source_video_uri}")
        return
    
    s3_bucket = s3_path[0]
    s3_key = s3_path[1]
    video_id = s3_key.split('.')[0]
    
    # Local file paths
    temp_dir = "/tmp"
    original_video_path = f"{temp_dir}/{video_id}.mp4"
    output_video_path = f"{temp_dir}/clip_{video_id}_segment_{segment_index}_{start_time:.2f}_{end_time:.2f}.mp4"
    
    # Progress placeholders
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    download_placeholder = st.empty()
    
    # Initialize progress
    progress_placeholder.progress(0)
    status_placeholder.info(f"Downloading original video from S3: {s3_bucket}/{video_id}")
    
    try:
        st.write(f"Downloading original video from S3: {video_id}")
        # Download the original video from S3
        s3_client.download_file(
            Bucket="uploaded-clips",
            Key=video_id,
            Filename=original_video_path
        )
        
        # Update progress after successful download
        progress = 0.3  # 30%
        st.session_state.video_generation_progress[source_video_uri] = progress
        progress_placeholder.progress(progress)
        
        status_placeholder.info(f"Trimming video from {start_time:.2f}s to {end_time:.2f}s...")
        
        # Here you would use FFmpeg to trim the video
        # For example:
        # import subprocess
        # subprocess.run([
        #     'ffmpeg', '-i', original_video_path, 
        #     '-ss', str(start_time), '-to', str(end_time),
        #     '-c:v', 'copy', '-c:a', 'copy',
        #     output_video_path
        # ])
        
        # Since we're not actually running FFmpeg, simulate progress
        for i in range(30, 60):
            progress = i / 100
            st.session_state.video_generation_progress[source_video_uri] = progress
            progress_placeholder.progress(progress)
            time.sleep(0.05)
        
        status_placeholder.info("Processing video and adding captions...")
        
        # Simulate processing
        for i in range(60, 90):
            progress = i / 100
            st.session_state.video_generation_progress[source_video_uri] = progress
            progress_placeholder.progress(progress)
            time.sleep(0.05)
        
        status_placeholder.info("Finalizing video for download...")
        
        # Simulate finalizing
        for i in range(90, 101):
            progress = i / 100
            st.session_state.video_generation_progress[source_video_uri] = progress
            progress_placeholder.progress(progress)
            time.sleep(0.05)
        
        # Mark as complete
        st.session_state.video_generation_progress[source_video_uri] = 1.0
        progress_placeholder.progress(1.0)
        
        # Store in session state that this video has been generated
        if video_id not in st.session_state.generated_videos:
            st.session_state.generated_videos[video_id] = []
        
        # Create a unique filename for this segment
        filename = f"clip_{video_id}_segment_{segment_index}_{start_time:.2f}_{end_time:.2f}.mp4"
        
        # Add to generated videos
        st.session_state.generated_videos[video_id].append({
            'segment_index': segment_index,
            'start_time': start_time,
            'end_time': end_time,
            'transcript': transcript,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'filename': filename
        })
        
        status_placeholder.success(f"Video segment ({duration:.2f}s) successfully generated!")
        
        # In a real implementation, you would read the processed file for download
        # For now, let's read the original downloaded file since we didn't actually process it
        with open(original_video_path, 'rb') as f:
            video_bytes = f.read()
            download_placeholder.download_button(
                label="Download Generated Clip",
                data=io.BytesIO(video_bytes),
                file_name=filename,
                mime="video/mp4",
                key=f"download_segment_{segment_index}_{start_time:.2f}"
            )
        
    except Exception as e:
        status_placeholder.error(f"Error generating video: {str(e)}")
        progress_placeholder.progress(0)
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
    
    # Mock video metadata
    video_data = {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "filename": "file_name",
        "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_size_mb": 15.7,  # Mock file size
        "status": "processed",
        "path": f"mock_path/mock_path"
    }
    
    # Mock transcript data (WE WILL GET THIS WORKING ACTUALLY TRUSTTT)
    video_data["transcript"] = [
        {"start_time": 0.0, "end_time": 5.2, "text": "Welcome to this video about clip farming."},
        {"start_time": 5.5, "end_time": 10.8, "text": "Today we'll explore how to automatically find the most engaging parts of your content."},
        {"start_time": 11.2, "end_time": 17.5, "text": "This technology can save content creators hours of editing time."},
        {"start_time": 18.0, "end_time": 25.3, "text": "The key is in analyzing speech patterns, sentiment, and audience reactions."},
        {"start_time": 26.0, "end_time": 35.7, "text": "Let me show you an exciting example of how this works in practice!"},
        {"start_time": 36.0, "end_time": 45.5, "text": "As you can see, the algorithm detected this segment as highly engaging due to tone and keyword density."}
    ]
    
    # Mock clip suggestions (Mock now BUT sentiment analysis WILL be working later)
    mock_suggested_clips = [
        {
            "start_time": 26.0,
            "end_time": 45.5,
            "duration": 19.5,
            "transcript": "Let me show you an exciting example of how this works in practice! As you can see, the algorithm detected this segment as highly engaging due to tone and keyword density.",
            "confidence": 0.92
        },
        {
            "start_time": 11.2,
            "end_time": 25.3,
            "duration": 14.1,
            "transcript": "This technology can save content creators hours of editing time. The key is in analyzing speech patterns, sentiment, and audience reactions.",
            "confidence": 0.85
        },
        {
            "start_time": 0.0,
            "end_time": 10.8,
            "duration": 10.8,
            "transcript": "Welcome to this video about clip farming. Today we'll explore how to automatically find the most engaging parts of your content.",
            "confidence": 0.75
        }
    ]
    
    return video_data, mock_suggested_clips

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
    if st.button("Refresh S3 Contents"):
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
            
            st.write(best_segments)
            
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
                
                # Extract a readable video ID from the source video URI
                video_id = source_video.split('/')[-1].split('.')[0]
                
                with st.expander(f"Video: {video_id} - {len(segments)} best segments"):
                    st.write(f"**Source Video:** {source_video}")
                    st.write(f"**Source Transcript:** {processed['source_transcript']}")
                    
                    # Display each segment with controls
                    for i, segment in enumerate(segments):
                        with st.container():
                            # Create columns for better layout
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                st.subheader(f"Segment {i+1}")
                                st.write(f"**Time Range:** {segment['start_time']:.2f}s - {segment['end_time']:.2f}s (Duration: {segment['duration']:.2f}s)")
                                st.write(f"**Transcript:** {segment['transcript']}")
                                st.write(f"**Confidence:** {segment['confidence']:.2%}")
                            
                            with col2:
                                # Generate Video button
                                if st.button(f"Generate Video", key=f"gen_video_{video_id}_{i}"):
                                    generate_video_for_best_segment(segment, source_video, i)
                            
                            st.markdown("---")
        else:
            st.info("No best-segments data found in the expected format.")
        
        # Display count of objects
        st.write(f"Total objects in S3: {len(st.session_state.s3_contents)}")
    else:
        st.info("No objects found in S3 bucket or contents haven't been fetched yet.")

# Footer
st.markdown("---")
st.caption("Clip Farm - With Delayed S3 Fetch | Automatically fetches S3 contents 45 seconds after upload")