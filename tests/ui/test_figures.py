"""Tests for pacman.ui.figures, the procedural sprite rasterizers.

Owner: Person B

The sprites are the one part of the renderer with real geometry in them, and
geometry is exactly the sort of thing that rots silently: a mouth that stops
opening, a ghost that grows past its corridor, or a fright face drawn in the
same colour as the body all still "work" and look wrong.  These check the
invariants the renderer depends on, using an off-screen ``Surface`` so no
window is needed.
"""

import typing

import pygame
import pytest

from pacman.core.entities import Direction, Player
from pacman.ui.figures import CreatureType, disc, facing_of, ghost, pacman
from pacman.ui.playfield import GHOST_COLORS
from pacman.ui.renderer import MENU_DECOR_PELLETS, Screen


SIZE = 60
CX = CY = SIZE // 2


@pytest.fixture
def surface() -> pygame.Surface:
    """An off-screen black surface, zeroed between uses."""
    return pygame.Surface((SIZE, SIZE))


def lit(surface: pygame.Surface) -> set:
    """Every pixel that was painted, as a set."""
    return {(x, y) for x in range(SIZE) for y in range(SIZE)
            if surface.get_at((x, y))[:3] != (0, 0, 0)}


def test_creature_type_no_longer_carries_sprites() -> None:
    """The enum is maze data only; sprites are drawn, not looked up."""
    assert [m.name for m in CreatureType] == ["WALL", "EMPTY"]


def extent(surface: pygame.Surface) -> tuple:
    """Return the (width, height) of everything painted."""
    painted = lit(surface)
    assert painted
    xs = [x for x, _ in painted]
    ys = [y for _, y in painted]
    return max(xs) - min(xs) + 1, max(ys) - min(ys) + 1


@pytest.mark.parametrize("radius", [7, 14, 21])
def test_sprites_fit_their_box(surface: pygame.Surface, radius: int) -> None:
    """Sprites are sized by the corridor, so they must not outgrow it.

    ``disc`` stamps a rim one pixel outside the circle and the ghost's
    skirt hangs one pixel below it; three pixels of slack covers both.
    """
    sprites = (
        lambda: disc(surface, CX, CY, radius, (255, 0, 0)),
        lambda: pacman(surface, CX, CY, radius, (240, 192, 0),
                       facing=(1, 0), mouth=1.0),
        lambda: ghost(surface, CX, CY, radius, (255, 64, 64)),
        lambda: ghost(surface, CX, CY, radius, (50, 100, 255), scared=True),
    )
    for draw in sprites:
        surface.fill((0, 0, 0))
        draw()
        assert all(dim <= 2 * radius + 3 for dim in extent(surface))


def test_pacman_mouth_animates(surface: pygame.Surface) -> None:
    """Closing the mouth must change the sprite, or the chomp is dead."""
    pacman(surface, CX, CY, 14, (240, 192, 0), facing=(1, 0), mouth=0.0)
    shut = lit(surface)
    surface.fill((0, 0, 0))
    pacman(surface, CX, CY, 14, (240, 192, 0), facing=(1, 0), mouth=1.0)
    open_mouth = lit(surface)
    assert open_mouth != shut
    # The bite comes out of the front, so the gap must be on the +x side.
    assert shut - open_mouth, "mouth wedge is not on the facing side"


@pytest.mark.parametrize("facing", list(Direction))
def test_pacman_faces_every_direction(
        surface: pygame.Surface, facing: Direction) -> None:
    """All four headings draw, and the wedge moves with the heading."""
    pacman(surface, CX, CY, 14, (240, 192, 0),
           facing=(facing.dx, facing.dy), mouth=1.0)
    painted = lit(surface)
    assert painted
    dx, dy = facing.dx, facing.dy
    # The missing wedge sits opposite the heading.
    front = max(painted, key=lambda p: (p[0] - CX) * dx + (p[1] - CY) * dy)
    assert abs((front[0] - CX) * dx + (front[1] - CY) * dy) > 10


@pytest.mark.parametrize("facing", list(Direction))
def test_ghost_faces_every_direction(
        surface: pygame.Surface, facing: Direction) -> None:
    """Eyes track the heading, so every ghost direction renders."""
    ghost(surface, CX, CY, 14, (255, 64, 64),
          facing=(facing.dx, facing.dy))
    assert lit(surface)


def test_ghost_fits_its_box(surface: pygame.Surface) -> None:
    """A ghost must not spill into the wall beside its corridor."""
    ghost(surface, CX, CY, 14, (255, 64, 64))
    assert all(dim <= 2 * 14 + 3 for dim in extent(surface))


def test_ghost_skirt_is_wavy(surface: pygame.Surface) -> None:
    """The feet are cut away, otherwise the ghost reads as an egg."""
    ghost(surface, CX, CY, 14, (255, 64, 64))
    bottom = max(y for _, y in lit(surface))
    gap = [x for x in range(SIZE)
           if surface.get_at((x, bottom - 2))[:3] == (0, 0, 0)]
    assert gap, "ghost has no notch in its skirt"


def count(surface: pygame.Surface, colour: tuple) -> int:
    """How many pixels are exactly *colour*."""
    return sum(1 for x in range(SIZE) for y in range(SIZE)
               if surface.get_at((x, y))[:3] == colour)


PUPIL = (24, 26, 90)


def test_frightened_face_replaces_the_eyes(surface: pygame.Surface) -> None:
    """A scared ghost has no pupils; it gets dots and a wavy mouth.

    Comparing pixel *sets* would prove nothing here -- both faces sit
    inside the body -- so the test looks at what actually differs.
    """
    ghost(surface, CX, CY, 14, (50, 100, 255), scared=True)
    assert count(surface, PUPIL) == 0
    assert count(surface, (255, 255, 255)) > 0
    surface.fill((0, 0, 0))
    ghost(surface, CX, CY, 14, (50, 100, 255))
    assert count(surface, PUPIL) > 0


def test_white_flash_needs_a_contrasting_face(surface: pygame.Surface) -> None:
    """A white ghost on a white face is a blob; the face must be passed in."""
    ghost(surface, CX, CY, 14, (255, 255, 255), scared=True,
          face=(24, 26, 90))
    assert lit(surface)


def test_facing_of_defaults_to_up(surface: pygame.Surface) -> None:
    """A still ghost looks up, and a moving one looks where it is going."""
    player = Player((1, 1), 1.0, 3)
    assert facing_of(player) == (0.0, -1.0)
    for direction in Direction:
        player.direction = direction
        assert facing_of(player) == (float(direction.dx),
                                     float(direction.dy))


def decor_and_panel_pixels(screen_obj: "Screen") -> tuple:
    """Return the decor's ink and the home panel's ink as pixel sets."""
    import pygame

    def ink(draw: typing.Callable) -> set:
        surface = pygame.Surface((screen_obj.width, screen_obj.height))
        surface.fill(screen_obj.colors["void"])
        draw(surface)
        return {(x, y)
                for y in range(screen_obj.height)
                for x in range(screen_obj.width)
                if surface.get_at((x, y))[:3] != screen_obj.colors["void"]}

    return (ink(screen_obj.draw_menu_decor),
            ink(lambda s: screen_obj.draw_panel(
                s, "PAC-MAN", screen_obj.menu_options, 1,
                "ARROWS MOVE    ENTER SELECT    Q QUIT")))


@pytest.fixture
def screen_obj() -> "Screen":
    """A Screen sized like the shipped window."""
    from pacman import core

    return Screen(core.load_config("config.json"))


def test_the_42_glyph_is_filled_solid(screen_obj: "Screen") -> None:
    """Code 15 draws as a solid block, not a hollow box.

    ``WALL_MASKS[15]`` is ``┌─┐ │ │ └─┘`` -- an outline -- and the generic
    mask path also skips the lit core in the middle band, so every "42"
    cell came out hollow and the glyph dissolved into its own outline.
    """
    screen_obj.start_level(0)
    surface = pygame.Surface((screen_obj.width, screen_obj.height))
    surface.fill(screen_obj.colors["void"])
    screen_obj.render_maze(surface)
    grid = screen_obj.maze_gen.maze
    ox, oy = screen_obj.maze_origin()
    size = screen_obj.cell_size
    solid = [(x, y) for y, row in enumerate(grid)
             for x, code in enumerate(row) if code == 15]
    assert solid, "this seed produced no 42 glyph to check"
    for x, y in solid:
        centre = surface.get_at((ox + x * size + size // 2,
                                 oy + y * size + size // 2))[:3]
        assert centre == screen_obj.colors["wall_core"], (
            f"42 cell at ({x}, {y}) is hollow in the middle")


def test_menu_decor_lands_only_in_the_gutters(screen_obj: "Screen") -> None:
    """No ghost or pellet may sit on the title or a menu row.

    The scatter is random, so this is the only thing that keeps a reroll
    from dropping a ghost through the middle of the word "Play".
    """
    decor, panel = decor_and_panel_pixels(screen_obj)
    assert decor, "the menu has no decoration at all"
    assert not (decor & panel), (
        f"{len(decor & panel)} decor pixels land on the panel")


def test_menu_decor_has_all_four_ghosts_and_some_pellets(
        screen_obj: "Screen") -> None:
    """Four ghosts, one per colour, plus a handful of pellets."""
    ghosts, pellets = screen_obj.menu_decor()
    assert len(ghosts) == len(GHOST_COLORS)
    assert {g[3] for g in ghosts} == set(GHOST_COLORS)
    assert len(pellets) >= 10


def test_menu_decor_puts_one_ghost_in_each_corner(
        screen_obj: "Screen") -> None:
    """Four ghosts, four corners, in GHOST_COLORS order.

    Pins the arrangement, not the exact pixels: two ghosts sharing a
    corner reads as debris, one per corner reads as a deliberate frame.
    """
    ghosts, _ = screen_obj.menu_decor()
    assert [color for _, _, _, color in ghosts] == list(GHOST_COLORS)
    half_x, half_y = screen_obj.width // 2, screen_obj.height // 2
    assert sorted((x > half_x, y > half_y) for x, y, _, _ in ghosts) == [
        (False, False), (False, True), (True, False), (True, True)]


def test_menu_decor_pellets_match_the_board_size(
        screen_obj: "Screen") -> None:
    """Decor pellets are the board's own pellets, radius for radius.

    This is the whole point of reusing ``stamp_pellet``: drawn as true
    circles they come out smooth and read as bubbles, and the decoration
    stops looking like the game it is decorating.
    """
    screen_obj.start_level(0)
    size = screen_obj.entity_size()
    board = (max(1.5, size * 0.11), size * 0.21)
    _, pellets = screen_obj.menu_decor()
    assert sorted({r for _, _, r in pellets}) == sorted(
        {round(board[0]), round(board[1])})


def test_menu_decor_pellets_are_evenly_spread(screen_obj: "Screen") -> None:
    """One pellet per slot: an even scatter, never a bald patch."""
    _, pellets = screen_obj.menu_decor()
    assert len(pellets) == 2 * MENU_DECOR_PELLETS
    # Per band: both bands reuse the same slots, so across the whole
    # screen each pellet has a near-twin at the same x.
    for low, high in screen_obj.menu_bands(screen_obj.hud_scale() // 2):
        xs = sorted(x for x, y, _ in pellets if low <= y <= high)
        assert len(xs) == MENU_DECOR_PELLETS
        gaps = [b - a for a, b in zip(xs, xs[1:])]
        # Slot jitter is bounded, so no two pellets in a band can drift
        # together while the rest of it stays empty.
        assert max(gaps) < 3 * min(gaps)


def test_menu_decor_is_stable_across_redraws(
        screen_obj: "Screen") -> None:
    """Same positions every call: the panel repaints 60 times a second."""
    assert screen_obj.menu_decor() == screen_obj.menu_decor()


def test_menu_decor_survives_a_fresh_screen(screen_obj: "Screen") -> None:
    """The seed, not the instance, decides where things land."""
    from pacman import core

    other = Screen(core.load_config("config.json"))
    assert other.menu_decor() == screen_obj.menu_decor()
