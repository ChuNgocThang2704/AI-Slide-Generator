import asyncio
import os
import json
import sys
import redis.asyncio as aioredis

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    print(f"Connecting to Redis at {redis_url}...")
    client = aioredis.from_url(redis_url, decode_responses=True)
    
    # Let's find all keys starting with status: or task:
    keys = await client.keys("status:*")
    print("Found status keys:", keys)
    
    # Get the latest or specific key
    task_id = "3deb1b53-9d73-4e62-b392-2d92bc1f6f4b"
    task_key = f"task:{task_id}"
    status_key = f"status:{task_id}"
    
    task_val = await client.get(task_key)
    status_val = await client.get(status_key)
    
    print("\n--- TASK DATA ---")
    if task_val:
        print(json.dumps(json.loads(task_val), indent=2, ensure_ascii=False))
    else:
        print(f"No task data found for key {task_key}")
        
    print("\n--- STATUS/RESULT DATA ---")
    if status_val:
        status_data = json.loads(status_val)
        print(json.dumps(status_data, indent=2, ensure_ascii=False))
    else:
        print(f"No status data found for key {status_key}")
        
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
