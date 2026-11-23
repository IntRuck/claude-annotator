from functools import lru_cache

from annotator.config.settings import get_settings
from annotator.storage.storage_service import StorageService


@lru_cache
def get_storage() -> StorageService:
    """FastAPI dependency: one Storage client for the process, built from settings."""
    settings = get_settings()
    return StorageService(settings.supabase_url, settings.supabase_service_role_key)
