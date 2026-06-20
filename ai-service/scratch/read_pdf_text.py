import asyncio
import sys
from services.file_processor import FileProcessor

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    processor = FileProcessor()
    pdf_path = r"e:\DemoDoan\TỔNG HỢP NHÓM 2 - LỊCH SỬ ĐẢNG.pdf"
    
    print(f"Extracting text from PDF: {pdf_path}...")
    try:
        content = await processor.process_file(pdf_path)
        print(f"Success! Extracted {len(content)} characters.")
        
        # Save to scratch folder
        out_path = r"e:\DemoDoan\scratch\extracted_pdf_text.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Extracted text saved to: {out_path}")
        
        # Print first 2000 characters
        print("\n--- FIRST 2000 CHARS OF EXTRACTED TEXT ---")
        print(content[:2000])
        
    except Exception as e:
        print("Error processing PDF:", e)

if __name__ == "__main__":
    asyncio.run(main())
