import sys
import os
import time
import asyncio
import json
import httpx

# Thiết lập UTF-8 cho console
sys.stdout.reconfigure(encoding='utf-8')

API_BASE = "http://20.196.113.144:8000"
FILE_PATH = r"e:\DemoDoan\BÁO CÁO CSDLPT - NHÓM 17.pdf"
INSTRUCTION = "Làm slide chi tiết bám sát nội dung phân mảnh trong file."

async def poll_task(client: httpx.AsyncClient, task_id: str) -> bool:
    print(f"\nPolling task {task_id} status...")
    start_time = time.time()
    while True:
        try:
            status_resp = await client.get(f"{API_BASE}/api/status/{task_id}")
            if status_resp.status_code != 200:
                print(f"Error checking status: {status_resp.status_code}")
                await asyncio.sleep(4)
                continue
            
            status_data = status_resp.json()
            current_status = status_data.get("status")
            progress = status_data.get("progress", 0)
            result = status_data.get("result", {})
            
            print(f"[{int(time.time() - start_time)}s] Status: {current_status} | Progress: {progress}%")
            
            if current_status == "completed":
                print("\n🎉 Task completed! Slide Spec JSON Result:")
                # In đẹp JSON kết quả slide
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return True
            elif current_status == "error":
                print(f"❌ Task failed: {result}")
                return False
            elif current_status == "cancelled":
                print("⏹️ Task was cancelled.")
                return False
        except Exception as e:
            print(f"Polling exception: {e}")
        await asyncio.sleep(4)

async def test_case_file(client: httpx.AsyncClient):
    print("\n==================================================")
    print("TEST CASE 1: FILE PDF + PROMPT INSTRUCTION (JSON SPEC)")
    print("==================================================")
    if not os.path.exists(FILE_PATH):
        print(f"Error: File not found at {FILE_PATH}")
        return

    print(f"File: {os.path.basename(FILE_PATH)}")
    with open(FILE_PATH, "rb") as f:
        files = {"file": (os.path.basename(FILE_PATH), f, "application/pdf")}
        data = {
            "text": INSTRUCTION,
            "plan": "pro",
            "generate_images": "false"
        }
        
        print("Sending upload and spec generation request...")
        resp = await client.post(f"{API_BASE}/api/generate-slide-spec", data=data, files=files)
        if resp.status_code != 200:
            print(f"API Error: Status {resp.status_code}\n{resp.text}")
            return
            
        task_id = resp.json().get("task_id")
        print(f"Created Task ID: {task_id}")
        await poll_task(client, task_id)

async def test_case_text(client: httpx.AsyncClient):
    print("\n==================================================")
    print("TEST CASE 2: PLAIN TEXT PROMPT ONLY (5 SLIDES JSON SPEC)")
    print("==================================================")
    prompt = "Tạo 5 slide tiếng Việt giới thiệu về bãi đỗ xe thông minh sử dụng camera AI"
    data = {
        "text": prompt,
        "plan": "pro",
        "slide_count": "5",
        "generate_images": "false"
    }
    
    print(f"Prompt: '{prompt}'")
    resp = await client.post(f"{API_BASE}/api/generate-slide-spec", data=data)
    if resp.status_code != 200:
        print(f"API Error: Status {resp.status_code}\n{resp.text}")
        return
        
    task_id = resp.json().get("task_id")
    print(f"Created Task ID: {task_id}")
    await poll_task(client, task_id)

async def main():
    print(f"Testing deployed API at: {API_BASE}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        await test_case_text(client)
        await test_case_file(client)

if __name__ == "__main__":
    asyncio.run(main())


