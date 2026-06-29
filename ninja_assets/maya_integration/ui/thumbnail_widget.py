"""Thumbnail grid widget with async image loading."""

import logging
from pathlib import Path
from typing import List

from ninja_assets.maya_integration.ui.qt_compat import (
    QFrame, QLabel, QVBoxLayout, QScrollArea, QWidget,
    QPixmap, QImage, QFont, Qt, Signal, QObject,
    QRunnable, QThreadPool, QMenu, QCursor,
)
from ninja_assets.maya_integration.ui.flow_layout import FlowLayout
from ninja_assets.core.models import Asset

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

    # Scale name character limit with card width
    _CHARS_PER_PX = 0.14  # ~18 chars at 128px

    def __init__(self, asset, thumb_size=128, parent=None):
        super().__init__(parent)
        self.asset = asset
        self._thumb_size = thumb_size
        self._selected = False

        card_w = thumb_size + 8
        card_h = thumb_size + 42
        self.setFixedSize(card_w, card_h)
        self.setFrameShape(QFrame.NoFrame)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("selected", False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 2)
        layout.setSpacing(2)

        # Thumbnail image
        self.image_label = QLabel()
        self.image_label.setObjectName("cardThumb")
        self.image_label.setFixedSize(thumb_size, thumb_size)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setText("?")
        layout.addWidget(self.image_label, alignment=Qt.AlignCenter)

        # Breathing room between the thumbnail and its name
        layout.addSpacing(6)

        # Name label — scale max chars with thumbnail size
        max_chars = max(10, int(thumb_size * self._CHARS_PER_PX))
        name_label = QLabel(self._truncate(asset.name, max_chars))
        name_label.setObjectName("cardName")
        name_label.setAlignment(Qt.AlignCenter)
        name_font = QFont()
        name_font.setPointSize(8)
        name_label.setFont(name_font)
        name_label.setToolTip(asset.name)
        layout.addWidget(name_label)

        # Version — compact single line
        version_label = QLabel(f"v{asset.current_version}")
        version_label.setObjectName("cardVersion")
        version_label.setAlignment(Qt.AlignCenter)
        version_font = QFont()
        version_font.setPointSize(7)
        version_label.setFont(version_font)
        layout.addWidget(version_label)

    def set_pixmap(self, pixmap):
        """Set the thumbnail pixmap."""
        scaled = pixmap.scaled(
            self._thumb_size, self._thumb_size,
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.setText("")

    def set_selected(self, selected):
        """Toggle selection via a dynamic property; the stylesheet does the rest."""
        self._selected = selected
        self.setProperty("selected", selected)
        # Re-polish so the property-based QSS rule re-evaluates.
        self.style().unpolish(self)
        self.style().polish(self)

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

    def __init__(self, thumb_size=128, parent=None):
        super().__init__(parent)
        self._thumb_size = thumb_size
        self._cards = {}  # uuid -> ThumbnailCard
        self._selected_uuid = None

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)

        self._container = QWidget()
        self._flow = FlowLayout(self._container, margin=6, h_spacing=4, v_spacing=4)
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
