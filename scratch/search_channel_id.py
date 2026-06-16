import re
import os

transcript_path = r"C:\Users\user\.gemini\antigravity\brain\433d8db6-7739-409c-8085-e8f4f0ce53d1\.system_generated\logs\transcript.jsonl"

if not os.path.exists(transcript_path):
    print("Transcript not found")
    exit()

with open(transcript_path, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        # Find any occurrence of -100 followed by 8 to 12 digits
        matches = re.findall(r'-100\d{9,12}', line)
        if matches:
            print(f"Line {line_num}: {matches}")
            # print surrounding content
            idx = line.find(matches[0])
            start = max(0, idx - 100)
            end = min(len(line), idx + 150)
            print("Context:", line[start:end])
