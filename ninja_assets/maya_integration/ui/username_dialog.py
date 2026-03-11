"""First-launch setup dialog — username and GDrive asset root."""

from pathlib import Path
from typing import Optional, Tuple

from ninja_assets.maya_integration.ui.qt_compat import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QFileDialog, QGroupBox,
)
from ninja_assets.maya_integration.utils.maya_utils import get_maya_main_window
from ninja_assets.config import _default_gdrive_root


class FirstLaunchDialog(QDialog):
    """Setup dialog shown on first launch.

    Asks for a studio username and the path to the shared asset drive
    (typically a Shared Drive folder on Google Drive).
    """

    def __init__(self, default_gdrive_root=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NinjaAssets — First-Time Setup")
        self.setMinimumWidth(500)

        self._gdrive_root = default_gdrive_root or _default_gdrive_root()
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Welcome
        welcome = QLabel(
            "Welcome to NinjaAssets!\n\n"
            "Before you start, we need two things:"
        )
        welcome.setWordWrap(True)
        layout.addWidget(welcome)

        # -- Asset drive --
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
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._gdrive_edit)
        path_row.addWidget(browse_btn)
        drive_layout.addLayout(path_row)

        drive_group.setLayout(drive_layout)
        layout.addWidget(drive_group)

        # -- Username --
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
        user_form.addRow("Username:", self._username_edit)
        user_layout.addLayout(user_form)

        user_group.setLayout(user_layout)
        layout.addWidget(user_group)

        # -- Error label (hidden by default) --
        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #FF4444; font-weight: bold;")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        # -- Buttons --
        layout.addStretch()
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._ok_btn = QPushButton("Get Started")
        self._cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(self._ok_btn)
        btn_layout.addWidget(self._cancel_btn)
        layout.addLayout(btn_layout)

    def _connect_signals(self):
        self._ok_btn.clicked.connect(self._on_ok)
        self._cancel_btn.clicked.connect(self.reject)

    def _browse(self):
        """Open folder picker starting at the current GDrive root."""
        start_path = self._gdrive_edit.text() or str(self._gdrive_root)
        directory = QFileDialog.getExistingDirectory(
            self, "Select Asset Drive Folder", start_path
        )
        if directory:
            self._gdrive_edit.setText(directory)

    def _on_ok(self):
        """Validate and accept."""
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
                "That folder doesn't exist. Make sure Google Drive Desktop is running "
                "and the path is correct."
            )
            self._error_label.show()
            return

        self._error_label.hide()
        self.accept()

    def get_values(self) -> Tuple[str, Path]:
        """Return (username, gdrive_root) after dialog is accepted."""
        return (
            self._username_edit.text().strip(),
            Path(self._gdrive_edit.text().strip()),
        )


def prompt_first_launch(default_gdrive_root=None) -> Optional[Tuple[str, Path]]:
    """Show first-launch setup dialog.

    Returns (username, gdrive_root) or None if cancelled.
    """
    parent = get_maya_main_window()
    dialog = FirstLaunchDialog(
        default_gdrive_root=default_gdrive_root, parent=parent
    )
    if dialog.exec_() == QDialog.Accepted:
        return dialog.get_values()
    return None


# Backwards compat — old code calls prompt_username()
def prompt_username() -> Optional[str]:
    """Legacy wrapper. Returns just the username."""
    result = prompt_first_launch()
    if result:
        return result[0]
    return None
