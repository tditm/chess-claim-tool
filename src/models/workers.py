"""
Chess Claim Tool: workers

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

from __future__ import annotations

import os.path
from threading import Thread
from typing import List, TYPE_CHECKING, Dict

from PyQt5.QtCore import QRunnable, QThread, pyqtSignal
from chess.pgn import read_game

from src.helpers import get_appdata_path, Status
from src.models.claims import get_players, Claims, ClaimEntry
from src.models.download import check_download, download_pgn

if TYPE_CHECKING:
    from src.controllers import SourceDialogController
    from src.views.dialog_view import SourceHBox
    from threading import Event, Lock
    from PyQt5.QtWidgets import QAction


# ---------------------------------------------------------
# CHECK DOWNLOAD
# ---------------------------------------------------------

class CheckDownload(QRunnable):
    """Checks if a web source is valid."""

    __slots__ = ["controller", "source", "download_id"]

    def __init__(self, controller: SourceDialogController, source: SourceHBox, download_id: int):
        super().__init__()
        self.controller = controller
        self.source = source
        self.download_id = download_id

    def run(self):
        url = self.source.get_value()
        if check_download(url):
            self.source.set_status(Status.OK)
            if url not in self.controller.downloads:
                self.controller.add_valid_url(url, self.download_id)
        else:
            self.source.set_status(Status.ERROR)


# ---------------------------------------------------------
# DOWNLOAD GAMES
# ---------------------------------------------------------

class DownloadGames(QThread):
    """Downloads PGN files from the web."""

    status_signal = pyqtSignal(Status)
    INTERVAL = 4
    __slots__ = ["downloads", "stop_event", "app_path"]

    def __init__(self, downloads: Dict[str, str], stop_event: Event = None):
        super().__init__()
        self.downloads = downloads
        self.stop_event = stop_event
        self.app_path = get_appdata_path()

    def run(self) -> None:
        if not self.stop_event:
            return self.download_pgns()

        while not self.stop_event.is_set():
            self.download_pgns()
            self.stop_event.wait(self.INTERVAL)

    def download_pgns(self):
        for url in self.downloads:
            status = Status.OK

            data = download_pgn(url)
            if not data:
                status = Status.ERROR
            self.status_signal.emit(status)

            filename = self.downloads[url]
            try:
                with open(filename, "wb") as file:
                    file.write(data)
            except (FileNotFoundError, TypeError):
                self.status_signal.emit(Status.ERROR)
                continue


# ---------------------------------------------------------
# SCAN PGN
# ---------------------------------------------------------

class Scan(QThread):
    """
    Continuously scans the combined PGN file for new games.
    Emits ClaimEntry objects to update the GUI.
    """

    __slots__ = ["filename", "claims", "lock", "live_pgn_option", "stop_event"]

    add_entry_signal = pyqtSignal(object)   # emits ClaimEntry
    status_signal = pyqtSignal(Status)
    new_move_signal = pyqtSignal()

    INTERVAL = 4

    def __init__(self, claims: Claims, filename: str, lock: Lock,
                 live_pgn_option: QAction, stop_event: Event):
        super().__init__()
        self.filename = filename
        self.claims = claims
        self.lock = lock
        self.live_pgn_option = live_pgn_option
        self.stop_event = stop_event

    def run(self):
        last_size = 0

        while not self.stop_event.is_set():
            try:
                size_of_pgn = os.path.getsize(self.filename)
            except FileNotFoundError:
                size_of_pgn = 0

            if self.is_file_updated(last_size, size_of_pgn):
                self.status_signal.emit(Status.ACTIVE)
                self.new_move_signal.emit()
                self.check_pgn()

            self.status_signal.emit(Status.WAIT)
            last_size = size_of_pgn

            self.stop_event.wait(self.INTERVAL)

    def check_pgn(self):
        """
        Reads the PGN file and emits new ClaimEntry objects.
        """

        self.lock.acquire()
        try:
            with open(self.filename, "r", encoding="utf-8") as pgn:
                game_index = 0

                while not self.stop_event.is_set():
                    game = read_game(pgn)
                    if not game:
                        break

                    if self.live_pgn_option.isChecked() and game.headers["Result"] != "*":
                        continue

                    if get_players(game) in self.claims.dont_check:
                        continue

                    entries = self.claims.check_game(game, game_index)

                    for entry in entries:
                        self.add_entry_signal.emit(entry)

                    game_index += 1

        finally:
            self.lock.release()

    @staticmethod
    def is_file_updated(last_size: int, current_size: int):
        return current_size != 0 and last_size != current_size


# ---------------------------------------------------------
# STOP WORKERS
# ---------------------------------------------------------

class Stop(QThread):
    """Stops all running threads and resets the model."""

    enable_signal = pyqtSignal()
    disable_signal = pyqtSignal()

    __slots__ = ["stop_event", "make_pgn_worker", "scan_worker", "download_worker"]

    def __init__(self, stop_event: Event, make_pgn_worker: Thread,
                 scan_worker: QThread, download_worker: QThread = None):
        super().__init__()
        self.stop_event = stop_event
        self.download_worker = download_worker
        self.make_pgn_worker = make_pgn_worker
        self.scan_worker = scan_worker

    def run(self):
        self.disable_signal.emit()
        self.stop_event.set()

        if self.download_worker:
            self.download_worker.wait()

        self.scan_worker.wait()
        self.make_pgn_worker.join()

        self.enable_signal.emit()


# ---------------------------------------------------------
# MAKE PGN
# ---------------------------------------------------------

class MakePgn(Thread):
    """
    Creates a combined PGN file from all available sources.
    This worker does NOT emit Qt signals (it is a plain Thread).
    """

    INTERVAL = 4
    __slots__ = ["filepaths", "stop_event", "is_running", "lock", "daemon"]

    def __init__(self, filepaths: List[str], stop_event: Event = None, lock: Lock = None):
        super().__init__()
        self.filepaths = filepaths
        self.lock = lock
        self.stop_event = stop_event
        self.daemon = True

        app_path = get_appdata_path()
        self.filename = os.path.join(app_path, "games.pgn")

    def run(self) -> None:
        if not self.stop_event:
            return self.make_pgn()

        while not self.stop_event.is_set():
            self.make_pgn()
            self.stop_event.wait(self.INTERVAL)

    def make_pgn(self):
        """
        Merges all PGN files into a single combined PGN.
        Ensures proper separation between games.
        """

        data = b""
        for filepath in self.filepaths:
            try:
                with open(filepath, "rb") as in_file:
                    content = in_file.read().strip()
                    if not content:
                        continue
                    data += b"\n\n" + content + b"\n\n"
            except FileNotFoundError:
                continue

        self.lock_file()
        try:
            with open(self.filename, "wb") as file:
                file.write(data)
        finally:
            self.release_file()

    def lock_file(self):
        if self.lock:
            self.lock.acquire()

    def release_file(self):
        if self.lock:
            self.lock.release()
