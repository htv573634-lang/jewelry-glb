"""
Complex Indian jewelry designs — procedurally generated.
Extends the simple library from build_library.py.
"""

import os
import sys
import json
import numpy as np
import trimesh
from trimesh.creation import torus, icosphere

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_library import MATERIALS, attach, pbr

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "outputs"))
INDEX_PATH = os.path.join(OUTPUT_DIR, "library_index.json")

RING_INNER_R = 0.0092
RING_THICKNESS = 0.0018


# ══════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════

def sphere(center, radius, mat, subdiv=1):
    s = icosphere(radius=radius, subdivisions=subdiv)
    s = attach(s, mat)
    s.apply_translation(center)
    return s


def ring_at(center, major_r, minor_r, mat, major_seg=32, minor_seg=12):
    t = torus(major_radius=major_r, minor_radius=minor_r,
              major_segments=major_seg, minor_segments=minor_seg)
    t = attach(t, mat)
    t.apply_translation(center)
    return t


def arc_beads(radius, start_a, end_a, n, bead_r, mat, z=0.0, y_offset=0.0):
    """Chain of small beads along an arc in the XY plane."""
    parts = []
    for i in range(n):
        a = start_a + (end_a - start_a) * i / max(n - 1, 1)
        p = [radius * np.cos(a), radius * np.sin(a) + y_offset, z]
        parts.append(sphere(p, bead_r, mat))
    return trimesh.util.concatenate(parts)


def hanging_drop(top, length, n_beads, bead_r, drop_mat, chain_mat="gold"):
    """Chain of beads ending in a gemstone."""
    parts = [sphere(top, bead_r * 1.2, chain_mat)]
    for i in range(1, n_beads + 1):
        z = top[2] - length * i / (n_beads + 1)
        parts.append(sphere([top[0], top[1], z], bead_r, chain_mat))
    end = [top[0], top[1], top[2] - length]
    parts.append(sphere(end, bead_r * 1.8, drop_mat, subdiv=2))
    return trimesh.util.concatenate(parts)


# ══════════════════════════════════════════════════════
# COMPLEX RINGS
# ══════════════════════════════════════════════════════

def filigree_ring():
    """Band + double helix of micro-beads for a filigree look."""
    band_r = RING_INNER_R + RING_THICKNESS
    parts = [ring_at([0, 0, 0], band_r, RING_THICKNESS, "gold",
                     major_seg=72, minor_seg=16)]
    n = 96
    for i in range(n):
        a = 2 * np.pi * i / n
        for offset in [1, -1]:
            z = 0.0025 * np.sin(a * 3 + (0 if offset == 1 else np.pi))
            rr = band_r + offset * 0.0012
            parts.append(sphere([rr * np.cos(a), rr * np.sin(a), z], 0.00045, "gold"))
    return trimesh.util.concatenate(parts)


def cluster_ring():
    """Center stone + halo of 12 small stones."""
    band_r = RING_INNER_R + RING_THICKNESS
    parts = [ring_at([0, 0, 0], band_r, RING_THICKNESS, "platinum",
                     major_seg=72, minor_seg=16)]
    parts.append(ring_at([0, 0, band_r + 0.001], 0.003, 0.0004, "platinum"))
    parts.append(sphere([0, 0, band_r + 0.0045], 0.0035, "diamond", subdiv=2))
    for i in range(12):
        a = 2 * np.pi * i / 12
        parts.append(sphere([0.005 * np.cos(a), 0.005 * np.sin(a), band_r + 0.0035],
                            0.0012, "diamond", subdiv=2))
    return trimesh.util.concatenate(parts)


# ══════════════════════════════════════════════════════
# COMPLEX EARRINGS
# ══════════════════════════════════════════════════════

def jhumka():
    """Dome + bell rim + hanging bead fringe."""
    parts = [sphere([0, 0, 0.012], 0.0035, "gold", subdiv=2)]
    dome = icosphere(radius=0.008, subdivisions=2)
    dome.vertices[:, 2] -= 0.008
    dome.vertices[:, 2] *= -1
    dome = attach(dome, "gold")
    dome.apply_translation([0, 0, 0.008])
    parts.append(dome)

    cup_r = 0.011
    parts.append(arc_beads(cup_r, 0, 2 * np.pi, 36, 0.0009, "gold", z=0.001))

    for i in range(12):
        a = 2 * np.pi * i / 12
        p = [cup_r * np.cos(a), cup_r * np.sin(a), 0.001]
        parts.append(hanging_drop(p, 0.008, 3, 0.0007, "pearl", "gold"))

    parts.append(hanging_drop([0, 0, 0.001], 0.014, 5, 0.0008, "ruby", "gold"))
    return trimesh.util.concatenate(parts)


def chandbali():
    """Crescent moon earring with pearl fringe."""
    parts = [sphere([0, 0, 0.015], 0.003, "gold", subdiv=2)]
    cres_r = 0.010
    n = 40
    for i in range(n):
        t = i / (n - 1)
        a = -np.pi * 0.7 + t * np.pi * 1.4
        p = [cres_r * np.cos(a), 0, 0.002 + cres_r * np.sin(a) * 0.6]
        parts.append(sphere(p, 0.0011, "gold"))

    for i in range(9):
        t = i / 8
        a = -np.pi * 0.6 + t * np.pi * 1.2
        p = [cres_r * np.cos(a), 0, -0.002 + cres_r * np.sin(a) * 0.6]
        parts.append(hanging_drop(p, 0.008, 2, 0.0006, "pearl", "gold"))

    parts.append(sphere([0, 0, 0.003], 0.0025, "ruby", subdiv=2))
    return trimesh.util.concatenate(parts)


# ══════════════════════════════════════════════════════
# COMPLEX NECKLACES
# ══════════════════════════════════════════════════════

def kundan_choker():
    """Wide flat band with 24 stone settings and hanging drops."""
    band_r = 0.075
    parts = []
    base = torus(major_radius=band_r, minor_radius=0.012,
                 major_segments=128, minor_segments=24)
    base.vertices[:, 2] *= 0.15
    base = attach(base, "gold")
    parts.append(base)

    n_stones = 24
    for i in range(n_stones):
        a = -np.pi * 0.5 + np.pi * i / (n_stones - 1)
        p = [band_r * np.cos(a), band_r * np.sin(a), 0.003]
        parts.append(sphere(p, 0.0022, "diamond", subdiv=2))

    for i in range(n_stones - 1):
        a = -np.pi * 0.5 + np.pi * (i + 0.5) / (n_stones - 1)
        p = [band_r * np.cos(a) * 1.03, band_r * np.sin(a) * 1.03, -0.002]
        parts.append(hanging_drop(p, 0.006, 2, 0.0006, "ruby", "gold"))
    return trimesh.util.concatenate(parts)


def temple_necklace():
    """3 concentric arcs, hanging pendants on bottom tier."""
    parts = []
    tiers = [(0.09, 0.0012, 30), (0.07, 0.0010, 24), (0.05, 0.0009, 18)]
    for radius, thickness, n_pts in tiers:
        for i in range(n_pts):
            a = -np.pi * 0.5 + np.pi * i / (n_pts - 1)
            p = [radius * np.cos(a), radius * np.sin(a), 0]
            parts.append(sphere(p, thickness, "gold"))
            if radius == 0.09 and i % 2 == 0:
                p2 = [radius * np.cos(a), radius * np.sin(a), -0.001]
                parts.append(hanging_drop(p2, 0.007, 2, 0.0007, "ruby", "gold"))
    parts.append(hanging_drop([0, 0.09, 0], 0.02, 4, 0.0012, "ruby", "gold"))
    parts.append(sphere([0, 0.09, -0.025], 0.004, "diamond", subdiv=2))
    return trimesh.util.concatenate(parts)


def rani_haar():
    """60cm sagging chain with 5 small pendants + large center pendant."""
    parts = []
    length = 0.60
    n = 120
    pts = []
    for i in range(n):
        t = i / (n - 1)
        x = -length / 2 + length * t
        z = -0.08 * np.sin(np.pi * t)
        pts.append((x, z))
        parts.append(sphere([x, 0, z], 0.0009, "gold"))

    for i in range(1, 6):
        t = i / 6
        x = -length / 2 + length * t
        z = -0.08 * np.sin(np.pi * t)
        parts.append(hanging_drop([x, 0, z - 0.001], 0.015, 3, 0.0008, "ruby", "gold"))

    parts.append(hanging_drop([0, 0, -0.081], 0.03, 5, 0.0015, "diamond", "gold"))
    return trimesh.util.concatenate(parts)


# ══════════════════════════════════════════════════════
# HEAD / ARM / WAIST / ANKLE
# ══════════════════════════════════════════════════════

def maang_tikka():
    """Hairline chain + floral medallion + center drop."""
    parts = []
    length = 0.10
    for i in range(25):
        p = [0, 0, -length * i / 24]
        parts.append(sphere(p, 0.0007, "gold"))

    for i in range(8):
        a = 2 * np.pi * i / 8
        p = [0.003 * np.cos(a), 0.003 * np.sin(a), -length]
        parts.append(sphere(p, 0.0018, "gold"))

    parts.append(sphere([0, 0, -length], 0.0025, "ruby", subdiv=2))
    parts.append(hanging_drop([0, 0, -length - 0.003], 0.012, 3, 0.0008, "pearl", "gold"))
    return trimesh.util.concatenate(parts)


def bajuband():
    """Armlet: band + filigree double-row + hanging beads."""
    r = 0.045
    parts = [ring_at([0, 0, 0], r, 0.003, "gold", major_seg=96, minor_seg=16)]

    n = 48
    for i in range(n):
        a = -np.pi * 0.5 + np.pi * i / (n - 1)
        for z_off in [-0.002, 0.002]:
            parts.append(sphere([r * np.cos(a), r * np.sin(a), z_off], 0.0006, "gold"))

    for i in range(7):
        a = -np.pi * 0.4 + np.pi * i / 6
        p = [r * np.cos(a) * 1.03, r * np.sin(a) * 1.03, -0.002]
        parts.append(hanging_drop(p, 0.008, 2, 0.0006, "ruby", "gold"))
    return trimesh.util.concatenate(parts)


def kamarbandh():
    """75cm two-strand chain with periodic pendants."""
    parts = []
    length = 0.75
    n = 160
    for strand in [-0.001, 0.001]:
        for i in range(n):
            x = -length / 2 + length * i / (n - 1)
            parts.append(sphere([x, 0, strand], 0.0006, "gold"))

    for i in range(0, n, 15):
        x = -length / 2 + length * i / (n - 1)
        parts.append(hanging_drop([x, 0, -0.002], 0.008, 2, 0.0007, "ruby", "gold"))

    parts.append(hanging_drop([0, 0, -0.002], 0.015, 3, 0.0010, "diamond", "gold"))
    return trimesh.util.concatenate(parts)


def payal():
    """Ankle chain with dome bells every 6 beads."""
    r = 0.06
    n = 60
    parts = []
    for i in range(n):
        a = 2 * np.pi * i / n
        parts.append(sphere([r * np.cos(a), r * np.sin(a), 0], 0.0008, "silver"))

    for i in range(0, n, 6):
        a = 2 * np.pi * i / n
        p = [r * np.cos(a), r * np.sin(a)]
        bell = icosphere(radius=0.0025, subdivisions=1)
        bell.vertices[:, 2] -= bell.vertices[:, 2].min()
        bell = attach(bell, "silver")
        bell.apply_translation([p[0], p[1], -0.001])
        parts.append(bell)
        parts.append(sphere([p[0], p[1], -0.004], 0.0006, "silver"))
    return trimesh.util.concatenate(parts)


def mandala_brooch():
    """3 layers of petals + outer dots."""
    parts = [sphere([0, 0, 0], 0.003, "ruby", subdiv=2)]
    layers = [
        (0.010, 0.0035, "gold", 8),
        (0.008, 0.0028, "diamond", 12),
        (0.006, 0.0020, "gold", 16),
    ]
    for idx, (radius, petal_r, mat, n_petals) in enumerate(layers):
        for i in range(n_petals):
            a = 2 * np.pi * i / n_petals
            p = [radius * np.cos(a), radius * np.sin(a), 0.0005 * idx]
            parts.append(sphere(p, petal_r, mat))
    for i in range(24):
        a = 2 * np.pi * i / 24
        parts.append(sphere([0.014 * np.cos(a), 0.014 * np.sin(a), 0], 0.0008, "gold"))
    return trimesh.util.concatenate(parts)


# ══════════════════════════════════════════════════════
# EXPORT
# ══════════════════════════════════════════════════════

INDEX = {}


def load_existing():
    global INDEX
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH) as f:
            INDEX = json.load(f)
        print(f"[*] Loaded {sum(len(v) for v in INDEX.values())} existing pieces")


def export(mesh, category, name, anchor=None):
    d = os.path.join(OUTPUT_DIR, category, name)
    os.makedirs(d, exist_ok=True)
    glb = os.path.join(d, f"{name}.glb")
    mesh.export(glb)
    entry = {
        "category": category,
        "name": name,
        "path": f"{category}/{name}/{name}.glb",
        "verts": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "size_kb": round(os.path.getsize(glb) / 1024, 1),
        "bbox_min": [float(x) for x in mesh.bounds[0]],
        "bbox_max": [float(x) for x in mesh.bounds[1]],
        "size_m": [float(x) for x in (mesh.bounds[1] - mesh.bounds[0])],
        "anchor": anchor,
        "complex": True,
    }
    INDEX.setdefault(category, []).append(entry)
    print(f"  [{category}/{name}] {entry['verts']}v {entry['faces']}f {entry['size_kb']}KB")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    load_existing()
    print("\n[*] Building complex jewelry...\n")

    print("[RINGS]")
    export(filigree_ring(), "ring", "ring_filigree_helix", anchor="finger")
    export(cluster_ring(),  "ring", "ring_cluster_halo",    anchor="finger")

    print("\n[EARRINGS]")
    export(jhumka(),    "earring", "jhumka_bell",       anchor="ear")
    export(chandbali(), "earring", "chandbali_crescent", anchor="ear")

    print("\n[NECKLACES]")
    export(kundan_choker(),   "necklace", "choker_kundan_wide",   anchor="neck")
    export(temple_necklace(), "necklace", "necklace_temple_3tier", anchor="neck_chest")
    export(rani_haar(),       "necklace", "rani_haar_long",       anchor="neck_chest")

    print("\n[HEAD]")
    export(maang_tikka(), "head", "maang_tikka_floral", anchor="head_forehead")

    print("\n[ARM]")
    export(bajuband(), "arm", "bajuband_armlet", anchor="upper_arm")

    print("\n[WAIST]")
    export(kamarbandh(), "waist", "kamarbandh_chain", anchor="waist")

    print("\n[ANKLE]")
    export(payal(), "ankle", "payal_bells", anchor="ankle")

    print("\n[BROOCH]")
    export(mandala_brooch(), "brooch", "mandala_radial", anchor="chest")

    with open(INDEX_PATH, "w") as f:
        json.dump(INDEX, f, indent=2)

    total = sum(len(v) for v in INDEX.values())
    print(f"\n[SUCCESS] Total library: {total} pieces")
    for cat, items in sorted(INDEX.items()):
        print(f"  {cat}: {len(items)}")


if __name__ == "__main__":
    main()
