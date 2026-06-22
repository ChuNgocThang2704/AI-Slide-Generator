async def build_image_paths_for_slides(*args, **kwargs):
    from .pipeline import build_image_paths_for_slides as _impl
    return await _impl(*args, **kwargs)

__all__ = ['build_image_paths_for_slides']

