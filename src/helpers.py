"""
Chess Claim Tool: helpers

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

import enum
import os
import platform
import sys


def resource_path(relative_path: str) -> str:
    """
    Return the absolute path to a resource file.

    This function works correctly both when running the program normally
    and when packaged with PyInstaller. It also handles special cases
    for CSS files and icons based on the project's directory structure.

    Args:
        relative_path (str): Path to the resource relative to the project.

    Returns:
        str: Absolute path to the resource.
    """

    # PyInstaller "frozen" mode: resources are stored in sys._MEIPASS
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS

    else:
        # Directory where helpers.py is located (src/)
        current_dir = os.path.abspath(os.path.dirname(__file__))

        # CSS files are stored in src/views/
        if relative_path.endswith(".css"):
            base_path = os.path.join(current_dir, "views")

        # Icons are stored in icons/ (one level above src/)
        elif relative_path.endswith(".png"):
            base_path = os.path.abspath(os.path.join(current_dir, "..", "icons"))

        # Default: use the directory of helpers.py
        else:
            base_path = current_dir

    return os.path.join(base_path, relative_path)


def get_appdata_path() -> str:
    """
    Return the directory where the application should store its data.

    The location depends on the operating system:
        - Windows → %APPDATA%/Chess Claim Tool
        - macOS   → ~/Library/Application Support/Chess Claim Tool
        - Linux   → ~/.local/share/Chess Claim Tool

    Returns:
        str: Absolute path to the application's data directory.
    """

    system = platform.system()

    if system == "Darwin":  # macOS
        base_path = os.path.join(os.getenv("HOME"), "Library", "Application Support")

    elif system == "Windows":
        base_path = os.getenv("APPDATA")

    else:
        # Linux, BSD, and other Unix-like systems
        base_path = os.path.join(os.getenv("HOME"), ".local", "share")

    return os.path.join(base_path, "Chess Claim Tool")


class Status(enum.Enum):
    """
    Enum representing different application states.

    Used for UI updates, worker status reporting, and general state handling.
    """
    OK = 1
    ERROR = 2
    STOP = 3
    ACTIVE = 4
    WAIT = 5
    INACTIVE = 6
