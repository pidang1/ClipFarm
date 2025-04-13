import json

# Cherry pick the best segments from the transcribed video and return the timestamps and text for each segment

# fetch the json file from the transcripts folder
tedx_talk_digital_age = None
with open('transcripts/A one minute TEDx Talk for the digital age _ Woody Roseland _ TEDxMileHigh_20250413194910.json', 'r') as file:
    tedx_talk_digital_age = json.load(file)
    
print(tedx_talk_digital_age['results']['transcripts'][0]['transcript'])