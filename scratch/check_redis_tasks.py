import asyncio
import json
import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.append(str(backend_dir))

async def main():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    print(f"Connecting to Redis at {redis_url}...")
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(redis_url, decode_responses=True)
        keys = await client.keys("status:*")
        print(f"Found {len(keys)} task status keys:")
        for key in keys:
            val = await client.get(key)
            task_id = key.split(":", 1)[1]
            print(f"Task ID: {task_id}")
            print(f"  Status Data: {val}")
            
            # Get corresponding task data if available
            task_val = await client.get(f"task:{task_id}")
            if task_val:
                task_data = json.loads(task_val)
                # print plan, generate_images, etc. (but truncate raw_content)
                if "raw_content" in task_data:
                    task_data["raw_content"] = task_data["raw_content"][:60] + "..."
                print(f"  Task Data: {json.dumps(task_data)}")
        await client.close()
    except Exception as e:
        print("Error connecting to Redis:", e)

if __name__ == "__main__":
    asyncio.run(main())
