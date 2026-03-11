"""Save Version dialog – standalone dialog for saving a new scene version.

Per PRD 6.5: shows current scene info, version spinbox, multi-line comment,
option to open the new version after saving, and Cancel / Save buttons.
"""

import logging
from pathlib import Path

from ninja_assets.maya_integration.ui.qt_compat import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    Qt,
)

logger = logging.getLogger("ninja_assets")


class SaveVersionDialog(QDialog):
    """Dialog for saving a new versioned scene file."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save Scene Version")
        self.setMinimumWidth(450)

        self._scene_path = None
        self._scene_folder = None
        self._base_name = None
        self._scene_meta = None
        self._saved_path = None

        self._build_ui()
        self._load_scene_info()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Scene info
        form = QFormLayout()
        self._scene_label = QLabel("No scene open")
        self._scene_label.setWordWrap(True)
        form.addRow("Current Scene:", self._scene_label)

        self._location_label = QLabel("")
        self._location_label.setWordWrap(True)
        form.addRow("Location:", self._location_label)

        # Version spinbox
        self._version_spin = QSpinBox()
        self._version_spin.setMinimum(1)
        self._version_spin.setMaximum(9999)
        form.addRow("Version:", self._version_spin)

        layout.addLayout(form)

        # Comment (multi-line)
        layout.addWidget(QLabel("Comment:"))
        self._comment_edit = QTextEdit()
        self._comment_edit.setPlaceholderText("Describe changes...")
        self._comment_edit.setMaximumHeight(100)
        layout.addWidget(self._comment_edit)

        # Open after saving checkbox
        self._open_after_cb = QCheckBox("Open new version after saving")
        self._open_after_cb.setChecked(True)
        layout.addWidget(self._open_after_cb)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self._save_btn = QPushButton("Save Version")
        self._save_btn.setDefault(True)
        self._save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self._save_btn)

        layout.addLayout(btn_layout)

    # ----------------------------------------------------------- load info
    def _load_scene_info(self):
        """Populate labels and version spinbox from the current scene."""
        try:
            from ninja_assets.maya_integration.utils.maya_utils import load_scene_info
            result = load_scene_info()
        except Exception:
            result = None

        if not result:
            self._scene_path = None
            self._scene_label.setText("No scene open")
            self._location_label.setText("")
            self._save_btn.setEnabled(False)
            return

        scene_path, folder, base_name, scene_meta = result
        self._scene_path = scene_path
        self._scene_folder = folder
        self._base_name = base_name
        self._scene_meta = scene_meta

        self._scene_label.setText(Path(self._scene_path).name)
        self._location_label.setText(str(folder))

        if self._scene_meta:
            self._version_spin.setValue(self._scene_meta.get_next_version())
        else:
            self._version_spin.setValue(1)

        self._save_btn.setEnabled(True)

    # ----------------------------------------------------------- save
    def _on_save(self):
        """Save the scene as a new version and optionally open it."""
        from ninja_assets.maya_integration import plugin
        from ninja_assets.maya_integration import commands

        config = plugin.get_config()
        if config is None:
            QMessageBox.warning(self, "NinjaAssets", "Plugin not initialized.")
            return

        version_num = self._version_spin.value()
        comment = self._comment_edit.toPlainText().strip()

        try:
            result = commands.save_scene_version(
                config=config,
                comment=comment,
                version_override=version_num,
                prompt_comment=False,
            )
        except Exception as exc:
            logger.exception("Failed to save scene version")
            QMessageBox.critical(
                self, "Save Error", f"Failed to save version:\n{exc}"
            )
            return

        if not result:
            return

        self._saved_path = result

        # Open the newly saved file if requested
        if self._open_after_cb.isChecked():
            try:
                import maya.cmds as cmds

                cmds.file(str(result), open=True, force=True)
            except Exception as exc:
                logger.exception("Failed to open new version")
                QMessageBox.warning(
                    self, "Open Error",
                    f"Version saved but failed to open:\n{exc}",
                )

        self.accept()

    @property
    def saved_path(self):
        """Return the path of the saved file, or None if save was not completed."""
        return self._saved_path
