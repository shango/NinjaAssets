class NinjaAssetsError(Exception):
    """Base exception"""
    pass


class SidecarError(NinjaAssetsError):
    """E001: Error reading/writing sidecar files"""
    code = "E001"


class ConflictError(NinjaAssetsError):
    """E002: Optimistic locking conflict"""
    code = "E002"


class ChangelogError(NinjaAssetsError):
    """E003: Error with changelog operations"""
    code = "E003"


class SyncError(NinjaAssetsError):
    """E004: Sync engine error"""
    code = "E004"


class ExportError(NinjaAssetsError):
    """E005: Asset export error"""
    code = "E005"


class GDriveOfflineError(NinjaAssetsError):
    """E006: Google Drive not accessible"""
    code = "E006"


class CacheError(NinjaAssetsError):
    """E007: SQLite cache error"""
    code = "E007"
