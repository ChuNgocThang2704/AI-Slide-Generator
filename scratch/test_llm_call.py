import httpx
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = 'http://194.228.55.129:37451/v1/chat/completions'
system_msg = (
    '/nothink\n'
    'You are an expert content writer and researcher.\n\n'
    'TASK:\n'
    'Write a detailed, comprehensive document in the same language as the user\'s prompt (usually Vietnamese or English) '
    'based on the prompt. This document will be used to generate a presentation slide deck.\n\n'
    'REQUIREMENTS:\n'
    '- Write in-depth content with concrete facts, details, explanations, and structure.\n'
    '- Divide the content into logical sections using \'##\' followed by the section title (e.g., \'## 1. Giới thiệu\').\n'
    '- For each section, write detailed paragraphs explaining the concepts, why/how, impacts, and examples. Do not write short placeholders.\n'
    '- If the user\'s prompt includes an outline or list of slides (e.g., Slide 1: ..., Slide 2: ...), you MUST follow this structure. For each slide in the outline, create a corresponding section \'## Slide Title\' and write a detailed paragraph of content (at least 80-150 words of rich information) explaining that slide\'s topic, so that the slide generator has actual content to extract bullets from.\n'
    '- Generate enough sections and detail to cover roughly 10 slides.\n'
    '- Write in a formal, informative, and engaging tone.\n'
    '- DO NOT output slide JSON or code blocks. Output ONLY raw text/markdown content.'
)

prompt_history = (
    'Lịch sử\n'
    '"Trình bày nguyên nhân, diễn biến và kết quả của Chiến tranh thế giới thứ hai."\n'
    '"Giới thiệu các triều đại phong kiến Việt Nam qua dòng thời gian."\n'
    '"Phân tích tác động của Cách mạng Công nghiệp lần thứ nhất."\n'
    '"Lịch sử hình thành và phát triển của Internet."'
)

payload = {
    'model': 'Qwen3-8B',
    'messages': [
        {'role': 'system', 'content': system_msg},
        {'role': 'user', 'content': f'Prompt:\n{prompt_history}'}
    ],
    'temperature': 0.7,
    'top_p': 0.92,
    'max_tokens': 2000
}

try:
    resp = httpx.post(url, json=payload, timeout=60.0)
    resp.raise_for_status()
    data = resp.json()
    text = data['choices'][0]['message']['content']
    print('=== LLM Response ===')
    print(text)
except Exception as e:
    print('Error:', e)
