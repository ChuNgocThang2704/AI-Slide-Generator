import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Files to analyze and repair
FILES_TO_FIX = [
    r"backend/services/content/slide_normalizer.py",
    r"backend/services/content/chunking.py",
    r"backend/services/content/extractor.py",
    r"backend/services/content/image_extraction.py",
    r"backend/services/content/image_prompting.py",
    r"backend/services/content/input_processing.py",
    r"backend/services/content/slide_pipeline.py",
]

# CP1252 to byte mapping
CP1252_MAP = {
    '\u20ac': 0x80, '\u201a': 0x82, '\u0192': 0x83, '\u201e': 0x84, '\u2026': 0x85,
    '\u2020': 0x86, '\u2021': 0x87, '\u02c6': 0x88, '\u2030': 0x89, '\u0160': 0x8a,
    '\u2039': 0x8b, '\u0152': 0x8c, '\u017d': 0x8e, '\u2018': 0x91, '\u2019': 0x92,
    '\u201c': 0x93, '\u201d': 0x94, '\u2022': 0x95, '\u2013': 0x96, '\u2014': 0x97,
    '\u02dc': 0x98, '\u2122': 0x99, '\u0161': 0x9a, '\u203a': 0x9b, '\u0153': 0x9c,
    '\u017e': 0x9e, '\u0178': 0x9f
}

def to_cp1252_byte(char):
    # ASCII characters (< 128) are separators, returning None splits the chunk
    if ord(char) < 128:
        return None
    if char in CP1252_MAP:
        return CP1252_MAP[char]
    if 128 <= ord(char) <= 255:
        return ord(char)
    return None

def fix_mojibake(text):
    chunks = []
    current_chunk = bytearray()
    
    for char in text:
        b = to_cp1252_byte(char)
        if b is not None:
            current_chunk.append(b)
        else:
            if current_chunk:
                try:
                    decoded = current_chunk.decode('utf-8')
                    chunks.append(decoded)
                except Exception:
                    chunks.append(current_chunk.decode('cp1252', errors='replace'))
                current_chunk = bytearray()
            chunks.append(char)
            
    if current_chunk:
        try:
            decoded = current_chunk.decode('utf-8')
            chunks.append(decoded)
        except Exception:
            chunks.append(current_chunk.decode('cp1252', errors='replace'))
            
    fixed = "".join(chunks)
    
    # Specific cleanup replacements for corrupted words
    replacements = {
        "gá» i": "gọi",
        "gá»  i": "gọi",
        "nhiá» u": "nhiều",
        "Ä‘á»  ": "đề ",
        "Ä‘á» ": "đề",
        "tiáº¿p": "tiếp",
        "trá»‘ng": "trống",
    }
    for k, v in replacements.items():
        fixed = fixed.replace(k, v)
        
    return fixed

def process_file(filepath, dry_run=True):
    full_path = os.path.join(r"e:\DemoDoan", filepath)
    if not os.path.exists(full_path):
        print(f"File not found: {filepath}")
        return

    print(f"\nProcessing {filepath}...")
    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    lines = content.splitlines()
    changed_count = 0
    new_lines = []
    
    for i, line in enumerate(lines, 1):
        fixed_line = fix_mojibake(line)
        if fixed_line != line:
            print(f"  L{i}:")
            print(f"    - {line.strip()}")
            print(f"    + {fixed_line.strip()}")
            changed_count += 1
            new_lines.append(fixed_line)
        else:
            new_lines.append(line)

    if not dry_run and changed_count > 0:
        new_content = "\n".join(new_lines) + ("\n" if content.endswith("\n") else "")
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Saved {changed_count} fixes to {filepath}")
    else:
        print(f"Dry run: {changed_count} changes detected in {filepath}")

if __name__ == '__main__':
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == '--write':
        dry_run = False
    
    for f in FILES_TO_FIX:
        process_file(f, dry_run)
