"""Điểm bắt đầu tương thích cho việc trích xuất nội dung.

Triển khai hoạt động hiện tại nằm trong ``services.content``. Triển khai nguyên khối
cũ được lưu riêng biệt trong ``content_extractor_legacy.py`` chỉ nhằm mục đích
đối chiếu dự phòng khi cần thiết.
"""

from services.content.extractor import ContentExtractor, TaskCancelledError

__all__ = ["ContentExtractor", "TaskCancelledError"]
