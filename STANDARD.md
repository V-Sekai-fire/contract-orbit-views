# The orbit-view standard

Orbit views show one subject from cameras spread evenly around it, with the numbers kept beside them. It is a still sheet (one image, one cell per view) or a clip (the views in sequence). Every orbit-view bundle the workspace ships follows this standard, whatever renders it: Godot on a GPU, or Mitsuba on a CPU. `check_orbit_views.py` checks every rule marked **checked**. The rest hold by agreement.

## The bundle

A orbit-view bundle is three files sharing one stem:

| file | holds |
| --- | --- |
| `<stem>.png` or `<stem>.mkv` | the still sheet, or the clip |
| `<stem>.cff` | its citation: what it shows, from which commit, under which release |
| `<stem>.tsv` | one row per cell: the feature, its forecast, the view, and the cell's metric |
| `<stem>.chart.tsv` | where the color chart sits in a still sheet: one `x y w h` row in pixels |

A `<stem>.xmp` sidecar derived from the `.cff` joins the bundle once `mix cff.xmp` (RFD 2240) exists. Until then its absence is counted, not skipped.

## Media (checked)

A still sheet is a PNG. A clip is CineForm video with FLAC audio in Matroska (`.mkv`), recorded through `entities-godot-cineform` and delivered without re-encoding (RFD 2294 "Video"); the checker reads the Matroska header and both tracks. No WebM, MJPEG or FFmpeg output is an orbit-view bundle.

## Name (checked)

`YYYYMMDD_project_description_NNNN.png` or `.mkv`, lowercase ASCII, underscores between facets and hyphens inside one (RFD 2013). `NNNN` rises and an orbit-view bundle is never overwritten. Example: `20261002_meshing-pen_joy-walking_0001.png`.

## Cameras (checked)

The cameras are spread evenly around the subject by one fixed rule, so two bundles of the same subject are comparable view for view. Every camera comes from `sphere_hammersley_sequence(i, n, remap=True)`, never a hand-picked angle. The `.tsv` records `view` (i), `n`, `azimuth_deg` and `elevation_deg`, and the checker recomputes each pair to within 1e-4 degrees. A renderer may clamp pitch to ±85 degrees, as the station's player does, and records the clamped value. The reference implementations are `realize_check.gd`'s `_hammersley` in `entities-sakuragaoka-station` and `sphere_hammersley_sequence` in the trellis `random_utils.py`; `check_orbit_views.py` agrees with the latter to 3e-14 degrees.

## Layout (by agreement)

- A still sheet has one row per case and one column per view; a clip shows the views in index order, each held for the same time. A comparison adds columns: original, port, difference (RFD 2294 "Visual comparisons").
- Failures first, worst first.
- Each cell is labelled with its metric. The same number is in the `.tsv`.
- A joy orbit-view bundle's title names the feature and its forecast tag from RFD 2293, for example `walking a faithful station (likely, p=0.70)`.
- The layout precedent is `tools/prop_shots.gd` in `entities-sakuragaoka-station`.

## Composition (by agreement)

A orbit-view bundle is composed by rendering: a SubViewport, or a fragment shader for the difference column. It is never composed by a per-pixel GDScript loop, and a Godot tool ships as `.sgd` (RFD 2294 "Where compute runs").

## Color chart (checked)

Every still sheet carries lookdev-24, the workspace's 24-patch color chart, the same one `entities-sakuragaoka-station` calibrates with (`tools/calib/chart24.json`, `tools/chart_calib.gd`, station commit 74eb6b1). It is our own 6 by 4 layout carrying published colorimetric values: the BabelColor Avg. sRGB 8-bit and L*a*b* D50 figures from Pascale (2006). `chart24.json` and `chart24.svg` here are copies of the station's, and `check_orbit_views.py --write-chart chart.png` writes the same patches as a PNG.

- The chart is drawn flat and unlit through the same output path as the views, so a wrong transfer function, a tonemap on the overlay or a swapped channel moves a patch off its value.
- The checker reads the region `<stem>.chart.tsv` names, averages the central 60% of each patch, and scores it in CIEDE2000 against the patch's `srgb8` (sRGB 8-bit to linear, to XYZ D65, Bradford to D50, to L*a*b*). A patch over dE00 0.5 fails, the station's unlit gate.
- The cyan patch is clipped in sRGB (R' = 0), so it is not gated, as in the station.
- A sheet with no chart region fails, and a chart with patches 3 and 4 swapped fails (the station's control).
- A chart lit in a view's own light (the station's `chart_in_view.json`) is measured and reported per patch, not gated against the unlit values.
- A clip's chart is not checked, because the checker does not decode CineForm; each run counts the clips it left unchecked.

## Citation (checked)

The `.cff` carries `cff-version`, `title`, `version` (the release tag), `date-released`, `commit`, `license`, `authors` and `url: "https://github.com/v-sekai-fire"`.

## Zero views fail (checked)

A feature listed in the `.tsv` with `view` set to `none` has no rendered view, and the run fails. A blank cell never stands in for a missing render.

## Where orbit views go (by agreement)

- In CI, an orbit-view bundle is saved as a workflow artifact (`actions/upload-artifact`).
- On a release, the bundle is attached to the release and listed in its `SHA256SUMS`.
- A desk copy goes to `~/Desktop/lookdev-contact-sheets/<topic>-NN.<ext>`, with NN rising (the folder name RFD 2294 gives).
