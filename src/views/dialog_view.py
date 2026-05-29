"""
Chess Claim Tool: SourceDialogView

Copyright (C) 2022 Serntedakis Athanasios <thanserd@hotmail.com>
Modfied by Tomasz Delega (C) 2026 AI-assisted refactoring

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

from functools import partial
from typing import List

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QDialog, QWidget, QComboBox, QLineEdit, QPushButton,
    QLabel, QHBoxLayout, QVBoxLayout, QFileDialog
)

from src.helpers import resource_path, Status


class AddSourceDialog(QDialog):
    """
    Dialog window for managing PGN sources.

    Allows the user to add, remove, and validate multiple PGN sources,
    either from a web URL or a local file.
    """

    ICON_SIZE = 20
    __slots__ = ['controller', 'layout', 'bottomBox', 'sources', 'sources_cnt']

    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller

        # Basic dialog configuration
        self.setModal(True)
        self.setMinimumWidth(420)
        self.resize(420, 100)
        self.setWindowTitle("PGN Sources")

        # Remove the "?" help button from the title bar
        self.setWindowFlags(self.windowFlags() ^ Qt.WindowContextHelpButtonHint)

        self.layout = None
        self.bottomBox = None
        self.sources: List[SourceHBox] = []
        self.sources_cnt = 0

    def set_gui(self) -> None:
        """Initialize all GUI components for the dialog."""

        # Bottom button box (Apply + OK)
        self.bottomBox = BottomBox(self.controller)

        # Button for adding new source rows
        add_source_button = QPushButton("")
        add_source_button.setIcon(QIcon(resource_path("add_icon.png")))
        add_source_button.setIconSize(QSize(self.ICON_SIZE + 4, self.ICON_SIZE + 4))
        add_source_button.setObjectName('AddSource')
        add_source_button.clicked.connect(self.on_add_source_button_clicked)

        # Main layout
        self.layout = QVBoxLayout()
        self.layout.addWidget(add_source_button, 1, Qt.AlignRight)
        self.layout.addWidget(self.bottomBox)

        self.setLayout(self.layout)
        self.adjustSize()

    def on_add_source_button_clicked(self) -> None:
        """Triggered when the user clicks the '+' button."""
        self.add_default_source()

    def add_source(self, option: int, value: str) -> None:
        """
        Add a new source row to the dialog.

        Args:
            option (int): 0 = Web URL, 1 = Local file
            value (str): URL or file path
        """
        self.sources_cnt += 1
        source_hbox = SourceHBox(self)
        source_hbox.set_source(option)
        source_hbox.set_value(value)

        self.sources.append(source_hbox)
        self.layout.insertWidget(self.sources_cnt - 1, source_hbox)

    def add_default_source(self) -> None:
        """Add a new empty Web URL source row."""
        self.add_source(0, "")

    def enable_ok_button(self) -> None:
        """Enable the OK button."""
        self.bottomBox.change_ok_status(True)

    def disable_ok_button(self) -> None:
        """Disable the OK button."""
        self.bottomBox.change_ok_status(False)

    def remove_hbox(self, hbox) -> None:
        """
        Remove a source row from the dialog.

        Args:
            hbox (SourceHBox): The row to remove.
        """
        self.layout.removeWidget(hbox)
        self.sources.remove(hbox)
        self.sources_cnt -= 1

        hbox.deleteLater()
        self.adjustSize()


class SourceHBox(QWidget):
    """
    A single row representing one PGN source.

    Contains:
    - ComboBox (Web URL / Local file)
    - LineEdit for URL or file path
    - Optional "Choose File" button
    - Status icon (OK / Error)
    - Delete button
    """

    __slots__ = [
        'dialog', 'select_source', 'source_value', 'choose_button',
        'status_image', 'ok_pixmap', 'error_pixmap'
    ]

    def __init__(self, dialog: AddSourceDialog) -> None:
        super().__init__()
        self.dialog = dialog

        # Source type selector
        self.select_source = QComboBox()
        self.select_source.addItems(["Web(url)", "Local"])
        self.select_source.currentIndexChanged.connect(self.select_change)

        # Input field for URL or file path
        self.source_value = QLineEdit()
        self.source_value.textChanged.connect(self.line_edit_changed)
        self.source_value.setPlaceholderText("https://example.com/pgn/games.pgn")

        # File chooser button (only visible for local file option)
        self.choose_button = QPushButton("Choose File")
        self.choose_button.clicked.connect(self.on_choose_button_clicked)
        self.choose_button.setHidden(True)

        # Status icon (OK / Error)
        self.status_image = QLabel()
        self.ok_pixmap = QPixmap(resource_path("check_icon.png"))
        self.error_pixmap = QPixmap(resource_path("error_icon.png"))

        # Delete button
        delete_button = QPushButton("")
        delete_button.setIcon(QIcon(resource_path("delete_icon.png")))
        delete_button.setIconSize(QSize(self.dialog.ICON_SIZE, self.dialog.ICON_SIZE))
        delete_button.setObjectName('DeleteSource')
        delete_button.clicked.connect(
            partial(self.dialog.controller.on_delete_button_clicked, self)
        )

        # Layout for the row
        layout = QHBoxLayout()
        layout.addWidget(self.select_source)
        layout.addWidget(self.source_value)
        layout.addWidget(self.choose_button)
        layout.addWidget(self.status_image)
        layout.addWidget(delete_button)

        self.setLayout(layout)
        self.adjustSize()

    def set_value(self, text: str) -> None:
        """Set the text of the input field."""
        self.source_value.setText(text)

    def set_source(self, index: int) -> None:
        """Set the source type (0 = URL, 1 = Local)."""
        self.select_source.setCurrentIndex(index)

    def get_value(self) -> str:
        """Return the current text in the input field."""
        return self.source_value.text()

    def get_source_index(self) -> int:
        """Return the selected source type index."""
        return self.select_source.currentIndex()

    def has_url(self) -> bool:
        """Return True if the source type is Web URL."""
        return self.select_source.currentIndex() == 0

    def has_local(self) -> bool:
        """Return True if the source type is Local file."""
        return self.select_source.currentIndex() == 1

    def line_edit_changed(self) -> None:
        """Reset status when the user edits the input field."""
        self.dialog.disable_ok_button()
        self.status_image.clear()

    def select_change(self, index: int) -> None:
        """
        Handle switching between Web URL and Local file.

        Args:
            index (int): 0 = Web URL, 1 = Local file
        """
        self.line_edit_changed()

        if index == 0:
            # Web URL mode
            self.choose_button.setHidden(True)
            self.source_value.setText("")
            self.source_value.setPlaceholderText("https://example.com/pgn/games.pgn")

        elif index == 1:
            # Local file mode
            self.choose_button.setHidden(False)
            self.source_value.setText("")
            self.source_value.setPlaceholderText("")

    def set_status(self, status: Status) -> None:
        """
        Display the status icon (OK or Error).

        Args:
            status (Status): Validation result
        """
        if status == Status.OK:
            self.status_image.setPixmap(
                self.ok_pixmap.scaled(
                    self.dialog.ICON_SIZE,
                    self.dialog.ICON_SIZE,
                    transformMode=Qt.SmoothTransformation
                )
            )

        elif status == Status.ERROR:
            self.status_image.setPixmap(
                self.error_pixmap.scaled(
                    self.dialog.ICON_SIZE,
                    self.dialog.ICON_SIZE,
                    transformMode=Qt.SmoothTransformation
                )
            )

    def on_choose_button_clicked(self) -> None:
        """Open a file dialog for selecting a local PGN file."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select File", "", "PGN Files (*.pgn)"
        )
        if filename:
            self.source_value.setText(filename)


class BottomBox(QWidget):
    """
    Bottom section of the dialog containing:
    - Apply button
    - OK button
    """

    __slots__ = ['controller', 'ok_button']

    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller

        # Buttons
        apply_button = QPushButton("Apply")
        self.ok_button = QPushButton("OK")

        apply_button.setObjectName("apply")
        self.ok_button.setObjectName("ok")

        apply_button.clicked.connect(self.controller.on_apply_button_clicked)
        self.ok_button.clicked.connect(self.controller.on_ok_button_clicked)

        # OK button is disabled until validation succeeds
        self.ok_button.setEnabled(False)

        # Layout
        layout = QHBoxLayout()
        layout.setSpacing(30)
        layout.addWidget(apply_button)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def change_ok_status(self, status: bool) -> None:
        """Enable or disable the OK button."""
        self.ok_button.setEnabled(status)
