import os
from pathlib import Path

def run():
    base = Path(r"C:\Users\nguye\.gemini\antigravity-ide\brain")
    if not base.exists():
        print(f"Base folder {base} does not exist.")
        return
        
    print("Folders under brain:")
    for f in base.iterdir():
        print(f.name)
        if f.is_dir():
            print("  subfolders:")
            for sf in f.glob("**/*"):
                if sf.is_file() and sf.suffix == ".jsonl":
                    print("    ", sf.relative_to(base))

if __name__ == '__main__':
    run()
