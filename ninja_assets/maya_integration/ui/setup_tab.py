"""Setup tab - configure local + remote repos and scan the asset library."""

import logging
from pathlib import Path

from ninja_assets.maya_integration.ui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QProgressBar,
    QFileDialog, QInputDialog, QMessageBox,
    Qt, Signal, QRunnable, QThreadPool, QObject,
)
from ninja_assets.config import Repo, find_remote_by_path, find_remote_by_name

logger = logging.getLogger(__name__)


class _ScanSignals(QObject):
    finished = Signal(int)   # number of changed assets
    failed = Signal(str)


class _ScanTask(QRunnable):
    """Run a full library scan off the UI thread so Maya stays responsive."""

    def __init__(self, config, cache):
        super().__init__()
        self._config = config
        self._cache = cache
        self.signals = _ScanSignals()

    def run(self):
        try:
            from ninja_assets.sync.scanner import AssetScanner
            scanner = AssetScanner(self._config, self._cache)
            changed = scanner.full_scan()
            self.signals.finished.emit(len(changed))
        except Exception as exc:  # noqa: BLE001 - report any failure to the UI
            logger.exception("Library scan failed")
            self.signals.failed.emit(str(exc))


class SetupTab(QWidget):
    """Configure the local pull destination and the remote repos to scan."""

    repos_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = None
        self._scanning = False
        self._build_ui()
        self._connect_signals()
        self._load_values()

    # --- UI construction ---

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # -- Local repo --
        local_group = QGroupBox("Local Repo")
        local_form = QFormLayout(local_group)
        self._local_edit = QLineEdit()
        self._local_edit.setToolTip(
            "Folder where assets are copied when you 'pull to local' on import"
        )
        local_browse = QPushButton("Browse...")
        local_browse.clicked.connect(self._browse_local)
        local_row = QHBoxLayout()
        local_row.addWidget(self._local_edit)
        local_row.addWidget(local_browse)
        local_form.addRow("Local repo:", local_row)
        layout.addWidget(local_group)

        # -- Remote repos --
        remote_group = QGroupBox("Remote Repos")
        remote_layout = QVBoxLayout(remote_group)
        remote_layout.addWidget(
            QLabel("Cloud/synced folders to scan for assets:")
        )
        self._repo_list = QListWidget()
        self._repo_list.setToolTip("Each remote is scanned into the searchable library")
        remote_layout.addWidget(self._repo_list)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add...")
        self._edit_btn = QPushButton("Rename...")
        self._remove_btn = QPushButton("Remove")
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._edit_btn)
        btn_row.addWidget(self._remove_btn)
        btn_row.addStretch()
        remote_layout.addLayout(btn_row)
        layout.addWidget(remote_group)

        # -- Scan --
        scan_group = QGroupBox("Library")
        scan_layout = QVBoxLayout(scan_group)
        scan_row = QHBoxLayout()
        self._scan_btn = QPushButton("Scan Remotes Now")
        self._scan_btn.setToolTip(
            "Build the searchable metadata + thumbnail library from all remotes"
        )
        scan_row.addWidget(self._scan_btn)
        scan_row.addStretch()
        scan_layout.addLayout(scan_row)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setVisible(False)
        scan_layout.addWidget(self._progress)
        self._status_label = QLabel("")
        self._status_label.setObjectName("muted")
        scan_layout.addWidget(self._status_label)
        layout.addWidget(scan_group)

        layout.addStretch()

        # -- Save --
        save_row = QHBoxLayout()
        save_row.addStretch()
        self._save_btn = QPushButton("Save")
        save_row.addWidget(self._save_btn)
        layout.addLayout(save_row)

    def _connect_signals(self):
        self._add_btn.clicked.connect(self._on_add_remote)
        self._edit_btn.clicked.connect(self._on_rename_remote)
        self._remove_btn.clicked.connect(self._on_remove_remote)
        self._scan_btn.clicked.connect(self._on_scan)
        self._save_btn.clicked.connect(self._on_save)

    # --- Config <-> widgets ---

    def _load_values(self):
        try:
            from ninja_assets.maya_integration import plugin
            self._config = plugin.get_config()
        except Exception:
            self._config = None
        if self._config is None:
            return

        self._local_edit.setText(
            str(self._config.local_repo) if self._config.local_repo else ""
        )
        self._repo_list.clear()
        for repo in self._config.remotes:
            self._add_repo_item(repo)

    def _add_repo_item(self, repo: Repo):
        item = QListWidgetItem(f"{repo.name} — {repo.path}")
        item.setData(Qt.UserRole, repo)
        self._repo_list.addItem(item)

    def _collect_remotes(self):
        remotes = []
        for i in range(self._repo_list.count()):
            remotes.append(self._repo_list.item(i).data(Qt.UserRole))
        return remotes

    # --- Slots ---

    def _browse_local(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Local Repo", self._local_edit.text()
        )
        if directory:
            self._local_edit.setText(directory)

    def _on_add_remote(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Remote Repo")
        if not directory:
            return
        existing = self._collect_remotes()
        dup = find_remote_by_path(existing, directory)
        if dup is not None:
            QMessageBox.information(
                self,
                "Already Registered",
                f"That folder is already registered as remote '{dup.name}'.",
            )
            return
        default_name = Path(directory).name or directory
        name, ok = QInputDialog.getText(
            self, "Remote Name", "Name for this remote:", text=default_name
        )
        if not ok:
            return
        name = (name or default_name).strip()
        if find_remote_by_name(existing, name) is not None:
            QMessageBox.warning(
                self,
                "Duplicate Name",
                f"A remote named '{name}' already exists. Pick a different name.",
            )
            return
        self._add_repo_item(Repo(name=name, path=Path(directory)))

    def _on_rename_remote(self):
        item = self._repo_list.currentItem()
        if item is None:
            return
        repo = item.data(Qt.UserRole)
        name, ok = QInputDialog.getText(
            self, "Rename Remote", "Name:", text=repo.name
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        others = [r for r in self._collect_remotes() if r is not repo]
        if find_remote_by_name(others, name) is not None:
            QMessageBox.warning(
                self,
                "Duplicate Name",
                f"A remote named '{name}' already exists.",
            )
            return
        repo.name = name
        item.setText(f"{repo.name} — {repo.path}")
        item.setData(Qt.UserRole, repo)

    def _on_remove_remote(self):
        row = self._repo_list.currentRow()
        if row >= 0:
            self._repo_list.takeItem(row)

    def _on_save(self):
        if self._config is None:
            return
        local_text = self._local_edit.text().strip()
        self._config.local_repo = Path(local_text) if local_text else None
        if self._config.local_repo is not None:
            self._config.local_repo.mkdir(parents=True, exist_ok=True)
        self._config.remotes = self._collect_remotes()
        self._config.save()
        self._status_label.setText("Saved.")
        self.repos_changed.emit()

    def _on_scan(self):
        if self._scanning:
            return
        # Persist current edits first so the scan uses them.
        self._on_save()

        try:
            from ninja_assets.maya_integration import plugin
            cache = plugin.get_cache()
        except Exception:
            cache = None
        if self._config is None or cache is None:
            QMessageBox.warning(
                self, "Scan", "NinjaAssets is not fully initialized."
            )
            return

        self._scanning = True
        self._scan_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status_label.setText("Scanning remotes...")

        task = _ScanTask(self._config, cache)
        task.signals.finished.connect(self._on_scan_finished)
        task.signals.failed.connect(self._on_scan_failed)
        QThreadPool.globalInstance().start(task)

    def _on_scan_finished(self, changed_count: int):
        self._scanning = False
        self._scan_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._status_label.setText(
            f"Scan complete — {changed_count} asset(s) updated."
        )
        self.repos_changed.emit()

    def _on_scan_failed(self, message: str):
        self._scanning = False
        self._scan_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._status_label.setText(f"Scan failed: {message}")
