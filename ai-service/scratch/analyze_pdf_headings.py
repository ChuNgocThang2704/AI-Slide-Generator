import asyncio
import sys
from services.content.extractor import ContentExtractor

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    extractor = ContentExtractor(model_name="Qwen3-8B")
    
    # Read the extracted PDF text
    with open(r"e:\DemoDoan\scratch\extracted_pdf_text.txt", "r", encoding="utf-8") as f:
        content = f.read()
        
    print(f"Total content length: {len(content)} chars.")
    
    # Split by headings
    chunks = extractor._split_by_headings(content)
    print(f"Split by headings returned {len(chunks)} chunks.")
    
    for i, c in enumerate(chunks):
        print(f"\n--- Chunk {i+1} (length: {len(c)}) ---")
        print(c[:400] + ("..." if len(c) > 400 else ""))

if __name__ == "__main__":
    asyncio.run(main())
