# Neutron

A two-player abstract strategy game implemented in Python.

## Quick Start

Install and play:

```bash
# Install the package in development mode
pip install -e .

# Play the game
neutron

# Or run directly
python -m neutron
```

## Development

Install with dev dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Lint and format:

```bash
black .
ruff check .
```

## Game Rules

- **Setup**: 5×5 board with pieces at opposite ends, neutron in center
- **Movement**: Pieces and neutron move in straight lines (up, down, left, right) until blocked
- **Turn**: Players alternate moving a piece or the neutron
- **First Move**: Player 1 cannot move the neutron on their first turn
- **Win Condition**: Get a piece or the neutron to opponent's back row

## How to Play

```
Notation: a1-b2 (from column-row to column-row)
Rows: 1-5 (bottom to top)
Cols: a-e (left to right)
```

Example moves:
- `a2-a4` - move piece from a2 to a4
- `c3-c5` - move neutron from c3 to c5
