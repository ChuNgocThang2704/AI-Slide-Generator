import asyncio
import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')

from services.content.extractor import ContentExtractor

async def main():
    extractor = ContentExtractor(model_name="Qwen3-8B")
    
    # We want to test what happens in the exact same conditions as the worker:
    # 1. Start with vllm_available = True (but it will fail because the IP is offline)
    # 2. Use the exact raw content from the user
    # 3. Request 10 slides
    
    raw_content = (
        "Lịch sử\n"
        '"Trình bày nguyên nhân, diễn biến và kết quả của Chiến tranh thế giới thứ hai."\n'
        '"Giới thiệu các triều đại phong kiến Việt Nam qua dòng thời gian."\n'
        '"Phân tích tác động của Cách mạng Công nghiệp lần thứ nhất."\n'
        '"Lịch sử hình thành và phát triển của Internet."'
    )
    
    print("Running extract_and_structure...")
    try:
        structured_content = await extractor.extract_and_structure(
            raw_content,
            target_slides_override=10,
            force_exact_slide_count=True
        )
        print("\n--- STRUCTURED CONTENT ---")
        print(json.dumps(structured_content, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Error during extract_and_structure:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
