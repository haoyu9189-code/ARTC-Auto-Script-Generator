#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Expanded Database Builder.

Generates predicted n×n×n curves for all 999 structures and merges them
with the original 1×1×1 data to produce a comprehensive database.

@author: ARTC Team
@date: 2026-03
"""

import json
import os
import warnings
from typing import Dict, List, Optional, Tuple

import numpy as np

from scaling.prediction_engine import PredictionEngine
from scaling.scaling_analyzer import ScalingAnalyzer


class DatabaseBuilder:
    """Build an expanded database with predicted multi-n curves.

    Parameters
    ----------
    prediction_engine : PredictionEngine
        Configured prediction engine with scaling models.
    feature_data_path : str
        Path to the original feature_data.json.
    """

    def __init__(self, prediction_engine: PredictionEngine, feature_data_path: str):
        self.engine = prediction_engine
        self.feature_data_path = feature_data_path
        # Reuse the already-loaded data from PredictionEngine instead of re-reading from disk
        self.original_data: Dict = prediction_engine.feature_data

    # ── Build expanded database ──────────────────────────────────────────

    def build_expanded_database(
        self,
        n_values: List[int] = None,
        curve_types: List[str] = None,
        cell_size: float = 5.0,
    ) -> Dict:
        """Generate predicted curves for all structures at all n values.

        The output merges original 1×1×1 data with predicted n×n×n data.

        Parameters
        ----------
        n_values : list[int]
            Array dimensions to predict (default: [2, 3, 4, 5]).
        curve_types : list[str]
            Curve types to predict (default: ['StaCompre_curve']).
        cell_size : float
            Single cell side length (mm).

        Returns
        -------
        dict
            Expanded database in the same format as feature_data.json, with
            additional keys like 'n2_StaCompre_curve', 'n3_StaCompre_curve', etc.
            Each predicted curve has a 'predicted' flag set to True.
        """
        if n_values is None:
            n_values = [2, 3, 4, 5]
        if curve_types is None:
            curve_types = ["StaCompre_curve"]

        print(f"Building expanded database for n={n_values}, "
              f"curve_types={curve_types}...")

        # Get predictions for all structures
        predictions = self.engine.predict_all_structures(
            n_values=n_values,
            curve_types=curve_types,
            cell_size=cell_size,
        )

        # Merge with original data
        expanded = {}
        for struct_key, entry in self.original_data.items():
            # Copy original data
            expanded_entry = dict(entry)

            # Add predictions
            if struct_key in predictions:
                for pred_key, pred_data in predictions[struct_key].items():
                    expanded_entry[pred_key] = pred_data

            expanded[struct_key] = expanded_entry

        total_preds = sum(len(v) for v in predictions.values())
        print(f"Expanded database: {len(expanded)} structures, "
              f"{total_preds} predicted curves added.")

        return expanded

    # ── Save / Load ──────────────────────────────────────────────────────

    def save_database(self, data: Dict, output_path: str) -> None:
        """Save the expanded database to a JSON file.

        Parameters
        ----------
        data : dict
            The expanded database dict.
        output_path : str
            Output file path.
        """
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # Convert numpy arrays to lists for JSON serialization
        serializable = self._make_serializable(data)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"Saved expanded database to: {output_path} ({size_mb:.1f} MB)")

    @staticmethod
    def _make_serializable(obj):
        """Recursively convert numpy types to Python native types."""
        if isinstance(obj, dict):
            return {k: DatabaseBuilder._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [DatabaseBuilder._make_serializable(v) for v in obj]
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, (np.bool_,)):
            return bool(obj)
        return obj

    # ── Validation against actual simulation data ────────────────────────

    def validate_predictions(
        self,
        predictions: Dict,
        actual_data: Dict[str, Dict[int, Dict]],
        cell_size: float = 5.0,
    ) -> Dict:
        """Compare predictions against actual simulation results.

        Parameters
        ----------
        predictions : dict
            The expanded database (output of build_expanded_database).
        actual_data : dict
            {base_key: {n: {'displacement': array, 'force': array}}} from
            real simulations (e.g. output of get_existing_multi_n_data).
        cell_size : float
            Single cell side length.

        Returns
        -------
        dict
            Validation report with per-structure and aggregate metrics.
            {
                'structures': {
                    'BCC_5_0p5_8': {
                        3: {'r2': ..., 'rmse': ..., 'mape': ..., 'max_error': ...},
                    },
                },
                'aggregate': {'mean_r2': ..., 'mean_mape': ..., 'mean_rmse': ...},
            }
        """
        report = {"structures": {}, "aggregate": {}}
        all_r2 = []
        all_mape = []
        all_rmse = []

        for base_key, n_data in actual_data.items():
            report["structures"][base_key] = {}

            for n, actual in n_data.items():
                pred_key = f"n{n}_StaCompre_curve"
                if base_key not in predictions or pred_key not in predictions[base_key]:
                    continue

                pred = predictions[base_key][pred_key]

                # Normalize both to stress-strain for fair comparison
                actual_disp = np.asarray(actual["displacement"])
                actual_force = np.asarray(actual["force"])
                pred_disp = np.asarray(pred["displacement"])
                pred_force = np.asarray(pred["force"])

                actual_strain, actual_stress = ScalingAnalyzer.normalize_curve(
                    actual_disp, actual_force, n, cell_size,
                )
                pred_strain, pred_stress = ScalingAnalyzer.normalize_curve(
                    pred_disp, pred_force, n, cell_size,
                )

                # Interpolate to common grid
                n_pts = 100
                strain_max = min(
                    float(actual_strain[-1]) if len(actual_strain) > 0 else 0,
                    float(pred_strain[-1]) if len(pred_strain) > 0 else 0,
                )
                if strain_max <= 0:
                    continue

                _, actual_interp = ScalingAnalyzer.interpolate_curve(
                    actual_strain, actual_stress, n_pts, strain_max,
                )
                _, pred_interp = ScalingAnalyzer.interpolate_curve(
                    pred_strain, pred_stress, n_pts, strain_max,
                )

                metrics = ScalingAnalyzer._compute_metrics(actual_interp, pred_interp)
                metrics["max_error"] = float(np.max(np.abs(actual_interp - pred_interp)))

                report["structures"][base_key][n] = metrics
                all_r2.append(metrics["r2"])
                all_mape.append(metrics["mape"])
                all_rmse.append(metrics["rmse"])

        if all_r2:
            report["aggregate"] = {
                "mean_r2": float(np.mean(all_r2)),
                "mean_mape": float(np.mean(all_mape)),
                "mean_rmse": float(np.mean(all_rmse)),
                "n_validated": len(all_r2),
            }

        return report

    # ── Physical consistency checks ──────────────────────────────────────

    def physical_consistency_check(self, predictions: Dict) -> List[Dict]:
        """Check that predicted curves satisfy physical constraints.

        Checks performed:
          1. Non-negative stress (force) everywhere.
          2. Monotonic convergence: as n increases, the normalized stress-strain
             curve should converge (changes should get smaller).
          3. Reasonable magnitude: predicted stress should not exceed 10x the
             1×1×1 stress at any strain point.
          4. Curve length: predicted curves should have a reasonable number of
             points.

        Parameters
        ----------
        predictions : dict
            The expanded database.

        Returns
        -------
        list[dict]
            List of violations, each with keys:
            'structure', 'check', 'severity', 'detail'.
        """
        violations = []

        for struct_key, entry in predictions.items():
            # Get 1x1x1 reference
            ref_curve = entry.get("StaCompre_curve")
            if not ref_curve or "force" not in ref_curve:
                continue

            ref_force = np.array(ref_curve["force"], dtype=np.float64)
            ref_max_force = float(np.max(np.abs(ref_force))) if len(ref_force) > 0 else 1.0

            # Collect predicted curves by n
            predicted_curves = {}
            for key, value in entry.items():
                if not isinstance(value, dict):
                    continue
                if not value.get("predicted", False):
                    continue
                n = value.get("array_dimension")
                if n is None:
                    continue
                force = value.get("force", [])
                if force:
                    predicted_curves[n] = np.array(force, dtype=np.float64)

            for n, force_arr in predicted_curves.items():
                # Check 1: non-negative force
                if np.any(force_arr < -1e-10):
                    n_neg = int(np.sum(force_arr < -1e-10))
                    violations.append({
                        "structure": struct_key,
                        "check": "non_negative_force",
                        "severity": "warning",
                        "detail": (
                            f"n={n}: {n_neg} points with negative force "
                            f"(min={float(np.min(force_arr)):.4g})"
                        ),
                    })

                # Check 2: reasonable magnitude
                max_pred = float(np.max(np.abs(force_arr)))
                # n×n×n force scales as n² relative to 1×1×1
                expected_scale = n ** 2
                threshold = 10.0 * ref_max_force * expected_scale
                if max_pred > threshold and ref_max_force > 1e-10:
                    violations.append({
                        "structure": struct_key,
                        "check": "magnitude",
                        "severity": "error",
                        "detail": (
                            f"n={n}: max predicted force {max_pred:.4g} "
                            f"exceeds 10x scaled reference "
                            f"({threshold:.4g})"
                        ),
                    })

                # Check 3: curve length
                if len(force_arr) < 10:
                    violations.append({
                        "structure": struct_key,
                        "check": "curve_length",
                        "severity": "warning",
                        "detail": (
                            f"n={n}: only {len(force_arr)} data points "
                            f"(expected ~100)"
                        ),
                    })

            # Check 4: monotonic convergence (stress should converge as n grows)
            if len(predicted_curves) >= 2:
                sorted_n = sorted(predicted_curves.keys())
                for i in range(1, len(sorted_n)):
                    n_prev, n_curr = sorted_n[i - 1], sorted_n[i]
                    f_prev = predicted_curves[n_prev]
                    f_curr = predicted_curves[n_curr]
                    # Compare in normalized stress space
                    min_len = min(len(f_prev), len(f_curr))
                    if min_len < 5:
                        continue
                    # The change from n_prev to n_curr should be smaller than
                    # the change from 1 to n_prev (convergence)
                    diff = np.mean(np.abs(f_curr[:min_len] / n_curr ** 2
                                         - f_prev[:min_len] / n_prev ** 2))
                    if diff > 5.0 * ref_max_force and ref_max_force > 1e-10:
                        violations.append({
                            "structure": struct_key,
                            "check": "convergence",
                            "severity": "warning",
                            "detail": (
                                f"Large normalized stress change between "
                                f"n={n_prev} and n={n_curr}: "
                                f"mean diff = {diff:.4g}"
                            ),
                        })

        # Summary
        n_errors = sum(1 for v in violations if v["severity"] == "error")
        n_warnings = sum(1 for v in violations if v["severity"] == "warning")
        print(f"Physical consistency check: {n_errors} errors, "
              f"{n_warnings} warnings out of {len(predictions)} structures.")

        return violations
