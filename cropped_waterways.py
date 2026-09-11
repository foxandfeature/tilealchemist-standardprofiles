"""Cropped-waterways profile: keep each tile's waterway line features only
where they don't overlap real water polygons, so a style using the land
profile as its base layer doesn't draw a river stroke on top of the water
polygon it already runs through. See this repo's README.
"""
from tilealchemist import water
from tilealchemist.features import WATERWAYS
from tilealchemist.profiles.base import Profile


class CroppedWaterwaysProfile(Profile):
    name = "cropped-waterways"

    def output_fields(self, schema):
        # Properties are passed through unchanged below, so the output layer
        # carries exactly the schema's own waterway fields.
        return schema.fields_for(WATERWAYS)

    def transform(self, tile):
        return [waterway.with_geometry(
                    water.subtract_water(tile, waterway.geometry))
                for waterway in tile.features(WATERWAYS)]


PROFILE = CroppedWaterwaysProfile
