import json
from pathlib import Path

def run():
    log_path = Path(r"C:\Users\nguye\.gemini\antigravity-ide\brain\b4623a3b-c8de-4283-9e89-8bf6c30400eb\.system_generated\logs\transcript.jsonl")
    with open(log_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            try:
                data = json.loads(line)
            except Exception as e:
                print(f"Line {idx} invalid json: {e}")
                continue
            
            print(f"Step {idx}: type={data.get('type')}, status={data.get('status')}")
            content = data.get("content", "")
            print(f"  content preview: {repr(content[:150])}")
            if "tool_calls" in data:
                print(f"  tool_calls: {data['tool_calls']}")

if __name__ == '__main__':
    run()
