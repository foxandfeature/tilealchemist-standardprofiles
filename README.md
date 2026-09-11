# TileAlchemist Standard Profiles

The `land` and `cropped-waterways` global PMTiles layers: two
[TileAlchemist](https://github.com/foxandfeature/tilealchemist) profiles,
plus the workflow that builds and publishes them every month.

TileAlchemist itself is the pipeline — fetching, sharding, merging,
publishing — and ships no profiles of its own. This repository is one
consumer of it, and doubles as a worked example of the cross-repo path
described in TileAlchemist's
[`docs/PROFILES.md`](https://github.com/foxandfeature/tilealchemist/blob/main/docs/PROFILES.md).

| Profile | Produces | Example style |
| --- | --- | --- |
| `land` | Every tile's land polygon(s), derived by inverting the source's `water` layer. | [`examples/land.json`](examples/land.json) |
| `cropped-waterways` | The source's `waterway` lines, cropped to the portions that don't overlap real water. | [`examples/cropped-waterways.json`](examples/cropped-waterways.json) |

## Why these two exist

OpenFreeMap, and most other OpenMapTiles-schema vector tile providers, ship
a `water` layer but no `land` layer. That's fine for the default styles,
which just paint the map background as land color and draw water on top.
But a custom style that wants to treat land as its own styleable/maskable
layer (a distinct fill, a texture, a land-only overlay) has nothing to
attach it to. [MapTiler's `land` layer](https://docs.maptiler.com/schema/land/)
is the closest existing reference: plain, attribute-less land polygons
meant as a base layer for custom styling. OpenFreeMap doesn't publish an
equivalent, so the **land** profile derives one by inverting the `water`
layer it does publish.

Once land replaces water as a style's base layer, the source's `waterway`
line layer (rivers, streams) starts visually clashing with it: a stroked
line drawn straight through the water polygon it represents now runs across
solid land-colored fill instead. The **cropped-waterways** profile removes
exactly the overlapping portions, so waterway lines only appear where
they're actually on land. See it combined with `land` in
[`examples/cropped-waterways.json`](../examples/cropped-waterways.json).

## Using the prebuilt layers

Finished PMTiles files are published on every run; you don't need to run
the pipeline yourself just to use them. Preview a profile's output directly
in Maputnik:
[`land`](https://maplibre.org/maputnik/?style=https://raw.githubusercontent.com/foxandfeature/tilealchemist-standardprofiles/main/examples/land.json),
[`cropped-waterways`](https://maplibre.org/maputnik/?style=https://raw.githubusercontent.com/foxandfeature/tilealchemist-standardprofiles/main/examples/cropped-waterways.json).

Each layer carries its attribution (`TileAlchemist`, linked to the pipeline
repo, `· OpenFreeMap © OpenMapTiles Data from OpenStreetMap`, per
[OpenFreeMap's attribution guidance](https://github.com/hyperknot/openfreemap#attribution))
in its own metadata, so a MapLibre style pointing at it through the
[PMTiles protocol](https://github.com/protomaps/PMTiles) picks it up
automatically, no separate TileJSON or manual attribution string needed:

```js
import { Protocol } from "pmtiles";

const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

const map = new maplibregl.Map({
  style: {
    version: 8,
    sources: {
      land: {
        type: "vector",
        url: "pmtiles://https://f003.backblazeb2.com/file/tilealchemist/land.pmtiles",
      },
    },
    layers: [
      { id: "land", type: "fill", source: "land", "source-layer": "land" },
    ],
  },
  // ...
});
```

Or grab a file directly from its GitHub release, tagged `<profile>-latest`
(e.g. [`land-latest`](https://github.com/foxandfeature/tilealchemist-standardprofiles/releases/tag/land-latest),
[`cropped-waterways-latest`](https://github.com/foxandfeature/tilealchemist-standardprofiles/releases/tag/cropped-waterways-latest)):
large builds ship as multiple parts, the release description has a
one-line `gh release download` command that reassembles them.

## `land`

For every tile in the `min_zoom`..`max_zoom` pyramid, `LandProfile.transform()`
(`land.py`), called by the inherited
`Profile.transform_tile()`, computes
`water.subtract_water(tile, tile.buffered_square)`, which is:

1. This tile's real surface water, via the `SURFACE_WATER` feature set
   (`tile.features(SURFACE_WATER)`, see `FeatureSet` in
   [TileAlchemist's `docs/PROFILES.md`](https://github.com/foxandfeature/tilealchemist/blob/main/docs/PROFILES.md)). For `OPENMAPTILES` this reads the
   `water` layer and drops tunnel water (`brunnel == "tunnel"`: a water
   polygon running through a tunnel isn't open water at the surface).
   `Tile.features()` hands each remaining polygon back as shapely.
2. Unioned via `tilealchemist/water.py:surface_water_union()`, memoized on
   the `Tile`.
3. Inverting the tile: `land = tile_square - union(remaining water polygons)`,
   entirely in that tile's own local coordinates. `tile_square` is buffered
   4px (64 units at the standard 4096 extent) past the tile edge on every
   side, matching OpenMapTiles/Planetiler's own default buffer for the
   `water` layer, so the buffered land polygon is fully determined by data
   already fetched, no neighboring tiles needed. Without this, a renderer
   stroking the coastline as a thick line sees the polygon end abruptly at
   the tile boundary, producing a visible kink where two tiles meet instead
   of a continuous line.

Because each tile is inverted independently against its own square, there's
no cross-tile geometry work and no re-simplification beyond whatever detail
the source archive already has at that zoom.

Gap tiles (no archive entry at all for that tile_id) get an identical bare
buffered square: full land is the well-defined "nothing to subtract" case.

## `cropped-waterways`

`CroppedWaterwaysProfile.transform()`
(`cropped_waterways.py`), called by the inherited
`Profile.transform_tile()`, reads this tile's waterway line features via
`tile.features(WATERWAYS)` (already shapely, see `Tile` in
[TileAlchemist's `docs/PROFILES.md`](https://github.com/foxandfeature/tilealchemist/blob/main/docs/PROFILES.md)), then cuts each one with the
same `water.subtract_water(tile, ...)` the land profile uses, keeping only
the portion that doesn't overlap the water. Both profiles therefore share
one water union per tile - memoized on the `Tile` itself, so the second
profile to ask gets the first one's result rather than recomputing it.
Reusing the exact same union (not recomputing it independently) matters: if
the two profiles' water polygons disagreed even by a sub-pixel amount, a
cropped waterway line and the land polygon it's meant to hug could show a
visible seam once rendered together.

Gap tiles are skipped entirely for this profile: a gap means the source
archive had no water and no waterway data at all for that tile_id, so
there's no faithful "cropped waterway" content to invent, unlike land's
well-defined "whole square minus nothing" case.

## Running it

Both profiles are built together by
`.github/workflows/build-land-and-waterways.yml`, triggered manually
(`workflow_dispatch`, inputs `min_zoom`/`max_zoom`) or on a monthly
schedule. It calls TileAlchemist's `_pipeline.yml` cross-repo, once, with
both profiles (`profile`/`output_basename` accept a comma-separated list),
so one `prepare-shards` walk and one fetch per worker cover both layers and
OpenFreeMap only sees each tile's bytes fetched once per run. The pipeline
never checks this repository out; a first job uploads `land.py` and
`cropped_waterways.py` as the `profiles` artifact, and that is the whole
handover. Publishing —
GitHub Releases via TileAlchemist's `_publish-release.yml`, plus a
Backblaze B2 mirror as a local job — happens here, in the repository that
owns the credentials.

There is nothing to install or configure to trigger a run.

## License / attribution

The code in this repository (profiles, workflow, styles) is licensed under
the [MIT License](LICENSE).

The `.pmtiles` files themselves are a different matter: their data is
derived from OpenStreetMap via OpenFreeMap's planet archive, built with
OpenMapTiles (© OpenStreetMap contributors, ODbL), and that license carries
through however it's reshaped or repackaged downstream. See "Using the
prebuilt layers" above for the required attribution string and how each
`.pmtiles` file carries it automatically.
