"""P3-1 Step1 单测:FFT 谱均质化对解析解把关(界的正确性最易出假象)。"""
import numpy as np
import pytest

from atlas.mechanics.fft_homog import (analytic_bounds, homogenize_normal,
                                       voxelize_graph)
from atlas.schema.seeds import seed_graph


def _lame(E, nu):
    return E * nu / ((1 + nu) * (1 - 2 * nu)), E / (2 * (1 + nu))


def _backus_laminate(Es, Ev, nu, f):
    """沿 x 叠层两相层合板精确 C11/C12/C22(Backus 1962)。"""
    ls, ms = _lame(Es, nu)
    lv, mv = _lame(Ev, nu)
    ps, pv = ls + 2 * ms, lv + 2 * mv
    inv = f / ps + (1 - f) / pv
    C11 = 1 / inv
    lp = f * ls / ps + (1 - f) * lv / pv
    C12 = C11 * lp
    q = lambda l, m, p: 4 * m * (l + m) / p
    C22 = (f * q(ls, ms, ps) + (1 - f) * q(lv, mv, pv)) + lp ** 2 / inv
    return C11, C12, C22


def test_single_phase_recovers_exactly():
    occ = np.ones((16, 16, 16), bool)
    r = homogenize_normal(occ, E_s=1000.0, nu=0.3, E_void_ratio=1.0,
                          n_iter=50)
    for e in r['E_xyz']:
        assert abs(e - 1000.0) < 1.0      # 精确回收 E_s


@pytest.mark.parametrize('contrast', [0.5, 0.1, 0.01])
def test_laminate_matches_backus(contrast):
    """沿 x 叠层 → C* 必须命中 Backus 精确解(界正确性的金标准)。"""
    N = 48
    occ = np.zeros((N, N, N), bool)
    occ[:N // 2] = True
    r = homogenize_normal(occ, E_s=1000.0, nu=0.3, E_void_ratio=contrast,
                          n_iter=3000, tol=1e-10)
    Cn = np.array(r['Cn'])
    C11, C12, C22 = _backus_laminate(1000.0, 1000.0 * contrast, 0.3, 0.5)
    assert abs(Cn[0, 0] - C11) / C11 < 0.02
    assert abs(Cn[1, 1] - C22) / C22 < 0.02
    assert abs(Cn[0, 1] - C12) / C12 < 0.05


def test_stiffness_never_exceeds_voigt():
    """物理不可逾越:任何方向有效模量 ≤ Voigt 上界(曾因符号 bug 违反)。"""
    N = 40
    occ = np.zeros((N, N, N), bool)
    occ[:N // 2] = True
    r = homogenize_normal(occ, E_s=1000.0, nu=0.3, E_void_ratio=0.1,
                          n_iter=2000, tol=1e-9)
    rho = float(occ.mean())
    voigt_E = rho * 1000.0 + (1 - rho) * 100.0
    for e in r['E_xyz']:
        assert e <= voigt_E * 1.001       # 容 0.1% 数值


def test_voigt_reuss_ordering():
    b = analytic_bounds(0.3, 1700.0, 0.3, E_void_ratio=0.0)
    assert b['reuss_lower'] == 0.0        # solid/void:平凡下界恒 0(故需几何分辨)
    assert b['voigt_upper'] == pytest.approx(0.3 * 1700.0)


def test_voxelize_cubic_periodic_density():
    occ, rho = voxelize_graph(seed_graph('Cubic'), n_vox=32)
    assert 0.0 < rho < 1.0
    # Cubic = 3 正交杆,密度应为中低(非空非满)
    assert occ.shape == (32, 32, 32)
