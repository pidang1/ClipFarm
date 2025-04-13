import os
import sys
from moviepy.editor import VideoFileClip

# cuts video into segments of 5mins each
def cut_video(input_file, segment_length=300):
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input video file not found: {input_file}")
    
    try:
        # load the video
        print(f"Loading video: {input_file}")
        video = VideoFileClip(input_file)
        duration = video.duration
        print(f"Video duration: {duration} seconds")
        
        # calculates number of segments
        num_segments = int(duration / segment_length) + (1 if duration % segment_length > 0 else 0)
        print(f"Will create {num_segments} segments")
        
        output_files = []
        
        output_dir = "output_segments"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # creates segments
        for i in range(num_segments):
            start_time = i * segment_length
            
            # if last segment, use remaining duration
            if i == num_segments - 1 and duration % segment_length > 0:
                segment_duration = duration % segment_length
            else:
                segment_duration = segment_length
            
            # calculate end time
            end_time = min(start_time + segment_duration, duration)
            print(f"Creating segment {i+1}/{num_segments}: {start_time}s to {end_time}s")
            
            output_file = os.path.join(output_dir, f"segment_{i:03d}.mp4")
            subclip = video.subclip(start_time, end_time)
            
            subclip.write_videofile(
                output_file, 
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=f"{output_file}.temp-audio.m4a",
                remove_temp=True
            )
            
            output_files.append({
                'file': output_file,
                'start_time': start_time,
                'duration': end_time - start_time
            })

        video.close()
        return output_files
    
    except Exception as e:
        print(f"Error in cut_video: {str(e)}")
        raise

if __name__ == "__main__":
    input_video_path = r"C:\Users\pierr\Downloads\Trying the BEST STREET FOOD in NYC CHINATOWN🥢🥮⋆✶.˚.mp4"
    
    print(f"Checking for video file: {input_video_path}")
    if os.path.exists(input_video_path):
        print(f"File exists! Absolute path: {os.path.abspath(input_video_path)}")
    else:
        print(f"ERROR: File does not exist at: {input_video_path}")
        try:
            dir_path = os.path.dirname(input_video_path)
            print(f"Files in directory {dir_path}:")
            for file in os.listdir(dir_path):
                print(f"  - {file}")
        except Exception as e:
            print(f"Could not list directory contents: {e}")
        sys.exit(1)
    
    try:
        # each segment is 300s (5mins)
        segments = cut_video(input_video_path, segment_length=300)  
        
        print("\nCreated segments:")
        for i, segment in enumerate(segments):
            print(f"Segment {i}: {segment['file']} (Start: {segment['start_time']}s, Duration: {segment['duration']}s)")
            
        print("\nTest completed successfully!")
    except Exception as e:
        print(f"Error during test: {str(e)}")