#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prediction Engine — Predict n×n×n Curves from 1×1×1 Data.

Uses fitted CurveScalingModel coefficients to predict stress-strain (and
force-displacement) curves for arbitrary array dimensions n, given only
the original 1×1×1 simulation results.

Core prediction formula (in normalized stress-strain space):
    σ_nxn(ε) = σ_1x1(ε) - α(ε) * (1 - 1/n) - β(ε) * (1 - 1/n²)

Derivation:
    σ(ε, n) = σ_∞(ε) + α(ε)/n + β(ε)/n²
    σ(ε, 1) = σ_∞(ε) + α(ε) + β(ε)
    => σ(ε, n) = σ(ε, 1) - α(ε)(1 - 1/n) - β(ε)(1 - 1/n²)

@author: ARTC Team
@date: 2026-03
"""

import json
import warnings
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.interpolate import interp1d

from scaling.scaling_analyzer import CurveScalingModel, ScalingAnalyzer
from scaling.selection import classify_topology, _parse_structure_key


class PredictionEngine:
    """Predict n×n×n curves for any structure in the database.

    Parameters
    ----------
    scaling_models : dict
        {topology_class: [CurveScalingModel, ...]} — fitted models grouped
        by topology class.
    feature_data : dict
        The full feature_data.json loaded as a dict.
    """

    # Curve types available in feature_data.json
    CURVE_TYPES = [
        "StaCompre_curve",
        "StaShear_curve",
        "DynaCompre_curve",
        "DynaShear_curve",
    ]

    def __init__(self, scaling_models: Dict[str, List[CurveScalingModel]],
                 feature_data: Dict):
        self.scaling_models = scaling_models
        self.feature_data = feature_data

    # ── Main prediction ──────────────────────────────────────────────────

    def predict_curve(
        self,
        structure_key: str,
        n: int,
        curve_type: str = "StaCompre_curve",
        cell_size: float = 5.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Predict displacement and force for a structure at array size n.

        Parameters
        ----------
        structure_key : str
            The 1x1x1 structure key, e.g. 'BCC_5_0p5_8'.
        n : int
            Target array dimension (n×n×n).
        curve_type : str
            Which curve to predict (default: 'StaCompre_curve').
        cell_size : float
            Single cell side length (mm).

        Returns
        -------
        displacement : np.ndarray
            Predicted displacement in mm (for total n×n×n specimen).
        force : np.ndarray
            Predicted force in N (for total n×n×n specimen).

        Raises
        ------
        KeyError
            If the structure or curve is not found in feature_data.
        ValueError
            If no suitable scaling model is available.
        """
        if n == 1:
            # For n=1, just return the original data
            entry = self.feature_data[structure_key]
            curve = entry[curve_type]
            return (
                np.array(curve["displacement"], dtype=np.float64),
                np.array(curve["force"], dtype=np.float64),
            )

        # Get 1x1x1 curve
        entry = self.feature_data[structure_key]
        curve_1x1 = entry[curve_type]
        disp_1 = np.array(curve_1x1["displacement"], dtype=np.float64)
        force_1 = np.array(curve_1x1["force"], dtype=np.float64)
        density = entry.get("density", 0.0)

        # Normalize to stress-strain
        strain_1, stress_1 = ScalingAnalyzer.normalize_curve(
            disp_1, force_1, n=1, cell_size=cell_size,
        )

        # Find the best scaling model
        cell_type = _parse_structure_key(structure_key)[0]
        model = self._find_scaling_model(cell_type, density)

        if model is None:
            warnings.warn(
                f"No scaling model found for {structure_key} "
                f"(type={cell_type}, density={density:.4f}). "
                f"Returning naive n^2 scaling."
            )
            return self._naive_scaling(disp_1, force_1, n, cell_size)

        # Interpolate 1x1x1 stress to the model's strain grid
        strain_u, stress_1_u = ScalingAnalyzer.interpolate_curve(
            strain_1, stress_1,
            n_points=len(model.strain_points),
            strain_max=float(model.strain_points[-1]),
        )

        # Apply prediction formula:
        # σ_n(ε) = σ_1(ε) - α(ε)*(1 - 1/n) - β(ε)*(1 - 1/n²)
        correction_alpha = model.alpha * (1.0 - 1.0 / n)
        correction_beta = model.beta * (1.0 - 1.0 / n ** 2)
        stress_n = stress_1_u - correction_alpha - correction_beta

        # Ensure non-negative stress
        stress_n = np.maximum(stress_n, 0.0)

        # Convert back to displacement-force for the n×n×n specimen
        L_n = n * cell_size
        A_n = L_n ** 2
        displacement_n = strain_u * L_n
        force_n = stress_n * A_n

        return displacement_n, force_n

    # ── Model lookup ─────────────────────────────────────────────────────

    def _find_scaling_model(
        self, cell_type: str, density: float,
    ) -> Optional[CurveScalingModel]:
        """Find the best matching scaling model for a given cell type and density.

        Strategy:
          1. Look in the same topology class.
          2. Among models in that class, prefer one whose density range covers
             the target density.
          3. If multiple match, interpolate between them.
          4. If none match exactly, use the closest model.

        Parameters
        ----------
        cell_type : str
            Topology name.
        density : float
            Relative density of the structure.

        Returns
        -------
        CurveScalingModel or None
        """
        topo_class = classify_topology(cell_type)
        models = self.scaling_models.get(topo_class, [])

        if not models:
            # Fallback: try all classes
            all_models = []
            for class_models in self.scaling_models.values():
                all_models.extend(class_models)
            if not all_models:
                return None
            models = all_models

        # Filter models whose density range covers the target density
        covering = [
            m for m in models
            if m.density_range[0] <= density <= m.density_range[1]
        ]

        if len(covering) == 1:
            return covering[0]
        elif len(covering) > 1:
            return self._interpolate_between_models(covering, density)

        # No exact coverage — use nearest model by density midpoint
        def _dist(m: CurveScalingModel) -> float:
            mid = (m.density_range[0] + m.density_range[1]) / 2
            return abs(mid - density)

        models_sorted = sorted(models, key=_dist)
        return models_sorted[0]

    def _interpolate_between_models(
        self,
        models: List[CurveScalingModel],
        target_density: float,
    ) -> CurveScalingModel:
        """Interpolate scaling coefficients between multiple models.

        Uses inverse-distance weighting based on density midpoints.

        Parameters
        ----------
        models : list[CurveScalingModel]
            Models to interpolate between (should share strain_points length).
        target_density : float
            Target relative density.

        Returns
        -------
        CurveScalingModel
            Interpolated model.
        """
        if len(models) == 1:
            return models[0]

        # Compute weights (inverse distance to density midpoint)
        midpoints = [(m.density_range[0] + m.density_range[1]) / 2 for m in models]
        distances = [abs(mp - target_density) + 1e-10 for mp in midpoints]
        weights = [1.0 / d for d in distances]
        total = sum(weights)
        weights = [w / total for w in weights]

        # Use the strain grid from the first model
        n_pts = len(models[0].strain_points)

        # Weighted average of coefficients
        sigma_inf = np.zeros(n_pts)
        alpha = np.zeros(n_pts)
        beta = np.zeros(n_pts)
        r2 = np.zeros(n_pts)

        for m, w in zip(models, weights):
            # If models have different grid sizes, interpolate to match
            if len(m.strain_points) != n_pts:
                interp_s = interp1d(
                    m.strain_points, m.sigma_inf,
                    kind="linear", fill_value="extrapolate",
                )
                interp_a = interp1d(
                    m.strain_points, m.alpha,
                    kind="linear", fill_value="extrapolate",
                )
                interp_b = interp1d(
                    m.strain_points, m.beta,
                    kind="linear", fill_value="extrapolate",
                )
                sigma_inf += w * interp_s(models[0].strain_points)
                alpha += w * interp_a(models[0].strain_points)
                beta += w * interp_b(models[0].strain_points)
            else:
                sigma_inf += w * m.sigma_inf
                alpha += w * m.alpha
                beta += w * m.beta
            r2 += w * m.r_squared_per_point

        # Density range: union of all
        rho_min = min(m.density_range[0] for m in models)
        rho_max = max(m.density_range[1] for m in models)

        return CurveScalingModel(
            strain_points=models[0].strain_points.copy(),
            sigma_inf=sigma_inf,
            alpha=alpha,
            beta=beta,
            r_squared_per_point=r2,
            topology_class=models[0].topology_class,
            density_range=(rho_min, rho_max),
            n_values_used=models[0].n_values_used,
            structure_keys=[k for m in models for k in m.structure_keys],
        )

    # ── Naive fallback ───────────────────────────────────────────────────

    @staticmethod
    def _naive_scaling(
        disp_1: np.ndarray,
        force_1: np.ndarray,
        n: int,
        cell_size: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Naive scaling: assume identical stress-strain, scale by geometry.

        For an n×n×n array with the same stress-strain as 1×1×1:
            displacement_n = displacement_1 * n
            force_n = force_1 * n²

        This ignores boundary/interaction effects.
        """
        return disp_1 * n, force_1 * n ** 2

    # ── Batch prediction ─────────────────────────────────────────────────

    def predict_all_structures(
        self,
        n_values: List[int],
        curve_types: Optional[List[str]] = None,
        cell_size: float = 5.0,
    ) -> Dict[str, Dict]:
        """Predict curves for all structures in feature_data at given n values.

        Parameters
        ----------
        n_values : list[int]
            Array dimensions to predict (e.g. [2, 3, 4, 5]).
        curve_types : list[str] or None
            Curve types to predict.  If None, predicts only 'StaCompre_curve'.
        cell_size : float
            Single cell side length.

        Returns
        -------
        dict
            {structure_key: {f'n{n}_{curve_type}': {'displacement': list,
            'force': list, 'predicted': True}, ...}}
        """
        if curve_types is None:
            curve_types = ["StaCompre_curve"]

        predictions = {}
        total = len(self.feature_data)
        done = 0

        for struct_key, entry in self.feature_data.items():
            struct_pred = {}
            for ct in curve_types:
                if ct not in entry:
                    continue
                curve = entry[ct]
                if not curve or "displacement" not in curve or "force" not in curve:
                    continue
                if len(curve["displacement"]) < 5:
                    continue

                for n in n_values:
                    try:
                        disp, force = self.predict_curve(
                            struct_key, n, curve_type=ct, cell_size=cell_size,
                        )
                        pred_key = f"n{n}_{ct}"
                        struct_pred[pred_key] = {
                            "displacement": disp.tolist(),
                            "force": force.tolist(),
                            "predicted": True,
                            "array_dimension": n,
                        }
                    except Exception as e:
                        warnings.warn(
                            f"Failed to predict {struct_key} n={n} {ct}: {e}"
                        )

            if struct_pred:
                predictions[struct_key] = struct_pred

            done += 1
            if done % 100 == 0:
                print(f"  Predicted {done}/{total} structures...")

        print(f"  Predicted {done}/{total} structures (complete).")
        return predictions
