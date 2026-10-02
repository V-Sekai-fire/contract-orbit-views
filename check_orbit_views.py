#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check orbit-view bundles against STANDARD.md: name, media, .cff, the camera table and the color chart.

    python check_orbit_views.py <dir-or-file>...
    python check_orbit_views.py --self-test
    python check_orbit_views.py --write-chart chart.png
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
CHART_COLS, CHART_ROWS = 6, 4
CHART_TOLERANCE = 2
CHART = [
    (243, 243, 243), (200, 200, 200), (160, 160, 160), (122, 122, 122), (85, 85, 85), (52, 52, 52),
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 255, 255), (255, 0, 255), (255, 255, 0),
    (191, 64, 64), (64, 191, 64), (64, 64, 191), (64, 191, 191), (191, 64, 191), (191, 191, 64),
    (224, 172, 140), (141, 99, 74), (96, 128, 176), (96, 128, 64), (160, 128, 192), (240, 160, 32),
]


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


def png_read(path: pathlib.Path) -> tuple:
    """Decode an 8-bit, non-interlaced RGB or RGBA PNG to (width, height, rows of RGB tuples)."""
    data, pos, idat, w = path.read_bytes(), 8, b"", 0
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or ctype not in (2, 6) or interlace:
                raise ValueError("only 8-bit non-interlaced RGB or RGBA is read")
            bpp = 3 if ctype == 2 else 4
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw, stride, rows, prev = zlib.decompress(idat), w * bpp, [], bytearray(w * bpp)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b, c = prev[x], prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append([tuple(line[x * bpp:x * bpp + 3]) for x in range(w)])
        prev = line
    return w, h, rows


def png_write(path: pathlib.Path, rows: list) -> None:
    h, w = len(rows), len(rows[0])
    raw = b"".join(b"\x00" + bytes(c for px in row for c in px) for row in rows)
    chunk = lambda t, b: struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def chart_rows(patch: int) -> list:
    return [[CHART[(y // patch) * CHART_COLS + x // patch] for x in range(CHART_COLS * patch)]
            for y in range(CHART_ROWS * patch)]


def chart_problems(png: pathlib.Path) -> list:
    region = png.with_suffix(".chart.tsv")
    if not region.exists():
        return [f"{png.name}: no {region.name} naming where the color chart is"]
    lines = [ln.split("\t") for ln in region.read_text().splitlines() if ln.strip()]
    if len(lines) != 2 or lines[0] != ["x", "y", "w", "h"]:
        return [f"{region.name}: not one x y w h row"]
    x0, y0, cw, ch = map(int, lines[1])
    try:
        w, h, px = png_read(png)
    except (ValueError, zlib.error, struct.error) as e:
        return [f"{png.name}: chart unreadable ({e})"]
    if x0 < 0 or y0 < 0 or x0 + cw > w or y0 + ch > h:
        return [f"{region.name}: chart region lies outside the {w}x{h} image"]
    out, pw, ph = [], cw / CHART_COLS, ch / CHART_ROWS
    for k, want in enumerate(CHART):
        cx, cy = x0 + (k % CHART_COLS + 0.25) * pw, y0 + (k // CHART_COLS + 0.25) * ph
        cells = [px[y][x] for y in range(int(cy), max(int(cy) + 1, int(cy + ph / 2)))
                 for x in range(int(cx), max(int(cx) + 1, int(cx + pw / 2)))]
        got = tuple(round(sum(c[i] for c in cells) / len(cells)) for i in range(3))
        err = max(abs(g - t) for g, t in zip(got, want))
        if err > CHART_TOLERANCE:
            out.append(f"{png.name}: chart patch {k} is {got}, wants {want} (off by {err})")
    return out


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
    else:
        out += chart_problems(png)
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
        found += sorted(p for p in [*a.glob("*.png"), *a.glob("*.mkv")] if p.name != "chart.png") if a.is_dir() else [a]
    return found


MKV = (b"\x1a\x45\xdf\xa3\x42\x82\x88matroska" + b"\x00" * 16 + b"\x86\x86V_CFHD" + b"\x86\x86A_FLAC")


def write_bundle(d: pathlib.Path, name: str, cff: str, rows: list) -> pathlib.Path:
    if name.endswith(".mkv"):
        clip = d / name
        clip.write_bytes(MKV if "noflac" not in name else MKV.replace(b"A_FLAC", b"A_OPUS"))
        clip.with_suffix(".cff").write_text(cff)
        clip.with_suffix(".tsv").write_text("\n".join("\t".join(map(str, r)) for r in [TSV_HEADER] + rows) + "\n")
        return clip
    png = d / name
    rows_px = chart_rows(8)
    if "swapped" in name:
        rows_px = [row[8:16] + row[:8] + row[16:] for row in rows_px]
    if "linear" in name:
        rows_px = [[tuple(round(255 * (c / 255) ** 2.2) for c in p) for p in row] for row in rows_px]
    png_write(png, rows_px)
    if "nochart" not in name:
        png.with_suffix(".chart.tsv").write_text("x\ty\tw\th\n0\t0\t48\t32\n")
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
        ("a chart patch moved fails", "20261002_meshing-pen_joy-swapped_0008.png", GOOD_CFF, good_rows, 1),
        ("a chart written in linear light fails", "20261002_meshing-pen_joy-linear_0009.png", GOOD_CFF,
         good_rows, 1),
        ("a sheet with no chart region fails", "20261002_meshing-pen_joy-nochart_0010.png", GOOD_CFF, good_rows, 1),
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
    if argv[:1] == ["--write-chart"] and len(argv) == 2:
        png_write(pathlib.Path(argv[1]), chart_rows(96))
        print(f"wrote {argv[1]}: {CHART_COLS}x{CHART_ROWS} patches of 96 px")
        return 0
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
