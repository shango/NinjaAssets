"""Products tab - browse, search, filter, and preview assets.

Layout: a top filter bar (Category + Repo dropdowns, both carrying live counts,
plus a search box and a Refresh button) over a horizontal splitter with the
thumbnail grid on the left and the detail panel on the right.
"""

import logging
from typing import Set

from ninja_assets.maya_integration.ui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QComboBox, QLabel, QLineEdit, QPushButton,
    Qt, QTimer,
)
from ninja_assets.maya_integration.ui.thumbnail_widget import ThumbnailGrid
from ninja_assets.maya_integration.ui.preview_panel import PreviewPanel

logger = logging.getLogger(__name__)

_ALL_CATEGORIES = "All categories"
_ALL_REPOS = "All repos"


class ProductsTab(QWidget):
    """Main products browsing tab: filter bar + grid + detail panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._assets = []       # current filtered list
        self._all_assets = []   # everything loaded from the cache
        self._asset_map = {}    # uuid -> Asset
        self._build_ui()
        self._setup_connections()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # --- top filter bar -------------------------------------------------
        top = QHBoxLayout()
        top.setSpacing(6)

        self._cat_combo = QComboBox()
        self._cat_combo.setToolTip("Filter assets by category")
        self._cat_combo.setMinimumWidth(150)
        self._repo_combo = QComboBox()
        self._repo_combo.setToolTip("Filter assets by the remote repo they came from")
        self._repo_combo.setMinimumWidth(150)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search assets…")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setToolTip("Type to filter assets by name")

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setToolTip("Reload the library from the local cache")

        top.addWidget(QLabel("Category:"))
        top.addWidget(self._cat_combo)
        top.addWidget(QLabel("Repo:"))
        top.addWidget(self._repo_combo)
        top.addWidget(self._search_edit, 1)
        top.addWidget(self._refresh_btn)
        outer.addLayout(top)

        # --- splitter: grid | detail ---------------------------------------
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)

        grid_size = self._get_config_value("grid_thumbnail_size", 128)
        self._grid = ThumbnailGrid(thumb_size=grid_size)
        splitter.addWidget(self._grid)

        preview_size = self._get_config_value("preview_thumbnail_size", 320)
        self._preview = PreviewPanel(preview_size=preview_size)
        splitter.addWidget(self._preview)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, 1)

        # --- status line ----------------------------------------------------
        self._status = QLabel("")
        self._status.setObjectName("muted")
        outer.addWidget(self._status)

        # Debounce timer for search-as-you-type.
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)

    def _setup_connections(self):
        self._cat_combo.currentIndexChanged.connect(self._apply_filters)
        self._repo_combo.currentIndexChanged.connect(self._apply_filters)
        self._search_edit.textChanged.connect(lambda _t: self._search_timer.start())
        self._search_timer.timeout.connect(self._apply_filters)
        self._refresh_btn.clicked.connect(self.refresh)
        self._grid.asset_selected.connect(self._on_asset_selected)
        self._grid.asset_double_clicked.connect(self._on_asset_double_clicked)

    # --- Public API ---

    def refresh(self):
        """Re-query the cache, rebuild filter combos, and repopulate the grid."""
        cache = self._get_cache()
        if cache is None:
            self._all_assets = []
            self._asset_map = {}
            self._grid.clear()
            self._preview.clear()
            self._status.setText("Library not available.")
            return

        self._all_assets = cache.search_assets(query="", limit=100000)
        self._asset_map = {a.uuid: a for a in self._all_assets}

        self._rebuild_combo(self._cat_combo, _ALL_CATEGORIES,
                            cache.get_categories_with_counts())
        self._rebuild_combo(self._repo_combo, _ALL_REPOS,
                            cache.get_repos_with_counts())
        self._apply_filters()

    def on_assets_changed(self, changed_uuids: Set[str]):
        """Called when the sync engine reports changes. Refresh if any visible."""
        if changed_uuids & set(self._asset_map.keys()):
            self.refresh()

    # --- Internal ---

    def _get_config_value(self, attr, default):
        try:
            from ninja_assets.maya_integration import plugin
            config = plugin.get_config()
            if config:
                return getattr(config, attr, default)
        except Exception:
            pass
        return default

    def _get_cache(self):
        try:
            from ninja_assets.maya_integration import plugin
            return plugin.get_cache()
        except Exception:
            return None

    @staticmethod
    def _rebuild_combo(combo, all_label, counts):
        """Repopulate a filter combo as 'All (N)' + 'Name (count)' entries.

        The real filter value is stored in itemData (None for the 'All' row);
        the visible text carries the count. The prior selection is preserved
        when that value still exists after a rescan.
        """
        previous = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        total = sum(counts.values())
        combo.addItem("{} ({})".format(all_label, total), None)
        for name in sorted(counts):
            combo.addItem("{} ({})".format(name, counts[name]), name)
        # Restore the previous selection if it survived the rescan.
        idx = combo.findData(previous) if previous is not None else 0
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _apply_filters(self, *args):
        """Filter the loaded assets by category, repo, and search text."""
        category = self._cat_combo.currentData()
        source_repo = self._repo_combo.currentData()
        query = self._search_edit.text().strip().lower()

        filtered = self._all_assets
        if category:
            filtered = [a for a in filtered if a.category == category]
        if source_repo:
            filtered = [a for a in filtered if a.source_repo == source_repo]
        if query:
            filtered = [a for a in filtered if query in a.name.lower()]

        self._assets = filtered
        self._grid.set_assets(filtered)
        self._status.setText(
            "Showing {}/{} assets".format(len(filtered), len(self._all_assets))
        )

    def _on_asset_selected(self, uuid):
        asset = self._asset_map.get(uuid)
        if asset:
            self._preview.set_asset(asset)
        else:
            self._preview.clear()

    def _on_asset_double_clicked(self, uuid):
        asset = self._asset_map.get(uuid)
        if asset:
            try:
                from ninja_assets.maya_integration import commands
                commands.import_asset(asset)
            except Exception as e:
                logger.error("Import on double-click failed: %s", e)
