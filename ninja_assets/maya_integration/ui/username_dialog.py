"""Username prompt dialog for first-launch setup."""

from typing import Optional


def prompt_username() -> Optional[str]:
    """Show dialog to get username on first launch.

    Returns the entered username or None if cancelled.
    """
    from ninja_assets.maya_integration.ui.qt_compat import (
        QInputDialog, QLineEdit,
    )
    from ninja_assets.maya_integration.utils.maya_utils import get_maya_main_window

    parent = get_maya_main_window()

    text, ok = QInputDialog.getText(
        parent,
        "NinjaAssets Setup",
        "Enter your studio username:",
        QLineEdit.Normal,
        "",
    )

    if ok and text.strip():
        return text.strip()
    return None
