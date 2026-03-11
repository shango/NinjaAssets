"""First-launch setup — asset drive location and username.

Uses Maya's built-in dialogs (cmds.promptDialog / cmds.fileDialog2) so it
works even before PySide2/6 is fully loaded.  Falls back to a PySide dialog
if available.
"""

from pathlib import Path
from typing import Optional, Tuple

from ninja_assets.config import _default_gdrive_root


# ------------------------------------------------------------------ #
#  Maya-native implementation (always works at startup)               #
# ------------------------------------------------------------------ #

def _prompt_native(default_gdrive_root=None):
    """First-launch setup using Maya's built-in dialogs.

    Returns (username, gdrive_root) or None if cancelled.
    """
    import maya.cmds as cmds

    gdrive_root = default_gdrive_root or _default_gdrive_root()

    # --- Step 1: Asset drive location ---
    cmds.confirmDialog(
        title="NinjaAssets Setup (1/2)",
        message=(
            "Welcome to NinjaAssets!\n\n"
            "First, you'll pick the shared folder where studio assets are stored.\n"
            "This is usually inside Google Drive > Shared drives > [your studio drive].\n\n"
            "Don't pick \"My Drive\" — that's your personal folder."
        ),
        button=["OK"],
        defaultButton="OK",
    )

    result = cmds.fileDialog2(
        caption="Select Asset Drive Folder",
        fileMode=3,  # directory
        startingDirectory=str(gdrive_root),
        okCaption="Select",
    )

    if not result:
        return None

    gdrive_path = Path(result[0])

    # --- Step 2: Username ---
    response = cmds.promptDialog(
        title="NinjaAssets Setup (2/2)",
        message=(
            "Enter your studio username.\n"
            "This is the name other artists will see when you publish or save.\n"
            "(e.g. sarah.jones)"
        ),
        button=["Get Started", "Cancel"],
        defaultButton="Get Started",
        cancelButton="Cancel",
        dismissString="Cancel",
    )

    if response != "Get Started":
        return None

    username = cmds.promptDialog(query=True, text=True)
    if not username or not username.strip():
        cmds.warning("NinjaAssets: Username is required.")
        return None

    return (username.strip(), gdrive_path)


# ------------------------------------------------------------------ #
#  PySide implementation (richer UI, used from Settings or if available)
# ------------------------------------------------------------------ #

def _prompt_pyside(default_gdrive_root=None):
    """First-launch setup using a PySide dialog.

    Returns (username, gdrive_root) or None if cancelled.
    """
    from ninja_assets.maya_integration.ui.qt_compat import (
        QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
        QLineEdit, QPushButton, QLabel, QFileDialog, QGroupBox,
    )
    from ninja_assets.maya_integration.utils.maya_utils import get_maya_main_window

    gdrive_root = default_gdrive_root or _default_gdrive_root()

    class _Dialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("NinjaAssets — First-Time Setup")
            self.setMinimumWidth(500)
            self._gdrive_root = gdrive_root
            self._build_ui()

        def _build_ui(self):
            layout = QVBoxLayout(self)

            welcome = QLabel(
                "Welcome to NinjaAssets!\n\n"
                "Before you start, we need two things:"
            )
            welcome.setWordWrap(True)
            layout.addWidget(welcome)

            # Asset drive
            drive_group = QGroupBox("Asset Drive Location")
            drive_layout = QVBoxLayout()
            drive_help = QLabel(
                "Browse to the shared folder where studio assets are stored.\n"
                "This is usually inside Google Drive > Shared drives > [your studio drive].\n"
                "Don't pick \"My Drive\" — that's your personal folder."
            )
            drive_help.setWordWrap(True)
            drive_help.setStyleSheet("color: #888;")
            drive_layout.addWidget(drive_help)

            path_row = QHBoxLayout()
            self._gdrive_edit = QLineEdit(str(self._gdrive_root))
            self._gdrive_edit.setPlaceholderText("e.g. G:\\Shared drives\\StudioName")
            self._gdrive_edit.setToolTip("Path to your studio's shared asset folder on Google Drive")
            browse_btn = QPushButton("Browse...")
            browse_btn.setToolTip("Pick the shared folder in a file browser")
            browse_btn.clicked.connect(self._browse)
            path_row.addWidget(self._gdrive_edit)
            path_row.addWidget(browse_btn)
            drive_layout.addLayout(path_row)
            drive_group.setLayout(drive_layout)
            layout.addWidget(drive_group)

            # Username
            user_group = QGroupBox("Your Name")
            user_layout = QVBoxLayout()
            user_help = QLabel(
                "This is the name other artists will see when you publish assets or save scenes."
            )
            user_help.setWordWrap(True)
            user_help.setStyleSheet("color: #888;")
            user_layout.addWidget(user_help)
            user_form = QFormLayout()
            self._username_edit = QLineEdit()
            self._username_edit.setPlaceholderText("e.g. sarah.jones")
            self._username_edit.setToolTip("The name shown when you publish or save — doesn't need to match your login")
            user_form.addRow("Username:", self._username_edit)
            user_layout.addLayout(user_form)
            user_group.setLayout(user_layout)
            layout.addWidget(user_group)

            # Error label
            self._error_label = QLabel("")
            self._error_label.setStyleSheet("color: #FF4444; font-weight: bold;")
            self._error_label.setWordWrap(True)
            self._error_label.hide()
            layout.addWidget(self._error_label)

            # Buttons
            layout.addStretch()
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            ok_btn = QPushButton("Get Started")
            ok_btn.setToolTip("Save settings and launch NinjaAssets")
            ok_btn.clicked.connect(self._on_ok)
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setToolTip("Skip setup — NinjaAssets won't load until setup is complete")
            cancel_btn.clicked.connect(self.reject)
            btn_layout.addWidget(ok_btn)
            btn_layout.addWidget(cancel_btn)
            layout.addLayout(btn_layout)

        def _browse(self):
            start_path = self._gdrive_edit.text() or str(self._gdrive_root)
            directory = QFileDialog.getExistingDirectory(
                self, "Select Asset Drive Folder", start_path
            )
            if directory:
                self._gdrive_edit.setText(directory)

        def _on_ok(self):
            username = self._username_edit.text().strip()
            gdrive_path = self._gdrive_edit.text().strip()
            if not username:
                self._error_label.setText("Please enter a username.")
                self._error_label.show()
                return
            if not gdrive_path:
                self._error_label.setText("Please select the asset drive location.")
                self._error_label.show()
                return
            path = Path(gdrive_path)
            if not path.exists():
                self._error_label.setText(
                    "That folder doesn't exist. Make sure Google Drive Desktop "
                    "is running and the path is correct."
                )
                self._error_label.show()
                return
            self._error_label.hide()
            self.accept()

        def get_values(self):
            return (
                self._username_edit.text().strip(),
                Path(self._gdrive_edit.text().strip()),
            )

    parent = get_maya_main_window()
    dialog = _Dialog(parent)
    if dialog.exec_() == QDialog.Accepted:
        return dialog.get_values()
    return None


# ------------------------------------------------------------------ #
#  Public API                                                         #
# ------------------------------------------------------------------ #

def prompt_first_launch(default_gdrive_root=None) -> Optional[Tuple[str, Path]]:
    """Show first-launch setup dialog.

    Tries PySide first (nicer UI), falls back to Maya's native dialogs
    if PySide isn't available yet.

    Returns (username, gdrive_root) or None if cancelled.
    """
    try:
        return _prompt_pyside(default_gdrive_root)
    except (ImportError, Exception):
        return _prompt_native(default_gdrive_root)


def prompt_username() -> Optional[str]:
    """Legacy wrapper. Returns just the username."""
    result = prompt_first_launch()
    if result:
        return result[0]
    return None
