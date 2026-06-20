"""
Chess Claim Tool: Claims

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

from dataclasses import dataclass
from enum import Enum
from math import ceil
from chess.pgn import Game


def get_players(game: Game) -> str:
    """
    Returns a short 'White - Black' string for display.
    Names are trimmed to keep UI compact.
    """
    white = game.headers.get("White", "")[:22]
    black = game.headers.get("Black", "")[:22]
    return f"{white} - {black}"


class ClaimType(Enum):
    THREEFOLD = "3-fold repetition"
    FIVEFOLD = "5-fold repetition"
    FIFTY_MOVES = "50-move rule"
    SEVENTYFIVE_MOVES = "75-move rule"
    SCORESHEET_REMINDER = "Scoresheet reminder"
    TWO_FOLD_WARNING = "2-fold repetition"
    FORTYFIVE_MOVES_WARNING = "45-move reminder"
    
@dataclass(frozen=True)
class ClaimEntry:
    """
    Represents a single claim event detected in a game.
    start_move_counter is used for rules that require
    tracking the beginning of a counting sequence (e.g. 50-move rule).
    """
    type: ClaimType
    board_number: str
    players: str
    move: str
    game_index: int
    move_counter: int          # final move index (claim moment)
    start_move_counter: int    # starting move index
    comment: str = ""          # NEW — PGN comment (e.g. "First counting move: X")


class Claims:
    """
    Tracks draw claims (3-fold, 5-fold, 50-move, 75-move) across multiple games.
    Stores unique entries and prevents duplicates.
    """

    def __init__(self):
        self.dont_check: set[str] = set()
        self.entries: set[ClaimEntry] = set()

    def check_game(self, game: Game, game_index: int) -> set[ClaimEntry]:
        """
        Analyzes a single game and detects draw claims.
        Returns only new entries (no duplicates).
        """
        move_counter = 0
        board = game.board()
        players = get_players(game)
        board_number = self.get_board_number(game)

        new_entries: set[ClaimEntry] = set()

        # Track the last irreversible move (capture or pawn move)
        last_irreversible_move = 0

        for move in game.mainline_moves():
            san_move = board.san(move)

            # Detect irreversible moves BEFORE pushing
            if board.is_capture(move) or board.piece_at(move.from_square).piece_type == 1:
                last_irreversible_move = move_counter + 1

            board.push(move)
            move_counter += 1
            printable_move = self.get_printable_move(move_counter, san_move)

            # 5-fold repetition → immediate stop
            if board.is_fivefold_repetition():
                entry = ClaimEntry(
                    ClaimType.FIVEFOLD, board_number, players,
                    printable_move, game_index, move_counter, last_irreversible_move,
                    ""   # no comment
                )
                new_entries.add(entry)
                self.dont_check.add(players)
                break

            # 75-move rule → immediate stop (NO COMMENT)
            if board.is_seventyfive_moves():
                entry = ClaimEntry(
                    ClaimType.SEVENTYFIVE_MOVES, board_number, players,
                    printable_move, game_index, move_counter, last_irreversible_move,
                    ""   # no comment
                )
                new_entries.add(entry)
                self.dont_check.add(players)
                break

            # 50-move rule → ADD COMMENT
            if board.is_fifty_moves():
                comment = f"First counting move: {last_irreversible_move}"
                new_entries.add(ClaimEntry(
                    ClaimType.FIFTY_MOVES, board_number, players,
                    printable_move, game_index, move_counter, last_irreversible_move,
                    comment
                ))

            # 3-fold repetition → NO COMMENT
            if board.is_repetition(count=3):
                new_entries.add(ClaimEntry(
                    ClaimType.THREEFOLD, board_number, players,
                    printable_move, game_index, move_counter, last_irreversible_move,
                    ""   # no comment
                ))

        # Remove duplicates compared to previous runs
        unique_entries = new_entries.difference(self.entries)
        self.entries.update(unique_entries)
        return unique_entries

    def empty_dont_check(self) -> None:
        """Clears the list of players whose games should not be rechecked."""
        self.dont_check.clear()

    def empty_entries(self) -> None:
        """Clears all stored claim entries."""
        self.entries.clear()

    @staticmethod
    def get_printable_move(move_counter: int, san_move: str) -> str:
        """
        Formats the move number for display (e.g. '12.Nf3' or '12...Nf6').
        """
        move_num = ceil(move_counter / 2)
        return f"{move_num}...{san_move}" if move_counter % 2 == 0 else f"{move_num}.{san_move}"

    @staticmethod
    def get_board_number(game: Game) -> str:
        board = game.headers.get("Board")
        if board and board != "None":
            return board

        rnd = game.headers.get("Round")
        if rnd and rnd != "None":
            return rnd

        return "-"
