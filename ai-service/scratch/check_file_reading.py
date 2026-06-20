import os
from pathlib import Path

def run():
    p = Path(r"C:\Users\nguye\.gemini\antigravity-ide\brain\b4623a3b-c8de-4283-9e89-8bf6c30400eb\.system_generated\logs\transcript.jsonl")
    print("Path exists:", p.exists())
    if p.exists():
        print("File size:", p.stat().st_size)
        try:
            with open(p, "r", encoding="utf-8") as f:
                content = f.read(100)
                print("First 100 chars:", repr(content))
        except Exception as e:
            print("Error reading:", e)

if __name__ == '__main__':
    run()
