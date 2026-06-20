import asyncio
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

# Mock extractor to use the LLMClientMixin
from services.content.extractor import ContentExtractor

async def main():
    extractor = ContentExtractor(model_name="Qwen3-8B")
    
    # We will test plain text completion with Gemini/Vertex
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Output ONLY a short greeting in Vietnamese."},
        {"role": "user", "content": "Xin chào"}
    ]
    
    print("vLLM available:", extractor.vllm_available)
    print("Gemini available:", extractor.gemini_available)
    
    # Force vLLM to false to test Gemini/Vertex fallback
    extractor.vllm_available = False
    
    try:
        print("Calling Gemini completion...")
        resp = await extractor._llm_completion_plain_text(messages, max_tokens=100)
        print("Response:", repr(resp))
    except Exception as e:
        print("Error during LLM completion:", e)
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
