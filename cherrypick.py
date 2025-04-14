import json
import re
import requests

# Cherry pick the best segments from the transcribed video and return the timestamps and text for each segment (using ollama for now but will be using a different
# model when deployed on aws)

# fetch the json file from the transcripts folder
talk_about_life = None
with open('transcripts\\57 Years Apart - A Boy And a Man Talk About Life_20250413200547.json', 'r') as file:
    talk_about_life = json.load(file)
    


def extract_engaging_clips_ollama(transcript_json, num_clips=3, min_duration=30, max_duration=60, model="mistral"):
    """
    Extract engaging clips from a transcript using Ollama model suggestions
    
    Args:
        transcript_json: AWS Transcribe JSON output
        num_clips: Number of clips to extract
        min_duration: Minimum clip duration in seconds
        max_duration: Maximum clip duration in seconds
        model: Ollama model to use (default: llama3)
    
    Returns:
        List of clip suggestions with timestamps
    """
    # Extract the full transcript text
    full_transcript = transcript_json['results']['transcripts'][0]['transcript']
    
    # Get all word-level items with timestamps
    word_items = [item for item in transcript_json['results']['items'] 
                 if item['type'] == 'pronunciation']
    
    # Create prompt for the Ollama model
    prompt = f"""
    Below is a transcript from a video. Identify the {num_clips} most engaging, 
    interesting, or meaningful segments that would make excellent clips for Tiktok or Instagram Reels.
    (approximately {min_duration}-{max_duration} seconds when spoken).
    
    Look for segments that:
    - Contain surprising, valuable, or controversial statements
    - Express strong opinions or emotions
    - Present key insights or memorable points
    - Would work well as a standalone clip for social media
    - Have a clear beginning and end (complete thoughts)
    
    For each segment, respond ONLY with the exact text of the segment.
    Format your response as:
    
    SEGMENT 1: [exact text from transcript]
    SEGMENT 2: [exact text from transcript]
    SEGMENT 3: [exact text from transcript]
    
    Transcript:
    {full_transcript}
    """
    
    # Call the Ollama API
    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': model,
                'prompt': prompt,
                'stream': False
            },
            timeout=60
        )
        response.raise_for_status()
        ai_response = response.json().get('response', '')
    except requests.exceptions.RequestException as e:
        print(f"Error calling Ollama API: {e}")
        return []
    
    # Extract the suggested segments
    segment_matches = re.findall(r'SEGMENT \d+: (.*?)(?=SEGMENT \d+:|$)', ai_response, re.DOTALL)
    suggested_segments = [segment.strip() for segment in segment_matches if segment.strip()]
    
    # Map suggested segments to timestamps
    clip_suggestions = []
    
    for segment_text in suggested_segments:
        # Find the start and end words of the segment
        first_words = segment_text.split()[:5]  # Take first few words for matching
        last_words = segment_text.split()[-5:]  # Take last few words for matching
        
        start_time = None
        end_time = None
        
        # Find start time by looking for first words
        first_words_pattern = ' '.join(first_words).lower()
        for i in range(len(word_items) - len(first_words) + 1):
            word_sequence = ' '.join([word_items[i+j]['alternatives'][0]['content'].lower() 
                                     for j in range(min(len(first_words), 5))])
            if word_sequence.startswith(first_words[0].lower()) and similarity(word_sequence, first_words_pattern) > 0.8:
                start_time = float(word_items[i]['start_time'])
                break
        
        # Find end time by looking for last words
        last_words_pattern = ' '.join(last_words).lower()
        for i in range(len(word_items) - len(last_words) + 1):
            word_sequence = ' '.join([word_items[i+j]['alternatives'][0]['content'].lower() 
                                     for j in range(min(len(last_words), 5))])
            if word_sequence.endswith(last_words[-1].lower()) and similarity(word_sequence, last_words_pattern) > 0.8:
                end_idx = i + min(len(last_words), 5) - 1
                if end_idx < len(word_items):
                    end_time = float(word_items[end_idx]['end_time'])
                    break
        
        if start_time is not None and end_time is not None:
            duration = end_time - start_time
            confidence_score = min(1.0, duration / max_duration) if duration < min_duration else min(1.0, max_duration / duration)
            
            clip_suggestions.append({
                'start_time': round(start_time, 2),
                'end_time': round(end_time, 2),
                'duration': round(duration, 2),
                'transcript': segment_text,
                'confidence': round(confidence_score, 2)
            })
    
    return clip_suggestions

def similarity(str1, str2):
    """Simple similarity function for fuzzy matching"""
    # In production, you might want to use a better similarity algorithm
    # like Levenshtein distance or cosine similarity
    words1 = set(str1.lower().split())
    words2 = set(str2.lower().split())
    
    if not words1 or not words2:
        return 0
        
    intersection = words1.intersection(words2)
    return len(intersection) / max(len(words1), len(words2))

print(extract_engaging_clips_ollama(transcript_json=talk_about_life))
