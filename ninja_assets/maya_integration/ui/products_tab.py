"""Products tab - browse, search, filter, and preview assets."""

import logging
from typing import List, Optional, Set

from ninja_assets.maya_integration.ui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QLabel, QLineEdit,
    QRadioButton, QButtonGroup, QGroupBox, QFrame,
    Qt, QTimer, QSizePolicy,
)
from ninja_assets.maya_integration.ui.thumbnail_widget import ThumbnailGrid
from ninja_assets.maya_integration.ui.preview_panel import PreviewPanel
from ninja_assets.core.models import Asset, AssetStatus

logger = logging.getLogger(__name__)


class ProductsTab(QWidget):
    """Main products browsing tab with sidebar filters, grid, and preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._assets = []       # current filtered list
        self._all_assets = []   # all assets from cache
        self._asset_map = {}    # uuid -> Asset
        self._build_ui()
        self._setup_connections()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- Left Sidebar ---
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(6, 6, 6, 6)

        # Categories section
        cat_group = QGroupBox("CATEGORIES")
        cat_layout = QVBoxLayout(cat_group)
        self._cat_tree = QTreeWidget()
        self._cat_tree.setHeaderHidden(True)
        self._cat_tree.setRootIsDecorated(False)
        cat_layout.addWidget(self._cat_tree)
        sidebar_layout.addWidget(cat_group)

        # Status section
        status_group = QGroupBox("STATUS")
        status_layout = QVBoxLayout(status_group)
        self._status_group = QButtonGroup(self)
        self._status_radios = {}

        for label_text, value in [("All", None), ("WIP", "wip"),
                                  ("Review", "review"), ("Approved", "approved")]:
            radio = QRadioButton(label_text)
            self._status_group.addButton(radio)
            self._status_radios[value] = radio
            status_layout.addWidget(radio)

        self._status_radios[None].setChecked(True)
        sidebar_layout.addWidget(status_group)
        sidebar_layout.addStretch()

        main_layout.addWidget(sidebar)

        # --- Center + Bottom (splitter) ---
        right_splitter = QSplitter(Qt.Vertical)

        # Center: search + grid
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(4, 4, 4, 0)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search assets...")
        center_layout.addWidget(self._search_edit)

        self._grid = ThumbnailGrid(thumb_size=100)
        center_layout.addWidget(self._grid)

        right_splitter.addWidget(center_widget)

        # Bottom: preview panel
        self._preview = PreviewPanel(preview_size=250)
        right_splitter.addWidget(self._preview)

        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(right_splitter, stretch=1)

        # Debounce timer for search
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)

    def _setup_connections(self):
        self._cat_tree.currentItemChanged.connect(self._on_filter_changed)
        self._status_group.buttonClicked.connect(self._on_filter_changed)
        self._search_edit.textChanged.connect(self._on_search_text_changed)
        self._search_timer.timeout.connect(self._on_filter_changed)
        self._grid.asset_selected.connect(self._on_asset_selected)
        self._grid.asset_double_clicked.connect(self._on_asset_double_clicked)

    # --- Public API ---

    def refresh(self):
        """Re-query cache and update the grid with current filters."""
        cache = self._get_cache()
        if cache is None:
            self._all_assets = []
            self._asset_map = {}
            self._grid.clear()
            self._preview.clear()
            return

        # Pass current filters to the DB query for efficiency
        category = self._get_selected_category()
        status = self._get_selected_status()
        query = self._search_edit.text().strip().lower()

        self._all_assets = cache.search_assets(
            query=query,
            category=category,
            status=status,
            limit=10000,
        )
        self._asset_map = {a.uuid: a for a in self._all_assets}

        self._update_category_tree()
        self._update_status_counts()
        self._apply_filters()

    def on_assets_changed(self, changed_uuids: Set[str]):
        """Called when sync engine reports changes. Refresh if any visible."""
        visible_uuids = set(self._asset_map.keys())
        if changed_uuids & visible_uuids:
            self.refresh()

    # --- Internal ---

    def _get_cache(self):
        try:
            from ninja_assets.maya_integration import plugin
            return plugin.get_cache()
        except Exception:
            return None

    def _update_category_tree(self):
        """Rebuild category tree with counts."""
        cache = self._get_cache()
        counts = cache.get_categories_with_counts() if cache else {}
        total = sum(counts.values())

        self._cat_tree.blockSignals(True)
        current_cat = self._get_selected_category()
        self._cat_tree.clear()

        all_item = QTreeWidgetItem(["All ({})".format(total)])
        all_item.setData(0, Qt.UserRole, None)
        self._cat_tree.addTopLevelItem(all_item)

        for cat in sorted(counts.keys()):
            item = QTreeWidgetItem(["{} ({})".format(cat, counts[cat])])
            item.setData(0, Qt.UserRole, cat)
            self._cat_tree.addTopLevelItem(item)
            if cat == current_cat:
                self._cat_tree.setCurrentItem(item)

        if not self._cat_tree.currentItem():
            self._cat_tree.setCurrentItem(all_item)

        self._cat_tree.blockSignals(False)

    def _update_status_counts(self):
        """Update radio button labels with counts."""
        counts = {"wip": 0, "review": 0, "approved": 0}
        for a in self._all_assets:
            counts[a.status.value] = counts.get(a.status.value, 0) + 1
        total = len(self._all_assets)

        self._status_radios[None].setText(f"All ({total})")
        self._status_radios["wip"].setText(f"WIP ({counts['wip']})")
        self._status_radios["review"].setText(f"Review ({counts['review']})")
        self._status_radios["approved"].setText(f"Approved ({counts['approved']})")

    def _get_selected_category(self) -> Optional[str]:
        item = self._cat_tree.currentItem()
        if item:
            return item.data(0, Qt.UserRole)
        return None

    def _get_selected_status(self) -> Optional[str]:
        for value, radio in self._status_radios.items():
            if radio.isChecked():
                return value
        return None

    def _apply_filters(self):
        """Filter all_assets by current category, status, and search text."""
        category = self._get_selected_category()
        status = self._get_selected_status()
        query = self._search_edit.text().strip().lower()

        filtered = self._all_assets

        if category:
            filtered = [a for a in filtered if a.category == category]
        if status:
            filtered = [a for a in filtered if a.status.value == status]
        if query:
            filtered = [a for a in filtered if query in a.name.lower()]

        self._assets = filtered
        self._grid.set_assets(filtered)

    def _on_filter_changed(self, *args):
        self._apply_filters()

    def _on_search_text_changed(self, text):
        self._search_timer.start()

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
