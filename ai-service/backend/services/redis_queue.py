"""Quản lý queue bất đồng bộ sử dụng Redis (async-safe)."""
import json
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path
import os

from filename_utils import pptx_path_for_task
from config import (
    FREE_IMAGE_LIMIT,
    IMAGE_GEN_API_BASE_URL,
    OUTPUT_DIR,
    PRO_IMAGE_LIMIT_MAX,
    ULTRA_IMAGE_LIMIT_MAX,
    FREE_SLIDE_LIMIT,
)


def _resolve_plan_image_limit(
    plan: Optional[str],
    slide_count: Optional[int],
    image_limit: Optional[int] = None,
) -> int:
    plan_norm = (plan or "pro").strip().lower()
    if plan_norm == "free":
        max_limit = max(0, int(FREE_IMAGE_LIMIT))
        ratio = 0.5
    elif plan_norm == "ultra":
        max_limit = max(0, int(ULTRA_IMAGE_LIMIT_MAX))
        ratio = 0.7
    else:
        max_limit = max(0, int(PRO_IMAGE_LIMIT_MAX))
        ratio = 0.5

    total = int(slide_count or 10)
    calculated_limit = max(1, round(total * ratio))

    requested = None
    if image_limit is not None:
        try:
            requested = int(image_limit)
        except Exception:
            requested = None

    if requested is not None:
        return max(0, min(requested, calculated_limit, max_limit))
    return max(0, min(calculated_limit, max_limit))


def exc_to_error_message(exc: BaseException) -> str:
    """Luôn trả chuỗi không rỗng — tránh UI hiện 'Unknown error' khi str(exc) == ''."""
    name = type(exc).__name__
    s = str(exc).strip()

    if name == "ReadTimeout":
        base = (
            "ReadTimeout: vLLM không kịp trả hết response (sinh slide/JSON lâu, queue server, hoặc mạng chậm). "
            "Đặt VLLM_TIMEOUT_SEC cao hơn (ví dụ 900), hoặc giảm tải GPU / max-num-seqs trên vLLM."
        )
        return f"{base} Chi tiết: {s}" if s else base

    if name in ("ConnectError", "LocalProtocolError"):
        return (
            f"Không kết nối được tới máy chủ LLM (vLLM). Kiểm tra: VLLM_API_BASE_URL / firewall / VPN / "
            f"máy chủ có chạy vLLM và mở port không. Chi tiết: {s or name}"
        )
    low = s.lower()
    if "connection attempts failed" in low or "connection refused" in low:
        return (
            "Không kết nối được tới máy chủ LLM (thường là vLLM). "
            "Kiểm tra biến VLLM_API_BASE_URL, ping/telnet tới host:port, VPN/firewall, và xem tiến trình "
            f"`vllm serve` còn chạy. Chi tiết: {s}"
        )

    if s:
        return s
    return f"{name} (no message)"


# TTL mặc định: 4 giờ — đủ cho cả task lớn (nhiều slide + ảnh SDXL).
_TASK_TTL = 14_400


class RedisQueue:
    """Quản lý task queue với Redis (async-safe).

    Kết nối được kiểm tra đồng bộ khi khởi tạo để phát hiện sớm Redis không
    sẵn sàng.  Mọi thao tác I/O với Redis đều dùng redis.asyncio để không
    chặn event loop của FastAPI/Uvicorn.
    """

    WORKER_HEARTBEAT_KEY = "worker:heartbeat"
    WORKER_HEARTBEAT_TTL = 15

    def __init__(self, redis_url: str = None):
        if redis_url is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        self.redis_client = None  # redis.asyncio client, None nếu không có Redis
        self.memory_queue: Dict[str, Any] = {}
        self.memory_status: Dict[str, Any] = {}

        # Kiểm tra nhanh bằng sync redis (chỉ để phát hiện Redis có sẵn không)
        try:
            # pyrefly: ignore [missing-import]
            import redis as _redis_sync
            _sc = _redis_sync.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            _sc.ping()
            _sc.close()

            # Redis OK — tạo async client cho mọi thao tác thực tế
            # pyrefly: ignore [missing-import]
            import redis.asyncio as aioredis
            self.redis_client = aioredis.from_url(redis_url, decode_responses=True)
        except Exception as e:
            print(f"Warning: Redis not available: {e}")
            print("Using in-memory queue instead")

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def add_task(self, task_id: str, task_data: Dict[str, Any]):
        """Thêm task vào queue."""
        if self.redis_client:
            task_key = f"task:{task_id}"
            status_key = f"status:{task_id}"

            await self.redis_client.setex(task_key, _TASK_TTL, json.dumps(task_data))
            await self.redis_client.setex(
                status_key, _TASK_TTL,
                json.dumps({"status": "pending", "progress": 0})
            )
            # lpush → BLPOP sẽ lấy từ đuôi (rpop) — dùng nhất quán
            await self.redis_client.lpush("task_queue", task_id)
        else:
            self.memory_queue[task_id] = task_data
            self.memory_status[task_id] = {"status": "pending", "progress": 0}

    async def mark_worker_alive(self):
        """Ghi nhận worker đang hoạt động để API quyết định có nên dùng queue hay không."""
        if not self.redis_client:
            return
        await self.redis_client.setex(
            self.WORKER_HEARTBEAT_KEY,
            self.WORKER_HEARTBEAT_TTL,
            "1",
        )

    async def has_active_worker(self) -> bool:
        """Kiểm tra có worker Redis đang sống gần đây hay không."""
        if not self.redis_client:
            return False
        return bool(await self.redis_client.exists(self.WORKER_HEARTBEAT_KEY))

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Lấy trạng thái task."""
        if self.redis_client:
            status_key = f"status:{task_id}"
            status_json = await self.redis_client.get(status_key)
            if status_json:
                return json.loads(status_json)
            return {"status": "not_found", "progress": 0}
        return self.memory_status.get(task_id, {"status": "not_found", "progress": 0})

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: int = 0,
        result: Optional[Dict[str, Any]] = None,
    ):
        """Cập nhật trạng thái task."""
        status_data: Dict[str, Any] = {"status": status, "progress": progress}
        if result:
            status_data["result"] = result

        if self.redis_client:
            status_key = f"status:{task_id}"
            await self.redis_client.setex(status_key, _TASK_TTL, json.dumps(status_data))
        else:
            self.memory_status[task_id] = status_data

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Đánh dấu task bị hủy; loại khỏi queue nếu còn pending."""
        current = await self.get_task_status(task_id)
        current_status = current.get("status")

        if current_status in {"completed", "error", "cancelled", "not_found"}:
            return current

        if self.redis_client:
            await self.redis_client.lrem("task_queue", 0, task_id)
        else:
            self.memory_queue.pop(task_id, None)

        await self.update_task_status(
            task_id,
            "cancelled",
            progress=current.get("progress", 0),
            result={"message": "Task cancelled by user"},
        )
        return await self.get_task_status(task_id)

    async def is_task_cancelled(self, task_id: str) -> bool:
        status = await self.get_task_status(task_id)
        return status.get("status") == "cancelled"

    async def blpop_task(self, timeout: int = 10) -> Optional[str]:
        """Blocking pop — trả task_id hoặc None nếu hết timeout.

        Chỉ dùng được khi có Redis.  Worker gọi hàm này thay vì rpop+sleep.
        """
        if not self.redis_client:
            return None
        result = await self.redis_client.blpop("task_queue", timeout=timeout)
        if result is None:
            return None
        # result = (key_bytes, task_id)
        return result[1]

    # ------------------------------------------------------------------
    # Task processing
    # ------------------------------------------------------------------

    async def process_task(self, task_id: str):
        """Dispatcher — phân loại action và gọi handler tương ứng."""
        try:
            if self.redis_client:
                task_key = f"task:{task_id}"
                task_json = await self.redis_client.get(task_key)
                if not task_json:
                    print(f"[queue] Task {task_id} not found in Redis (expired?)")
                    return
                task_data = json.loads(task_json)
            else:
                task_data = self.memory_queue.get(task_id)
                if not task_data:
                    return

            if await self.is_task_cancelled(task_id):
                return

            action = task_data.get("action")
            if action == "generate_slide_full":
                await self._process_slide_full(task_id, task_data)
            elif action == "generate_slide_with_images":
                await self._process_slide_with_images(task_id, task_data)
            else:
                print(f"[queue] Unknown action '{action}' for task {task_id}")
                await self.update_task_status(
                    task_id, "error", progress=0,
                    result={"error": f"Unknown action: {action}"},
                )
        except Exception as e:
            await self.update_task_status(
                task_id, "error", progress=0,
                result={"error": exc_to_error_message(e)},
            )

    async def _process_slide_full(self, task_id: str, task_data: Dict[str, Any]):
        """Xử lý tạo slide full: extract → text quality → chart/table → (ảnh) → PPTX."""
        from services.content_extractor import ContentExtractor, TaskCancelledError
        from services.slide_generator import SlideGenerator
        from config import LLM_MODEL

        try:
            await self.update_task_status(task_id, "processing", progress=10)

            raw_content = task_data.get("raw_content")
            plan_norm = (task_data.get("plan") or "pro").strip().lower()
            free_mode = plan_norm == "free"

            slide_count_raw = task_data.get("slide_count")
            slide_count_int = None
            if slide_count_raw is not None:
                try:
                    slide_count_int = int(slide_count_raw)
                except Exception:
                    slide_count_int = None

            target_slides_override = FREE_SLIDE_LIMIT if free_mode else (
                slide_count_int if (slide_count_int and slide_count_int > 0) else None
            )
            force_exact_slide_count = bool(free_mode or (target_slides_override is not None))
            resolved_image_limit = _resolve_plan_image_limit(
                plan_norm,
                target_slides_override,
                task_data.get("image_limit"),
            )

            # ── Extract & structure ───────────────────────────────────
            await self.update_task_status(task_id, "processing", progress=20)
            print(f"[worker] Task {task_id}: extract_and_structure (model={LLM_MODEL})...")
            content_extractor = ContentExtractor(model_name=LLM_MODEL)

            async def on_chunk(done: int, total: int):
                if total <= 0:
                    return
                progress = 20 + int(35 * done / total)  # 20 → 55
                await self.update_task_status(
                    task_id, "processing", progress=progress,
                    result={"chunks": {"done": done, "total": total}},
                )

            async def should_stop() -> bool:
                return await self.is_task_cancelled(task_id)

            structured_content = await content_extractor.extract_and_structure(
                raw_content,
                progress_cb=on_chunk,
                should_stop=should_stop,
                target_slides_override=target_slides_override,
                force_exact_slide_count=force_exact_slide_count,
            )

            # ── Text quality pass ─────────────────────────────────────
            from services.slide_text_quality import improve_slide_text_quality
            structured_content = await improve_slide_text_quality(
                content_extractor,
                structured_content,
                task_id=task_id,
                max_refines=8,
            )

            if await self.is_task_cancelled(task_id):
                return

            # ── Chart & Table specs ───────────────────────────────────
            await self.update_task_status(task_id, "processing", progress=58)
            from services.slide_charts import build_chart_specs_for_slides
            from services.slide_tables import build_table_specs_for_slides

            table_specs = await build_table_specs_for_slides(
                content_extractor, structured_content,
                task_id=task_id, should_stop=should_stop,
                raw_content=raw_content or "",
            )
            chart_specs = await build_chart_specs_for_slides(
                content_extractor, structured_content,
                task_id=task_id, should_stop=should_stop,
                table_indices=set(table_specs.keys()),
                raw_content=raw_content or "",
            )

            # ── Image generation (tuỳ chọn) ───────────────────────────
            want_img = str(task_data.get("generate_images") or "").strip().lower() in (
                "1", "true", "yes", "on",
            ) and bool((IMAGE_GEN_API_BASE_URL or "").strip())

            image_paths = None
            if want_img:
                print(f"[worker] Task {task_id}: sinh anh ({IMAGE_GEN_API_BASE_URL})...")
                await self.update_task_status(
                    task_id, "processing", progress=68,
                    result={"images": {"done": 0, "total": 0}},
                )
                from services.images import build_image_paths_for_slides

                async def on_image_progress(done: int, total: int):
                    # Map 68%→79% theo từng slide ảnh hoàn thành
                    pct = 68 + int(11 * done / total) if total > 0 else 68
                    await self.update_task_status(
                        task_id, "processing", progress=pct,
                        result={"images": {"done": done, "total": total}},
                    )

                try:
                    image_paths = await build_image_paths_for_slides(
                        content_extractor, structured_content, task_id,
                        chart_specs=chart_specs, table_specs=table_specs,
                        image_limit=resolved_image_limit,
                        should_stop=should_stop,
                        progress_cb=on_image_progress,
                        plan=plan_norm,
                    )
                except Exception as image_error:
                    print(
                        f"[worker] Task {task_id}: image generation failed, continue without images: {image_error!r}"
                    )
                    image_paths = None

            if await self.is_task_cancelled(task_id):
                return

            # ── Generate PPTX ─────────────────────────────────────────
            await self.update_task_status(task_id, "processing", progress=80)
            slide_generator = SlideGenerator()
            st_raw = task_data.get("slide_theme")
            slide_preset = SlideGenerator.normalize_slide_preset(st_raw) or "modern"
            output_dir = Path(task_data.get("output_dir") or OUTPUT_DIR)
            output_path = pptx_path_for_task(
                output_dir, structured_content.get("title", ""), task_id
            )
            await slide_generator.create_slide(
                structured_content,
                output_path,
                generate_images=bool(image_paths),
                image_paths=image_paths,
                chart_specs=chart_specs,
                table_specs=table_specs,
                preset=slide_preset,
            )

            await self.update_task_status(
                task_id, "completed", progress=100,
                result={
                    "download_url": f"/outputs/{output_path.name}",
                    "view_url": f"/api/view-slide/{task_id}",
                },
            )
            print(f"[worker] Task {task_id}: done -> {output_path.name}")

        except TaskCancelledError:
            await self.update_task_status(
                task_id, "cancelled", progress=0,
                result={"message": "Task cancelled by user"},
            )
        except Exception as e:
            print(f"[worker] Task {task_id} error: {e}")
            await self.update_task_status(
                task_id, "error", progress=0,
                result={"error": exc_to_error_message(e)},
            )

    async def _process_slide_with_images(self, task_id: str, task_data: Dict[str, Any]):
        """Tạo PPTX từ nội dung đã được structure sẵn (không cần extract)."""
        from services.slide_generator import SlideGenerator

        try:
            await self.update_task_status(task_id, "processing", progress=30)

            content = task_data.get("content")
            if not content:
                raise ValueError("task_data missing 'content'")

            output_dir = Path(task_data.get("output_dir") or OUTPUT_DIR)
            title = content.get("title", "") if isinstance(content, dict) else ""
            output_path = pptx_path_for_task(output_dir, title, task_id)

            st_raw = task_data.get("slide_theme")
            slide_preset = SlideGenerator.normalize_slide_preset(st_raw) or "modern"

            await self.update_task_status(task_id, "processing", progress=70)
            slide_generator = SlideGenerator()
            await slide_generator.create_slide(
                content,
                output_path,
                generate_images=False,
                image_paths=None,
                preset=slide_preset,
            )

            await self.update_task_status(
                task_id, "completed", progress=100,
                result={
                    "download_url": f"/outputs/{output_path.name}",
                    "view_url": f"/api/view-slide/{task_id}",
                },
            )
            print(f"[worker] Task {task_id}: done (with_images path) -> {output_path.name}")

        except Exception as e:
            print(f"[worker] Task {task_id} error: {e}")
            await self.update_task_status(
                task_id, "error", progress=0,
                result={"error": exc_to_error_message(e)},
            )
