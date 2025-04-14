import json
import re
import requests
from collections import defaultdict

def extract_engaging_clips_ollama(transcript_json, num_clips=3, min_duration=30, max_duration=60, model="mistral"):
    """
    Extract engaging clips from a transcript using Ollama model suggestions
    with advanced n-gram matching for better timestamp extraction
    """
    print("Starting clip extraction process...")
    
    # Extract the full transcript text
    full_transcript = transcript_json['results']['transcripts'][0]['transcript']
    print(f"Successfully extracted full transcript ({len(full_transcript)} characters)")
    
    # Get all word-level items with timestamps
    word_items = [item for item in transcript_json['results']['items'] 
                 if item['type'] == 'pronunciation']
    print(f"Found {len(word_items)} word items with timestamps")
    
    # Build word index and n-gram indices
    print("Building word and n-gram indices...")
    word_index = defaultdict(list)
    bigram_index = defaultdict(list)
    trigram_index = defaultdict(list)
    
    # Create indices for faster lookup
    for i in range(len(word_items)):
        # Word index
        word = word_items[i]['alternatives'][0]['content'].lower()
        word_index[word].append(i)
        
        # Bigram index (pairs of words)
        if i < len(word_items) - 1:
            next_word = word_items[i+1]['alternatives'][0]['content'].lower()
            bigram = (word, next_word)
            bigram_index[bigram].append(i)
            
        # Trigram index (triplets of words)
        if i < len(word_items) - 2:
            next_word = word_items[i+1]['alternatives'][0]['content'].lower() 
            next_next_word = word_items[i+2]['alternatives'][0]['content'].lower()
            trigram = (word, next_word, next_next_word)
            trigram_index[trigram].append(i)
    
    print(f"Created index with {len(word_index)} unique words")
    print(f"Created index with {len(bigram_index)} unique bigrams")
    print(f"Created index with {len(trigram_index)} unique trigrams")
    
    # Create prompt for the Ollama model
    prompt = f"""
    Below is a transcript from a video. Identify the {num_clips} most engaging, 
    interesting, or meaningful segments (at least {min_duration} - {max_duration} seconds for each segment) that would make excellent clips for Tiktok.
    
    Look for segments that:
    - Contain surprising, valuable, funny, entertaining, or controversial statements
    - Express strong opinions or emotions
    - Present key insights or memorable points
    - Would work well as a standalone clip for social media
    - Have a clear beginning and end (complete thoughts)
    
    For each segment, respond with the **EXACT** text from the transcript. Do not paraphrase or summarize, just exact quotes extracted.
    Format your response as:
    
    SEGMENT n: [exact text from transcript without quotation marks]
    
    Transcript:
    {full_transcript}
    """
    
    print(f"Calling Ollama API with model: {model}")
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
        print(f"Received response from Ollama ({len(ai_response)} characters)")
        print("Response:", ai_response) 
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to call Ollama API: {e}")
        return []
    
    # Extract the suggested segments
    segment_matches = re.findall(r'SEGMENT \d+: (.*?)(?=SEGMENT \d+:|$)', ai_response, re.DOTALL)
    suggested_segments = [segment.strip() for segment in segment_matches if segment.strip()]
    
    # Remove any quotation marks from the beginning and end of segments
    cleaned_segments = []
    for segment in suggested_segments:
        # Remove leading/trailing quotes if present
        cleaned = segment
        if cleaned.startswith('"') and cleaned.endswith('"'):
            cleaned = cleaned[1:-1].strip()
        elif cleaned.startswith('"'):
            cleaned = cleaned[1:].strip()
        elif cleaned.endswith('"'):
            cleaned = cleaned[:-1].strip()
        cleaned_segments.append(cleaned)
    
    suggested_segments = cleaned_segments
    print(f"Found {len(suggested_segments)} suggested segments")
    
    # Map suggested segments to timestamps
    print("Mapping segments to timestamps...")
    clip_suggestions = []
    
    for segment_idx, segment_text in enumerate(suggested_segments):
        print(f"\nProcessing segment {segment_idx+1}...")
        
        # Get the words from the segment
        segment_words = [word.lower() for word in segment_text.split()]
        
        if len(segment_words) < 3:
            print(f"Segment too short: '{segment_text}'")
            continue
            
        # Try to find the start position using trigrams first (most accurate)
        start_pos = find_position_with_ngrams(segment_words[:5], trigram_index, 3)
        
        # If trigram matching failed, try bigrams
        if start_pos is None:
            start_pos = find_position_with_ngrams(segment_words[:5], bigram_index, 2)
            
        # If bigram matching failed, try individual words
        if start_pos is None:
            # Try to find positions of first few words
            candidate_positions = []
            for word in segment_words[:3]:  # Try first 3 words
                if word in word_index and len(word) > 3:  # Only use substantial words
                    candidate_positions.extend(word_index[word])
                    
            if candidate_positions:
                # Take the earliest position that has several matches nearby
                candidate_positions.sort()
                start_pos = candidate_positions[0]
                print(f"Found approximate start with single word matching at position {start_pos}")
        
        # If all attempts to find start position failed
        if start_pos is None:
            print(f"Could not find start position for segment: '{segment_text[:50]}...'")
            continue
            
        # Get the start time from the position
        start_time = float(word_items[start_pos]['start_time'])
        print(f"Found start time: {start_time}s at position {start_pos}")
        
        # Try to find the end position using trigrams first (most accurate)
        end_words = segment_words[-5:] if len(segment_words) >= 5 else segment_words
        end_pos = find_position_with_ngrams(end_words, trigram_index, 3, find_last=True)
        
        # If trigram matching failed, try bigrams
        if end_pos is None:
            end_pos = find_position_with_ngrams(end_words, bigram_index, 2, find_last=True)
            
        # If bigram matching failed, try individual words
        if end_pos is None:
            # Try to find positions of last few words
            candidate_positions = []
            for word in reversed(end_words):  # Try last few words
                if word in word_index and len(word) > 3:  # Only use substantial words
                    candidate_positions.extend(word_index[word])
                    
            if candidate_positions:
                # Take the latest position
                candidate_positions.sort(reverse=True)
                end_pos = min(candidate_positions[0] + 1, len(word_items) - 1)  # +1 to include the last word
                print(f"Found approximate end with single word matching at position {end_pos}")
        
        # If we still couldn't find the end position, estimate based on start time and desired duration
        if end_pos is None:
            # Look for a word position approximately 45 seconds after start
            target_time = start_time + 45  # Target middle of min_duration and max_duration
            closest_pos = start_pos
            min_diff = float('inf')
            
            # Search for the closest word to our target time
            for i in range(start_pos + 1, len(word_items)):
                time_diff = abs(float(word_items[i]['start_time']) - target_time)
                if time_diff < min_diff:
                    min_diff = time_diff
                    closest_pos = i
                    
            end_pos = closest_pos
            print(f"Estimated end position based on desired duration: {end_pos}")
        
        # Get the end time from the position
        end_time = float(word_items[end_pos]['end_time'])
        print(f"Found end time: {end_time}s at position {end_pos}")
        
        # Ensure end time is after start time
        if end_time <= start_time:
            print(f"WARNING: End time ({end_time}s) is before or equal to start time ({start_time}s)")
            continue
            
        duration = end_time - start_time
        print(f"Clip duration: {duration:.2f}s")
        
        # Calculate a confidence score based on match quality and duration appropriateness
        confidence_score = 0.8  # Base confidence
        
        # Factor in duration appropriateness (without adjusting the duration)
        if duration < min_duration:
            confidence_score *= (duration / min_duration)
            print(f"Duration below minimum ({min_duration}s), reducing confidence")
        elif duration > max_duration:
            confidence_score *= (max_duration / duration)
            print(f"Duration above maximum ({max_duration}s), reducing confidence")
        
        # Extract the actual transcript text from word_items for better accuracy
        actual_transcript = " ".join([
            word_items[i]['alternatives'][0]['content']
            for i in range(start_pos, end_pos + 1)
        ])
        
        print(f"Adding clip: {start_time:.2f}s - {end_time:.2f}s (Duration: {duration:.2f}s)")
        clip_suggestions.append({
            'start_time': round(start_time, 2),
            'end_time': round(end_time, 2),
            'duration': round(duration, 2),
            'transcript': actual_transcript,
            'confidence': round(confidence_score, 2)
        })
    
    print(f"Finished extracting clips. Found {len(clip_suggestions)} valid clips.")
    return clip_suggestions

# Find position in transcript using n-grams and return position found
# words: List of words to match
# ngram_index: Index of n-grams mapping to positions
# n: Size of n-gram (2 for bigrams, 3 for trigrams)
# find_last: Whether to find the last occurrence (for end position)
def find_position_with_ngrams(words, ngram_index, n, find_last=False):
    if len(words) < n:
        return None
        
    positions = []
    
    # Try each possible n-gram from the words
    for i in range(len(words) - n + 1):
        ngram = tuple(words[i:i+n])
        if ngram in ngram_index:
            # Found a match
            if find_last:
                # For end position, take the last occurrence
                positions.extend(ngram_index[ngram])
            else:
                # For start position, prefer earlier occurrences
                positions.extend(ngram_index[ngram])
    
    if positions:
        if find_last:
            # For end position, take the last occurrence plus offset to include all matched words
            return max(positions) + (n - 1)  # Add offset for n-gram length
        else:
            # For start position, take the earliest occurrence
            return min(positions)
    
    return None

# Example usage
if __name__ == "__main__":
    # Load the transcription JSON
    try:
        with open('transcripts\segment_000_20250413210526.json', 'r') as file:
            talk_about_life = json.load(file)
            
        # Run the extraction
        result = extract_engaging_clips_ollama(transcript_json=talk_about_life)
        print("\nFinal result:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")