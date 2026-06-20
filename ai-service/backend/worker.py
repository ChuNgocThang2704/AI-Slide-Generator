"""Worker xử lý task queue bất đồng bộ.

Chạy độc lập song song với main API:
    python worker.py

Worker dùng Redis BLPOP (blocking pop) thay vì polling để không tốn CPU khi
queue trống.  Graceful shutdown khi nhận Ctrl+C hoặc SIGTERM (Unix).
"""
import asyncio
import signal
import sys

# Configure console encoding to UTF-8 to prevent charmap/UnicodeEncodeError on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


from services.redis_queue import RedisQueue


def _print_worker_banner():
    try:
        from config import (
            LLM_MODEL,
            VLLM_API_BASE_URL,
            REDIS_URL,
            REDIS_OFFLOAD_WHEN_WORKER_ALIVE,
            IMAGE_GEN_API_BASE_URL,
        )
        print("=" * 60)
        print("  Slide queue worker")
        print(f"  REDIS_URL            : {REDIS_URL}")
        print(f"  LLM_MODEL            : {LLM_MODEL}")
        print(f"  VLLM_API_BASE_URL    : {VLLM_API_BASE_URL or '(empty)'}")
        print(f"  IMAGE_GEN_API_BASE_URL: {IMAGE_GEN_API_BASE_URL or '(empty)'}")
        print(f"  REDIS_OFFLOAD_ACTIVE : {REDIS_OFFLOAD_WHEN_WORKER_ALIVE}")
        print("=" * 60)
    except Exception as e:
        print(f"(Could not load config banner: {e})")


class TaskWorker:
    """Worker lấy task từ Redis queue và xử lý bất đồng bộ."""

    # Thời gian BLPOP block chờ task (giây).  Sau timeout worker cập nhật
    # heartbeat rồi block tiếp — không tốn CPU khi queue trống.
    _BLPOP_TIMEOUT = 10

    def __init__(self):
        self.redis_queue = RedisQueue()
        self._stop_event = asyncio.Event()

    async def start(self):
        """Vòng lặp chính của worker."""
        _print_worker_banner()

        if not self.redis_queue.redis_client:
            print("[worker] Redis unavailable — worker requires Redis to operate.")
            print("[worker] Start Redis then restart the worker.")
            return

        print(f"[worker] Ready. Blocking on task_queue (BLPOP timeout={self._BLPOP_TIMEOUT}s)...")

        while not self._stop_event.is_set():
            try:
                # Heartbeat trước mỗi lần block để API biết worker còn sống
                await self.redis_queue.mark_worker_alive()

                task_id = await self.redis_queue.blpop_task(timeout=self._BLPOP_TIMEOUT)

                if task_id is None:
                    # Timeout bình thường — lặp lại để cập nhật heartbeat
                    continue

                print(f"[worker] Dequeued task: {task_id}")
                # Xử lý task — lỗi được bắt bên trong process_task
                await self.redis_queue.process_task(task_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[worker] Unexpected error in main loop: {e}")
                # Chờ ngắn trước khi thử lại để tránh spam log khi Redis lỗi
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=5.0,
                    )
                except asyncio.TimeoutError:
                    pass

        print("[worker] Loop exited.")

    def stop(self):
        """Ra hiệu cho vòng lặp dừng sau lần xử lý task hiện tại xong."""
        self._stop_event.set()


async def main():
    worker = TaskWorker()

    loop = asyncio.get_running_loop()

    def _handle_signal():
        print("\n[worker] Shutdown signal received — stopping after current task...")
        worker.stop()

    # Đăng ký signal handler (Unix: SIGINT + SIGTERM; Windows: chỉ qua KeyboardInterrupt)
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _handle_signal)

    try:
        await worker.start()
    except KeyboardInterrupt:
        # Windows fallback
        print("\n[worker] KeyboardInterrupt — stopping...")
        worker.stop()
    finally:
        print("[worker] Stopped.")


if __name__ == "__main__":
    asyncio.run(main())
