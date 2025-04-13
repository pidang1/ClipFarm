import streamlit as st
import time
from datetime import datetime
import pandas as pd

# Set page configuration
st.set_page_config(
    page_title="Clip Farm - Video Processing",
    page_icon="🎬",
    layout="wide"
)

# Initialize session state variables
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'current_video' not in st.session_state:
    st.session_state.current_video = None
if 'clip_suggestions' not in st.session_state:
    st.session_state.clip_suggestions = []

# Mock data function - simply returns predefined data
def get_mock_data(file_name):
    # Mock video metadata
    video_data = {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "filename": file_name,
        "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_size_mb": 15.7,  # Mock file size
        "status": "processed",
        "path": f"mock_path/{file_name}"
    }
    
    # Mock transcript data (WE WILL GET THIS WORKING ACTUALLY TRUSTTT)
    video_data["transcript"] = [
        {"start_time": 0.0, "end_time": 5.2, "text": "Welcome to this video about clip farming."},
        {"start_time": 5.5, "end_time": 10.8, "text": "Today we'll explore how to automatically find the most engaging parts of your content."},
        {"start_time": 11.2, "end_time": 17.5, "text": "This technology can save content creators hours of editing time."},
        {"start_time": 18.0, "end_time": 25.3, "text": "The key is in analyzing speech patterns, sentiment, and audience reactions."},
        {"start_time": 26.0, "end_time": 35.7, "text": "Let me show you an exciting example of how this works in practi ce!"},
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

tab1, tab2 = st.tabs(["Upload Video", "Clips Generated"])

with tab1:
    st.write("Upload your video file here to generate engaging clips.")
    
    # File uploader widget
    uploaded_file = st.file_uploader("Choose a video file", type=["mp4"])
    
    if uploaded_file is not None and not st.session_state.processing_complete:
        # Show processing indicators
        with st.spinner("Processing your video..."):
            # Create a progress bar
            progress_bar = st.progress(0)
            
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
            
            # Get mock data
            file_name = uploaded_file.name if uploaded_file.name else "unknown_file.mp4"
            st.session_state.current_video, st.session_state.clip_suggestions = get_mock_data(file_name)
            st.session_state.processing_complete = True
            
        st.success("Processing complete! 🎉 Check the suggested clips below.")
    
    # Display results if processing is complete
    if st.session_state.processing_complete:
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

# The other tab that will later display all processed videos
with tab2:
    st.write("Previously processed videos:")
    st.info("No videos processed yet in this simplified prototype.")

# Footer
st.markdown("---")
st.caption("Clip Farm - Local Prototype | This is a simplified mock version with no actual file processing.")