"""Configuración y fixtures compartidas de pytest para MintPlay."""

import sys
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Instancia única de QApplication para toda la suite de pruebas."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
