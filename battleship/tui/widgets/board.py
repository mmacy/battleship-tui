import enum
import string
from dataclasses import dataclass
from itertools import cycle
from typing import Any, Iterable

from rich.emoji import EMOJI  # type: ignore[attr-defined]
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.coordinate import Coordinate
from textual.events import Click, Mount, MouseMove
from textual.message import Message
from textual.reactive import var
from textual.widget import Widget
from textual.widgets import DataTable, Static

from battleship.engine import domain
from battleship.engine.domain import Direction

SHIP = EMOJI["ship"]
WATER = EMOJI["water_wave"]
FIRE = EMOJI["fire"]
CROSS = EMOJI["cross_mark"]
TARGET = EMOJI["dart"]


@dataclass
class ShipToPlace:
    type: str
    length: int
    direction: str = ""

    def __post_init__(self) -> None:
        self._directions = cycle((Direction.RIGHT, Direction.DOWN))
        self.direction = next(self._directions)

    def rotate(self) -> None:
        self.direction = next(self._directions)


class MouseButton(enum.IntEnum):
    LEFT = 1
    RIGHT = 3


class Board(Widget):
    class Mode(enum.StrEnum):
        DISPLAY = "display"
        ARRANGE = "arrange"
        TARGET = "target"

    DEFAULT_CSS = """
    Board {
      width: 1fr;
    }
    """
    min_targets: var[int] = var(1)
    mode: var[Mode] = var(Mode.DISPLAY, init=False)

    class ShipPlaced(Message):
        def __init__(self, ship: ShipToPlace, coordinates: list[Coordinate]):
            super().__init__()
            self.ship = ship
            self.coordinates = coordinates

    class CellShot(Message):
        def __init__(self, coordinates: list[Coordinate]):
            super().__init__()
            self.coordinates = coordinates

    def __init__(self, *args: Any, player: str, size: int, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.player = player
        self.board_size = size
        self._table: DataTable[Text] = DataTable(cell_padding=0, cursor_type="none")
        self._cursor_coordinate: Coordinate | None = None

        self._ship_to_place: ShipToPlace | None = None
        self._preview_coordinates: list[Coordinate] = []
        self._place_forbidden = True

        self._target_coordinates: list[Coordinate] = []

        self._cell = " " * 2
        self._forbidden_cell = Text(self._cell, style="on red")
        self._ship_cell = Text(self._cell, style="on green")
        self._even_cell = Text(self._cell, style="on #2D2D2D")
        self._odd_cell = Text(self._cell, style="on #1E1E1E")

    @staticmethod
    def detect_cell_coordinate(event: Click | MouseMove) -> Coordinate | None:
        meta = event.style.meta

        if not meta:
            # Event outside board.
            return None

        row, column = meta["row"], meta["column"]

        if row < 0 or column < 0:
            # Event outside cells.
            return None

        return Coordinate(row, column)

    @on(Mount)
    def handle_mount(self) -> None:
        self.initialize_grid()

    @on(MouseMove)
    def handle_mouse_move(self, event: MouseMove) -> None:
        coordinate = self.detect_cell_coordinate(event)

        if self.mode == self.Mode.TARGET:
            self.move_crosshair(coordinate)

        if self.mode == self.Mode.ARRANGE:
            self.move_ship_preview(coordinate)

        self._cursor_coordinate = coordinate

    @on(Click)
    def handle_click(self, event: Click) -> None:
        coordinate = self.detect_cell_coordinate(event)

        if not coordinate:
            return

        if self.mode == self.Mode.TARGET:
            match event.button:
                case MouseButton.LEFT:
                    self.select_target()
                case MouseButton.RIGHT:
                    self.clean_targets()

        if self.mode == self.Mode.ARRANGE:
            match event.button:
                case MouseButton.LEFT:
                    self.place_ship()
                case MouseButton.RIGHT:
                    self.rotate_preview()

    def set_ship_to_place(self, ship: ShipToPlace) -> None:
        self._ship_to_place = ship

    def initialize_grid(self) -> None:
        self._table.clear()
        self._table.add_columns(*string.ascii_uppercase[: self.board_size])

        for i, row in enumerate(range(self.board_size), start=1):
            cells = []
            for column in range(self.board_size):
                cells.append(self.get_bg_cell(row, column))

            self._table.add_row(*cells, label=Text(str(i), style="#B0FC38 italic"))

    def get_bg_cell(self, row: int, column: int) -> Text:
        """
        Decide what cell should be at this position.

        Args:
            row: 0-based row index.
            column: 0-based column index.

        Returns: Even cell or odd cell.

        """
        row, column = row + 1, column + 1
        # Cell considered even if the sum of its row and column indices is even.
        is_cell_even = (row + column) % 2 == 0
        return self._even_cell if is_cell_even else self._odd_cell

    def compose(self) -> ComposeResult:
        yield Static(self.player)
        yield self._table

    def move_crosshair(self, coordinate: Coordinate | None) -> None:
        self.clean_crosshair()

        if coordinate:
            self.paint_crosshair(coordinate)

    def paint_crosshair(self, coordinate: Coordinate) -> None:
        if not self.mode == self.Mode.TARGET:
            return

        if coordinate in self._target_coordinates:
            return

        cell = self.get_bg_cell(*coordinate)
        # Paint crosshair preserving cell's background color.
        self._table.update_cell_at(coordinate, value=Text(TARGET, style=cell.style))

    def clean_crosshair(self) -> None:
        if self._cursor_coordinate and self._cursor_coordinate not in self._target_coordinates:
            self.paint_background_cell(self._cursor_coordinate)

    def paint_background_cell(self, coordinate: Coordinate) -> None:
        self._table.update_cell_at(
            coordinate,
            value=self.get_bg_cell(*coordinate),
        )

    def move_ship_preview(self, coordinate: Coordinate | None) -> None:
        # We don't know if we could place the ship
        # after the move, so we forbid it until we know
        # there is enough place.
        self._place_forbidden = True
        self.clean_ship_preview()

        if coordinate:
            self.preview_ship(coordinate.row, coordinate.column)

    def clean_targets(self) -> None:
        while self._target_coordinates:
            coor = self._target_coordinates.pop()
            self.paint_background_cell(coor)

    def select_target(self) -> None:
        if not self.mode == self.Mode.TARGET:
            return

        self._target_coordinates.append(
            self._cursor_coordinate,  # type: ignore[arg-type]
        )

        if len(self._target_coordinates) == self.min_targets:
            self.post_message(self.CellShot(self._target_coordinates[:]))
            self.clean_targets()

    def rotate_preview(self) -> None:
        if not self.mode == self.Mode.ARRANGE:
            return

        self._ship_to_place.rotate()  # type: ignore[union-attr]
        self.preview_ship(*self._cursor_coordinate)  # type: ignore[misc]

    def clean_ship_preview(self) -> None:
        while self._preview_coordinates:
            coor = self._preview_coordinates.pop()
            self.paint_background_cell(coor)

    def paint_ship(self, coordinates: Iterable[Coordinate]) -> None:
        for coor in coordinates:
            self._table.update_cell_at(coor, value=self._ship_cell)

    def paint_forbidden(self, coordinates: Iterable[Coordinate]) -> None:
        for coor in coordinates:
            self._table.update_cell_at(coor, value=self._forbidden_cell)

    def is_coordinate_outside_board(self, coordinate: Coordinate) -> bool:
        return (coordinate.column >= self.board_size or coordinate.column < 0) or (
            coordinate.row > self.board_size - 1 or coordinate.row < 0
        )

    def preview_ship(self, row: int, column: int) -> None:
        if self.mode != self.Mode.ARRANGE:
            return

        self.clean_ship_preview()

        start = Coordinate(row, column)

        if self._table.get_cell_at(start) is self._ship_cell:
            return

        self._preview_coordinates.append(start)

        for _ in range(self._ship_to_place.length - 1):  # type: ignore[union-attr]
            match self._ship_to_place.direction:  # type: ignore[union-attr]
                case domain.Direction.DOWN:
                    next_cell = start.down()
                case domain.Direction.RIGHT:
                    next_cell = start.right()
                case _:
                    return

            if self.is_coordinate_outside_board(next_cell):
                break

            if self._table.get_cell_at(next_cell) is self._ship_cell:
                break

            self._preview_coordinates.append(next_cell)
            start = next_cell
        else:
            self._place_forbidden = False
            self.paint_ship(self._preview_coordinates)
            return

        self.paint_forbidden(self._preview_coordinates)

    def place_ship(self) -> None:
        if self._place_forbidden:
            return

        self.post_message(
            self.ShipPlaced(
                self._ship_to_place,  # type: ignore[arg-type]
                self._preview_coordinates[:],
            )
        )
        self._preview_coordinates.clear()
        self._ship_to_place = None
        self._place_forbidden = True
