The orbit-view standard: one subject seen from cameras spread evenly around it, as a still sheet or a clip.

[`STANDARD.md`](STANDARD.md) states the rules: the bundle, the name, the camera positions, the media formats, the layout, and where an orbit-view bundle goes. `check_orbit_views.py` checks the rules marked checked, and its self-test plants one broken bundle per rule.

    python check_orbit_views.py <dir-or-file>...
    python check_orbit_views.py --self-test

A renderer in another repository (the pen's joy views in Godot, the Mitsuba CPU template) writes orbit views; this repository says what one is and fails one that is not.
