import os
import sys
from moviepy.editor import VideoFileClip
import time
import threading
from queue import Queue
from queue_upload import upload_worker, upload_clip_to_s3


def cut_video(input_file, segment_length=300, upload_queue=None, video_id=None):
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input video file not found: {input_file}")
    
    try:
        # generate a video ID if not provided
        if video_id is None:
            video_id = f"video_{int(time.time())}"
        
        # loads the video
        print(f"Loading video: {input_file}")
        video = VideoFileClip(input_file)
        duration = video.duration
        print(f"Video duration: {duration} seconds")
        
        # calculate # of segments
        num_segments = int(duration / segment_length) + (1 if duration % segment_length > 0 else 0)
        print(f"Will create {num_segments} segments")
        
        output_files = []
        
        output_dir = "output_segments"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # creates segments
        for i in range(num_segments):
            start_time = i * segment_length
            
            # uses remaining duration if last segment is shorter than 5mins
            if i == num_segments - 1 and duration % segment_length > 0:
                segment_duration = duration % segment_length
            else:
                segment_duration = segment_length
            
            # calculates end time
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
            
            segment_info = {
                'file': output_file,
                'start_time': start_time,
                'duration': end_time - start_time,
                'segment_index': i,
                'video_id': video_id
            }
            
            output_files.append(segment_info)
            
            if upload_queue is not None:
                upload_queue.put(segment_info)

        video.close()
        return output_files
    
    except Exception as e:
        print(f"Error in cut_video: {str(e)}")
        raise

if __name__ == "__main__":
    input_video_path = r"C:\Users\daoho\Downloads\READING YOUR CONFESSIONS FT. ALEX CONSANI.mp4"
    
    # check if file exists and print absolute path
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
        # create an upload queue
        upload_queue = Queue()
        
        # start the upload worker thread
        upload_thread = threading.Thread(target=upload_worker, args=(upload_queue,))
        upload_thread.start()
        
        # generate a video ID
        video_id = f"video_{int(time.time())}"
        
        # create 5-minute segments and add them to the upload queue
        segments = cut_video(
            input_video_path, 
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
        print("\nTest completed successfully!")
    except Exception as e:
        print(f"Error during test: {str(e)}")