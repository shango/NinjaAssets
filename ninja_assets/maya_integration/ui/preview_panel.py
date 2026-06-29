"""Detail panel: a large preview plus structured metadata and actions.

Laid out vertically to sit on the right of the Products splitter - preview image
at the top, then the asset name with a colored category badge, a right-aligned
metadata form, an elided path row with Copy/Open, and the action buttons.
"""

import logging
from pathlib import Path

from ninja_assets.maya_integration.ui import style
from ninja_assets.maya_integration.ui.qt_compat import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox,
    QPushButton, QToolButton, QCheckBox, QPixmap, QFontMetrics,
    QSizePolicy, Qt, Signal,
)
from ninja_assets.core.models import Asset

logger = logging.getLogger(__name__)

_PREVIEW_MAX = 360


class PreviewPanel(QFrame):
    """Panel showing a large preview and metadata for the selected asset."""

    import_requested = Signal(str, int)     # uuid, version
    reference_requested = Signal(str, int)  # uuid, version

    def __init__(self, preview_size=320, parent=None):
        super().__init__(parent)
        self._preview_size = preview_size
        self._asset = None
        self._full_pixmap = None  # original, rescaled on resize
        self._build_ui()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 8, 8, 8)
        v.setSpacing(8)

        # --- preview image --------------------------------------------------
        self._thumb_label = QLabel("No Selection")
        self._thumb_label.setObjectName("previewImage")
        self._thumb_label.setAlignment(Qt.AlignCenter)
        self._thumb_label.setMinimumHeight(200)
        self._thumb_label.setMaximumHeight(_PREVIEW_MAX)
        self._thumb_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        v.addWidget(self._thumb_label)

        # --- name + category badge -----------------------------------------
        header = QHBoxLayout()
        self._name_label = QLabel("-")
        self._name_label.setObjectName("assetName")
        self._name_label.setWordWrap(True)
        self._badge = QLabel("")
        self._badge.setObjectName("typeBadge")
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setVisible(False)
        header.addWidget(self._name_label, 1)
        header.addWidget(self._badge, 0, Qt.AlignTop)
        v.addLayout(header)

        v.addWidget(self._hline())

        # --- metadata form --------------------------------------------------
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(6)
        self._meta = {}
        for key, caption in (
            ("repo", "Repo"),
            ("author", "Author"),
            ("polys", "Polycount"),
            ("size", "Size"),
            ("modified", "Modified"),
            ("tags", "Tags"),
        ):
            value = QLabel("-")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._meta[key] = value
            form.addRow(self._field_caption(caption), value)
        v.addLayout(form)

        # --- version row + comment -----------------------------------------
        ver_row = QHBoxLayout()
        ver_row.setSpacing(6)
        ver_row.addWidget(self._field_caption("Version"))
        self._version_combo = QComboBox()
        self._version_combo.setToolTip("Pick a version to import or reference")
        self._version_combo.setFixedWidth(90)
        self._version_combo.currentIndexChanged.connect(self._on_version_changed)
        ver_row.addWidget(self._version_combo)
        ver_row.addStretch(1)
        v.addLayout(ver_row)

        self._comment_label = QLabel("")
        self._comment_label.setObjectName("description")
        self._comment_label.setWordWrap(True)
        v.addWidget(self._comment_label)

        v.addStretch(1)
        v.addWidget(self._hline())

        # --- elided path row ------------------------------------------------
        path_row = QHBoxLayout()
        path_row.setSpacing(4)
        self._path_label = QLabel("-")
        self._path_label.setObjectName("muted")
        self._path_label.setMinimumWidth(0)
        self._path_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._copy_btn = QToolButton()
        self._copy_btn.setText("Copy")
        self._copy_btn.setToolTip("Copy the asset's path to the clipboard")
        self._copy_btn.clicked.connect(self._on_copy_path)
        self._open_btn = QToolButton()
        self._open_btn.setText("Open ▸")
        self._open_btn.setToolTip("Show this asset's folder in your file browser")
        self._open_btn.clicked.connect(self._on_open_folder)
        path_row.addWidget(self._path_label, 1)
        path_row.addWidget(self._copy_btn)
        path_row.addWidget(self._open_btn)
        v.addLayout(path_row)

        # --- actions --------------------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._import_btn = QPushButton("Import")
        self._import_btn.setProperty("accent", True)
        self._import_btn.setToolTip("Import a copy of this asset into your scene")
        self._reference_btn = QPushButton("Reference")
        self._reference_btn.setToolTip(
            "Reference this asset — stays linked to the original file")
        btn_row.addWidget(self._import_btn)
        btn_row.addWidget(self._reference_btn)
        btn_row.addStretch(1)
        v.addLayout(btn_row)

        self._pull_check = QCheckBox("Pull to local before import")
        self._pull_check.setToolTip(
            "Copy the asset into your local repo and import from there. "
            "Set a local repo in the Setup tab to enable this.")
        v.addWidget(self._pull_check)

        self._import_btn.clicked.connect(self._on_import)
        self._reference_btn.clicked.connect(self._on_reference)
        self._set_buttons_enabled(False)

    # --- small builders ---

    def _hline(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #1d1d1f; background: #1d1d1f; max-height: 1px;")
        return line

    @staticmethod
    def _field_caption(text):
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl

    # --- config helpers ---

    def _get_config(self):
        try:
            from ninja_assets.maya_integration import plugin
            return plugin.get_config()
        except Exception:
            return None

    def _local_root_for_pull(self):
        """Return the local repo path if pull is requested and configured."""
        if not self._pull_check.isChecked():
            return None
        config = self._get_config()
        return config.local_repo if config and config.local_repo else None

    # --- population ---

    def set_asset(self, asset: Asset):
        """Update the panel with the given asset."""
        self._asset = asset
        self._set_buttons_enabled(True)

        # Enable pull only when a local repo is configured.
        config = self._get_config()
        has_local = bool(config and config.local_repo)
        self._pull_check.setEnabled(has_local)
        if not has_local:
            self._pull_check.setChecked(False)

        self._name_label.setText(asset.name)
        self._set_badge(asset.category)

        repo_text = asset.source_repo or "—"
        if asset.local_path:
            repo_text += "  (local)"
        self._meta["repo"].setText(repo_text)

        latest = asset.get_latest_version()
        self._meta["author"].setText(latest.created_by if latest else "Unknown")

        polys = latest.poly_count if latest and latest.poly_count else "N/A"
        self._meta["polys"].setText(str(polys))

        if asset.bounds:
            self._meta["size"].setText(
                "{:.1f} x {:.1f} x {:.1f}".format(
                    asset.bounds.x, asset.bounds.y, asset.bounds.z)
            )
        else:
            self._meta["size"].setText("N/A")

        self._meta["modified"].setText(
            asset.modified_at.strftime("%Y-%m-%d %H:%M"))
        self._meta["tags"].setText(", ".join(asset.tags) if asset.tags else "None")

        # Version combo (newest first).
        self._version_combo.blockSignals(True)
        self._version_combo.clear()
        for ver in sorted(asset.versions, key=lambda x: x.version, reverse=True):
            self._version_combo.addItem("v{}".format(ver.version), ver.version)
        self._version_combo.blockSignals(False)
        self._on_version_changed(0)

        self._set_path(asset.path)
        self._load_preview(asset)

    def clear(self):
        """Reset the panel to its empty state."""
        self._asset = None
        self._full_pixmap = None
        self._name_label.setText("-")
        self._badge.setVisible(False)
        for lbl in self._meta.values():
            lbl.setText("-")
        self._version_combo.clear()
        self._comment_label.setText("")
        self._path_label.setText("-")
        self._path_label.setToolTip("")
        self._thumb_label.setPixmap(QPixmap())
        self._thumb_label.setText("No Selection")
        self._set_buttons_enabled(False)

    def _set_badge(self, category):
        if not category:
            self._badge.setVisible(False)
            return
        self._badge.setText(category.upper())
        color = style.badge_color(category)
        self._badge.setStyleSheet(
            "background: {}; color: #ffffff; border-radius: 9px; "
            "padding: 2px 10px; font-size: 11px; font-weight: 600;".format(color)
        )
        self._badge.setVisible(True)

    def _load_preview(self, asset):
        self._full_pixmap = None
        self._thumb_label.setText("")
        if asset.thumbnail:
            thumb_path = Path(asset.path) / asset.thumbnail
            pixmap = QPixmap(str(thumb_path))
            if not pixmap.isNull():
                self._full_pixmap = pixmap
                self._render_preview()
                return
        self._thumb_label.setPixmap(QPixmap())
        self._thumb_label.setText("No Thumbnail")

    def _render_preview(self):
        """Scale the stored pixmap to the label, preserving aspect ratio."""
        if self._full_pixmap is None:
            return
        target = self._thumb_label.size()
        if target.width() < 2 or target.height() < 2:
            return
        self._thumb_label.setPixmap(self._full_pixmap.scaled(
            target, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _set_path(self, path):
        """Show the path elided in the middle so it never widens the panel."""
        text = str(path)
        metrics = QFontMetrics(self._path_label.font())
        avail = max(60, self._path_label.width() - 4)
        self._path_label.setText(metrics.elidedText(text, Qt.ElideMiddle, avail))
        self._path_label.setToolTip(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_preview()
        if self._asset is not None:
            self._set_path(self._asset.path)

    # --- version / actions ---

    def _on_version_changed(self, index):
        if not self._asset or index < 0:
            self._comment_label.setText("")
            return
        ver_num = self._version_combo.itemData(index)
        if ver_num is not None:
            v = self._asset.get_version(ver_num)
            self._comment_label.setText('"{}"'.format(v.comment) if v and v.comment else "")

    def _selected_version(self) -> int:
        ver = self._version_combo.currentData()
        if ver is not None:
            return ver
        return self._asset.current_version if self._asset else 1

    def _record_local_pull(self, local_path):
        """Persist the pulled local path to the cache so the UI can reflect it."""
        try:
            from ninja_assets.maya_integration import plugin
            cache = plugin.get_cache()
            if cache is not None:
                cache.set_local_path(self._asset.uuid, str(local_path))
                self._asset.local_path = str(local_path)
        except Exception:
            logger.debug("Could not record local pull path", exc_info=True)

    def _on_import(self):
        if not self._asset:
            return
        ver = self._selected_version()
        local_root = self._local_root_for_pull()
        self.import_requested.emit(self._asset.uuid, ver)
        try:
            from ninja_assets.maya_integration import commands
            commands.import_asset(self._asset, ver, local_root=local_root)
            if local_root is not None:
                self._record_local_pull(
                    commands.pull_asset(self._asset, ver, local_root))
        except Exception as e:
            logger.error("Import failed: %s", e)

    def _on_reference(self):
        if not self._asset:
            return
        ver = self._selected_version()
        local_root = self._local_root_for_pull()
        self.reference_requested.emit(self._asset.uuid, ver)
        try:
            from ninja_assets.maya_integration import commands
            commands.reference_asset(self._asset, ver, local_root=local_root)
            if local_root is not None:
                self._record_local_pull(
                    commands.pull_asset(self._asset, ver, local_root))
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
                    self._copy_btn, self._open_btn):
            btn.setEnabled(enabled)
