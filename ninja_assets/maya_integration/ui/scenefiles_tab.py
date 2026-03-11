"""Scenefiles tab – version history and save-new-version UI.

Per PRD 6.4: shows current scene info, version history table, and a
save-new-version form at the bottom.
"""

import logging
from pathlib import Path

from ninja_assets.maya_integration.ui.qt_compat import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    Qt,
)

logger = logging.getLogger("ninja_assets")


class ScenefilesTab(QWidget):
    """Tab showing scene version history and save-new-version controls."""

    # Column indices
    COL_INDICATOR = 0
    COL_FILE = 1
    COL_COMMENT = 2
    COL_AUTHOR = 3
    COL_DATE = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene_meta = None
        self._scene_folder = None
        self._base_name = None
        self._current_scene_path = None
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # --- Top: current scene info ---
        top_group = QGroupBox("Current Scene")
        top_layout = QVBoxLayout(top_group)
        self._scene_label = QLabel("No scene open")
        self._scene_label.setWordWrap(True)
        top_layout.addWidget(self._scene_label)
        layout.addWidget(top_group)

        # --- Middle: version history table ---
        mid_group = QGroupBox("Version History")
        mid_layout = QVBoxLayout(mid_group)

        self._table = QTableWidget(0, 5)
        self._table.setToolTip("Double-click a version to open it — right-click for more options")
        self._table.setHorizontalHeaderLabels(
            ["", "File", "Comment", "Author", "Date"]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._table.doubleClicked.connect(self._on_double_click)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(self.COL_INDICATOR, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_FILE, QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_COMMENT, QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_AUTHOR, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_DATE, QHeaderView.ResizeToContents)

        mid_layout.addWidget(self._table)
        layout.addWidget(mid_group, stretch=1)

        # --- Bottom: save new version form ---
        bot_group = QGroupBox("Save New Version")
        bot_layout = QHBoxLayout(bot_group)

        bot_layout.addWidget(QLabel("Version:"))
        self._version_spin = QSpinBox()
        self._version_spin.setMinimum(1)
        self._version_spin.setMaximum(9999)
        self._version_spin.setToolTip("Version number for the new save — auto-increments, but you can change it")
        bot_layout.addWidget(self._version_spin)

        bot_layout.addWidget(QLabel("Comment:"))
        self._comment_edit = QLineEdit()
        self._comment_edit.setPlaceholderText("Describe changes...")
        self._comment_edit.setToolTip("Short note about what changed in this version")
        bot_layout.addWidget(self._comment_edit, stretch=1)

        self._save_btn = QPushButton("Save Version")
        self._save_btn.setToolTip("Save the current scene as a new versioned file")
        self._save_btn.clicked.connect(self._on_save_version)
        bot_layout.addWidget(self._save_btn)

        layout.addWidget(bot_group)

    # ----------------------------------------------------------- public API
    def refresh(self):
        """Re-read current scene info and repopulate the table."""
        self._load_scene_info()
        self._populate_table()
        self._update_save_controls()

    def showEvent(self, event):  # noqa: N802
        """Called when the tab becomes visible."""
        super().showEvent(event)
        self.refresh()

    # --------------------------------------------------------- internal
    def _load_scene_info(self):
        """Read the current scene path and its scene_meta.json."""
        try:
            from ninja_assets.maya_integration.utils.maya_utils import load_scene_info
            result = load_scene_info()
        except Exception:
            result = None

        if not result:
            self._scene_meta = None
            self._scene_folder = None
            self._base_name = None
            self._current_scene_path = None
            self._scene_label.setText("No scene open")
            return

        scene_path, folder, base_name, scene_meta = result
        self._current_scene_path = scene_path
        self._scene_folder = folder
        self._base_name = base_name
        self._scene_meta = scene_meta
        self._scene_label.setText(f"Current Scene: {scene_path}")

    def _populate_table(self):
        """Fill the version history table from scene meta."""
        self._table.setRowCount(0)

        if self._scene_meta is None or not self._scene_meta.versions:
            return

        # Sort versions descending (newest first)
        versions_sorted = sorted(
            self._scene_meta.versions, key=lambda v: v.version, reverse=True
        )

        current_file = None
        if self._current_scene_path:
            current_file = Path(self._current_scene_path).name

        self._table.setRowCount(len(versions_sorted))
        for row, ver in enumerate(versions_sorted):
            # Indicator column
            is_current = current_file and ver.file == current_file
            indicator_item = QTableWidgetItem("\u25b6" if is_current else "")
            indicator_item.setTextAlignment(Qt.AlignCenter)
            indicator_item.setData(Qt.UserRole, ver)
            self._table.setItem(row, self.COL_INDICATOR, indicator_item)

            self._table.setItem(row, self.COL_FILE, QTableWidgetItem(ver.file))
            self._table.setItem(row, self.COL_COMMENT, QTableWidgetItem(ver.comment or ""))
            self._table.setItem(row, self.COL_AUTHOR, QTableWidgetItem(ver.created_by))

            date_str = ver.created_at.strftime("%Y-%m-%d %H:%M")
            self._table.setItem(row, self.COL_DATE, QTableWidgetItem(date_str))

    def _update_save_controls(self):
        """Enable/disable save controls and set default version number."""
        has_scene = self._current_scene_path is not None

        self._save_btn.setEnabled(has_scene)
        self._version_spin.setEnabled(has_scene)
        self._comment_edit.setEnabled(has_scene)

        if has_scene:
            if self._scene_meta:
                self._version_spin.setValue(self._scene_meta.get_next_version())
            else:
                self._version_spin.setValue(1)
        else:
            self._version_spin.setValue(1)

    # ------------------------------------------------------------- actions
    def _on_save_version(self):
        """Save a new scene version using commands.save_scene_version()."""
        from ninja_assets.maya_integration import plugin
        from ninja_assets.maya_integration import commands

        config = plugin.get_config()
        if config is None:
            QMessageBox.warning(self, "NinjaAssets", "Plugin not initialized.")
            return

        version_num = self._version_spin.value()
        comment = self._comment_edit.text().strip()

        try:
            result = commands.save_scene_version(
                config=config,
                comment=comment,
                version_override=version_num,
                prompt_comment=False,
            )
            if result:
                self._comment_edit.clear()
                self.refresh()
        except Exception as exc:
            logger.exception("Failed to save scene version")
            QMessageBox.critical(
                self, "Save Error", f"Failed to save version:\n{exc}"
            )

    def _get_version_at_row(self, row):
        """Return the Version object stored in the indicator column."""
        item = self._table.item(row, self.COL_INDICATOR)
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def _on_double_click(self, index):
        """Open the scene version that was double-clicked."""
        ver = self._get_version_at_row(index.row())
        if ver and self._scene_folder:
            self._open_version(ver)

    def _on_context_menu(self, pos):
        """Right-click context menu on the version table."""
        index = self._table.indexAt(pos)
        if not index.isValid():
            return

        ver = self._get_version_at_row(index.row())
        if ver is None or self._scene_folder is None:
            return

        file_path = self._scene_folder / ver.file
        menu = QMenu(self)

        open_action = menu.addAction("Open")
        explorer_action = menu.addAction("Open in Explorer")
        copy_action = menu.addAction("Copy Path")

        action = menu.exec_(self._table.viewport().mapToGlobal(pos))

        if action == open_action:
            self._open_version(ver)
        elif action == explorer_action:
            self._open_in_explorer(file_path)
        elif action == copy_action:
            self._copy_path(file_path)

    def _open_version(self, ver):
        """Open a specific scene version file in Maya."""
        if self._scene_folder is None:
            return
        file_path = self._scene_folder / ver.file
        if not file_path.exists():
            QMessageBox.warning(
                self, "File Not Found", f"Scene file not found:\n{file_path}"
            )
            return
        try:
            import maya.cmds as cmds

            cmds.file(str(file_path), open=True, force=True)
            self.refresh()
        except Exception as exc:
            logger.exception("Failed to open scene version")
            QMessageBox.critical(
                self, "Open Error", f"Failed to open scene:\n{exc}"
            )

    @staticmethod
    def _open_in_explorer(file_path):
        """Open the containing folder in the OS file browser."""
        from ninja_assets.maya_integration.utils.maya_utils import open_folder
        open_folder(str(file_path.parent))

    @staticmethod
    def _copy_path(file_path):
        """Copy the file path to the system clipboard."""
        from ninja_assets.maya_integration.utils.maya_utils import copy_to_clipboard
        copy_to_clipboard(str(file_path))
