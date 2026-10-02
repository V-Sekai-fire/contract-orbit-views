#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check orbit-view bundles against STANDARD.md: name, media, .cff and the camera table.

    python check_orbit_views.py <dir-or-file>...
    python check_orbit_views.py --self-test
"""
import math
import pathlib
import re
import struct
import sys
import tempfile
import zlib

NAME = re.compile(r"^(\d{8})_([a-z0-9-]+)_([a-z0-9-]+)_(\d{4})\.(png|mkv)$")
URL = "https://github.com/v-sekai-fire"
CFF_KEYS = ("cff-version", "title", "version", "date-released", "commit", "url", "license", "authors")
TSV_HEADER = ["row", "feature", "forecast", "view", "n", "azimuth_deg", "elevation_deg", "metric", "value"]
TOLERANCE_DEG = 1e-4
PITCH_LIMIT_DEG = 85.0


def sphere_hammersley(i: int, n: int) -> tuple:
    """sphere_hammersley_sequence(i, n, remap=True) as (azimuth, elevation) in degrees."""
    u = i / n
    v, f, k = 0.0, 0.5, i
    while k > 0:
        v += (k & 1) * f
        k >>= 1
        f *= 0.5
    u = 2 * u if u < 0.25 else 2 / 3 * u + 1 / 3
    return v * 360.0, math.degrees(math.acos(1 - 2 * u) - math.pi / 2)


def png_size(path: pathlib.Path) -> tuple:
    head = path.read_bytes()[:24]
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return (0, 0)
    return struct.unpack(">II", head[16:24])


def mkv_problem(path: pathlib.Path) -> str:
    data = path.read_bytes()
    if data[:4] != b"\x1a\x45\xdf\xa3" or b"matroska" not in data[:64]:
        return "not a Matroska file"
    if b"CFHD" not in data:
        return "has no CineForm video track"
    if b"A_FLAC" not in data:
        return "has no FLAC audio track"
    return ""


def cff_fields(text: str) -> dict:
    return {m.group(1): m.group(2).strip().strip('"') for m in re.finditer(r"^([a-z-]+):\s*(.*)$", text, re.M)}


def check(png: pathlib.Path) -> list:
    out = []
    m = NAME.match(png.name)
    if not m:
        return [f"{png.name}: name is not YYYYMMDD_project_description_NNNN.png or .mkv"]
    if png.suffix == ".mkv":
        bad = mkv_problem(png)
        if bad:
            out.append(f"{png.name}: {bad}")
    elif 0 in png_size(png):
        out.append(f"{png.name}: not a readable PNG")
    cff, tsv = png.with_suffix(".cff"), png.with_suffix(".tsv")
    if not cff.exists():
        out.append(f"{png.name}: no {cff.name}")
    else:
        fields = cff_fields(cff.read_text())
        out += [f"{cff.name}: no {k}" for k in CFF_KEYS if k not in fields]
        if fields.get("url") and fields["url"].rstrip("/").lower() != URL:
            out.append(f"{cff.name}: url is {fields['url']}, not {URL}")
    if not tsv.exists():
        return out + [f"{png.name}: no {tsv.name}"]
    lines = [ln.split("\t") for ln in tsv.read_text().splitlines() if ln.strip()]
    if not lines or lines[0] != TSV_HEADER:
        return out + [f"{tsv.name}: header is not {' '.join(TSV_HEADER)}"]
    views = {}
    for row in lines[1:]:
        if len(row) != len(TSV_HEADER):
            out.append(f"{tsv.name}: row {row[:1]} has {len(row)} fields")
            continue
        r = dict(zip(TSV_HEADER, row))
        try:
            i, n, az, el = int(r["view"]), int(r["n"]), float(r["azimuth_deg"]), float(r["elevation_deg"])
            float(r["value"])
        except ValueError:
            out.append(f"{tsv.name}: row {r['row']} has a non-number")
            continue
        views.setdefault(r["feature"], []).append(i)
        if not 0 <= i < n:
            out.append(f"{tsv.name}: row {r['row']} view {i} outside 0..{n - 1}")
            continue
        want_az, want_el = sphere_hammersley(i, n)
        want_el = max(-PITCH_LIMIT_DEG, min(PITCH_LIMIT_DEG, want_el))
        if abs(az - want_az) > TOLERANCE_DEG or abs(el - want_el) > TOLERANCE_DEG:
            out.append(f"{tsv.name}: row {r['row']} view {i}/{n} is ({az}, {el}), "
                       f"sphere_hammersley_sequence gives ({want_az:.6f}, {want_el:.6f})")
    if not views:
        out.append(f"{tsv.name}: no feature has a view")
    for line in lines[1:]:
        if len(line) == len(TSV_HEADER) and line[3] == "none":
            out.append(f"{tsv.name}: feature {line[1]} has zero rendered views")
    return out


def bundles(args: list) -> list:
    found = []
    for a in map(pathlib.Path, args):
        found += sorted([*a.glob("*.png"), *a.glob("*.mkv")]) if a.is_dir() else [a]
    return found


MKV = (b"\x1a\x45\xdf\xa3\x42\x82\x88matroska" + b"\x00" * 16 + b"\x86\x86V_CFHD" + b"\x86\x86A_FLAC")


def write_bundle(d: pathlib.Path, name: str, cff: str, rows: list) -> pathlib.Path:
    if name.endswith(".mkv"):
        clip = d / name
        clip.write_bytes(MKV if "noflac" not in name else MKV.replace(b"A_FLAC", b"A_OPUS"))
        clip.with_suffix(".cff").write_text(cff)
        clip.with_suffix(".tsv").write_text("\n".join("\t".join(map(str, r)) for r in [TSV_HEADER] + rows) + "\n")
        return clip
    raw = b"\x00\x00\x00\x00"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    chunk = lambda t, b: struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b))
    png = d / name
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    png.with_suffix(".cff").write_text(cff)
    png.with_suffix(".tsv").write_text("\n".join("\t".join(map(str, r)) for r in [TSV_HEADER] + rows) + "\n")
    return png


GOOD_CFF = """cff-version: 1.2.0
title: "walking a faithful station"
version: v20261002-dev.2
date-released: 2026-10-02
commit: 0b5b11e
url: "https://github.com/v-sekai-fire"
license: MIT
authors:
  - name: "V-Sekai-fire"
"""


def hammersley_rows(feature: str, n: int) -> list:
    rows = []
    for i in range(n):
        az, el = sphere_hammersley(i, n)
        el = max(-PITCH_LIMIT_DEG, min(PITCH_LIMIT_DEG, el))
        rows.append([i, feature, "(likely, p=0.70)", i, n, f"{az:.6f}", f"{el:.6f}", "mad", 1.5])
    return rows


def self_test() -> int:
    good_rows = hammersley_rows("walking", 8)
    cases = [
        ("a well-formed bundle passes", "20261002_meshing-pen_joy-walking_0001.png", GOOD_CFF, good_rows, 0),
        ("a name off the pattern fails", "joy.png", GOOD_CFF, good_rows, 1),
        ("a .cff with no commit fails", "20261002_meshing-pen_joy-walking_0002.png",
         GOOD_CFF.replace("commit: 0b5b11e\n", ""), good_rows, 1),
        ("a .cff naming another url fails", "20261002_meshing-pen_joy-walking_0003.png",
         GOOD_CFF.replace("https://github.com/v-sekai-fire", "https://example.com"), good_rows, 1),
        ("a hand-picked azimuth fails", "20261002_meshing-pen_joy-walking_0004.png", GOOD_CFF,
         [r[:5] + ["45.0"] + r[6:] for r in good_rows[:1]] + good_rows[1:], 1),
        ("a CineForm and FLAC clip in Matroska passes", "20261002_meshing-pen_joy-walking_0006.mkv", GOOD_CFF,
         good_rows, 0),
        ("a clip with no FLAC track fails", "20261002_meshing-pen_joy-walking-noflac_0007.mkv", GOOD_CFF,
         good_rows, 1),
        ("a feature with zero rendered views fails", "20261002_meshing-pen_joy-walking_0005.png", GOOD_CFF,
         good_rows + [[9, "world-grab", "(likely, p=0.65)", "none", 8, 0, 0, "mad", 0]], 1),
    ]
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for i, (label, name, cff, rows, want) in enumerate(cases):
            d = pathlib.Path(tmp) / str(i)
            d.mkdir()
            problems = check(write_bundle(d, name, cff, rows))
            ok = (len(problems) > 0) == bool(want)
            failed += 0 if ok else 1
            print(f"{'PASS' if ok else 'FAIL'} {label}: {len(problems)} problem(s)")
    return 1 if failed else 0


def main(argv: list) -> int:
    if "--self-test" in argv:
        return self_test()
    pngs = bundles(argv)
    if not pngs:
        print("FAIL no orbit-view bundle found")
        return 1
    problems = [p for png in pngs for p in check(png)]
    for p in problems:
        print(f"FAIL {p}")
    print(f"{len(pngs)} orbit-view bundle(s), {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
