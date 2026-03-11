"""NinjaAssets Settings Dialog."""

from ninja_assets.maya_integration.ui.qt_compat import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QPushButton,
    QFileDialog, QGroupBox,
    Signal,
)


class SettingsDialog(QDialog):
    """Settings dialog for NinjaAssets configuration."""

    grid_size_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NinjaAssets Settings")
        self.resize(450, 400)

        self._config = None
        self._original_grid_size = None

        self._build_ui()
        self._load_values()
        self._connect_signals()

    def _build_ui(self):
        """Build the dialog layout."""
        main_layout = QVBoxLayout(self)

        # -- Paths group --
        paths_group = QGroupBox("Paths")
        paths_form = QFormLayout()

        self._gdrive_edit = QLineEdit()
        self._gdrive_edit.setToolTip("Path to the shared asset folder on Google Drive")
        browse_btn = QPushButton("Browse...")
        browse_btn.setToolTip("Pick the shared folder in a file browser")
        browse_btn.setObjectName("browse_btn")
        browse_btn.clicked.connect(self._browse_gdrive)
        gdrive_layout = QHBoxLayout()
        gdrive_layout.addWidget(self._gdrive_edit)
        gdrive_layout.addWidget(browse_btn)
        paths_form.addRow("GDrive Root:", gdrive_layout)

        paths_group.setLayout(paths_form)
        main_layout.addWidget(paths_group)

        # -- User group --
        user_group = QGroupBox("User")
        user_form = QFormLayout()

        self._username_edit = QLineEdit()
        self._username_edit.setToolTip("The name shown when you publish or save")
        user_form.addRow("Username:", self._username_edit)

        user_group.setLayout(user_form)
        main_layout.addWidget(user_group)

        # -- Sync group --
        sync_group = QGroupBox("Sync")
        sync_form = QFormLayout()

        self._sync_interval_spin = QSpinBox()
        self._sync_interval_spin.setRange(10, 300)
        self._sync_interval_spin.setSuffix(" seconds")
        self._sync_interval_spin.setToolTip("How often to check Google Drive for changes — higher = less background load")
        sync_form.addRow("Sync Interval:", self._sync_interval_spin)

        self._changelog_poll_spin = QSpinBox()
        self._changelog_poll_spin.setRange(5, 120)
        self._changelog_poll_spin.setSuffix(" seconds")
        self._changelog_poll_spin.setToolTip("How often to check the shared changelog for new publishes")
        sync_form.addRow("Changelog Poll:", self._changelog_poll_spin)

        sync_group.setLayout(sync_form)
        main_layout.addWidget(sync_group)

        # -- UI group --
        ui_group = QGroupBox("UI")
        ui_form = QFormLayout()

        self._grid_size_spin = QSpinBox()
        self._grid_size_spin.setRange(50, 200)
        self._grid_size_spin.setSuffix(" px")
        self._grid_size_spin.setToolTip("Size of thumbnails in the asset browser grid")
        ui_form.addRow("Thumbnail Grid Size:", self._grid_size_spin)

        self._preview_size_spin = QSpinBox()
        self._preview_size_spin.setRange(100, 500)
        self._preview_size_spin.setSuffix(" px")
        self._preview_size_spin.setToolTip("Size of the large preview thumbnail at the bottom")
        ui_form.addRow("Preview Thumbnail Size:", self._preview_size_spin)

        ui_group.setLayout(ui_form)
        main_layout.addWidget(ui_group)

        # -- Buttons --
        main_layout.addStretch()
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._ok_btn = QPushButton("OK")
        self._cancel_btn = QPushButton("Cancel")
        self._apply_btn = QPushButton("Apply")

        btn_layout.addWidget(self._ok_btn)
        btn_layout.addWidget(self._cancel_btn)
        btn_layout.addWidget(self._apply_btn)

        main_layout.addLayout(btn_layout)

    def _connect_signals(self):
        """Wire up button signals."""
        self._ok_btn.clicked.connect(self._on_ok)
        self._cancel_btn.clicked.connect(self.reject)
        self._apply_btn.clicked.connect(self._on_apply)

    def _load_values(self):
        """Load current values from config."""
        from ninja_assets.maya_integration import plugin
        self._config = plugin.get_config()
        if self._config is None:
            return

        self._gdrive_edit.setText(str(self._config.gdrive_root))
        self._username_edit.setText(self._config.username or "")
        self._sync_interval_spin.setValue(self._config.sync_interval_seconds)
        self._changelog_poll_spin.setValue(self._config.changelog_poll_interval)
        self._grid_size_spin.setValue(self._config.grid_thumbnail_size)
        self._preview_size_spin.setValue(self._config.preview_thumbnail_size)
        self._original_grid_size = self._config.grid_thumbnail_size

    def _browse_gdrive(self):
        """Open a directory picker for GDrive root."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select GDrive Root", self._gdrive_edit.text()
        )
        if directory:
            self._gdrive_edit.setText(directory)

    def _apply_settings(self):
        """Write current widget values back to config and save."""
        if self._config is None:
            return

        from pathlib import Path
        self._config.gdrive_root = Path(self._gdrive_edit.text())
        self._config.username = self._username_edit.text() or None
        self._config.sync_interval_seconds = self._sync_interval_spin.value()
        self._config.changelog_poll_interval = self._changelog_poll_spin.value()
        self._config.grid_thumbnail_size = self._grid_size_spin.value()
        self._config.preview_thumbnail_size = self._preview_size_spin.value()
        self._config.save()

        new_grid_size = self._grid_size_spin.value()
        if new_grid_size != self._original_grid_size:
            self.grid_size_changed.emit(new_grid_size)
            self._original_grid_size = new_grid_size

    def _on_apply(self):
        """Handle Apply button."""
        self._apply_settings()

    def _on_ok(self):
        """Handle OK button."""
        self._apply_settings()
        self.accept()
