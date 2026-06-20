import asyncio
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

# Import ContentExtractor
from services.content.extractor import ContentExtractor

async def main():
    extractor = ContentExtractor(model_name="Qwen3-8B")
    extractor.vllm_available = False # Force Gemini
    
    prompt = """Lịch sử\n"Trình bày nguyên nhân, diễn biến và kết quả của Chiến tranh thế giới thứ hai."\n"Giới thiệu các triều đại phong kiến Việt Nam qua dòng thời gian."\n"Phân tích tác động của Cách mạng Công nghiệp lần thứ nhất."\n"Lịch sử hình thành và phát triển của Internet." """
    
    target_slides = 10
    
    print("Sending prompt to LLM...")
    response = await extractor._generate_content_from_prompt(prompt, target_slides)
    print("\n--- LLM RESPONSE ---")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
