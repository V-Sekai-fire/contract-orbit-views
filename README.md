# contract-orbit-views

The orbit-view standard: one subject seen from cameras spread evenly around it, as an OpenEXR still sheet or a clip.

## What it is for

[`STANDARD.md`](STANDARD.md) states what an orbit-view bundle is: its files, its name, the camera positions, the color chart, the media and the layout. An orbit-view still sheet is also called a contact sheet. Renderers in other repositories write orbit views; this repository says what one is and fails one that is not.

## Build and run

    uv run check_orbit_views.py <dir-or-file>...
    uv run check_orbit_views.py --self-test

The self-test plants one broken bundle per checked rule.

## Licence

MIT; see `LICENSE`.
