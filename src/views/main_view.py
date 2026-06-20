"""
Chess Claim Tool: ChessClaimView

Copyright (C) 2019 Serntedakis Athanasios <thanasis@brainfriz.com>
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

from __future__ import annotations

import platform
from datetime import datetime
from typing import Optional, Callable, TYPE_CHECKING, List

from PyQt5.QtCore import Qt, QSize, QEvent
from PyQt5.QtGui import QStandardItemModel, QPixmap, QMovie, QStandardItem, QColor
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QTreeView,
    QPushButton,
    QDesktopWidget,
    QAbstractItemView,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QStatusBar,
    QMessageBox,
    QAction,
    QDialog,
    QSpinBox,
    QCheckBox,
    QWidgetAction,
)

from src.helpers import resource_path, Status
from src.models.claims import ClaimType

if platform.system() == "Darwin":
    from src.notifications.mac import Notification
elif platform.system() == "Windows":
    from windows_toasts import WindowsToaster, ToastImageAndText2, ToastDisplayImage, ToastDuration

if TYPE_CHECKING:
    from src.controllers import ChessClaimController


def sources_warning() -> None:
    """Display a warning dialog when no valid PGN sources are found."""
    warning_dialog = QMessageBox()
    warning_dialog.setIcon(warning_dialog.Warning)
    warning_dialog.setWindowTitle("Warning")
    warning_dialog.setText("PGN File(s) Not Found")
    warning_dialog.setInformativeText("Please enter at least one valid PGN source.")
    warning_dialog.exec()


class ChessClaimView(QMainWindow):
    """
    Main application window.

    Displays:
    - claims table
    - control buttons (scan, stop, board viewer)
    - status bar with sources / download / scan status
    """

    ICON_SIZE = 16
    __slots__ = [
        "controller",
        "claims_table",
        "claims_table_model",
        "button_box",
        "ok_pixmap",
        "error_pixmap",
        "source_label",
        "source_image",
        "download_label",
        "download_image",
        "scan_label",
        "scan_image",
        "spinner",
        "status_bar",
        "about_dialog",
        "notification",
        "scoresheet_action",
        "scoresheet_spin",
        "possible_threefold_action",
        "possible_fiftymove_action",
    ]

    def __init__(self, controller: ChessClaimController) -> None:
        super().__init__()
        self.controller = controller

        # Basic window setup
        self.resize(720, 275)
        self.setWindowTitle("Chess Claim Tool")
        self.center()

        # Main widgets
        self.claims_table = QTreeView()
        self.claims_table_model = QStandardItemModel()
        self.button_box = ButtonBox()

        # Status icons and labels
        self.ok_pixmap = QPixmap(resource_path("check_icon.png"))
        self.error_pixmap = QPixmap(resource_path("error_icon.png"))
        self.source_label = QLabel()
        self.source_image = QLabel()
        self.download_label = QLabel()
        self.download_image = QLabel()
        self.scan_label = QLabel()
        self.scan_image = QLabel()
        self.spinner = QMovie(resource_path("spinner.gif"))
        self.status_bar = QStatusBar()

        # About dialog
        self.about_dialog = AboutDialog()

        # OS-specific notifications
        if platform.system() == "Darwin":
            self.notification = Notification()
        elif platform.system() == "Windows":
            self.notification = WindowsToaster("Chess Claim Tool")
        else:
            self.notification = None

        # Scoresheet reminder widgets
        self.scoresheet_action = None
        self.scoresheet_spin = None
        self.possible_threefold_action = None
        self.possible_fiftymove_action = None

    def center(self) -> None:
        """Center the window on the screen."""
        screen = QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move(
            int((screen.width() - size.width()) / 2),
            int((screen.height() - size.height()) / 2),
        )

    def set_gui(self) -> None:
        """Initialize all GUI components."""
        self.create_menu()
        self.create_claims_table()
        self.create_status_bar()

        # Connect buttons to controller callbacks
        self.button_box.set_scan_button_callback(self.controller.on_scan_button_clicked)
        self.button_box.set_stop_button_callback(self.controller.on_stop_button_clicked)
        self.button_box.set_board_button_callback(self.controller.on_board_viewer_clicked)

        # Main layout
        container_layout = QVBoxLayout()
        container_layout.setSpacing(0)
        container_layout.addWidget(self.claims_table)
        container_layout.addWidget(self.button_box)

        container_widget = QWidget()
        container_widget.setLayout(container_layout)

        self.setCentralWidget(container_widget)
        self.setStatusBar(self.status_bar)

    def create_menu(self) -> None:
        """Create the main menu bar."""
        menu_bar = self.menuBar()

        # ---------------------------------------------------------
        # OPTIONS MENU
        # ---------------------------------------------------------
        options_menu = menu_bar.addMenu("&Options")

        # ---------------------------------------------------------
        # Scoresheet reminder (checkbox + spinbox)
        # ---------------------------------------------------------
        widget_scoresheet = QWidget()
        layout_scoresheet = QHBoxLayout()
        layout_scoresheet.setContentsMargins(10, 2, 10, 2)
        layout_scoresheet.setSpacing(0)

        self.scoresheet_action = QCheckBox("Scoresheet change reminder after move")
        self.scoresheet_action.setChecked(False)

        self.scoresheet_spin = QSpinBox()
        self.scoresheet_spin.setRange(1, 200)
        self.scoresheet_spin.setValue(55)
        self.scoresheet_spin.setEnabled(False)

        layout_scoresheet.addWidget(self.scoresheet_action)
        layout_scoresheet.addWidget(self.scoresheet_spin)
        layout_scoresheet.addStretch()
        widget_scoresheet.setLayout(layout_scoresheet)

        widget_action_scoresheet = QWidgetAction(self)
        widget_action_scoresheet.setDefaultWidget(widget_scoresheet)
        options_menu.addAction(widget_action_scoresheet)

        # ---------------------------------------------------------
        # Possible Threefold Reminder (checkbox)
        # ---------------------------------------------------------
        widget_threefold = QWidget()
        layout_threefold = QHBoxLayout()
        layout_threefold.setContentsMargins(10, 2, 10, 2)

        self.possible_threefold_action = QCheckBox("Possible threefold reminder (2 fold)")
        self.possible_threefold_action.setChecked(False)

        layout_threefold.addWidget(self.possible_threefold_action)
        layout_threefold.addStretch()
        widget_threefold.setLayout(layout_threefold)

        widget_action_threefold = QWidgetAction(self)
        widget_action_threefold.setDefaultWidget(widget_threefold)
        options_menu.addAction(widget_action_threefold)

        # ---------------------------------------------------------
        # Possible 50-move Reminder (checkbox)
        # ---------------------------------------------------------
        widget_fifty = QWidget()
        layout_fifty = QHBoxLayout()
        layout_fifty.setContentsMargins(10, 2, 10, 2)

        self.possible_fiftymove_action = QCheckBox("Possible 50-move reminder (45 moves)")
        self.possible_fiftymove_action.setChecked(False)

        layout_fifty.addWidget(self.possible_fiftymove_action)
        layout_fifty.addStretch()
        widget_fifty.setLayout(layout_fifty)

        widget_action_fifty = QWidgetAction(self)
        widget_action_fifty.setDefaultWidget(widget_fifty)
        options_menu.addAction(widget_action_fifty)

        # Connect to controller
        self.scoresheet_action.stateChanged.connect(self._update_scoresheet_settings)
        self.scoresheet_spin.valueChanged.connect(self._update_scoresheet_settings)

        self.possible_threefold_action.stateChanged.connect(
            lambda state: setattr(self.controller, "possible_threefold_enabled", state)
        )

        self.possible_fiftymove_action.stateChanged.connect(
            lambda state: setattr(self.controller, "possible_fiftymove_enabled", state)
        )

        # ---------------------------------------------------------
        # HELP MENU
        # ---------------------------------------------------------
        about_action = QAction("About", self)
        about_menu = menu_bar.addMenu("&Help")
        about_menu.addAction(about_action)
        about_action.triggered.connect(self.controller.on_about_clicked)


    def _update_scoresheet_settings(self) -> None:
        """Update controller settings from menu widgets."""
        enabled = self.scoresheet_action.isChecked()
        self.scoresheet_spin.setEnabled(enabled)

        self.controller.scoresheet_reminder_enabled = enabled
        self.controller.scoresheet_threshold = self.scoresheet_spin.value()

    def create_claims_table(self) -> None:
        """Create and configure the claims table."""
        from PyQt5.QtWidgets import QHeaderView

        # Basic table configuration
        self.claims_table.setFocusPolicy(Qt.NoFocus)
        self.claims_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.claims_table.header().setDefaultAlignment(Qt.AlignCenter)
        self.claims_table.setSortingEnabled(True)
        self.claims_table.setIndentation(0)
        self.claims_table.setUniformRowHeights(True)

        # Set column headers
        labels = ["#", "Timestamp", "Type", "Board", "Players", "Move"]
        self.claims_table_model.setHorizontalHeaderLabels(labels)
        self.claims_table.setModel(self.claims_table_model)

        # Row click → open Board Viewer
        self.claims_table.clicked.connect(self.on_claim_clicked)

        header = self.claims_table.header()

        # Auto-size for small columns
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)   # #
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)   # Timestamp
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)   # Type
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)   # Board

        # Players → fixed
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.claims_table.setColumnWidth(4, 400)

        # Move → stretch (wypełnia wolne miejsce)
        header.setSectionResizeMode(5, QHeaderView.Stretch)

        # Hard widths (no auto logic)
        self.claims_table.setColumnWidth(4, 400)   # Players: wide (≈40 chars)
        self.claims_table.setColumnWidth(5, 100)   # Move: narrow

        # Make sure header does not stretch the last section
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(20)

        # Allow horizontal scrollbar if needed
        self.claims_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Optional: initial window width
        self.resize(860, self.height())

    def create_status_bar(self) -> None:
        """Create and configure the status bar."""
        sources_button = QPushButton("Add Sources")
        sources_button.setObjectName("sources")
        sources_button.clicked.connect(self.controller.on_sources_button_clicked)

        self.source_image.setObjectName("source-image")
        self.download_image.setObjectName("download-image")
        self.scan_image.setObjectName("scan-image")

        self.spinner.setScaledSize(QSize(self.ICON_SIZE, self.ICON_SIZE))
        self.spinner.start()

        self.status_bar.setSizeGripEnabled(False)
        self.status_bar.addWidget(self.source_label)
        self.status_bar.addWidget(self.source_image)
        self.status_bar.addWidget(self.download_label)
        self.status_bar.addWidget(self.download_image)
        self.status_bar.addWidget(self.scan_label)
        self.status_bar.addWidget(self.scan_image)
        self.status_bar.addPermanentWidget(sources_button)
        self.status_bar.setContentsMargins(10, 5, 9, 5)

    def resize_claims_table(self) -> None:
        """Resize the table columns after inserting a new element."""
        for index in range(0, 6):
            self.claims_table.resizeColumnToContents(index)

    def add_item_to_table(self, entry) -> None:
        """
        Add a new row to the claims table.
        Expected entry: ClaimEntry object
        """
        claim_type = entry.type.value
        board_number = entry.board_number
        players = entry.players
        move = entry.move

        # Remove previous rows for same players and claim type (or weaker claim)
        self.remove_rows_by_claim_type(claim_type, players)

        timestamp = str(datetime.now().strftime("%H:%M:%S"))
        row: List[QStandardItem] = []
        count = str(self.claims_table_model.rowCount() + 1)

        # Items to display in the table
        items = [
            count,
            timestamp,
            claim_type,
            board_number,
            players,
            move,
        ]

        for idx, item in enumerate(items):
            standard_item = self.create_standard_item(item, idx)
            row.append(standard_item)

        # Add row to model FIRST
        self.claims_table_model.appendRow(row)

        # Now safely store game and move index for Board Viewer navigation
        first_item = self.claims_table_model.item(self.claims_table_model.rowCount() - 1, 0)
        first_item.setData(
            {
                "game_index": entry.game_index,
                "move_index": entry.move_counter,
                "start_move_index": entry.start_move_counter,
            },
            Qt.UserRole,
        )

        self.resize_claims_table()
        self.claims_table.scrollToBottom()

        # Desktop notification
        self.notify(claim_type, players, move)

    @staticmethod
    def create_standard_item(item: str, idx: int) -> QStandardItem:
        """
        Create a styled QStandardItem for the claims table.

        Bold for claim type column, red color for strong claims.
        """
        q_item = QStandardItem(item)
        q_item.setTextAlignment(Qt.AlignCenter)

        # Bold font for claim type column
        if idx == 2:
            font = q_item.font()
            font.setBold(True)
            q_item.setFont(font)

        # Highlight strong claims in red
        if item == ClaimType.FIVEFOLD.value or item == ClaimType.SEVENTYFIVE_MOVES.value:
            q_item.setData(QColor(255, 0, 0), Qt.ForegroundRole)

        return q_item

    def on_claim_clicked(self, index) -> None:
        """
        Handle click on a claim row and open Board Viewer
        at the correct game and move.
        """
        first_col_item = self.claims_table_model.item(index.row(), 0)
        if first_col_item is None:
            return

        data = first_col_item.data(Qt.UserRole)
        if not data:
            return

        game_index = data.get("game_index")
        move_index = data.get("move_index")

        if game_index is None or move_index is None:
            return

        self.controller.open_viewer_for_claim(game_index, move_index)

    def notify(self, claim_type: ClaimType, players: str, move: str) -> None:
        """Send a desktop notification depending on the OS."""
        if self.notification is None:
            return

        if platform.system() == "Darwin":
            self.notification.clearNotifications()
            self.notification.notify(claim_type.value, players, move)

        elif platform.system() == "Windows":
            newToast = ToastImageAndText2()
            newToast.SetHeadline(claim_type)
            newToast.SetBody(f"{players} \n{move}")
            newToast.AddImage(ToastDisplayImage.fromPath(resource_path("logo.ico")))
            newToast.SetDuration(ToastDuration("short"))
            self.notification.show_toast(newToast)

    def remove_row_by_index(self, index: int) -> None:
        """Remove a row from the claims table by index."""
        self.claims_table_model.removeRow(index)

    def remove_rows_by_claim_type(self, claim_type: str, players: str) -> None:
        """
        Remove previous rows for the same players and same or weaker claim type.
        """
        model = self.claims_table_model
        rows_to_remove = []

        for row in range(model.rowCount()):
            model_type = model.item(row, 2).text()
            model_players = model.item(row, 4).text()

            if model_type == claim_type and model_players == players:
                rows_to_remove.append(row)

        # Remove rows from bottom to top
        for row in reversed(rows_to_remove):
            model.removeRow(row)

        # Renumber rows (fixes viewer bug!)
        for i in range(model.rowCount()):
            model.item(i, 0).setText(str(i + 1))

    def reset_column_count(self) -> None:
        """Re-index the numbers in the first column after row removal."""
        row_count = self.claims_table_model.rowCount()
        for index in range(row_count):
            standard_item = QStandardItem(str(index + 1))
            standard_item.setTextAlignment(Qt.AlignCenter)
            self.claims_table_model.setItem(index, 0, standard_item)

    def clear_table(self) -> None:
        """Clear all rows from the claims table."""
        for _ in range(self.claims_table_model.rowCount()):
            self.claims_table_model.removeRow(0)

    def set_sources_status(self, status: Status, valid_sources: Optional[List] = None) -> None:
        """
        Update the sources status in the status bar.

        Shows a tooltip listing all valid sources.
        """
        if valid_sources is None:
            valid_sources = []

        self.source_label.setText("Sources:")

        try:
            text = ""
            for idx, source in enumerate(valid_sources):
                text += f"{idx + 1}) {source.get_value()}"
                if idx != len(valid_sources) - 1:
                    text += "\n"
            self.source_label.setToolTip(text)
        except TypeError:
            # In case valid_sources is not iterable or contains unexpected types
            pass

        self.set_pixmap(self.source_image, status)

    def set_download_status(self, status: Status) -> None:
        """Update the download status in the status bar."""
        timestamp = str(datetime.now().strftime("%H:%M:%S"))
        self.download_label.setText(f"{timestamp} Download:")

        self.set_pixmap(self.download_image, status)

        if status == Status.STOP:
            self.download_image.clear()
            self.download_label.clear()

    def set_scan_status(self, status: Status) -> None:
        """Update the scan status in the status bar."""
        timestamp = str(datetime.now().strftime("%H:%M:%S"))
        self.scan_label.setText(f"{timestamp} Scan:")
        self.set_pixmap(self.scan_image, status)

        if status == Status.ACTIVE:
            self.scan_image.clear()
            self.scan_image.setMovie(self.spinner)
        elif status == Status.STOP:
            self.scan_label.clear()
            self.scan_image.clear()

    def change_scan_button_text(self, status: Status) -> None:
        """Change the scan button text depending on the scan status."""
        if status == Status.ACTIVE:
            self.button_box.scan_button.setText("Scanning PGN...")
        elif status == Status.STOP:
            self.button_box.scan_button.setText("Start Scan")
        elif status == Status.WAIT:
            self.button_box.scan_button.setText("Please Wait")

    def set_pixmap(self, image: QLabel, status: Status) -> None:
        """Set the appropriate status icon."""
        if status in (Status.OK, Status.WAIT):
            image.setPixmap(
                self.ok_pixmap.scaled(
                    self.ICON_SIZE,
                    self.ICON_SIZE,
                    transformMode=Qt.SmoothTransformation,
                )
            )
        elif status == Status.ERROR:
            image.setPixmap(
                self.error_pixmap.scaled(
                    self.ICON_SIZE,
                    self.ICON_SIZE,
                    transformMode=Qt.SmoothTransformation,
                )
            )

    def enable_buttons(self) -> None:
        """Enable main control buttons."""
        self.button_box.scan_button.setEnabled(True)
        self.button_box.stop_button.setEnabled(True)

    def disable_buttons(self) -> None:
        """Disable main control buttons."""
        self.button_box.scan_button.setEnabled(False)
        self.button_box.stop_button.setEnabled(False)

    def enable_status_bar(self) -> None:
        """Show download and scan status messages in the status bar."""
        self.download_label.setVisible(True)
        self.scan_label.setVisible(True)
        self.download_image.setVisible(True)
        self.scan_image.setVisible(True)

    def disable_status_bar(self) -> None:
        """Hide download and scan status messages from the status bar."""
        self.download_label.setVisible(False)
        self.download_image.setVisible(False)
        self.scan_label.setVisible(False)
        self.scan_image.setVisible(False)

    def closeEvent(self, event: QEvent) -> None:
        """
        Reimplement the close event to warn if scanning is in progress.
        """
        try:
            if self.controller.scan_worker and self.controller.scan_worker.isRunning():
                exit_dialog = QMessageBox()
                exit_dialog.setWindowTitle("Warning")
                exit_dialog.setText("Scanning in Progress")
                exit_dialog.setInformativeText("Do you want to quit?")
                exit_dialog.setIcon(exit_dialog.Warning)
                exit_dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
                exit_dialog.setDefaultButton(QMessageBox.Cancel)

                # --- poszerzenie przycisków ---
                yes_button = exit_dialog.button(QMessageBox.Yes)
                cancel_button = exit_dialog.button(QMessageBox.Cancel)
                yes_button.setMinimumWidth(100)
                cancel_button.setMinimumWidth(100)
                # --------------------------------

                replay = exit_dialog.exec()

                if replay == QMessageBox.Yes:
                    event.accept()
                else:
                    event.ignore()
            else:
                event.accept()
        except Exception:
            event.accept()

    def load_about_dialog(self) -> None:
        """Display the About dialog."""
        self.about_dialog.set_gui()
        self.about_dialog.show()


class ButtonBox(QWidget):
    """
    Provides a horizontal box with three buttons:
    - Scan
    - Stop
    - Board Viewer
    """

    __callbacks__ = ["scan_button", "stop_button", "board_button"]

    def __init__(self) -> None:
        super().__init__()

        self.scan_button = QPushButton("Start Scan")
        self.scan_button.setObjectName("Scan")

        self.stop_button = QPushButton("Stop Scan")
        self.stop_button.setObjectName("Stop")

        self.board_button = QPushButton("Board Viewer")
        self.board_button.setObjectName("BoardViewer")

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 5, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self.scan_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.board_button)

        self.setLayout(layout)

    def set_scan_button_callback(self, on_clicked: Callable) -> None:
        """Set callback for the scan button."""
        self.scan_button.clicked.connect(on_clicked)

    def set_stop_button_callback(self, on_clicked: Callable) -> None:
        """Set callback for the stop button."""
        self.stop_button.clicked.connect(on_clicked)

    def set_board_button_callback(self, on_clicked: Callable) -> None:
        """Set callback for the board viewer button."""
        self.board_button.clicked.connect(on_clicked)


class AboutDialog(QDialog):
    """
    About dialog GUI.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("About")
        self.setWindowFlags(self.windowFlags() ^ Qt.WindowContextHelpButtonHint)

        self._layout_built = False   # prevent building the layout more than once

    def set_gui(self) -> None:
        """Build About dialog GUI components."""

        # if layout already exists → do nothing
        if self._layout_built:
            return

        # create layout only once
        layout = QVBoxLayout()
        self.setLayout(layout)

        logo = QLabel()
        logo_pixmap = QPixmap(resource_path("logo.png"))
        logo.setPixmap(logo_pixmap)
        logo.setAlignment(Qt.AlignCenter)

        appname = QLabel("Chess Claim Tool")
        appname.setObjectName("appname")
        appname.setAlignment(Qt.AlignCenter)

        version = QLabel("Version 0.4.1")
        version.setObjectName("version")
        version.setAlignment(Qt.AlignCenter)

        copyright = QLabel(
            "Author Serntedakis Athanasios 2022 © Modified by Tomasz Delega 2026 ©"
        )
        copyright.setObjectName("copyright")
        copyright.setAlignment(Qt.AlignCenter)

        layout.addWidget(logo)
        layout.addWidget(appname)
        layout.addWidget(version)
        layout.addWidget(copyright)

        self._layout_built = True
