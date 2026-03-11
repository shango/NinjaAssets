"""Main NinjaAssets floating window."""

import logging
from datetime import datetime

from ninja_assets.maya_integration.ui.qt_compat import (
    QMainWindow, QTabWidget, QLabel, QStatusBar, Qt,
)
from ninja_assets.maya_integration.utils.maya_utils import get_maya_main_window

logger = logging.getLogger(__name__)


class NinjaAssetsWindow(QMainWindow):
    """Main browser window with Products and Scenefiles tabs."""

    def __init__(self, parent=None):
        if parent is None:
            parent = get_maya_main_window()
        super().__init__(parent)

        self.setWindowTitle("NinjaAssets")
        self.resize(1000, 700)
        self.setWindowFlags(self.windowFlags() | Qt.Window)

        # Store references
        self._config = self._get_config()
        self._cache = self._get_cache()

        # Tab widget
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        # Products tab
        self._products_tab = self._create_products_tab()
        self._tabs.addTab(self._products_tab, "Products")
        self._tabs.setTabToolTip(0, "Browse and import assets from the studio library")

        # Scenefiles tab
        self._scenefiles_tab = self._create_scenefiles_tab()
        self._tabs.addTab(self._scenefiles_tab, "Scenefiles")
        self._tabs.setTabToolTip(1, "Save and manage versions of your current scene")

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._update_sync_status()

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
