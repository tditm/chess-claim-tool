
from typing import List, Dict, Any, Optional
import chess
import re

from src.models.claims import ClaimEntry, ClaimType, get_players


class ReminderManager:
    """
    Manages all reminder logic for chess games.
    
    This class is decoupled from the GUI - it takes game data and claims model
    as arguments and returns ClaimEntry objects without calling any view methods.
    """

    def __init__(self) -> None:
        self.shown_reminders: set = set()
        self.sofia_rule_settings: Dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def make_game_id(self, game) -> str:
        """
        Generates a stable identifier for a game based on PGN headers.
        This ID does NOT change even if the PGN file is rebuilt or reordered.
        """
        return "|".join([
            game.headers.get("Event", ""),
            game.headers.get("Site", ""),
            game.headers.get("Date", ""),
            game.headers.get("Round", ""),
            game.headers.get("White", ""),
            game.headers.get("Black", ""),
        ])

    def extract_clock_from_node(self, node) -> Optional[str]:
        """Extract clock time from a PGN node comment."""
        if not node or not node.comment:
            return None

        match = re.search(r"\[%clk\s+(\d{1,2}:\d{2}:\d{2})\]", node.comment)
        if match:
            return match.group(1)
        return None

    def get_move_count(self, game) -> int:
        """Get the number of full moves in a game."""
        return len(list(game.mainline_moves())) // 2

    # -------------------------------------------------------------------------
    # Reminder Check Methods - All Return List[ClaimEntry]
    # -------------------------------------------------------------------------

    def check_scoresheet_reminders(
        self,
        games: List[Any],
        claims_model: Any,
        enabled: bool,
        threshold: int,
        fired_dict: Dict[int, bool]
    ) -> tuple:
        """
        Check for scoresheet reminders.
        
        Returns: (list of ClaimEntry objects, updated fired_dict)
        """
        entries = []

        if not enabled or not games:
            return entries, fired_dict

        for idx, game in enumerate(games, start=1):
            result = game.headers.get("Result", "").strip()
            if result in ("1-0", "0-1", "1/2-1/2", "½-½"):
                continue

            move_count = self.get_move_count(game)
            already = fired_dict.get(idx, False)

            if not already and move_count >= threshold:
                fired_dict[idx] = True

                board_number = claims_model.get_board_number(game)
                gid = self.make_game_id(game)

                entry = ClaimEntry(
                    type=ClaimType.SCORESHEET_REMINDER,
                    board_number=board_number,
                    players=get_players(game),
                    move=f"{threshold}-move game",
                    game_index=idx - 1,
                    move_counter=move_count,
                    start_move_counter=0,
                    game_id=gid,
                )
                entries.append(entry)

        return entries, fired_dict

    def check_timecontrol_reminders(
        self,
        games: List[Any],
        claims_model: Any,
        enabled: bool,
        threshold: int,
        fired_dict: Dict[int, bool]
    ) -> tuple:
        """
        Check for time control reminders.
        
        Returns: (list of ClaimEntry objects, updated fired_dict)
        """
        entries = []

        if not enabled or not games:
            return entries, fired_dict

        for idx, game in enumerate(games, start=1):
            result = game.headers.get("Result", "").strip()
            if result in ("1-0", "0-1", "1/2-1/2", "½-½"):
                continue

            move_count = self.get_move_count(game)
            already = fired_dict.get(idx, False)

            if not already and move_count >= threshold:
                fired_dict[idx] = True

                board_number = claims_model.get_board_number(game)
                gid = self.make_game_id(game)

                entry = ClaimEntry(
                    type=ClaimType.TIMECONTROL_REMINDER,
                    board_number=board_number,
                    players=get_players(game),
                    move=f"{threshold}-move game",
                    game_index=idx - 1,
                    move_counter=move_count,
                    start_move_counter=0,
                    game_id=gid,
                )
                entries.append(entry)

        return entries, fired_dict

    def check_possible_threefold(
        self,
        games: List[Any],
        claims_model: Any,
        enabled: bool
    ) -> tuple:
        """
        Check for possible threefold repetition warnings.
        
        Returns: (list of ClaimEntry objects, updated shown_reminders set)
        """
        entries = []

        if not enabled or not games:
            return entries, self.shown_reminders

        for idx, game in enumerate(games, start=1):
            board = game.board()
            positions: Dict[str, int] = {}

            start_fen = " ".join(board.fen().split(" ")[:4])
            positions[start_fen] = 1

            move_counter = 0
            for move in game.mainline_moves():
                board.push(move)
                move_counter += 1

                fen = " ".join(board.fen().split(" ")[:4])
                positions[fen] = positions.get(fen, 0) + 1

                if positions[fen] == 2:
                    key = ("twofold", idx, fen)

                    if key not in self.shown_reminders:
                        self.shown_reminders.add(key)

                        board_number = claims_model.get_board_number(game)
                        gid = self.make_game_id(game)

                        entry = ClaimEntry(
                            type=ClaimType.TWO_FOLD_WARNING,
                            board_number=board_number,
                            players=get_players(game),
                            move="near 3-fold repetition",
                            game_index=idx - 1,
                            move_counter=move_counter,
                            start_move_counter=0,
                            game_id=gid,
                        )
                        entries.append(entry)

        return entries, self.shown_reminders

    def check_possible_fiftymove(
        self,
        games: List[Any],
        claims_model: Any,
        enabled: bool
    ) -> tuple:
        """
        Check for possible 50-move rule warnings.
        
        Returns: (list of ClaimEntry objects, updated shown_reminders set)
        """
        entries = []

        if not enabled or not games:
            return entries, self.shown_reminders

        for idx, game in enumerate(games, start=1):
            board = game.board()
            halfmove_clock = 0
            move_counter = 0

            for move in game.mainline_moves():
                piece = board.piece_at(move.from_square)
                if board.is_capture(move) or (piece and piece.piece_type == chess.PAWN):
                    halfmove_clock = 0
                else:
                    halfmove_clock += 1

                board.push(move)
                move_counter += 1

                if halfmove_clock >= 90:
                    key = ("fiftymove", idx, halfmove_clock)

                    if key not in self.shown_reminders:
                        self.shown_reminders.add(key)

                        board_number = claims_model.get_board_number(game)
                        gid = self.make_game_id(game)

                        entry = ClaimEntry(
                            type=ClaimType.FORTYFIVE_MOVES_WARNING,
                            board_number=board_number,
                            players=get_players(game),
                            move="near 50-move rule",
                            game_index=idx - 1,
                            move_counter=move_counter,
                            start_move_counter=0,
                            game_id=gid,
                        )
                        entries.append(entry)

        return entries, self.shown_reminders

    def check_low_time_reminder(
        self,
        games: List[Any],
        claims_model: Any,
        enabled: bool,
        threshold_seconds: int,
        fired_dict: Dict[int, bool]
    ) -> tuple:
        """
        Check for low time reminders.
        
        Returns: (list of ClaimEntry objects, updated fired_dict)
        """
        entries = []

        if not enabled or not games:
            return entries, fired_dict

        for idx, game in enumerate(games, start=1):
            node = game.end()
            clk = None

            while node is not None and clk is None:
                clk = self.extract_clock_from_node(node)
                node = node.parent

            if not clk:
                continue

            try:
                h, m, s = map(int, clk.split(":"))
            except ValueError:
                continue

            total_seconds = h * 3600 + m * 60 + s
            already = fired_dict.get(idx, False)

            if not already and total_seconds <= threshold_seconds:
                fired_dict[idx] = True

                board_number = claims_model.get_board_number(game)
                gid = self.make_game_id(game)

                entry = ClaimEntry(
                    type=ClaimType.LOW_TIME_REMINDER,
                    board_number=board_number,
                    players=get_players(game),
                    move=f"Low time: {clk}",
                    game_index=idx - 1,
                    move_counter=len(list(game.mainline_moves())),
                    start_move_counter=0,
                    game_id=gid,
                )
                entries.append(entry)

        return entries, fired_dict

    def check_flag_fall_reminder(
        self,
        games: List[Any],
        claims_model: Any,
        enabled: bool,
        fired_dict: Dict[int, bool]
    ) -> tuple:
        """
        Check for flag fall reminders.
        
        Returns: (list of ClaimEntry objects, updated fired_dict)
        """
        entries = []

        if not enabled or not games:
            return entries, fired_dict

        for idx, game in enumerate(games, start=1):
            node = game.end()
            clk = None

            while node is not None and clk is None:
                clk = self.extract_clock_from_node(node)
                node = node.parent

            if not clk:
                continue

            if clk not in ("00:00:00", "00:00", "0:00"):
                continue

            already = fired_dict.get(idx, False)

            if not already:
                fired_dict[idx] = True

                board_number = claims_model.get_board_number(game)
                gid = self.make_game_id(game)

                entry = ClaimEntry(
                    type=ClaimType.FLAG_FALL_REMINDER,
                    board_number=board_number,
                    players=get_players(game),
                    move="Flag fall",
                    game_index=idx - 1,
                    move_counter=len(list(game.mainline_moves())),
                    start_move_counter=0,
                    game_id=gid,
                )
                entries.append(entry)

        return entries, fired_dict

    def check_sofia_rule_reminder(
        self,
        games: List[Any],
        claims_model: Any,
        enabled: bool,
        threshold: int,
        fired_dict: Dict[int, bool]
    ) -> tuple:
        """
        Check for Sofia rule violations.
        
        The Sofia rule states that players cannot agree to a draw before the 
        specified number of moves (typically 30) have been played.
        
        However, this check MUST EXCLUDE draws that result from technical chess rules:
        - Stalemate
        - Insufficient material
        - Threefold repetition (claimed or position repeated 3 times)
        - Fivefold repetition (automatic draw)
        - Fifty-move rule (claimed)
        - Seventy-five move rule (automatic draw)
        
        These are legal draws by the strict rules of chess and do NOT violate Sofia rule.
        
        Note on move counting: PGN move numbers count individual half-moves (plies).
        A game ending at PGN move 38 means white played move 38, which is 19 full moves + 1 ply.
        We use board.fullmove_number property to get the current full move number for comparison.
        
        Returns: (list of ClaimEntry objects, updated fired_dict)
        """
        entries = []

        if not enabled or not games:
            return entries, fired_dict

        for idx, game in enumerate(games, start=1):
            result = game.headers.get("Result", "").strip()
            
            # Only check drawn games (draw agreed or draw claimed)
            if result not in ("1/2-1/2", "½-½"):
                continue

            # BUG FIX #1: Use board.fullmove_number for accurate move comparison
            # PGN move numbers are half-moves, but fullmove_number gives us the actual move number
            board = game.board()
            
            # Replay the game to get final position state and move count
            # Skip games with illegal/corrupted moves
            try:
                for move in game.mainline_moves():
                    board.push(move)
            except Exception:
                # Game has malformed PGN - skip it
                continue
            
            # Get the final full move number (this is what players see in PGN)
            # Note: fullmove_number is a property, not a method - no parentheses!
            final_move_number = board.fullmove_number
            
            already = fired_dict.get(idx, False)

            # Skip if warning already fired for this game
            if already:
                continue

            # BUG FIX #1: Compare against fullmove_number directly (not half-moves // 2)
            # If final move number >= threshold, no Sofia violation occurred
            if final_move_number >= threshold:
                continue

            is_technical_draw = False

            # Check 1: Stalemate
            if board.is_stalemate():
                is_technical_draw = True

            # Check 2: Insufficient material
            elif board.is_insufficient_material():
                is_technical_draw = True

            # Check 3: Fivefold repetition (automatic draw by chess rules)
            elif board.is_fivefold_repetition():
                is_technical_draw = True

            # Check 4: Seventy-five move rule (automatic draw by chess rules)
            elif board.is_seventyfive_moves():
                is_technical_draw = True

            # BUG FIX #2: Directly check live board state for threefold repetition claim possibility
            # This checks if the position has occurred 3 times, which allows a draw claim
            elif board.can_claim_threefold_repetition():
                is_technical_draw = True

            # Check 5: Fifty-move rule - check if 50 moves without capture/pawn move
            elif board.is_fifty_moves():
                is_technical_draw = True

            # Check 6: Fifty-move/Threefold claim detected in the game model entries
            # We also verify against existing claims for this specific game
            gid = self.make_game_id(game)
            for entry in claims_model.entries:
                if (entry.game_id == gid and 
                    entry.type in (ClaimType.FIFTY_MOVES, ClaimType.THREEFOLD)):
                    is_technical_draw = True
                    break

            # Check 7: If this game appears in don't_check, it means a technical rule was triggered
            players = get_players(game)
            if players in claims_model.dont_check:
                is_technical_draw = True

            # Only trigger Sofia rule warning if this was NOT a technical draw
            # This means the players likely agreed to a draw prematurely
            if not is_technical_draw:
                fired_dict[idx] = True

                board_number = claims_model.get_board_number(game)
                entry = ClaimEntry(
                    type=ClaimType.SOFIA_RULE,
                    board_number=board_number,
                    players=get_players(game),
                    move=f"Draw at move {final_move_number} (Sofia rule: {threshold} moves)",
                    game_index=idx - 1,
                    move_counter=final_move_number * 2 - 1 if board.turn else final_move_number * 2,
                    start_move_counter=0,
                    game_id=gid,
                )
                entries.append(entry)

        return entries, fired_dict

    # -------------------------------------------------------------------------
    # Central Orchestration Method
    # -------------------------------------------------------------------------

    def run_all_reminders(
        self,
        games: List[Any],
        claims_model: Any,
        scoresheet_enabled: bool,
        scoresheet_threshold: int,
        scoresheet_fired: Dict[int, bool],
        timecontrol_enabled: bool,
        timecontrol_threshold: int,
        timecontrol_fired: Dict[int, bool],
        threefold_enabled: bool,
        fiftymove_enabled: bool,
        low_time_enabled: bool,
        low_time_threshold_seconds: int,
        low_time_fired: Dict[int, bool],
        flag_fall_enabled: bool,
        flag_fall_fired: Dict[int, bool],
        sofia_rule_enabled: bool,
        sofia_rule_threshold: int,
        sofia_rule_fired: Dict[int, bool]
    ) -> tuple:
        """
        Run all enabled reminders and return collected entries.
        
        Returns: (list of ClaimEntry objects, updated state dicts)
        """
        all_entries = []

        # Scoresheet reminder
        if scoresheet_enabled:
            entries, scoresheet_fired = self.check_scoresheet_reminders(
                games, claims_model, scoresheet_enabled,
                scoresheet_threshold, scoresheet_fired
            )
            all_entries.extend(entries)

        # Time control reminder
        if timecontrol_enabled:
            entries, timecontrol_fired = self.check_timecontrol_reminders(
                games, claims_model, timecontrol_enabled,
                timecontrol_threshold, timecontrol_fired
            )
            all_entries.extend(entries)

        # Possible threefold
        if threefold_enabled:
            entries, self.shown_reminders = self.check_possible_threefold(
                games, claims_model, threefold_enabled
            )
            all_entries.extend(entries)

        # Possible fiftymove
        if fiftymove_enabled:
            entries, self.shown_reminders = self.check_possible_fiftymove(
                games, claims_model, fiftymove_enabled
            )
            all_entries.extend(entries)

        # Low time reminder
        if low_time_enabled:
            entries, low_time_fired = self.check_low_time_reminder(
                games, claims_model, low_time_enabled,
                low_time_threshold_seconds, low_time_fired
            )
            all_entries.extend(entries)

        # Flag fall reminder
        if flag_fall_enabled:
            entries, flag_fall_fired = self.check_flag_fall_reminder(
                games, claims_model, flag_fall_enabled,
                flag_fall_fired
            )
            all_entries.extend(entries)

        # Sofia rule reminder
        if sofia_rule_enabled:
            entries, sofia_rule_fired = self.check_sofia_rule_reminder(
                games, claims_model, sofia_rule_enabled,
                sofia_rule_threshold, sofia_rule_fired
            )
            all_entries.extend(entries)

        return (
            all_entries,
            scoresheet_fired,
            timecontrol_fired,
            low_time_fired,
            flag_fall_fired,
            sofia_rule_fired
        )
