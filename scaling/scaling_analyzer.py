#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scaling Coefficient Fitting for Lattice Structures.

Given stress-strain curves at multiple array dimensions n, fits the model:

    σ(ε_j, n) = σ_∞(ε_j) + α(ε_j)/n + β(ε_j)/n²

where:
    σ_∞  = bulk (infinite-array) stress
    α    = first-order finite-size correction
    β    = second-order finite-size correction

The least-squares system at each strain point j:
    A x = b
where A[i,:] = [1, 1/n_i, 1/n_i²], b[i] = σ_j(n_i), x = [σ_∞_j, α_j, β_j].

@author: ARTC Team
@date: 2026-03
"""

import json
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.interpolate import interp1d


# ── Data class for fitted scaling model ──────────────────────────────────────

@dataclass
class CurveScalingModel:
    """Stores the fitted scaling coefficients for one set of curves.

    Attributes
    ----------
    strain_points : np.ndarray
        M uniform strain values at which the model is defined.
    sigma_inf : np.ndarray
        M bulk stress values (σ_∞).
    alpha : np.ndarray
        M first-order correction coefficients.
    beta : np.ndarray
        M second-order correction coefficients.
    r_squared_per_point : np.ndarray
        M R² values measuring fit quality at each strain point.
    topology_class : str
        'stretch', 'bending', or 'hybrid'.
    density_range : tuple
        (rho_min, rho_max) density range this model covers.
    n_values_used : list
        Array dimensions used for fitting (e.g. [1, 3]).
    structure_keys : list
        Structure keys used to build this model.
    """
    strain_points: np.ndarray
    sigma_inf: np.ndarray
    alpha: np.ndarray
    beta: np.ndarray
    r_squared_per_point: np.ndarray
    topology_class: str = "unknown"
    density_range: tuple = (0.0, 1.0)
    n_values_used: list = field(default_factory=list)
    structure_keys: list = field(default_factory=list)


# ── Main analyzer class ──────────────────────────────────────────────────────

class ScalingAnalyzer:
    """Fit scaling coefficients from multi-n simulation data.

    Parameters
    ----------
    feature_data_path : str
        Path to feature_data.json (1x1x1 data for all 999 structures).
    """

    # Default cell size (mm) for the current database
    DEFAULT_CELL_SIZE = 5.0
    # Default number of interpolation points
    DEFAULT_N_POINTS = 100

    def __init__(self, feature_data_path: str):
        with open(feature_data_path, "r", encoding="utf-8") as f:
            self.feature_data: Dict = json.load(f)

    # ── Load curves for multiple n ───────────────────────────────────────

    def load_multi_n_curves(
        self,
        structure_key: str,
        data_sources: Dict[int, object],
    ) -> Dict[int, Tuple[np.ndarray, np.ndarray]]:
        """Load displacement-force curves for multiple array dimensions.

        Parameters
        ----------
        structure_key : str
            Base structure key, e.g. 'BCC_5_0p5_8'.
        data_sources : dict
            Maps n -> data.  Each value can be:
              - tuple/list of (displacement_array, force_array)
              - dict with keys 'displacement' and 'force'
              - str file path to a force_displacement CSV

        Returns
        -------
        dict
            {n: (displacement_array, force_array)} for each valid n.
        """
        curves = {}

        # n=1 from feature_data if not explicitly provided
        if 1 not in data_sources:
            entry = self.feature_data.get(structure_key, {})
            curve = entry.get("StaCompre_curve")
            if curve and "displacement" in curve and "force" in curve:
                d = np.array(curve["displacement"], dtype=np.float64)
                f = np.array(curve["force"], dtype=np.float64)
                if len(d) > 5:
                    curves[1] = (d, f)

        for n, src in data_sources.items():
            if isinstance(src, str):
                # CSV file path
                d, f = self._load_csv(src)
                if d is not None:
                    curves[n] = (d, f)
            elif isinstance(src, dict):
                d = np.array(src["displacement"], dtype=np.float64)
                f = np.array(src["force"], dtype=np.float64)
                curves[n] = (d, f)
            elif isinstance(src, (tuple, list)) and len(src) == 2:
                d = np.asarray(src[0], dtype=np.float64)
                f = np.asarray(src[1], dtype=np.float64)
                curves[n] = (d, f)

        return curves

    @staticmethod
    def _load_csv(filepath: str) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Load displacement and force from a force_displacement CSV."""
        import csv
        displacement, force = [], []
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    displacement.append(float(row["Abs_Displacement_mm"]))
                    force.append(float(row["Abs_Force_N"]))
        except Exception:
            return None, None
        if not displacement:
            return None, None
        return np.array(displacement), np.array(force)

    # ── Normalization ────────────────────────────────────────────────────

    @staticmethod
    def normalize_curve(
        displacement: np.ndarray,
        force: np.ndarray,
        n: int,
        cell_size: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Convert force-displacement to engineering stress-strain for n×n×n.

        The n×n×n array has total side length L = n * cell_size.

        Parameters
        ----------
        displacement : np.ndarray
            Displacement values (mm).
        force : np.ndarray
            Force values (N).
        n : int
            Array dimension.
        cell_size : float
            Single cell side length (mm).

        Returns
        -------
        strain : np.ndarray
            Engineering strain = displacement / (n * cell_size).
        stress : np.ndarray
            Engineering stress = force / (n * cell_size)^2.
        """
        L = n * cell_size
        A = L ** 2
        strain = displacement / L
        stress = force / A
        return strain, stress

    # ── Interpolation ────────────────────────────────────────────────────

    @staticmethod
    def interpolate_curve(
        strain: np.ndarray,
        stress: np.ndarray,
        n_points: int = 100,
        strain_max: Optional[float] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Interpolate a stress-strain curve to uniform strain points.

        Parameters
        ----------
        strain : np.ndarray
            Strain values (must be non-decreasing).
        stress : np.ndarray
            Stress values.
        n_points : int
            Number of output points.
        strain_max : float or None
            Maximum strain for interpolation.  If None, uses max of input.

        Returns
        -------
        strain_uniform : np.ndarray
        stress_uniform : np.ndarray
        """
        # Remove duplicate strain values (keep first occurrence)
        _, unique_idx = np.unique(strain, return_index=True)
        unique_idx = np.sort(unique_idx)
        strain_clean = strain[unique_idx]
        stress_clean = stress[unique_idx]

        if len(strain_clean) < 2:
            return np.zeros(n_points), np.zeros(n_points)

        # Handle NaN / Inf
        valid = np.isfinite(strain_clean) & np.isfinite(stress_clean)
        strain_clean = strain_clean[valid]
        stress_clean = stress_clean[valid]

        if len(strain_clean) < 2:
            return np.zeros(n_points), np.zeros(n_points)

        s_min = float(strain_clean[0])
        s_max = float(strain_clean[-1]) if strain_max is None else strain_max
        s_max = min(s_max, float(strain_clean[-1]))

        if s_max <= s_min:
            return np.zeros(n_points), np.zeros(n_points)

        interp_fn = interp1d(
            strain_clean, stress_clean,
            kind="linear",
            bounds_error=False,
            fill_value=(float(stress_clean[0]), float(stress_clean[-1])),
        )
        strain_uniform = np.linspace(s_min, s_max, n_points)
        stress_uniform = interp_fn(strain_uniform)
        return strain_uniform, stress_uniform

    # ── Core fitting ─────────────────────────────────────────────────────

    def fit_scaling_model(
        self,
        curves_by_n: Dict[int, Tuple[np.ndarray, np.ndarray]],
        cell_size: float = 5.0,
        n_points: int = 100,
        topology_class: str = "unknown",
        density_range: Tuple[float, float] = (0.0, 1.0),
        structure_keys: Optional[List[str]] = None,
    ) -> CurveScalingModel:
        """Fit the scaling model σ(ε,n) = σ_∞(ε) + α(ε)/n + β(ε)/n².

        Parameters
        ----------
        curves_by_n : dict
            {n: (displacement, force)} for each available array dimension.
        cell_size : float
            Single cell side length (mm).
        n_points : int
            Number of interpolation points.
        topology_class : str
            Topology class label.
        density_range : tuple
            (min_density, max_density).
        structure_keys : list[str] or None
            Keys of structures used.

        Returns
        -------
        CurveScalingModel
            Fitted model with coefficients at each strain point.
        """
        n_values = sorted(curves_by_n.keys())

        # Normalize all curves to stress-strain
        normalized = {}
        for n in n_values:
            disp, force = curves_by_n[n]
            strain, stress = self.normalize_curve(disp, force, n, cell_size)
            normalized[n] = (strain, stress)

        # Find common strain range (intersection of all curves)
        strain_min = max(float(s[0]) for s, _ in normalized.values())
        strain_max = min(float(s[-1]) for s, _ in normalized.values())

        if strain_max <= strain_min:
            warnings.warn(
                f"No overlapping strain range for n={n_values}. "
                f"Using n=1 range as fallback."
            )
            if 1 in normalized:
                strain_min = float(normalized[1][0][0])
                strain_max = float(normalized[1][0][-1])
            else:
                first_n = n_values[0]
                strain_min = float(normalized[first_n][0][0])
                strain_max = float(normalized[first_n][0][-1])

        # Interpolate all curves to common uniform strain grid
        interp_curves = {}
        for n in n_values:
            strain_u, stress_u = self.interpolate_curve(
                normalized[n][0], normalized[n][1],
                n_points=n_points, strain_max=strain_max,
            )
            interp_curves[n] = stress_u

        strain_grid = np.linspace(strain_min, strain_max, n_points)

        # Build design matrix A and solve at each strain point
        # A[i,:] = [1, 1/n_i, 1/n_i^2]
        n_arr = np.array(n_values, dtype=np.float64)
        A = np.column_stack([
            np.ones(len(n_values)),
            1.0 / n_arr,
            1.0 / n_arr ** 2,
        ])

        sigma_inf = np.zeros(n_points)
        alpha = np.zeros(n_points)
        beta = np.zeros(n_points)
        r_squared = np.zeros(n_points)

        for j in range(n_points):
            b = np.array([interp_curves[n][j] for n in n_values])

            if len(n_values) >= 3:
                # Full least-squares solve
                x, residuals, rank, sv = np.linalg.lstsq(A, b, rcond=None)
                sigma_inf[j] = x[0]
                alpha[j] = x[1]
                beta[j] = x[2]
            elif len(n_values) == 2:
                # Under-determined: set β=0, solve for σ_∞ and α
                A_reduced = A[:, :2]
                x, _, _, _ = np.linalg.lstsq(A_reduced, b, rcond=None)
                sigma_inf[j] = x[0]
                alpha[j] = x[1]
                beta[j] = 0.0
            else:
                # Single n value: cannot fit scaling, just store the value
                sigma_inf[j] = b[0]
                alpha[j] = 0.0
                beta[j] = 0.0

            # Compute R²
            b_pred = A @ np.array([sigma_inf[j], alpha[j], beta[j]])
            ss_res = np.sum((b - b_pred) ** 2)
            ss_tot = np.sum((b - np.mean(b)) ** 2)
            r_squared[j] = 1.0 - ss_res / max(ss_tot, 1e-30)

        return CurveScalingModel(
            strain_points=strain_grid,
            sigma_inf=sigma_inf,
            alpha=alpha,
            beta=beta,
            r_squared_per_point=r_squared,
            topology_class=topology_class,
            density_range=density_range,
            n_values_used=n_values,
            structure_keys=structure_keys or [],
        )

    # ── Fit quality evaluation ───────────────────────────────────────────

    def evaluate_fit_quality(
        self,
        model: CurveScalingModel,
        actual_curves: Dict[int, Tuple[np.ndarray, np.ndarray]],
        cell_size: float = 5.0,
    ) -> Dict:
        """Evaluate the scaling model against actual simulation curves.

        Parameters
        ----------
        model : CurveScalingModel
            The fitted scaling model.
        actual_curves : dict
            {n: (displacement, force)} for validation curves.
        cell_size : float
            Single cell side length.

        Returns
        -------
        dict
            Per-n and per-strain-region metrics:
            {
                'overall_r2': float,
                'overall_rmse': float,
                'overall_mape': float,
                'per_n': {n: {'r2': ..., 'rmse': ..., 'mape': ...}},
                'per_region': {
                    'elastic': {...},
                    'plateau': {...},
                    'densification': {...},
                }
            }
        """
        strain_pts = model.strain_points
        n_pts = len(strain_pts)

        # Define strain regions (approximate)
        elastic_mask = strain_pts < 0.05
        densification_mask = strain_pts > 0.5
        plateau_mask = ~elastic_mask & ~densification_mask

        all_errors = []
        all_actual = []
        per_n = {}

        for n, (disp, force) in actual_curves.items():
            strain, stress = self.normalize_curve(disp, force, n, cell_size)
            _, stress_interp = self.interpolate_curve(
                strain, stress, n_points=n_pts, strain_max=float(strain_pts[-1])
            )

            # Predict
            predicted = (
                model.sigma_inf
                + model.alpha / n
                + model.beta / n ** 2
            )

            error = stress_interp - predicted
            all_errors.append(error)
            all_actual.append(stress_interp)

            # Per-n metrics
            per_n[n] = self._compute_metrics(stress_interp, predicted)

        if not all_errors:
            return {"overall_r2": 0, "overall_rmse": 0, "overall_mape": 0,
                    "per_n": {}, "per_region": {}}

        all_errors = np.concatenate(all_errors)
        all_actual = np.concatenate(all_actual)
        all_predicted = all_actual - all_errors

        # Per-region metrics (using first validation curve for regions)
        per_region = {}
        for region_name, mask in [
            ("elastic", elastic_mask),
            ("plateau", plateau_mask),
            ("densification", densification_mask),
        ]:
            if not np.any(mask):
                per_region[region_name] = {"r2": np.nan, "rmse": np.nan, "mape": np.nan}
                continue
            # Collect errors for this region across all n values
            region_actual = []
            region_pred = []
            for n, (disp, force) in actual_curves.items():
                strain, stress = self.normalize_curve(disp, force, n, cell_size)
                _, stress_interp = self.interpolate_curve(
                    strain, stress, n_points=n_pts,
                    strain_max=float(strain_pts[-1]),
                )
                predicted = model.sigma_inf + model.alpha / n + model.beta / n ** 2
                region_actual.append(stress_interp[mask])
                region_pred.append(predicted[mask])
            region_actual = np.concatenate(region_actual)
            region_pred = np.concatenate(region_pred)
            per_region[region_name] = self._compute_metrics(region_actual, region_pred)

        overall = self._compute_metrics(all_actual, all_predicted)
        return {
            "overall_r2": overall["r2"],
            "overall_rmse": overall["rmse"],
            "overall_mape": overall["mape"],
            "per_n": per_n,
            "per_region": per_region,
        }

    @staticmethod
    def _compute_metrics(actual: np.ndarray, predicted: np.ndarray) -> Dict:
        """Compute R², RMSE, MAPE between actual and predicted arrays."""
        residuals = actual - predicted
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((actual - np.mean(actual)) ** 2)
        r2 = 1.0 - ss_res / max(ss_tot, 1e-30)

        rmse = float(np.sqrt(np.mean(residuals ** 2)))

        # MAPE — avoid division by zero
        denom = np.abs(actual)
        valid = denom > 1e-12
        if np.any(valid):
            mape = float(np.mean(np.abs(residuals[valid]) / denom[valid]) * 100)
        else:
            mape = 0.0

        return {"r2": float(r2), "rmse": rmse, "mape": mape}
