import sys

sys.stdout.reconfigure(encoding='utf-8')

CP1252_MAP = {
    '\u20ac': 0x80, '\u201a': 0x82, '\u0192': 0x83, '\u201e': 0x84, '\u2026': 0x85,
    '\u2020': 0x86, '\u2021': 0x87, '\u02c6': 0x88, '\u2030': 0x89, '\u0160': 0x8a,
    '\u2039': 0x8b, '\u0152': 0x8c, '\u017d': 0x8e, '\u2018': 0x91, '\u2019': 0x92,
    '\u201c': 0x93, '\u201d': 0x94, '\u2022': 0x95, '\u2013': 0x96, '\u2014': 0x97,
    '\u02dc': 0x98, '\u2122': 0x99, '\u0161': 0x9a, '\u203a': 0x9b, '\u0153': 0x9c,
    '\u017e': 0x9e, '\u0178': 0x9f
}

def to_cp1252_byte(char):
    # ASCII characters (< 128) are separators, so we return None to split the chunk
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
            
    return "".join(chunks)

# Test cases
tests = [
    "Khi cÃ³ backend LLM, má»—i láº§n gá» i thÃ nh cÃ´ng vÃ  parse Ä‘Æ°á»£c JSON (Ollama/vLLM)",
    "tÄƒng done; total Æ°á»›c lÆ°á»£ng ban Ä‘áº§u vÃ  giÃ£n náº¿u pipeline gá» i nhiá» u láº§n hÆ¡n.",
    "                \"title\": \"TiÃªu Ä‘á»  chÃ­nh\",",
    "# 1b. Dedup slides có nội dung quá trùng (token overlap > 65%) â€”"
]

for t in tests:
    fixed = fix_mojibake(t)
    print(f"Original: {t}")
    print(f"Fixed:    {fixed}")
    print()
