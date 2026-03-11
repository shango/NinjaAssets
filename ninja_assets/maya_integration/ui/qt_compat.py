"""
PySide2/PySide6 compatibility shim.

Maya 2022-2023 ships PySide2 (Qt5), Maya 2024+ ships PySide6 (Qt6).
This module provides a single import point so the rest of the codebase
doesn't need try/except blocks everywhere.
"""

try:
    from PySide6.QtWidgets import (  # noqa: F401
        QApplication, QMainWindow, QWidget, QDialog,
        QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
        QTabWidget, QSplitter, QGroupBox, QFrame,
        QPushButton, QLabel, QLineEdit, QTextEdit, QSpinBox,
        QComboBox, QCheckBox, QRadioButton, QButtonGroup,
        QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
        QHeaderView, QAbstractItemView,
        QScrollArea, QSizePolicy, QSpacerItem,
        QMenu, QAction, QToolBar, QStatusBar,
        QFileDialog, QMessageBox, QInputDialog,
        QStyle, QStyleFactory,
        QLayout, QLayoutItem,
    )
    from PySide6.QtCore import (  # noqa: F401
        Qt, Signal, Slot, QObject, QThread, QTimer,
        QSize, QPoint, QRect, QUrl,
        QRunnable, QThreadPool,
        QMimeData, QEvent,
    )
    from PySide6.QtGui import (  # noqa: F401
        QPixmap, QImage, QIcon, QFont, QColor, QPalette,
        QCursor, QPainter, QBrush, QPen,
        QKeySequence, QShortcut,
        QDesktopServices,
    )
    from shiboken6 import wrapInstance  # noqa: F401

    QT_VERSION = 6

except ImportError:
    from PySide2.QtWidgets import (  # noqa: F401
        QApplication, QMainWindow, QWidget, QDialog,
        QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
        QTabWidget, QSplitter, QGroupBox, QFrame,
        QPushButton, QLabel, QLineEdit, QTextEdit, QSpinBox,
        QComboBox, QCheckBox, QRadioButton, QButtonGroup,
        QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
        QHeaderView, QAbstractItemView,
        QScrollArea, QSizePolicy, QSpacerItem,
        QMenu, QAction, QToolBar, QStatusBar,
        QFileDialog, QMessageBox, QInputDialog,
        QStyle, QStyleFactory,
        QShortcut,
        QLayout, QLayoutItem,
    )
    from PySide2.QtCore import (  # noqa: F401
        Qt, Signal, Slot, QObject, QThread, QTimer,
        QSize, QPoint, QRect, QUrl,
        QRunnable, QThreadPool,
        QMimeData, QEvent,
    )
    from PySide2.QtGui import (  # noqa: F401
        QPixmap, QImage, QIcon, QFont, QColor, QPalette,
        QCursor, QPainter, QBrush, QPen,
        QKeySequence,
        QDesktopServices,
    )
    from shiboken2 import wrapInstance  # noqa: F401

    QT_VERSION = 2
