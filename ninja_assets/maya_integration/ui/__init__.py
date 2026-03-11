"""NinjaAssets Maya UI package - PySide2/PySide6 compatibility layer"""

from ninja_assets.core.models import AssetStatus

STATUS_DISPLAY = {
    AssetStatus.WIP: {"text": "WIP", "symbol": "\u25cf", "color": "#FFA500"},
    AssetStatus.REVIEW: {"text": "Review", "symbol": "\u25cf", "color": "#FFD700"},
    AssetStatus.APPROVED: {"text": "Approved", "symbol": "\u2713", "color": "#00CC00"},
}
