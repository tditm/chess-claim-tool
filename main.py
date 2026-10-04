"""
Chess Claim Tool

Copyright (C) 2022 Serntedakis Athanasios <thanserd@hotmail.com>
Modified by Tomasz Delega (C) 2026 AI-assisted refactoring

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

# Standard library imports
from sys import exit

# Third-party library imports
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

# Local application imports
from src.controllers import ChessClaimController
from src.helpers import resource_path

if __name__ == '__main__':
    # Enable automatic scaling for High DPI displays
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

    # Initialize the main application controller
    app = ChessClaimController()

    # Set a visual theme across all operating systems
    app.setStyle('fusion')

    # Set the application window icon using the resource path helperbo 
    app.setWindowIcon(QIcon(resource_path("logo.png")))

    # Load and apply custom styles from the CSS file
    with open(resource_path('main.css'), 'r') as css_file:
        css = css_file.read().replace('\n', '')
    app.setStyleSheet(css)

    # Start the Qt main event loop and exit the script when the window is closed
    app.do_start()
    exit(app.exec_())
