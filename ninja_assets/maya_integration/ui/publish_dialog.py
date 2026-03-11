"""Publish dialog for exporting assets with metadata."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ninja_assets.maya_integration.ui.qt_compat import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox, QPushButton,
    QRadioButton, QButtonGroup, QPixmap, QMessageBox,
    QFileDialog, Qt, QSizePolicy,
)
from ninja_assets.constants import CATEGORIES
from ninja_assets.core.models import Asset, Version, AssetStatus, ChangelogEvent, EventType

logger = logging.getLogger(__name__)


class PublishDialog(QDialog):
    """Dialog for publishing (exporting) an asset with full metadata."""

    def __init__(self, config=None, cache=None, changelog=None, parent=None):
        super().__init__(parent)
        if config is None:
            from ninja_assets.maya_integration.plugin import get_config
            config = get_config()
        self._config = config
        self._cache = cache
        self._changelog = changelog
        self._thumbnail_path = None

        self.setWindowTitle("Publish Asset")
        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Selection info
        self._selection_label = QLabel("Selection: (none)")
        layout.addWidget(self._selection_label)

        form = QFormLayout()

        # Asset name
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. hero_sword")
        form.addRow("Name:", self._name_edit)

        # Category
        self._category_combo = QComboBox()
        self._category_combo.addItems(CATEGORIES)
        form.addRow("Category:", self._category_combo)

        # Version
        self._version_spin = QSpinBox()
        self._version_spin.setMinimum(1)
        self._version_spin.setMaximum(9999)
        self._version_spin.setValue(1)
        form.addRow("Version:", self._version_spin)

        # Tags
        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText("comma-separated tags")
        form.addRow("Tags:", self._tags_edit)

        # Format
        format_layout = QHBoxLayout()
        self._format_group = QButtonGroup(self)
        self._obj_radio = QRadioButton("OBJ")
        self._ma_radio = QRadioButton("Maya ASCII")
        self._both_radio = QRadioButton("Both")
        self._both_radio.setChecked(True)
        self._format_group.addButton(self._obj_radio)
        self._format_group.addButton(self._ma_radio)
        self._format_group.addButton(self._both_radio)
        format_layout.addWidget(self._obj_radio)
        format_layout.addWidget(self._ma_radio)
        format_layout.addWidget(self._both_radio)
        form.addRow("Format:", format_layout)

        # Comment
        self._comment_edit = QLineEdit()
        self._comment_edit.setPlaceholderText("Version comment")
        form.addRow("Comment:", self._comment_edit)

        layout.addLayout(form)

        # Thumbnail section
        thumb_layout = QHBoxLayout()
        self._thumb_preview = QLabel()
        self._thumb_preview.setFixedSize(128, 128)
        self._thumb_preview.setAlignment(Qt.AlignCenter)
        self._thumb_preview.setStyleSheet("background-color: #3a3a3a; border: 1px solid #555;")
        self._thumb_preview.setText("No Thumbnail")
        thumb_layout.addWidget(self._thumb_preview)

        thumb_btn_layout = QVBoxLayout()
        self._capture_btn = QPushButton("Capture from Viewport")
        self._load_thumb_btn = QPushButton("Load from File...")
        thumb_btn_layout.addWidget(self._capture_btn)
        thumb_btn_layout.addWidget(self._load_thumb_btn)
        thumb_btn_layout.addStretch()
        thumb_layout.addLayout(thumb_btn_layout)
        layout.addLayout(thumb_layout)

        # Destination path
        self._dest_label = QLabel("Destination: (auto)")
        self._dest_label.setWordWrap(True)
        self._dest_label.setStyleSheet("color: #aaa;")
        layout.addWidget(self._dest_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        self._publish_btn = QPushButton("Publish")
        self._publish_btn.setDefault(True)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self._publish_btn)
        layout.addLayout(btn_layout)

        # Connections
        cancel_btn.clicked.connect(self.reject)
        self._publish_btn.clicked.connect(self._on_publish)
        self._capture_btn.clicked.connect(self._on_capture_viewport)
        self._load_thumb_btn.clicked.connect(self._on_load_thumbnail)
        self._name_edit.textChanged.connect(self._update_destination)
        self._category_combo.currentIndexChanged.connect(self._update_destination)

        # Update selection info
        self._update_selection_info()

    def _update_selection_info(self):
        """Show selected objects and poly count."""
        try:
            import maya.cmds as cmds
            sel = cmds.ls(selection=True)
            if sel:
                from ninja_assets.maya_integration.utils.export import get_selection_poly_count
                polys = get_selection_poly_count()
                poly_str = f" ({polys:,} polys)" if polys else ""
                names = ", ".join(sel[:3])
                if len(sel) > 3:
                    names += f" ... (+{len(sel) - 3} more)"
                self._selection_label.setText(f"Selection: {names}{poly_str}")
            else:
                self._selection_label.setText("Selection: (nothing selected)")
        except ImportError:
            self._selection_label.setText("Selection: (Maya not available)")

    def _update_destination(self):
        """Compute and display the destination path."""
        name = self._name_edit.text().strip()
        category = self._category_combo.currentText().lower()
        if name and self._config:
            dest = self._config.assets_root / category / name
            self._dest_label.setText(f"Destination: {dest}")
        else:
            self._dest_label.setText("Destination: (enter a name)")

    def _on_capture_viewport(self):
        """Capture thumbnail from Maya viewport."""
        try:
            from ninja_assets.maya_integration.utils.thumbnail import capture_viewport
            path = capture_viewport(
                width=self._config.thumbnail_size[0],
                height=self._config.thumbnail_size[1],
                image_format=self._config.thumbnail_format,
                quality=self._config.thumbnail_quality,
            )
            self._set_thumbnail(path)
        except Exception as e:
            logger.error("Viewport capture failed: %s", e)
            QMessageBox.warning(self, "Capture Failed", str(e))

    def _on_load_thumbnail(self):
        """Load thumbnail from a file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Thumbnail", "",
            "Images (*.jpg *.jpeg *.png *.bmp)"
        )
        if path:
            self._set_thumbnail(Path(path))

    def _set_thumbnail(self, path):
        """Set the thumbnail preview from a file path."""
        self._thumbnail_path = path
        pixmap = QPixmap(str(path))
        scaled = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._thumb_preview.setPixmap(scaled)
        self._thumb_preview.setText("")

    def _on_publish(self):
        """Execute the publish operation."""
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Asset name is required.")
            return

        category = self._category_combo.currentText()
        version = self._version_spin.value()
        tags = [t.strip() for t in self._tags_edit.text().split(",") if t.strip()]
        comment = self._comment_edit.text().strip()

        # Determine format(s) to export
        export_obj = self._obj_radio.isChecked() or self._both_radio.isChecked()
        export_ma = self._ma_radio.isChecked() or self._both_radio.isChecked()

        # Build destination
        asset_dir = self._config.assets_root / category.lower() / name
        asset_dir.mkdir(parents=True, exist_ok=True)

        try:
            from ninja_assets.maya_integration.utils.export import (
                export_obj as do_export_obj,
                export_ma as do_export_ma,
                get_selection_poly_count,
                get_selection_bounds,
            )
            from ninja_assets.core.sidecar import SidecarManager

            ver_str = f"v{version:03d}"
            exported_file = None

            if export_obj:
                obj_path = asset_dir / f"{name}_{ver_str}.obj"
                do_export_obj(obj_path)
                exported_file = exported_file or obj_path.name

            if export_ma:
                ma_path = asset_dir / f"{name}_{ver_str}.ma"
                do_export_ma(ma_path)
                exported_file = exported_file or ma_path.name

            # Copy thumbnail
            thumb_name = None
            if self._thumbnail_path and self._thumbnail_path.exists():
                import shutil
                ext = self._thumbnail_path.suffix
                thumb_name = f"thumbnail{ext}"
                shutil.copy2(str(self._thumbnail_path), str(asset_dir / thumb_name))

            # Build or update asset
            poly_count = get_selection_poly_count()
            bounds = get_selection_bounds()

            sidecar_path = SidecarManager.get_sidecar_path(asset_dir, name)

            if sidecar_path.exists():
                asset, mtime = SidecarManager.read(sidecar_path)
            else:
                asset = Asset.new(name=name, category=category, path=str(asset_dir))
                mtime = None

            new_version = Version(
                version=version,
                file=exported_file or "",
                created_by=self._config.username or "unknown",
                created_at=datetime.utcnow(),
                comment=comment,
                poly_count=poly_count,
            )
            asset.versions.append(new_version)
            asset.current_version = version
            asset.current_file = exported_file or ""
            asset.modified_at = datetime.utcnow()
            asset.tags = tags
            asset.bounds = bounds
            if thumb_name:
                asset.thumbnail = thumb_name

            try:
                SidecarManager.write(sidecar_path, asset, expected_mtime=mtime)
            except Exception as conflict_err:
                from ninja_assets.core.exceptions import ConflictError
                if isinstance(conflict_err, ConflictError):
                    result = QMessageBox.warning(
                        self, "Conflict Detected",
                        "The asset metadata was modified by another user.\n"
                        "Do you want to overwrite?",
                        QMessageBox.Yes | QMessageBox.No,
                    )
                    if result == QMessageBox.Yes:
                        SidecarManager.write(sidecar_path, asset)
                    else:
                        return
                else:
                    raise

            # Update changelog
            if self._changelog:
                event = ChangelogEvent(
                    timestamp=datetime.utcnow(),
                    event_type=EventType.ASSET_CREATED if version == 1 else EventType.ASSET_UPDATED,
                    uuid=asset.uuid,
                    path=str(asset_dir),
                    user=self._config.username or "unknown",
                    version=version,
                )
                self._changelog.append(event)

            # Update cache
            if self._cache:
                import os
                new_mtime = os.path.getmtime(sidecar_path)
                self._cache.upsert_asset(asset, new_mtime)

            QMessageBox.information(
                self, "Published",
                f"Successfully published {name} v{version}."
            )
            self.accept()

        except Exception as e:
            logger.exception("Publish failed")
            QMessageBox.critical(self, "Publish Failed", str(e))
