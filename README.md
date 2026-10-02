The view-set standard: Hammersley views of one subject as a still sheet or a clip, each with a .cff and a metrics table.

[`STANDARD.md`](STANDARD.md) states the rules: the bundle, the name, the views from `sphere_hammersley_sequence`, the media formats, the layout, and where a view set goes. `check_views.py` checks the rules marked checked, and its self-test plants one broken bundle per rule.

    python check_views.py <dir-or-file>...
    python check_views.py --self-test

A renderer in another repository (the pen's joy views in Godot, the Mitsuba CPU template) writes view sets; this repository says what one is and fails one that is not.
