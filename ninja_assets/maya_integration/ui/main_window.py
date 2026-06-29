"""Main NinjaAssets floating window."""

import logging
from datetime import datetime

from ninja_assets import __version__
from ninja_assets.maya_integration.ui import style
from ninja_assets.maya_integration.ui.qt_compat import (
    QMainWindow, QTabWidget, QLabel, QStatusBar, Qt,
    QWidget, QVBoxLayout, QHBoxLayout,
)
from ninja_assets.maya_integration.utils.maya_utils import get_maya_main_window

logger = logging.getLogger(__name__)


class NinjaAssetsWindow(QMainWindow):
    """Main browser window with Products and Scenefiles tabs."""

    def __init__(self, parent=None):
        if parent is None:
            parent = get_maya_main_window()
        super().__init__(parent)

        self.setWindowTitle("Ninja Browser")
        self.resize(1100, 750)
        self.setMinimumSize(800, 500)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        # One centralized stylesheet on the window only (not the QApplication),
        # so the tool is themed without bleeding into Maya's other UI.
        self.setStyleSheet(style.stylesheet())

        # Store references
        self._config = self._get_config()
        self._cache = self._get_cache()

        # Central layout: title header on top, tabs below
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._build_header())
        self.setCentralWidget(central)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        central_layout.addWidget(self._tabs, stretch=1)

        # Products tab
        self._products_tab = self._create_products_tab()
        self._tabs.addTab(self._products_tab, "Products")
        self._tabs.setTabToolTip(0, "Browse and import assets from the studio library")

        # Scenefiles tab
        self._scenefiles_tab = self._create_scenefiles_tab()
        self._tabs.addTab(self._scenefiles_tab, "Scenefiles")
        self._tabs.setTabToolTip(1, "Save and manage versions of your current scene")

        # Setup tab
        self._setup_tab = self._create_setup_tab()
        self._tabs.addTab(self._setup_tab, "Setup")
        self._tabs.setTabToolTip(2, "Configure local + remote repos and scan the library")

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._update_sync_status()

    def _build_header(self):
        """Title bar: 'Ninja Browser' wordmark with the version beside it.

        Font sizes/weights/colors come from the stylesheet (#appName,
        #appVersion); a programmatic QFont here would be overridden by the
        global ``QWidget { font-size }`` rule.
        """
        header = QWidget()
        header.setObjectName("appHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        title = QLabel("Ninja Browser")
        title.setObjectName("appName")
        layout.addWidget(title)

        version = QLabel(f"v{__version__}")
        version.setObjectName("appVersion")
        version.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        layout.addWidget(version)

        layout.addStretch()
        return header

    def _create_products_tab(self):
        """Create the products tab, with fallback if not yet available."""
        try:
            from ninja_assets.maya_integration.ui.products_tab import ProductsTab
            tab = ProductsTab()
            tab.refresh()
            return tab
        except Exception as e:
            logger.warning("Could not load ProductsTab: %s", e)
            placeholder = QLabel("Products tab is not available yet.")
            placeholder.setAlignment(Qt.AlignCenter)
            return placeholder

    def _create_scenefiles_tab(self):
        """Create the scenefiles tab, with fallback if not yet available."""
        try:
            from ninja_assets.maya_integration.ui.scenefiles_tab import ScenefilesTab
            return ScenefilesTab()
        except Exception as e:
            logger.debug("ScenefilesTab not available: %s", e)
            placeholder = QLabel("Scenefiles tab coming soon.")
            placeholder.setAlignment(Qt.AlignCenter)
            return placeholder

    def _create_setup_tab(self):
        """Create the setup tab, with fallback if not yet available."""
        try:
            from ninja_assets.maya_integration.ui.setup_tab import SetupTab
            tab = SetupTab()
            tab.repos_changed.connect(self._on_repos_changed)
            return tab
        except Exception as e:
            logger.warning("Could not load SetupTab: %s", e)
            placeholder = QLabel("Setup tab is not available yet.")
            placeholder.setAlignment(Qt.AlignCenter)
            return placeholder

    def _on_repos_changed(self):
        """Refresh the products tab after repos are reconfigured or rescanned."""
        if hasattr(self._products_tab, 'refresh'):
            self._products_tab.refresh()

    def on_assets_changed(self, changed_uuids):
        """Delegate asset-change notifications to the products tab."""
        if hasattr(self._products_tab, 'on_assets_changed'):
            self._products_tab.on_assets_changed(changed_uuids)
        self._update_sync_status()

    def _update_sync_status(self):
        """Update the status bar with sync info."""
        now = datetime.utcnow().strftime("%H:%M:%S")
        self._status_bar.showMessage(f"Synced: {now}")

    @staticmethod
    def _get_config():
        try:
            from ninja_assets.maya_integration import plugin
            return plugin.get_config()
        except Exception:
            return None

    @staticmethod
    def _get_cache():
        try:
            from ninja_assets.maya_integration import plugin
            return plugin.get_cache()
        except Exception:
            return None

    def showEvent(self, event):
        """Refresh products tab when window is shown."""
        super().showEvent(event)
        if hasattr(self._products_tab, 'refresh'):
            self._products_tab.refresh()
