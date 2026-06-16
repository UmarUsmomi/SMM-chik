import json
import os
import re

transcript_path = r"C:\Users\user\.gemini\antigravity\brain\001e8bf7-8d92-4ccb-8c4e-f4525685ed33\.system_generated\logs\transcript.jsonl"
out_path = r"d:\SMM\scratch\out.txt"

if not os.path.exists(transcript_path):
    print(f"Error: Transcript not found at {transcript_path}")
    exit(1)

turns_count = 0
tool_calls = []
errors = []
user_requests = []

with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            step = json.loads(line)
            stype = step.get("type", "")
            scontent = step.get("content", "")
            
            if stype == "USER_INPUT":
                turns_count += 1
                # Clean up USER_REQUEST tag
                clean_content = re.sub(r'<USER_REQUEST>|<\/USER_REQUEST>', '', scontent).strip()
                user_requests.append(clean_content)
                
            calls = step.get("tool_calls", [])
            for c in calls:
                tool_calls.append(c.get("name", ""))
                
            if step.get("status") == "ERROR":
                errors.append(scontent)
        except Exception as e:
            pass

report = []
report.append("=== COCHING AUDIT REPORT ===")
report.append(f"Total user requests: {turns_count}")
report.append(f"Total tool invocations: {len(tool_calls)}")
report.append(f"Unique tools used: {set(tool_calls)}")
report.append(f"Total step errors: {len(errors)}")

report.append("\n--- User Request Summary ---")
for idx, req in enumerate(user_requests):
    first_lines = [line.strip() for line in req.split("\n") if line.strip()]
    first_line = first_lines[0] if first_lines else ""
    if len(first_line) > 100:
        first_line = first_line[:100] + "..."
    report.append(f"{idx+1}. {first_line}")

# Write report in UTF-8
with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(report))

print("Audit report written to scratch/out.txt successfully.")
