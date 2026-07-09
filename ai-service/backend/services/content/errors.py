"""Các ngoại lệ dùng chung cho quá trình trích xuất nội dung."""


class TaskCancelledError(Exception):
    """Ném ra khi tác vụ trích xuất đang chạy bị người dùng hủy."""
