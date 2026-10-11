# contract-orbit-views

The orbit-view standard: one subject seen from cameras spread evenly around it, as an OpenEXR still sheet or a clip.

It also holds lookdev-24, the workspace's colour checker (color checker): a ColorChecker-style (Macbeth) 24-patch chart in our own 6 by 4 layout, carrying the classic ColorChecker's published values (BabelColor Avg., Pascale 2006) as a stand-in for one. It checks that colours survive a render or stream pipeline, scored by CIEDE2000; see [`chart24.json`](chart24.json), [`chart24.svg`](chart24.svg) and [`chart24.cff`](chart24.cff).

## What it is for

[`STANDARD.md`](STANDARD.md) states what an orbit-view bundle is: its files, its name, the camera positions, the color chart, the media and the layout. Renderers in other repositories write orbit views; this repository says what one is and fails one that is not.

## Build and run

    uv run check_orbit_views.py <dir-or-file>...
    uv run check_orbit_views.py --self-test

The self-test plants one broken bundle per checked rule.

## Licence

MIT; see `LICENSE`.
