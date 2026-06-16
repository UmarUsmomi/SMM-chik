import json
import os

transcript_path = r"C:\Users\user\.gemini\antigravity\brain\433d8db6-7739-409c-8085-e8f4f0ce53d1\.system_generated\logs\transcript.jsonl"

if not os.path.exists(transcript_path):
    print("Transcript not found at:", transcript_path)
    exit()

print("Searching transcript...")
found_count = 0
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        if "TELEGRAM_CHANNEL_ID" in line or "-100" in line:
            # print first 500 chars of matching line to avoid giant output
            print(line[:300] + "...")
            found_count += 1
            if found_count > 20:
                print("Too many matches, truncating...")
                break

print(f"Done, found {found_count} matches.")
