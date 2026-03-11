"""Preview panel showing detailed asset information and action buttons."""

import logging
from pathlib import Path
from typing import Optional

from ninja_assets.maya_integration.ui.qt_compat import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QComboBox,
    QPushButton, QPixmap, QFont, Qt, Signal, QSizePolicy,
)
from ninja_assets.maya_integration.ui import STATUS_DISPLAY
from ninja_assets.core.models import Asset, AssetStatus

logger = logging.getLogger(__name__)


class PreviewPanel(QFrame):
    """Panel showing a large preview and metadata for the selected asset."""

    import_requested = Signal(str, int)   # uuid, version
    reference_requested = Signal(str, int)  # uuid, version

    def __init__(self, preview_size=250, parent=None):
        super().__init__(parent)
        self._preview_size = preview_size
        self._asset = None
        self.setFrameShape(QFrame.StyledPanel)
        self._build_ui()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Left: large thumbnail
        self._thumb_label = QLabel()
        self._thumb_label.setFixedSize(self._preview_size, self._preview_size)
        self._thumb_label.setAlignment(Qt.AlignCenter)
        self._thumb_label.setStyleSheet("background-color: #3a3a3a; border: 1px solid #555;")
        self._thumb_label.setText("No Selection")
        main_layout.addWidget(self._thumb_label)

        # Center: metadata
        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(4)

        self._name_label = QLabel()
        bold_font = QFont()
        bold_font.setPointSize(14)
        bold_font.setBold(True)
        self._name_label.setFont(bold_font)
        meta_layout.addWidget(self._name_label)

        self._category_label = QLabel()
        self._status_label = QLabel()
        self._author_label = QLabel()
        self._polys_label = QLabel()
        self._modified_label = QLabel()
        self._size_label = QLabel()
        self._tags_label = QLabel()

        for lbl in (
            self._category_label, self._status_label, self._author_label,
            self._polys_label, self._modified_label, self._size_label,
            self._tags_label,
        ):
            lbl.setWordWrap(True)
            meta_layout.addWidget(lbl)

        # Version selector
        ver_layout = QHBoxLayout()
        ver_layout.addWidget(QLabel("Version:"))
        self._version_combo = QComboBox()
        self._version_combo.setToolTip("Pick a version to import or reference")
        self._version_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._version_combo.currentIndexChanged.connect(self._on_version_changed)
        ver_layout.addWidget(self._version_combo)
        meta_layout.addLayout(ver_layout)

        self._comment_label = QLabel()
        self._comment_label.setWordWrap(True)
        self._comment_label.setStyleSheet("color: #aaa; font-style: italic;")
        meta_layout.addWidget(self._comment_label)

        meta_layout.addStretch()
        main_layout.addLayout(meta_layout, stretch=1)

        # Right: action buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)

        self._import_btn = QPushButton("Import")
        self._import_btn.setToolTip("Import a copy of this asset into your scene")
        self._reference_btn = QPushButton("Reference")
        self._reference_btn.setToolTip("Reference this asset — stays linked to the original file")
        self._open_folder_btn = QPushButton("Open Folder")
        self._open_folder_btn.setToolTip("Show this asset's folder in your file browser")
        self._copy_path_btn = QPushButton("Copy Path")
        self._copy_path_btn.setToolTip("Copy the file path to your clipboard")

        for btn in (self._import_btn, self._reference_btn,
                    self._open_folder_btn, self._copy_path_btn):
            btn.setMinimumWidth(100)
            btn_layout.addWidget(btn)

        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # Connect buttons
        self._import_btn.clicked.connect(self._on_import)
        self._reference_btn.clicked.connect(self._on_reference)
        self._open_folder_btn.clicked.connect(self._on_open_folder)
        self._copy_path_btn.clicked.connect(self._on_copy_path)

        self._set_buttons_enabled(False)

    def set_asset(self, asset: Asset):
        """Update the panel with the given asset."""
        self._asset = asset
        self._set_buttons_enabled(True)

        self._name_label.setText(asset.name)
        self._category_label.setText(f"Category: {asset.category}")
        status_info = STATUS_DISPLAY.get(asset.status)
        status_text = f"{status_info['symbol']} {status_info['text']}" if status_info else str(asset.status.value)
        self._status_label.setText(f"Status: {status_text}")

        # Author from latest version
        latest = asset.get_latest_version()
        author = latest.created_by if latest else "Unknown"
        self._author_label.setText(f"Author: {author}")

        polys = latest.poly_count if latest and latest.poly_count else "N/A"
        self._polys_label.setText(f"Polys: {polys}")
        self._modified_label.setText(f"Modified: {asset.modified_at.strftime('%Y-%m-%d %H:%M')}")

        if asset.bounds:
            self._size_label.setText(
                f"Size: {asset.bounds.x:.1f} x {asset.bounds.y:.1f} x {asset.bounds.z:.1f}"
            )
        else:
            self._size_label.setText("Size: N/A")

        self._tags_label.setText(f"Tags: {', '.join(asset.tags) if asset.tags else 'None'}")

        # Populate version combo
        self._version_combo.blockSignals(True)
        self._version_combo.clear()
        for v in sorted(asset.versions, key=lambda v: v.version, reverse=True):
            self._version_combo.addItem(f"v{v.version}", v.version)
        self._version_combo.blockSignals(False)
        self._on_version_changed(0)

        # Load thumbnail
        self._thumb_label.setText("")
        if asset.thumbnail:
            thumb_path = Path(asset.path) / asset.thumbnail
            pixmap = QPixmap(str(thumb_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self._preview_size, self._preview_size,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
                self._thumb_label.setPixmap(scaled)
                return
        self._thumb_label.setText("No Thumbnail")

    def clear(self):
        """Reset the panel to empty state."""
        self._asset = None
        self._name_label.setText("")
        self._category_label.setText("")
        self._status_label.setText("")
        self._author_label.setText("")
        self._polys_label.setText("")
        self._modified_label.setText("")
        self._size_label.setText("")
        self._tags_label.setText("")
        self._version_combo.clear()
        self._comment_label.setText("")
        self._thumb_label.setPixmap(QPixmap())
        self._thumb_label.setText("No Selection")
        self._set_buttons_enabled(False)

    def _on_version_changed(self, index):
        if not self._asset or index < 0:
            self._comment_label.setText("")
            return
        ver_num = self._version_combo.itemData(index)
        if ver_num is not None:
            v = self._asset.get_version(ver_num)
            if v and v.comment:
                self._comment_label.setText(f'"{v.comment}"')
            else:
                self._comment_label.setText("")

    def _selected_version(self) -> int:
        ver = self._version_combo.currentData()
        if ver is not None:
            return ver
        return self._asset.current_version if self._asset else 1

    def _on_import(self):
        if not self._asset:
            return
        ver = self._selected_version()
        self.import_requested.emit(self._asset.uuid, ver)
        try:
            from ninja_assets.maya_integration import commands
            commands.import_asset(self._asset, ver)
        except Exception as e:
            logger.error("Import failed: %s", e)

    def _on_reference(self):
        if not self._asset:
            return
        ver = self._selected_version()
        self.reference_requested.emit(self._asset.uuid, ver)
        try:
            from ninja_assets.maya_integration import commands
            commands.reference_asset(self._asset, ver)
        except Exception as e:
            logger.error("Reference failed: %s", e)

    def _on_open_folder(self):
        if self._asset:
            from ninja_assets.maya_integration.utils.maya_utils import open_folder
            open_folder(self._asset.path)

    def _on_copy_path(self):
        if self._asset:
            from ninja_assets.maya_integration.utils.maya_utils import copy_to_clipboard
            copy_to_clipboard(self._asset.path)

    def _set_buttons_enabled(self, enabled):
        for btn in (self._import_btn, self._reference_btn,
                    self._open_folder_btn, self._copy_path_btn):
            btn.setEnabled(enabled)
