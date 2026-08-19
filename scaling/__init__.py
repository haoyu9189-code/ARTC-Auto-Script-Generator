"""
Scaling Analysis Framework for ARTC Lattice Structures.

This module provides tools to analyze how stress-strain curves scale with
array dimension n (n×n×n), and to predict multi-cell behavior from single-cell
(1×1×1) simulation data.

Core workflow:
    1. selection.py      — Select representative structures from the database
    2. scaling_analyzer.py — Fit scaling coefficients from multi-n simulation data
    3. prediction_engine.py — Predict n×n×n curves from 1×1×1 data
    4. database_builder.py — Generate an expanded database for all structures

Scaling model:
    σ(ε, n) = σ_∞(ε) + α(ε)/n + β(ε)/n²

where σ_∞ is the bulk (infinite-array) stress, and α, β capture finite-size
boundary effects that diminish as n increases.

@author: ARTC Team
@date: 2026-03
"""

from scaling.selection import (
    classify_topology,
    select_representative_structures,
    get_existing_multi_n_data,
)
from scaling.scaling_analyzer import CurveScalingModel, ScalingAnalyzer
from scaling.prediction_engine import PredictionEngine
from scaling.database_builder import DatabaseBuilder

__all__ = [
    "classify_topology",
    "select_representative_structures",
    "get_existing_multi_n_data",
    "CurveScalingModel",
    "ScalingAnalyzer",
    "PredictionEngine",
    "DatabaseBuilder",
]
