"""A single, self-contained dark stylesheet for the Ninja Browser window.

Returns a QSS string applied to the ``NinjaAssetsWindow`` instance only (set on
the window, not the ``QApplication``), so it themes the tool without bleeding
into Maya's other UI. No external image assets - all chrome is drawn by Qt from
these rules. Centralizing the look here is what replaced the inline
``setStyleSheet`` calls that were previously scattered across every widget.

Conventions used by the widgets (objectName / dynamic property -> rule):
  * branded header     -> ``#appHeader``, ``#appName``, ``#appVersion``
  * detail panel       -> ``#assetName``, ``#fieldLabel``, ``#muted``,
                          ``#description``, ``#previewImage``, ``#typeBadge``
  * section captions    -> ``#sectionHeading``
  * primary action btn -> ``button.setProperty("accent", True)``
  * positive action    -> ``button.setProperty("positive", True)``
  * selected grid card -> ``card.setProperty("selected", True)``
"""

# Brand colors. Accent blue matches the shelf icon; version yellow the header.
ACCENT = "#4D9EFF"
VERSION_YELLOW = "#FFD33D"

# Palette - tuned to sit comfortably next to Maya's dark theme.
_BG = "#2b2b2b"          # window background
_SURFACE = "#323335"     # panels / inputs at rest
_SURFACE_HI = "#3c3d40"  # hover / raised
_BORDER = "#1d1d1f"      # separators / input borders
_TEXT = "#dcdcdc"
_MUTED = "#9a9a9a"


def stylesheet(accent: str = ACCENT) -> str:
    """Full QSS for the window, themed around ``accent`` (a hex color)."""
    accent_hi = _lighten(accent, 0.15)
    accent_dim = _darken(accent, 0.18)
    return """
    QWidget {{
        background: {bg};
        color: {text};
        font-size: 12px;
    }}
    QLabel {{ background: transparent; }}

    /* Branded app header: 'Ninja Browser' wordmark + version (font set in code) */
    QWidget#appHeader {{
        background: {surface};
        border-bottom: 1px solid {border};
    }}
    QLabel#appName {{
        color: {accent};
        font-family: "Segoe UI", "SF Pro Display", "Helvetica Neue", "Roboto", Arial;
        font-size: 22px;
        font-weight: 900;
    }}
    QLabel#appVersion {{
        color: {version}; font-size: 12px; font-weight: 600; padding-bottom: 3px;
    }}

    QLabel#assetName {{ font-size: 16px; font-weight: 600; color: #ffffff; }}
    /* Section captions: pass them already upper-cased - Qt QSS has no
       text-transform, so casing is done in code. */
    QLabel#sectionHeading {{
        font-size: 11px; font-weight: 600; color: {muted};
    }}
    QLabel#fieldLabel {{ color: {muted}; }}
    QLabel#muted {{ color: {muted}; }}
    QLabel#description {{ color: #c4c4c4; font-style: italic; }}

    /* Type badge - a rounded accent chip (per-category color set in code) */
    QLabel#typeBadge {{
        background: {accent_dim};
        color: #ffffff;
        border-radius: 9px;
        padding: 2px 10px;
        font-size: 11px;
        font-weight: 600;
    }}

    /* Preview image frame */
    QLabel#previewImage {{
        background: #232325;
        border: 1px solid {border};
        border-radius: 8px;
    }}

    QGroupBox {{
        border: 1px solid {border};
        border-radius: 6px;
        margin-top: 8px;
        padding-top: 6px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
        color: {muted};
    }}

    QTabWidget::pane {{ border: 1px solid {border}; border-radius: 6px; top: -1px; }}
    QTabBar::tab {{
        background: transparent; color: {muted};
        padding: 7px 18px; margin-right: 2px;
        border-top-left-radius: 6px; border-top-right-radius: 6px;
    }}
    QTabBar::tab:selected {{ background: {surface}; color: {text}; }}
    QTabBar::tab:hover:!selected {{ color: {text}; }}

    QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QSpinBox {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 5px;
        padding: 5px 8px;
        selection-background-color: {accent};
    }}
    QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus,
    QTextEdit:focus, QSpinBox:focus {{
        border: 1px solid {accent};
    }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox QAbstractItemView {{
        background: {surface}; border: 1px solid {border};
        selection-background-color: {accent};
    }}

    QPushButton {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 5px;
        padding: 6px 14px;
        color: {text};
    }}
    QPushButton:hover {{ background: {surface_hi}; }}
    QPushButton:pressed {{ background: {border}; }}
    QPushButton:disabled {{ color: #6a6a6a; background: #2e2e30; }}
    QPushButton[accent="true"] {{
        background: {accent}; border: 1px solid {accent}; color: #ffffff;
        font-weight: 600;
    }}
    QPushButton[accent="true"]:hover {{ background: {accent_hi}; }}
    QPushButton[accent="true"]:pressed {{ background: {accent_dim}; }}
    QPushButton[positive="true"] {{
        background: #3a9d5d; border: 1px solid #3a9d5d; color: #ffffff;
        font-weight: 600;
    }}
    QPushButton[positive="true"]:hover {{ background: #49b06d; }}
    QPushButton[positive="true"]:pressed {{ background: #2f8550; }}

    /* Compact ghost buttons used for path Copy/Open in the detail panel */
    QToolButton {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 5px;
        padding: 4px 8px;
        color: {muted};
    }}
    QToolButton:hover {{ background: {surface_hi}; color: {text}; }}
    QToolButton:pressed {{ background: {border}; }}

    /* Thumbnail grid cards (ThumbnailCard sets the 'selected' property) */
    ThumbnailCard {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
    }}
    ThumbnailCard:hover {{ background: #333; border: 1px solid #555; }}
    ThumbnailCard[selected="true"] {{
        background: #2a3a4a; border: 2px solid {accent};
    }}
    QLabel#cardThumb {{ background: #2b2b2b; border-radius: 3px; }}
    QLabel#cardName {{ color: #ddd; }}
    QLabel#cardVersion {{ color: {muted}; }}

    QListWidget, QTreeWidget {{
        background: #262628;
        border: 1px solid {border};
        border-radius: 6px;
        outline: none;
    }}
    QListWidget::item, QTreeWidget::item {{
        padding: 4px 6px; border-radius: 4px; color: {text};
    }}
    QListWidget::item:hover, QTreeWidget::item:hover {{ background: {surface_hi}; }}
    QListWidget::item:selected, QTreeWidget::item:selected {{
        background: {surface_hi}; color: #ffffff;
    }}

    QProgressBar {{
        background: {surface}; border: 1px solid {border};
        border-radius: 5px; text-align: center; color: {text};
    }}
    QProgressBar::chunk {{ background: {accent}; border-radius: 4px; }}

    QCheckBox {{ color: {text}; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{
        background: #4a4a4d; border-radius: 5px; min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #5a5a5d; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

    QSplitter::handle {{ background: {border}; }}
    QStatusBar {{ color: {muted}; }}
    QStatusBar::item {{ border: none; }}
    QToolTip {{
        background: #1b1b1d; color: {text};
        border: 1px solid {accent}; padding: 4px;
    }}
    """.format(
        bg=_BG, surface=_SURFACE, surface_hi=_SURFACE_HI, border=_BORDER,
        text=_TEXT, muted=_MUTED, version=VERSION_YELLOW,
        accent=accent, accent_hi=accent_hi, accent_dim=accent_dim,
    )


# A small fixed palette of badge colors; categories outside it get a stable
# color hashed from their name, so every category reads consistently.
_BADGE_COLORS = [
    "#5a8fc0", "#5ab0a0", "#b05a9a", "#9a7ac0",
    "#c0a85a", "#c0795a", "#5fa85f", "#c05a5a",
]


def badge_color(category: str) -> str:
    """Stable accent-chip color for a category name."""
    if not category:
        return _darken(ACCENT, 0.18)
    return _BADGE_COLORS[sum(ord(c) for c in category) % len(_BADGE_COLORS)]


# --- tiny hex helpers (no external color lib needed) -------------------------
def _clamp(v: int) -> int:
    return max(0, min(255, v))


def _scale(hex_color: str, factor: float, toward: int) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r = _clamp(int(r + (toward - r) * factor))
    g = _clamp(int(g + (toward - g) * factor))
    b = _clamp(int(b + (toward - b) * factor))
    return "#{:02x}{:02x}{:02x}".format(r, g, b)


def _lighten(hex_color: str, factor: float) -> str:
    return _scale(hex_color, factor, 255)


def _darken(hex_color: str, factor: float) -> str:
    return _scale(hex_color, factor, 0)
