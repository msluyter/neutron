#!/usr/bin/env python3
"""
Neutron - A two-player abstract strategy game.

Rules:
- 5x5 board. Each player has 5 soldiers on opposite rows, neutron starts at center.
- All pieces slide in a straight line (orthogonal or diagonal) until hitting the
  board edge or another piece. No intermediate stops. No capturing.
- Each turn: move the neutron, then move one of your soldiers.
  Exception: the first player skips the neutron move on their opening turn.
- Win by: (1) the neutron reaching your home row (no matter who moved it), or
  (2) your opponent being unable to move the neutron on their turn.
- The game ends the instant the neutron reaches a home row.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import random

# Board geometry
BOARD_SIZE = 5
COLS = "abcde"

# 8 directions: orthogonal + diagonal
DIRECTIONS = [
    (0, 1), (0, -1), (1, 0), (-1, 0),  # up, down, right, left
    (1, 1), (1, -1), (-1, 1), (-1, -1),  # diagonals
]


@dataclass(frozen=True)
class Pos:
    col: int  # 0-4 internally
    row: int  # 0-4 internally (row 0 = display row 1 = bottom)

    @classmethod
    def from_notation(cls, s: str) -> Pos:
        """Parse 'a1' .. 'e5' notation."""
        s = s.strip().lower()
        if len(s) != 2 or s[0] not in COLS or not s[1].isdigit():
            raise ValueError(f"Invalid square: '{s}'")
        col = COLS.index(s[0])
        row = int(s[1]) - 1  # '1' -> 0
        if not (0 <= row < BOARD_SIZE):
            raise ValueError(f"Row out of range: '{s}'")
        return cls(col, row)

    def to_notation(self) -> str:
        return f"{COLS[self.col]}{self.row + 1}"

    def __str__(self) -> str:
        return self.to_notation()


class Board:
    """Immutable-style board; use copy() before mutating for search."""

    def __init__(self, bottom_player: int = 1) -> None:
        # grid[row][col]: ' ' empty, '1'/'2' soldiers, 'N' neutron
        self.grid: list[list[str]] = [[' '] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.neutron: Pos = Pos(2, 2)  # c3
        self.soldiers: dict[int, set[Pos]] = {1: set(), 2: set()}
        # home_row[player] = row index where that player's soldiers start (and wins)
        top_player = 2 if bottom_player == 1 else 1
        self.home_row: dict[int, int] = {bottom_player: 0, top_player: 4}
        self._setup(bottom_player)

    def _setup(self, bottom_player: int) -> None:
        top_player = 2 if bottom_player == 1 else 1
        for c in range(BOARD_SIZE):
            self._place(Pos(c, 0), str(bottom_player))
            self.soldiers[bottom_player].add(Pos(c, 0))
            self._place(Pos(c, 4), str(top_player))
            self.soldiers[top_player].add(Pos(c, 4))
        self._place(self.neutron, 'N')

    def _place(self, pos: Pos, ch: str) -> None:
        self.grid[pos.row][pos.col] = ch

    def copy(self) -> Board:
        b = Board.__new__(Board)
        b.grid = [row[:] for row in self.grid]
        b.neutron = self.neutron
        b.soldiers = {1: set(self.soldiers[1]), 2: set(self.soldiers[2])}
        b.home_row = self.home_row
        return b

    # --- movement ---

    def slide_dest(self, pos: Pos, dc: int, dr: int) -> Optional[Pos]:
        """Return the final square a piece at `pos` reaches sliding in (dc, dr),
        or None if it cannot move in that direction at all."""
        c, r = pos.col, pos.row
        last = None
        while True:
            c, r = c + dc, r + dr
            if not (0 <= c < BOARD_SIZE and 0 <= r < BOARD_SIZE):
                break
            if self.grid[r][c] != ' ':
                break
            last = Pos(c, r)
        return last

    def get_slides(self, pos: Pos) -> list[Pos]:
        """All legal destinations for the piece at `pos` (one per direction)."""
        dests = []
        for dc, dr in DIRECTIONS:
            d = self.slide_dest(pos, dc, dr)
            if d is not None:
                dests.append(d)
        return dests

    def move(self, frm: Pos, to: Pos) -> None:
        """Move the piece at `frm` to `to`. No validation — caller must check."""
        ch = self.grid[frm.row][frm.col]
        self.grid[frm.row][frm.col] = ' '
        self.grid[to.row][to.col] = ch
        if ch == 'N':
            self.neutron = to
        else:
            player = int(ch)
            self.soldiers[player].discard(frm)
            self.soldiers[player].add(to)

    def is_valid_slide(self, frm: Pos, to: Pos) -> bool:
        """Check that `to` is reachable from `frm` by a legal slide."""
        return to in self.get_slides(frm)

    # --- win detection ---

    def check_winner(self) -> Optional[int]:
        """Return winning player (1 or 2) or None."""
        nr = self.neutron.row
        for player, hr in self.home_row.items():
            if nr == hr:
                return player
        return None

    def neutron_can_move(self) -> bool:
        """Can the neutron slide in any direction?"""
        return bool(self.get_slides(self.neutron))

    def has_soldier_move(self, player: int) -> bool:
        """Does `player` have at least one legal soldier slide?"""
        return any(self.get_slides(s) for s in self.soldiers[player])

    # --- display ---

    def display(self) -> None:
        """Print the board. Row 5 at top, row 1 at bottom. Labels = real coords."""
        symbols = {'1': '○', '2': '●', 'N': '◈', ' ': '·'}
        print()
        print("  ┌───┬───┬───┬───┬───┐")
        for r in range(BOARD_SIZE - 1, -1, -1):
            if r < BOARD_SIZE - 1:
                print("  ├───┼───┼───┼───┼───┤")
            cells = " │ ".join(symbols[self.grid[r][c]] for c in range(BOARD_SIZE))
            print(f"{r + 1} │ {cells} │")
        print("  └───┴───┴───┴───┴───┘")
        print("    a   b   c   d   e")


# ---------------------------------------------------------------------------
# AI
# ---------------------------------------------------------------------------

class SimpleAI:
    """Simple AI: avoid immediate losses, prefer wins, otherwise random.

    The game loop calls choose_neutron_move() and choose_soldier_move()
    separately (with the board mutated between them), mirroring the two-phase
    turn structure. On the first turn of the game the loop calls only
    choose_soldier_move().

    Internally the AI plans both moves together so it can evaluate full turns,
    then caches the soldier move for the second call.
    """

    def __init__(self, player: int) -> None:
        self.player = player
        self.opponent = 2 if player == 1 else 1
        self._planned_soldier_move: Optional[tuple[Pos, Pos]] = None

    # --- public interface (called by Game) ---

    def choose_neutron_move(self, board: Board) -> Pos:
        """Pick the neutron destination and internally plan the soldier move."""
        n_dest, s_move = self._plan_full_turn(board)
        self._planned_soldier_move = s_move
        print(f"\nComputer plays neutron: N → {n_dest}")
        return n_dest

    def choose_soldier_move(self, board: Board) -> tuple[Pos, Pos]:
        """Return the soldier move (planned or freshly computed)."""
        if self._planned_soldier_move is not None:
            move = self._planned_soldier_move
            self._planned_soldier_move = None
            # Verify the planned move is still valid (board may have changed
            # if the neutron move ended the game, but the loop won't call us).
            if board.is_valid_slide(move[0], move[1]):
                print(f"Computer plays soldier: {move[0]} → {move[1]}")
                return move
        # Fallback: pick any legal soldier move
        move = self._pick_soldier_move(board)
        print(f"Computer plays soldier: {move[0]} → {move[1]}")
        return move

    # --- planning ---

    def _plan_full_turn(self, board: Board) -> tuple[Pos, tuple[Pos, Pos]]:
        """Evaluate all (neutron_dest, soldier_move) pairs and pick the best."""
        candidates = self._enumerate_turns(board)

        # Prefer winning turns
        for n_dest, s_move in candidates:
            if self._turn_wins(board, n_dest, s_move):
                return n_dest, s_move

        # Then safe turns (opponent can't win on their next turn)
        safe = [(n, s) for n, s in candidates if not self._turn_loses(board, n, s)]
        if safe:
            return random.choice(safe)

        # All turns lose — pick randomly
        return random.choice(candidates)

    def _pick_soldier_move(self, board: Board) -> tuple[Pos, Pos]:
        """Pick any legal soldier move on the current board."""
        moves = []
        for s in board.soldiers[self.player]:
            for dest in board.get_slides(s):
                moves.append((s, dest))
        return random.choice(moves)

    def _enumerate_turns(self, board: Board) -> list[tuple[Pos, tuple[Pos, Pos]]]:
        """All legal (neutron_dest, (soldier_from, soldier_to)) combinations."""
        turns: list[tuple[Pos, tuple[Pos, Pos]]] = []
        for n_dest in board.get_slides(board.neutron):
            b1 = board.copy()
            b1.move(b1.neutron, n_dest)
            # If neutron move wins, we still need a soldier move but any will do
            if b1.check_winner() == self.player:
                for s in b1.soldiers[self.player]:
                    for s_dest in b1.get_slides(s):
                        return [(n_dest, (s, s_dest))]
            for s in b1.soldiers[self.player]:
                for s_dest in b1.get_slides(s):
                    turns.append((n_dest, (s, s_dest)))
        return turns

    def _turn_wins(self, board: Board, n_dest: Pos, s_move: tuple[Pos, Pos]) -> bool:
        b = board.copy()
        b.move(b.neutron, n_dest)
        if b.check_winner() == self.player:
            return True
        b.move(*s_move)
        return b.check_winner() == self.player

    def _turn_loses(self, board: Board, n_dest: Pos, s_move: tuple[Pos, Pos]) -> bool:
        """Would the opponent win on their very next turn?"""
        b = board.copy()
        b.move(b.neutron, n_dest)
        # If our neutron move hands the opponent a win, that's a loss
        winner = b.check_winner()
        if winner == self.opponent:
            return True
        b.move(*s_move)
        winner = b.check_winner()
        if winner == self.opponent:
            return True
        # Check if opponent's neutron move can reach their home row
        for opp_n_dest in b.get_slides(b.neutron):
            b2 = b.copy()
            b2.move(b2.neutron, opp_n_dest)
            if b2.check_winner() == self.opponent:
                return True
        return False


# ---------------------------------------------------------------------------
# Game loop
# ---------------------------------------------------------------------------

class Game:
    def __init__(self) -> None:
        self.board: Board = None  # type: ignore[assignment]  # created after intro
        self.human: int = 0  # 1 or 2
        self.ai_player: int = 0
        self.current: int = 1  # player 1 goes first
        self.first_turn = True

    def _display(self) -> None:
        self.board.display()

    def run(self) -> None:
        self._intro()
        self.board = Board(bottom_player=self.human)
        self._display()

        while True:
            is_human = self.current == self.human
            opponent = 2 if self.current == 1 else 1

            # --- Phase 1: Neutron move (skip on the very first turn) ---
            if not self.first_turn:
                # Check if neutron is blocked → current player loses
                if not self.board.neutron_can_move():
                    self._display()
                    self._game_over(opponent, reason="neutron is blocked")
                    return

                n_to = self._get_neutron_move(is_human)
                self.board.move(self.board.neutron, n_to)

                # Neutron on a home row? Game over immediately.
                winner = self.board.check_winner()
                if winner is not None:
                    self._display()
                    self._game_over(winner)
                    return

                # Show the board after the neutron move
                self._display()

            # --- Phase 2: Soldier move ---
            if not self.board.has_soldier_move(self.current):
                self._display()
                self._game_over(opponent, reason="no soldier moves available")
                return

            s_from, s_to = self._get_soldier_move(is_human)
            self.board.move(s_from, s_to)

            self._display()

            # Switch turn
            self.current = opponent
            self.first_turn = False

    # --- input dispatch ---

    def _get_neutron_move(self, is_human: bool) -> Pos:
        """Get the neutron destination for this turn."""
        if is_human:
            return self._human_neutron_move()
        return self._ai_neutron_move()

    def _get_soldier_move(self, is_human: bool) -> tuple[Pos, Pos]:
        """Get (from, to) for the soldier move."""
        if is_human:
            return self._human_soldier_move()
        return self._ai_soldier_move()

    # --- human input ---

    def _human_neutron_move(self) -> Pos:
        while True:
            try:
                raw = input("\nMove the neutron (e.g. N-c1): ").strip()
                parts = raw.split('-', 1)
                if len(parts) != 2 or parts[0].strip().upper() != 'N':
                    print("Format: N-<dest> (e.g. N-c1)")
                    continue
                n_to = Pos.from_notation(parts[1])
                if not self.board.is_valid_slide(self.board.neutron, n_to):
                    print("Invalid neutron slide.")
                    continue
                return n_to
            except ValueError as e:
                print(f"  {e}")

    def _human_soldier_move(self) -> tuple[Pos, Pos]:
        while True:
            try:
                raw = input("Move a soldier (e.g. a5-a3): ").strip()
                frm, to = self._parse_single_move(raw)
                if frm not in self.board.soldiers[self.human]:
                    print("That's not one of your soldiers.")
                    continue
                if not self.board.is_valid_slide(frm, to):
                    print("Invalid slide — pieces must travel the full distance.")
                    continue
                return frm, to
            except ValueError as e:
                print(f"  {e}")

    @staticmethod
    def _parse_single_move(s: str) -> tuple[Pos, Pos]:
        parts = s.strip().split('-', 1)
        if len(parts) != 2:
            raise ValueError("Move format: <from>-<to> (e.g. a5-a3)")
        return Pos.from_notation(parts[0]), Pos.from_notation(parts[1])

    # --- AI ---

    def _ai_neutron_move(self) -> Pos:
        # Create AI and stash it so the soldier phase can reuse the plan
        self._ai = SimpleAI(self.ai_player)
        return self._ai.choose_neutron_move(self.board)

    def _ai_soldier_move(self) -> tuple[Pos, Pos]:
        ai = getattr(self, '_ai', None) or SimpleAI(self.ai_player)
        move = ai.choose_soldier_move(self.board)
        self._ai = None
        return move

    # --- intro / game over ---

    def _intro(self) -> None:
        print("=" * 36)
        print("  N E U T R O N")
        print("=" * 36)
        print()
        print("Each turn: slide the neutron, then slide one of your soldiers.")
        print("Pieces slide in any direction until hitting the edge or another piece.")
        print("Win by getting the neutron to YOUR home row (bottom of the board).")
        print()
        print("Move format:")
        print("  Neutron move:  N-a4")
        print("  Soldier move:  d5-d3")
        print("  First turn:    soldier move only (no neutron)")
        print()

        while True:
            choice = input("Play as Player 1 (go first)? [y/n]: ").strip().lower()
            if choice in ('y', 'n'):
                break
            print("Enter 'y' or 'n'.")

        if choice == 'y':
            self.human = 1
            self.ai_player = 2
            print("You are Player 1 (○). Computer is Player 2 (●).")
        else:
            self.human = 2
            self.ai_player = 1
            print("Computer is Player 1 (○). You are Player 2 (●).")

    def _game_over(self, winner: int, reason: str = "") -> None:
        label = "You win!" if winner == self.human else "Computer wins!"
        detail = f" ({reason})" if reason else ""
        print(f"\n{'=' * 36}")
        print(f"  Game over — {label}{detail}")
        print(f"{'=' * 36}")


def main() -> None:
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
