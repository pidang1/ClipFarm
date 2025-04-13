import json
import os
import uuid
import subprocess
import pymysql
import time
from datetime import datetime
import ffmpeg
import sys

def get_video_duration(filepath):
    """Get video duration using ffprobe"""
    cmd = [
        '/opt/ffmpeg/ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', filepath
    ]
    output = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return float(output.stdout.decode('utf-8').strip())

# cuts video into segments of 5mins each
def cut_video(input_file, segment_length=300):
    duration = get_video_duration(input_file)
    num_segments = int(duration / segment_length) + (1 if duration % segment_length > 0 else 0)
    output_files = []

    # creates segments
    for i in range(num_segments):
        start_time = i * segment_length
        # if last segment, use remaining duration
        if i == num_segments - 1 and duration % segment_length > 0:
            segment_duration = duration % segment_length
        else:
            segment_duration = segment_length
            
        output_file = f'/tmp/segment_{i:03d}.mp4'
        cmd = [
            '/opt/ffmpeg/ffmpeg', '-i', input_file, '-ss', str(start_time),
            '-t', str(segment_duration), '-c:v', 'libx264', '-c:a', 'aac',
            '-strict', 'experimental', output_file
        ]
        
        subprocess.check_call(cmd)
        output_files.append({
            'file': output_file,
            'start_time': start_time,
            'duration': segment_duration
        })
    
    return output_files

if __name__ == "__main__":
    # Replace with your input video path
    input_video_path = r"C:\Users\pierr\Downloads\Trying the BEST STREET FOOD in NYC CHINATOWN🥢🥮⋆✶.˚.mp4"
    
    try:
        # Test with a smaller segment length for quicker testing
        segments = cut_video(input_video_path, segment_length=60)  # 1-minute segments for testing
        
        print("\nCreated segments:")
        for i, segment in enumerate(segments):
            print(f"Segment {i}: {segment['file']} (Start: {segment['start_time']}s, Duration: {segment['duration']}s)")
            
        print("\nTest completed successfully!")
    except Exception as e:
        print(f"Error during test: {str(e)}")