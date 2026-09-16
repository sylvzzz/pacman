"""Adapter around the assigned A-Maze-ing package. The only module that imports it.

Owner: Person A
Planned contents: _load_generator_class(), _generate() (perfect=False, wraps every failure in MazeGenerationError), _read_walls() validation, blocked_from_walls(), cells_to_tiles() expanding cell bitmasks N=1 E=2 S=4 W=8 into a (2w+1)x(2h+1) tile grid, generate_tile_grid().
"""
