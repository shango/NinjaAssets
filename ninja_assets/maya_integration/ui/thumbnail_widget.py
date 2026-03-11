"""Thumbnail grid widget with async image loading."""

import logging
from pathlib import Path
from typing import List, Optional

from ninja_assets.maya_integration.ui.qt_compat import (
    QFrame, QLabel, QVBoxLayout, QScrollArea, QWidget, QSizePolicy,
    QPixmap, QImage, QFont, QColor, Qt, Signal, QObject, QSize,
    QRunnable, QThreadPool, QMenu, QCursor, QApplication,
)
from ninja_assets.maya_integration.ui.flow_layout import FlowLayout
from ninja_assets.maya_integration.ui import STATUS_DISPLAY
from ninja_assets.core.models import Asset, AssetStatus

logger = logging.getLogger(__name__)


class _ThumbnailSignals(QObject):
    """Helper QObject for cross-thread signaling from QRunnable."""
    loaded = Signal(str, QImage)  # uuid, image


class ThumbnailLoader(QRunnable):
    """Load a thumbnail image from disk in a background thread."""

    def __init__(self, uuid, image_path, signals):
        super().__init__()
        self.uuid = uuid
        self.image_path = image_path
        self.signals = signals
        self.setAutoDelete(True)

    def run(self):
        try:
            image = QImage(str(self.image_path))
            if not image.isNull():
                self.signals.loaded.emit(self.uuid, image)
        except Exception:
            logger.debug("Failed to load thumbnail: %s", self.image_path)


class ThumbnailCard(QFrame):
    """A single asset thumbnail card in the grid."""

    asset_selected = Signal(str)
    asset_double_clicked = Signal(str)

    def __init__(self, asset, thumb_size=100, parent=None):
        super().__init__(parent)
        self.asset = asset
        self._thumb_size = thumb_size
        self._selected = False

        self.setFixedSize(thumb_size + 10, thumb_size + 40)
        self.setFrameShape(QFrame.Box)
        self.setLineWidth(1)
        self.setCursor(Qt.PointingHandCursor)
        self._update_border()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 2)
        layout.setSpacing(1)

        # Thumbnail image
        self.image_label = QLabel()
        self.image_label.setFixedSize(thumb_size, thumb_size)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #3a3a3a;")
        self.image_label.setText("?")
        layout.addWidget(self.image_label, alignment=Qt.AlignCenter)

        # Name label
        name_label = QLabel(self._truncate(asset.name, 14))
        name_label.setAlignment(Qt.AlignCenter)
        small_font = QFont()
        small_font.setPointSize(8)
        name_label.setFont(small_font)
        name_label.setToolTip(asset.name)
        layout.addWidget(name_label)

        # Version + status
        status_info = STATUS_DISPLAY.get(asset.status)
        if status_info:
            indicator_text = f"{status_info['symbol']} {status_info['text']}"
            indicator_color = status_info["color"]
        else:
            indicator_text = "\u25cf ?"
            indicator_color = "#999999"
        status_label = QLabel(f"v{asset.current_version}  {indicator_text}")
        status_label.setAlignment(Qt.AlignCenter)
        tiny_font = QFont()
        tiny_font.setPointSize(7)
        status_label.setFont(tiny_font)
        status_label.setStyleSheet(f"color: {indicator_color};")
        layout.addWidget(status_label)

    def set_pixmap(self, pixmap):
        """Set the thumbnail pixmap."""
        scaled = pixmap.scaled(
            self._thumb_size, self._thumb_size,
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.setText("")

    def set_selected(self, selected):
        self._selected = selected
        self._update_border()

    def _update_border(self):
        if self._selected:
            self.setStyleSheet("ThumbnailCard { border: 2px solid #3daee9; }")
        else:
            self.setStyleSheet("ThumbnailCard { border: 1px solid #555; }")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.asset_selected.emit(self.asset.uuid)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.asset_double_clicked.emit(self.asset.uuid)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        import_action = menu.addAction("Import")
        reference_action = menu.addAction("Reference")
        menu.addSeparator()
        open_folder_action = menu.addAction("Open Folder")
        copy_path_action = menu.addAction("Copy Path")

        action = menu.exec_(QCursor.pos())
        if action == import_action:
            self._do_import()
        elif action == reference_action:
            self._do_reference()
        elif action == open_folder_action:
            self._open_folder()
        elif action == copy_path_action:
            self._copy_path()

    def _do_import(self):
        try:
            from ninja_assets.maya_integration import commands
            commands.import_asset(self.asset)
        except Exception as e:
            logger.error("Import failed: %s", e)

    def _do_reference(self):
        try:
            from ninja_assets.maya_integration import commands
            commands.reference_asset(self.asset)
        except Exception as e:
            logger.error("Reference failed: %s", e)

    def _open_folder(self):
        from ninja_assets.maya_integration.utils.maya_utils import open_folder
        open_folder(self.asset.path)

    def _copy_path(self):
        from ninja_assets.maya_integration.utils.maya_utils import copy_to_clipboard
        copy_to_clipboard(self.asset.path)

    @staticmethod
    def _truncate(text, max_len):
        if len(text) > max_len:
            return text[: max_len - 1] + "\u2026"
        return text


class ThumbnailGrid(QScrollArea):
    """Scrollable grid of ThumbnailCard widgets using FlowLayout."""

    asset_selected = Signal(str)
    asset_double_clicked = Signal(str)

    def __init__(self, thumb_size=100, parent=None):
        super().__init__(parent)
        self._thumb_size = thumb_size
        self._cards = {}  # uuid -> ThumbnailCard
        self._selected_uuid = None

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._flow = FlowLayout(self._container, margin=8, h_spacing=6, v_spacing=6)
        self._container.setLayout(self._flow)
        self.setWidget(self._container)

        # Thread pool for async thumbnail loading
        self._thread_pool = QThreadPool.globalInstance()
        self._signals = _ThumbnailSignals()
        self._signals.loaded.connect(self._on_thumbnail_loaded)

    def set_assets(self, assets: List[Asset]):
        """Populate the grid with asset thumbnails."""
        self.clear()
        for asset in assets:
            card = ThumbnailCard(asset, self._thumb_size)
            card.asset_selected.connect(self._on_card_selected)
            card.asset_double_clicked.connect(self.asset_double_clicked.emit)
            self._flow.addWidget(card)
            self._cards[asset.uuid] = card

            # Queue async thumbnail loading
            if asset.thumbnail:
                thumb_path = Path(asset.path) / asset.thumbnail
                loader = ThumbnailLoader(asset.uuid, thumb_path, self._signals)
                self._thread_pool.start(loader)

    def clear(self):
        """Remove all cards from the grid."""
        self._selected_uuid = None
        self._cards.clear()
        while self._flow.count():
            item = self._flow.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def _on_card_selected(self, uuid):
        # Deselect previous
        if self._selected_uuid and self._selected_uuid in self._cards:
            self._cards[self._selected_uuid].set_selected(False)
        # Select new
        self._selected_uuid = uuid
        if uuid in self._cards:
            self._cards[uuid].set_selected(True)
        self.asset_selected.emit(uuid)

    def _on_thumbnail_loaded(self, uuid, image):
        """Called when a thumbnail finishes loading in the background."""
        if uuid in self._cards:
            pixmap = QPixmap.fromImage(image)
            self._cards[uuid].set_pixmap(pixmap)
