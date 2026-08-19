#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Representative Structure Selection for Scaling Analysis.

Selects 8-10 structures from the 999 in feature_data.json that cover:
  - Stretch-dominated topologies  (Octet, FCCZ, G7, AFCC)
  - Bending-dominated topologies  (BCC, FCC, Kelvin, Diamond)
  - Hybrid / special topologies   (Auxetic, WeairePhelan)

Also loads existing n>1 simulation results (e.g. 3x3x3 from test2/).

@author: ARTC Team
@date: 2026-03
"""

import json
import os
import csv
import numpy as np
from typing import List, Dict, Optional, Tuple


# ── Topology classification ──────────────────────────────────────────────────

# Stretch-dominated: members primarily carry axial loads
STRETCH_DOMINATED = {
    "Octet", "FCCZ", "G7", "AFCC", "FBCCZ", "FBCCXYZ", "BCCZ",
    "Octahedron", "Cuboctahedron",
}

# Bending-dominated: members primarily carry bending moments
BENDING_DOMINATED = {
    "BCC", "FCC", "Kelvin", "Diamond", "DiamondPlus", "CBCC",
    "Rhombic", "Tetrahedron", "Iso", "Cubic", "CubicRosette",
}

# Hybrid or special topologies
HYBRID_SPECIAL = {
    "Auxetic", "WeairePhelan", "Truncated",
}


def classify_topology(cell_type: str) -> str:
    """Classify a cell type as 'stretch', 'bending', or 'hybrid'.

    Parameters
    ----------
    cell_type : str
        The topology name, e.g. 'BCC', 'Octet', 'Auxetic'.

    Returns
    -------
    str
        One of 'stretch', 'bending', or 'hybrid'.
    """
    if cell_type in STRETCH_DOMINATED:
        return "stretch"
    elif cell_type in BENDING_DOMINATED:
        return "bending"
    elif cell_type in HYBRID_SPECIAL:
        return "hybrid"
    else:
        # Unknown topology — default to hybrid
        return "hybrid"


# ── Helper: parse structure key ──────────────────────────────────────────────

def _parse_structure_key(key: str) -> Tuple[Optional[str], Optional[float],
                                             Optional[float], Optional[int]]:
    """Parse 'CellType_CellSize_StrutRadius_Transform' into components.

    Handles multi-word cell types like 'Octet_truss_5_0p5_6' by scanning
    from the right: the last 3 underscore-separated tokens are always
    size / radius / transform, everything before them is the cell type.
    """
    parts = key.split("_")
    if len(parts) < 4:
        return None, None, None, None
    # Last 3 parts are always: cell_size, strut_radius, transform
    # Everything before that is the cell type (may contain underscores)
    try:
        transform = int(parts[-1])
        radius_str = parts[-2].replace("p", ".")
        strut_radius = float(radius_str)
        cell_size = float(parts[-3])
        cell_type = "_".join(parts[:-3])
        if not cell_type:
            return None, None, None, None
        return cell_type, cell_size, strut_radius, transform
    except (ValueError, IndexError):
        return parts[0], None, None, None


# ── Representative selection ─────────────────────────────────────────────────

# Structures that already have n=3 data (must always be included)
KNOWN_MULTI_N_KEYS = [
    "BCC_5_0p5_8",
    "FCC_5_0p5_8",
    "FCCZ_5_0p5_8",
]

# Preferred topologies for each class (order = priority)
PREFERRED_STRETCH = ["Octet", "FCCZ", "G7", "AFCC"]
PREFERRED_BENDING = ["BCC", "FCC", "Kelvin", "Diamond"]
PREFERRED_HYBRID  = ["Auxetic", "WeairePhelan"]


def select_representative_structures(
    feature_data_path: str,
    n_per_class: int = 3,
) -> List[Dict]:
    """Select representative structures covering all topology classes and
    density ranges.

    The selection strategy:
      1. Always include the 3 structures with existing n=3 data.
      2. For each topology class, pick *n_per_class* structures from the
         preferred topologies, choosing varied density levels (low / mid / high).
      3. Return a list of dicts with metadata for each selected structure.

    Parameters
    ----------
    feature_data_path : str
        Path to feature_data.json.
    n_per_class : int
        Target number of structures per topology class (default 3).

    Returns
    -------
    list[dict]
        Each dict has keys: 'key', 'cell_type', 'cell_size', 'strut_radius',
        'transform', 'density', 'topology_class', 'has_multi_n'.
    """
    with open(feature_data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Build an index: cell_type -> list of (key, density)
    type_index: Dict[str, List[Tuple[str, float]]] = {}
    for key, entry in data.items():
        cell_type, cell_size, strut_radius, transform = _parse_structure_key(key)
        if cell_type is None or cell_size is None:
            continue
        density = entry.get("density", 0.0)
        type_index.setdefault(cell_type, []).append((key, density))

    selected_keys = set()
    results = []

    # Step 1: always include structures with existing multi-n data
    for key in KNOWN_MULTI_N_KEYS:
        if key in data:
            cell_type, cell_size, strut_radius, transform = _parse_structure_key(key)
            density = data[key].get("density", 0.0)
            results.append({
                "key": key,
                "cell_type": cell_type,
                "cell_size": cell_size,
                "strut_radius": strut_radius,
                "transform": transform,
                "density": density,
                "topology_class": classify_topology(cell_type),
                "has_multi_n": True,
            })
            selected_keys.add(key)

    # Step 2: for each class, pick from preferred topologies at varied densities
    class_prefs = [
        ("stretch", PREFERRED_STRETCH),
        ("bending", PREFERRED_BENDING),
        ("hybrid",  PREFERRED_HYBRID),
    ]

    for topo_class, preferred_types in class_prefs:
        needed = n_per_class
        for ptype in preferred_types:
            if needed <= 0:
                break
            candidates = type_index.get(ptype, [])
            if not candidates:
                continue
            # Sort by density
            candidates.sort(key=lambda x: x[1])
            # Pick from low / mid / high density
            n_cand = len(candidates)
            if n_cand == 0:
                continue
            indices = _spread_indices(n_cand, min(needed, 3))
            for idx in indices:
                key, density = candidates[idx]
                if key in selected_keys:
                    continue
                cell_type, cell_size, strut_radius, transform = _parse_structure_key(key)
                results.append({
                    "key": key,
                    "cell_type": cell_type,
                    "cell_size": cell_size,
                    "strut_radius": strut_radius,
                    "transform": transform,
                    "density": density,
                    "topology_class": topo_class,
                    "has_multi_n": key in KNOWN_MULTI_N_KEYS,
                })
                selected_keys.add(key)
                needed -= 1

    return results


def _spread_indices(n: int, k: int) -> List[int]:
    """Pick k indices evenly spread across 0..n-1."""
    if k >= n:
        return list(range(n))
    if k == 1:
        return [n // 2]
    return [int(round(i * (n - 1) / (k - 1))) for i in range(k)]


# ── Load existing multi-n simulation results ─────────────────────────────────

def get_existing_multi_n_data(test_dir: str) -> Dict[str, Dict]:
    """Load existing n>1 simulation results from a test directory.

    Searches for CSV files matching the pattern
    ``{CellType}_{CellSize}_{Radius}_{Slider}_{n}x{n}x{n}_force_displacement.csv``.

    Parameters
    ----------
    test_dir : str
        Directory containing simulation output CSVs (e.g. ``work/test2/``).

    Returns
    -------
    dict
        Nested dict: ``{base_key: {n: {'displacement': array, 'force': array,
        'strain': array, 'stress': array}}}`` where *base_key* is the 1x1x1
        structure key (e.g. 'BCC_5_0p5_8') and *n* is the array dimension.
    """
    result: Dict[str, Dict] = {}

    if not os.path.isdir(test_dir):
        return result

    for fname in os.listdir(test_dir):
        if not fname.endswith("_force_displacement.csv"):
            continue

        # Parse filename: e.g. BCC_5_0p5_8_3x3x3_force_displacement.csv
        base = fname.replace("_force_displacement.csv", "")
        # Find the NxNxN part
        parts = base.split("_")
        nxn_idx = None
        for i, p in enumerate(parts):
            if "x" in p and p.count("x") == 2:
                try:
                    dims = p.split("x")
                    n_val = int(dims[0])
                    if int(dims[1]) == n_val and int(dims[2]) == n_val:
                        nxn_idx = i
                        break
                except ValueError:
                    continue

        if nxn_idx is None:
            continue

        base_key = "_".join(parts[:nxn_idx])
        n_val = int(parts[nxn_idx].split("x")[0])

        # Read CSV
        filepath = os.path.join(test_dir, fname)
        displacement = []
        force = []
        strain = []
        stress = []

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    displacement.append(float(row["Abs_Displacement_mm"]))
                    force.append(float(row["Abs_Force_N"]))
                    strain.append(float(row["Strain"]))
                    stress.append(float(row["Stress_MPa"]))
                except (KeyError, ValueError):
                    continue

        if not displacement:
            continue

        result.setdefault(base_key, {})[n_val] = {
            "displacement": np.array(displacement),
            "force": np.array(force),
            "strain": np.array(strain),
            "stress": np.array(stress),
        }

    return result
