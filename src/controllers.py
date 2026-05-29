"""
Chess Claim Tool: ChessClaimController

Copyright (C) 2019 Serntedakis Athanasios <thanasis@brainfriz.com>
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

import json
import os
import sys
from threading import Event, Thread, Lock
from typing import List, Dict

from PyQt5.QtCore import QThreadPool
from PyQt5.QtWidgets import QApplication

from src.helpers import get_appdata_path, Status
from src.models.claims import Claims
from src.models.workers import CheckDownload, DownloadGames, MakePgn, Scan, Stop
from src.views.dialog_view import AddSourceDialog, SourceHBox
from src.views.main_view import ChessClaimView, sources_warning
from src.board_viewer import BoardViewerWindow


class ChessClaimController(QApplication):

    __slots__ = [
        'view', 'model', 'sources_dialog',
        'make_pgn_worker', 'stop_worker', 'download_worker', 'scan_worker',
        'stop_event', 'board_viewer'
    ]

    def __init__(self) -> None:
        super().__init__(sys.argv)

        self.view = ChessClaimView(self)
        self.model = Claims()
        self.sources_dialog = None

        self.make_pgn_worker = None
        self.download_worker = None
        self.scan_worker = None
        self.stop_worker = None

        self.stop_event = Event()
        self.board_viewer = None

    def do_start(self) -> None:
        app_path = get_appdata_path()
        os.makedirs(app_path, exist_ok=True)

        self.view.set_gui()
        self.view.show()

    # ---------------------------------------------------------
    # ABOUT
    # ---------------------------------------------------------
    def on_about_clicked(self) -> None:
        self.view.load_about_dialog()

    # ---------------------------------------------------------
    # BOARD VIEWER
    # ---------------------------------------------------------
    def on_board_viewer_clicked(self) -> None:
        app_path = get_appdata_path()
        pgn_path = os.path.join(app_path, "games.pgn")

        if not os.path.exists(pgn_path):
            return

        if self.board_viewer is None:
            self.board_viewer = BoardViewerWindow(pgn_path=pgn_path)
        else:
            if hasattr(self.board_viewer, "reload_pgn"):
                self.board_viewer.reload_pgn(pgn_path)
                self.board_viewer.go_end()

        self.board_viewer.show()
        self.board_viewer.raise_()

    def open_viewer_for_claim(self, game_index: int, move_index: int):
        if self.board_viewer is None:
            self.on_board_viewer_clicked()
        else:
            # upewnij się, że Viewer ma świeży PGN
            self.on_pgn_updated()

        try:
            self.board_viewer.load_game_at_index(game_index)
            self.board_viewer.jump_to_move(move_index)
        except Exception:
            return

        self.board_viewer.show()
        self.board_viewer.raise_()

    # ---------------------------------------------------------
    # PGN UPDATE
    # ---------------------------------------------------------
    def on_pgn_updated(self):
        """
        Called whenever games.pgn is rewritten.
        Refreshes Board Viewer if open and jumps to last move.
        """
        if self.board_viewer is None:
            return

        app_path = get_appdata_path()
        pgn_path = os.path.join(app_path, "games.pgn")

        if hasattr(self.board_viewer, "reload_pgn"):
            self.board_viewer.reload_pgn(pgn_path)
            self.board_viewer.go_end()

    # ---------------------------------------------------------
    # NEW MOVE → rebuild PGN + refresh viewer
    # ---------------------------------------------------------
    def on_new_move(self):
        """
        Called when Scan worker detects a new move.
        Rebuilds games.pgn and immediately refreshes Board Viewer (if open).
        """
        if not self.sources_dialog:
            return

        filepaths = self.sources_dialog.get_filepath_list()
        if not filepaths:
            return

        lock = Lock()
        make_pgn = MakePgn(filepaths, self.stop_event, lock)

        # MakePgn jest zwykłym wątkiem – wywołujemy logikę bez kombinowania z sygnałami
        make_pgn.make_pgn()

        # PGN gotowy – odśwież Viewer (jeśli otwarty)
        self.on_pgn_updated()

    # ---------------------------------------------------------
    # SCAN / DOWNLOAD / STOP
    # ---------------------------------------------------------
    def on_sources_button_clicked(self) -> None:
        if not self.sources_dialog:
            self.sources_dialog = SourceDialogController()
            self.sources_dialog.view.accepted.connect(self.update_status_bar_sources)
            self.sources_dialog.do_start()
            return

        if self.scan_worker and self.scan_worker.isRunning():
            self.on_stop_button_clicked()

        self.sources_dialog.do_resume()

    def on_scan_button_clicked(self) -> None:
        if not self.sources_dialog or not self.sources_dialog.has_valid_sources():
            sources_warning()
            return

        if self.scan_worker and self.scan_worker.isRunning():
            return

        self.view.clear_table()
        self.view.change_scan_button_text(Status.ACTIVE)

        download_list = self.sources_dialog.get_download_list()
        if download_list:
            self.start_download_worker(download_list)

        games_pgn_mutex = Lock()
        self.start_make_png_worker(games_pgn_mutex)
        self.start_scan_worker(games_pgn_mutex)

    def on_stop_button_clicked(self) -> None:
        if not self.scan_worker or not self.scan_worker.isRunning():
            return

        self.stop_worker = Stop(
            self.stop_event,
            self.make_pgn_worker,
            self.scan_worker,
            self.download_worker
        )

        self.stop_worker.enable_signal.connect(self.on_stop_enable_status)
        self.stop_worker.disable_signal.connect(self.on_stop_disable_status)
        self.stop_worker.start()
        self.stop_worker.wait()

        self.model.empty_dont_check()
        self.model.empty_entries()
        self.stop_event.clear()

    def on_stop_enable_status(self) -> None:
        self.view.set_scan_status(Status.ACTIVE)

    def on_stop_disable_status(self) -> None:
        self.view.set_scan_status(Status.INACTIVE)
        self.view.change_scan_button_text(Status.INACTIVE)

    def update_status_bar_sources(self) -> None:
        valid_sources = self.sources_dialog.get_valid_sources()
        if valid_sources:
            self.view.set_sources_status(Status.OK, valid_sources)
        else:
            self.view.set_sources_status(Status.ERROR)

    def update_claims_table(self, entry: list) -> None:
        self.view.add_item_to_table(entry)

    def update_download_status(self, status: Status) -> None:
        self.view.set_download_status(status)

    def update_bar_scan_status(self, status: Status) -> None:
        self.view.set_scan_status(status)

    # ---------------------------------------------------------
    # WORKERS
    # ---------------------------------------------------------
    def start_download_worker(self, downloads: Dict[str, str]) -> None:
        if not downloads:
            return

        self.download_worker = DownloadGames(downloads, self.stop_event)
        self.download_worker.status_signal.connect(self.update_download_status)
        self.download_worker.start()

    def start_make_png_worker(self, lock: Lock) -> None:
        filepaths = self.sources_dialog.get_filepath_list()
        self.make_pgn_worker = MakePgn(filepaths, self.stop_event, lock)

        # tu nie polegamy na finished_signal/finished – Scan i tak wykryje zmiany,
        # a Viewer będzie odświeżany przez on_new_move / on_pgn_updated
        self.make_pgn_worker.start()

    def start_scan_worker(self, lock: Lock) -> None:
        app_path = get_appdata_path()
        filename = os.path.join(app_path, "games.pgn")

        self.scan_worker = Scan(
            self.model,
            filename,
            lock,
            self.view.live_pgn_option,
            self.stop_event
        )

        self.scan_worker.add_entry_signal.connect(self.update_claims_table)
        self.scan_worker.status_signal.connect(self.update_bar_scan_status)

        # reaguj na każdy nowy ruch
        if hasattr(self.scan_worker, "new_move_signal"):
            self.scan_worker.new_move_signal.connect(self.on_new_move)

        self.scan_worker.start()


# ---------------------------------------------------------
# SOURCE DIALOG CONTROLLER
# ---------------------------------------------------------

class SourceDialogController:

    def __init__(self) -> None:
        self.view = AddSourceDialog(self)
        self.app_path = get_appdata_path()
        self.threadPool = QThreadPool()
        self.filepaths: List[str] = []
        self.downloads: Dict[str, str] = dict()
        self.apply_lock = Lock()

    def do_start(self) -> None:
        self.view.set_gui()
        self.restore()
        self.view.show()

    def do_resume(self) -> None:
        self.view.show()

    def get_filepath_list(self) -> List[str]:
        return self.filepaths

    def get_valid_sources(self) -> List[SourceHBox]:
        return self.view.sources

    def get_download_list(self) -> Dict[str, str]:
        return self.downloads

    def has_valid_sources(self) -> bool:
        return len(self.filepaths) > 0

    def restore(self) -> None:
        try:
            with open(os.path.join(self.app_path, "sources.json"), "r") as file:
                data = json.load(file)
                if not data:
                    self.view.add_default_source()
                for entry in data:
                    self.view.add_source(entry["option"], entry["value"])
        except Exception:
            self.view.add_default_source()

    def on_delete_button_clicked(self, source_hbox) -> None:
        with self.apply_lock:
            self.remove_hbox_refs(source_hbox)
            self.view.remove_hbox(source_hbox)

    def remove_hbox_refs(self, hbox: SourceHBox) -> None:
        value = hbox.get_value()
        if hbox.has_url() and value in self.downloads:
            filepath = self.downloads[value]
            if filepath in self.filepaths:
                self.filepaths.remove(filepath)
            del self.downloads[value]
        elif hbox.has_local() and value in self.filepaths:
            self.filepaths.remove(value)

    def on_apply_button_clicked(self) -> None:
        Thread(target=self._apply_thread, daemon=True).start()

    def _apply_thread(self) -> None:
        with self.apply_lock:
            self.filepaths = []
            self.downloads = {}

            download_id = 0
            for source_hbox in self.view.sources:
                if source_hbox.has_url():
                    self.threadPool.start(CheckDownload(self, source_hbox, download_id))
                    download_id += 1
                elif source_hbox.has_local():
                    filepath = source_hbox.get_value()
                    if os.path.exists(filepath):
                        source_hbox.set_status(Status.OK)
                        if filepath not in self.filepaths:
                            self.filepaths.append(filepath)
                    else:
                        source_hbox.set_status(Status.ERROR)

            self.threadPool.waitForDone()

            if self.filepaths:
                self.view.enable_ok_button()

    def on_ok_button_clicked(self) -> None:
        Thread(target=self._exit_thread, daemon=True).start()
        self.view.accept()
        self.view.close()

    def _exit_thread(self) -> None:
        worker = DownloadGames(self.downloads)
        worker.start()
        worker.wait()

        make_pgn = MakePgn(self.filepaths)
        make_pgn.start()
        make_pgn.join()

        self.save_sources()

    def save_sources(self) -> None:
        data = [
            {"option": source.get_source_index(), "value": source.get_value()}
            for source in self.view.sources
        ]

        with open(os.path.join(self.app_path, 'sources.json'), 'w') as file:
            json.dump(data, file, indent=4)

    def add_valid_url(self, url: str, download_id: int) -> None:
        filepath = os.path.join(self.app_path, f"games{download_id}.pgn")
        self.downloads[url] = filepath
        if filepath not in self.filepaths:
            self.filepaths.append(filepath)
