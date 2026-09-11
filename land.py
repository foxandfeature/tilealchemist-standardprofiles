"""Land profile: invert each tile's water polygons into whatever's left of
a buffered tile square after subtracting them. See this repo's README
("land") for the full rationale, including why the square is buffered past
the tile edge.
"""
from tilealchemist import water
from tilealchemist.profiles.base import Profile


class LandProfile(Profile):
    name = "land"

    def transform(self, tile):
        return water.subtract_water(tile, tile.buffered_square)


PROFILE = LandProfile
