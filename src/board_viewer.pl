"""
Chess Claim Tool: helpers

Copyright (C) 2026 by Tomasz Delega (C) AI-assisted refactoring

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

import chess
import chess.pgn
import chess.svg
import io

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QLabel, QTextBrowser, QPushButton, QLineEdit,
    QSizePolicy
)
from PyQt5.QtGui import QPixmap, QPainter, QPen
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtSvg import QSvgRenderer


class BoardViewerWindow(QMainWindow):
    """
    PGN viewer window with LIVE PGN support and threefold snapshots.
    """

    def showEvent(self, event):
        super().showEvent(event)
        self.update_board()

    def __init__(self, pgn_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chess Claim Tool – Board Viewer")
        self.resize(1100, 580)

        self.pgn_path = pgn_path
        self.games = []
        self.filtered_games = []
        self.current_game = None
        self.current_board = None
        self.move_list = []
        self.move_index = 0
        self.current_game_index = 0

        self.repetition_snapshots = set()

        self._build_ui()
        self._load_games()
        self._refresh_game_list()

        if self.filtered_games:
            self.game_list.setCurrentRow(0)
            self.load_game_at_index(0)

        self.setFocusPolicy(Qt.StrongFocus)
        self.centralWidget().setFocus()

        self.pgn_view.setFocusPolicy(Qt.NoFocus)
        self.game_list.setFocusPolicy(Qt.NoFocus)
        self.search_box.setFocusPolicy(Qt.ClickFocus)

    # ---------------------------------------------------------
    # LOAD GAME / SELECTION
    # ---------------------------------------------------------
    def load_game_at_index(self, game_index: int):
        """Load a specific game from the PGN list (by index in self.games)."""
        if not self.games:
            return
        if game_index < 0 or game_index >= len(self.games):
            return

        self.current_game_index = game_index
        index, game = self.games[game_index]

        self.current_game = game
        self.current_board = game.board()
        self.move_list = list(game.mainline_moves())
        self.move_index = len(self.move_list)

        self._compute_repetition_snapshots()

        if hasattr(self, "game_list"):
            self.game_list.setCurrentRow(game_index)

        self._refresh_pgn_with_highlight()
        self.update_board()

    def on_game_selected(self, arg) -> None:
        if isinstance(arg, int):
            row = arg
        else:
            row = self.game_list.row(arg)

        if row < 0 or row >= len(self.filtered_games):
            return

        index, game = self.filtered_games[row]

        self.current_game_index = index

        self.current_game = game
        self.current_board = game.board()
        self.move_list = list(game.mainline_moves())
        self.move_index = len(self.move_list)

        self._compute_repetition_snapshots()

        self._refresh_pgn_with_highlight()
        self.update_board()

    # ---------------------------------------------------------
    # UI SETUP
    # ---------------------------------------------------------
    def _build_ui(self) -> None:
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # LEFT SIDE
        left_layout = QVBoxLayout()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search by player name or by board number ...")
        self.search_box.textChanged.connect(self._apply_filter)
        left_layout.addWidget(self.search_box)

        self.game_list = QListWidget()
        self.game_list.setMinimumWidth(350)
        self.game_list.currentRowChanged.connect(self.on_game_selected)
        left_layout.addWidget(self.game_list)

        main_layout.addLayout(left_layout, 40)

        # RIGHT SIDE
        right_layout = QVBoxLayout()

        self.board_label = QLabel()
        self.board_label.setMinimumSize(350, 350)
        self.board_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.board_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.board_label, stretch=60)

        self.pgn_view = QTextBrowser()
        self.pgn_view.setOpenLinks(False)
        self.pgn_view.anchorClicked.connect(self.on_move_clicked)
        self._apply_no_underline_style()

        font = self.game_list.font()
        font.setPointSize(10)
        self.pgn_view.setFont(font)
        right_layout.addWidget(self.pgn_view, 40)

        # Navigation buttons
        buttons_layout = QHBoxLayout()
        self.btn_start = QPushButton("⏮")
        self.btn_prev = QPushButton("◀")
        self.btn_next = QPushButton("▶")
        self.btn_end = QPushButton("⏭")

        for btn in [self.btn_start, self.btn_prev, self.btn_next, self.btn_end]:
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.btn_start.clicked.connect(self.go_start)
        self.btn_prev.clicked.connect(self.go_prev)
        self.btn_next.clicked.connect(self.go_next)
        self.btn_end.clicked.connect(self.go_end)

        buttons_layout.addWidget(self.btn_start)
        buttons_layout.addWidget(self.btn_prev)
        buttons_layout.addWidget(self.btn_next)
        buttons_layout.addWidget(self.btn_end)

        right_layout.addLayout(buttons_layout)
        main_layout.addLayout(right_layout, 60)

    def _apply_no_underline_style(self):
        self.pgn_view.document().setDefaultStyleSheet("""
            a { text-decoration: none; color: black; }
            a:link { text-decoration: none; color: black; }
            a:visited { text-decoration: none; color: black; }
            a:hover { text-decoration: none; color: black; }
            a:active { text-decoration: none; color: black; }
        """)

    # ---------------------------------------------------------
    # LOAD GAMES / FILTER
    # ---------------------------------------------------------
    def _load_games(self) -> None:
        self.games.clear()

        try:
            with open(self.pgn_path, "r", encoding="utf-8") as f:
                index = 1
                while True:
                    game = chess.pgn.read_game(f)
                    if game is None:
                        break
                    self.games.append((index, game))
                    index += 1
        except Exception as e:
            self.game_list.addItem(f"Error loading PGN: {e}")

        self.filtered_games = list(self.games)

    def _apply_filter(self) -> None:
        text = self.search_box.text().lower().strip()

        if not text:
            self.filtered_games = list(self.games)
        else:
            self.filtered_games = []
            is_number = text.isdigit()
            number_query = int(text) if is_number else None

            for index, game in self.games:
                white = game.headers.get("White", "").lower()
                black = game.headers.get("Black", "").lower()

                if is_number and index == number_query:
                    self.filtered_games.append((index, game))
                    continue

                if text in white or text in black:
                    self.filtered_games.append((index, game))

        self._refresh_game_list()

    def _refresh_game_list(self) -> None:
        self.game_list.clear()

        for index, game in self.filtered_games:
            white = game.headers.get("White", "White")
            black = game.headers.get("Black", "Black")
            result = game.headers.get("Result", "")

            if result == "1-0":
                result_text = "1-0"
            elif result == "0-1":
                result_text = "0-1"
            elif result in ("1/2-1/2", "½-½"):
                result_text = "½-½"
            else:
                result_text = ""

            if result_text:
                item_text = f"{index}. {white} – {black} ({result_text})"
            else:
                item_text = f"{index}. {white} – {black}"

            self.game_list.addItem(item_text)

    # ---------------------------------------------------------
    # PGN HTML
    # ---------------------------------------------------------
    def build_pgn_html(self, game, highlight_index=None) -> str:
        board = game.board()
        moves = list(game.mainline_moves())

        white = game.headers.get("White", "White")
        black = game.headers.get("Black", "Black")

        html_parts = []
        html_parts.append(
            f'<div style="font-size:14pt; font-weight:bold; margin-bottom:10px;">'
            f'{white} – {black}'
            f'</div>'
        )
        html_parts.append('<div style="height:8px;"></div>')

        ply_index = 0
        move_number = 1
        i = 0

        while i < len(moves):
            html_parts.append(
                f'<span style="font-weight:bold; color:#333;">[{move_number}]</span> '
            )

            # White move
            white_move = moves[i]
            white_san = board.san(white_move)
            board.push(white_move)

            flags = []
            if board.is_repetition(3):
                flags.append("three fold")
            if board.halfmove_clock >= 100:
                flags.append("50-move rule")

            flag_text = ""
            if flags:
                flag_text = (
                    ' <span style="color:#008000; font-weight:bold;">('
                    + ", ".join(flags)
                    + ')</span>'
                )

            if highlight_index == ply_index:
                html_parts.append(
                    f'<span style="color:red; font-weight:bold;"><a href="move_{ply_index}">{white_san}</a></span>{flag_text} '
                )
            else:
                html_parts.append(
                    f'<a href="move_{ply_index}">{white_san}</a>{flag_text} '
                )

            ply_index += 1
            i += 1

            # Black move
            if i < len(moves):
                black_move = moves[i]
                black_san = board.san(black_move)
                board.push(black_move)

                flags = []
                if board.is_repetition(3):
                    flags.append("three fold")
                if board.halfmove_clock >= 100:
                    flags.append("50-move rule")

                flag_text = ""
                if flags:
                    flag_text = (
                        ' <span style="color:#008000; font-weight:bold;">('
                        + ", ".join(flags)
                        + ')</span>'
                    )

                if highlight_index == ply_index:
                    html_parts.append(
                        f'<span style="color:red; font-weight:bold;"><a href="move_{ply_index}">{black_san}</a></span>{flag_text} '
                    )
                else:
                    html_parts.append(
                        f'<a href="move_{ply_index}">{black_san}</a>{flag_text} '
                    )

                ply_index += 1
                i += 1

            move_number += 1

        return "".join(html_parts)

    # ---------------------------------------------------------
    # LIVE PGN RELOAD (from controller)
    # ---------------------------------------------------------
    def reload_pgn(self, pgn_path):
        """
        Reload PGN file and rebuild game list.
        Keep the same game selected using current_game_index.
        """
        try:
            with open(pgn_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            return

        # --- POPRAWIONE WCZYTYWANIE WIELU PARTII ---
        self.all_games = []
        pgn_io = io.StringIO(text)
        while True:
            game = chess.pgn.read_game(pgn_io)
            if game is None:
                break
            self.all_games.append(game)

        self.filtered_games = [(i, g) for i, g in enumerate(self.all_games)]

        # rebuild list widget
        self.game_list.clear()
        for idx, game in self.filtered_games:
            white = game.headers.get("White", "White")
            black = game.headers.get("Black", "Black")
            result = game.headers.get("Result", "*")
            self.game_list.addItem(f"{idx+1}. {white} vs {black}   {result}")

        # restore selection of the current game
        if 0 <= self.current_game_index < len(self.filtered_games):
            self.game_list.setCurrentRow(self.current_game_index)

            # reload the actual game object
            _, game = self.filtered_games[self.current_game_index]
            self.current_game = game
            self.current_board = game.board()
            self.move_list = list(game.mainline_moves())
            self.move_index = len(self.move_list)

            self._compute_repetition_snapshots()
            self._refresh_pgn_with_highlight()
            self.update_board()

    # ---------------------------------------------------------
    # REPETITION SNAPSHOTS
    # ---------------------------------------------------------
    def _compute_repetition_snapshots(self):
        self.repetition_snapshots = set()

        board = chess.Board()
        key_map = {}

        for idx, move in enumerate(self.move_list):
            board.push(move)
            key = board._transposition_key()
            key_map.setdefault(key, []).append(idx)

        for key, indices in key_map.items():
            if len(indices) >= 3:
                self.repetition_snapshots.update(indices)

    # ---------------------------------------------------------
    # BOARD RENDERING
    # ---------------------------------------------------------
    def update_board(self) -> None:
        if self.current_board is None:
            self.board_label.clear()
            return

        board = self.current_board.copy()

        current_index = self.move_index - 1
        is_snapshot = current_index in self.repetition_snapshots

        border_color = Qt.green if is_snapshot else Qt.transparent

        last_move = None
        for move in self.move_list[:self.move_index]:
            last_move = move
            board.push(move)

        svg = chess.svg.board(
            board,
            lastmove=last_move,
            colors={
                "square light lastmove": "#fff066",
                "square dark lastmove": "#fff066"
            }
        )

        renderer = QSvgRenderer(bytearray(svg, encoding="utf-8"))

        label_size = self.board_label.size()
        border = 12
        available = min(label_size.width(), label_size.height())
        side = max(available - border * 2, 300)

        pixmap = QPixmap(side + border * 2, side + border * 2)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        pen = QPen(border_color)
        pen.setWidth(border)
        painter.setPen(pen)

        offset = border // 2
        painter.drawRect(
            offset,
            offset,
            side + border * 2 - border,
            side + border * 2 - border
        )

        renderer.render(painter, QRectF(border, border, side, side))
        painter.end()

        self.board_label.setPixmap(pixmap)

    # ---------------------------------------------------------
    # KEYBOARD CONTROL
    # ---------------------------------------------------------
    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key_Left:
            self.go_prev()
            return
        if key == Qt.Key_Right:
            self.go_next()
            return
        if key == Qt.Key_Home:
            self.go_start()
            return
        if key == Qt.Key_End:
            self.go_end()
            return

        super().keyPressEvent(event)

    # ---------------------------------------------------------
    # MOVE NAVIGATION
    # ---------------------------------------------------------
    def _refresh_pgn_with_highlight(self):
        if not self.current_game:
            return
        highlight = self.move_index - 1 if self.move_index > 0 else None
        html = self.build_pgn_html(self.current_game, highlight_index=highlight)
        self.pgn_view.setHtml(html)
        self._apply_no_underline_style()

    def go_start(self) -> None:
        self.move_index = 0
        self.update_board()
        self._refresh_pgn_with_highlight()

    def go_prev(self) -> None:
        if self.move_index > 0:
            self.move_index -= 1
        self.update_board()
        self._refresh_pgn_with_highlight()

    def go_next(self) -> None:
        if self.move_index < len(self.move_list):
            self.move_index += 1
        self.update_board()
        self._refresh_pgn_with_highlight()

    def go_end(self) -> None:
        self.move_index = len(self.move_list)
        self.update_board()
        self._refresh_pgn_with_highlight()

    # ---------------------------------------------------------
    # MOVE CLICK
    # ---------------------------------------------------------
    def on_move_clicked(self, url):
        move_str = url.toString()
        index = int(move_str.split("_")[1])

        self.move_index = index + 1
        self.update_board()
        self.highlight_current_move(index)

    # ---------------------------------------------------------
    # MOVE HIGHLIGHT
    # ---------------------------------------------------------
    def highlight_current_move(self, index):
        if self.current_game is None:
            return

        html = self.build_pgn_html(self.current_game, highlight_index=index)
        self.pgn_view.setHtml(html)
        self._apply_no_underline_style()

    # ---------------------------------------------------------
    # JUMP TO MOVE (for controller)
    # ---------------------------------------------------------
    def jump_to_move(self, move_index: int):
        if not self.move_list:
            return

        if move_index < 0:
            move_index = 0
        if move_index > len(self.move_list):
            move_index = len(self.move_list)

        self.move_index = move_index
        self.update_board()
        self._refresh_pgn_with_highlight()
