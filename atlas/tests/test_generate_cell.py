"""A1 单测:generate_cell API 与 24 拓扑水密回归。

水密双轨判据(raw 流形 + welded 焊接后)见 atlas/geometry/cells.py 模块注释。
"""
import numpy as np
import pytest
import manifold3d
import trimesh as trimesh_pkg

from atlas.geometry import generate_cell, list_topologies, CellMesh

ALL_TOPOLOGIES = list_topologies()


def test_topology_count():
    assert len(ALL_TOPOLOGIES) == 24


@pytest.mark.parametrize('topology', ALL_TOPOLOGIES)
def test_all_24_watertight(topology):
    cm = generate_cell(topology, slider=4, radius=0.5)
    assert cm.manifold.status() == manifold3d.Error.NoError
    assert cm.trimesh_raw.is_watertight, f'{topology}: raw 非水密'
    assert cm.trimesh.is_watertight, f'{topology}: 焊接后非水密'
    assert cm.volume > 0


@pytest.mark.parametrize('segments', [16, 23, 24, 32])
def test_cuboctahedron_z_regression(segments):
    """历史失败用例:球-柱整圆相切 × F1/F2 悬挑暴露,采样相位敏感。"""
    cm = generate_cell('Cuboctahedron_Z', slider=4, radius=0.5,
                       segments=segments)
    assert cm.is_watertight, f'Cuboctahedron_Z @segments={segments} 非水密'


def test_determinism():
    a = generate_cell('BCC', slider=4, radius=0.5)
    b = generate_cell('BCC', slider=4, radius=0.5)
    va, fa = a.trimesh_raw.vertices, a.trimesh_raw.faces
    vb, fb = b.trimesh_raw.vertices, b.trimesh_raw.faces
    assert va.shape == vb.shape and fa.shape == fb.shape
    assert np.allclose(va, vb) and (fa == fb).all()
    assert abs(a.volume - b.volume) < 1e-12


def test_n_array():
    single = generate_cell('BCC', slider=4, radius=0.5, n=1)
    block = generate_cell('BCC', slider=4, radius=0.5, n=2)
    assert block.is_watertight
    # 2×2×2 = 8 胞,共享边界节点有重叠,体积应在 (4×, 8×] 单胞之间
    assert 4 * single.volume < block.volume <= 8 * single.volume + 1e-6
    # 居中:包围盒应关于原点对称
    lo, hi = block.trimesh.bounds
    assert np.allclose(lo, -hi, atol=1e-6)


def test_return_types():
    assert isinstance(generate_cell('Cubic'), CellMesh)
    assert isinstance(generate_cell('Cubic', return_type='manifold'),
                      manifold3d.Manifold)
    assert isinstance(generate_cell('Cubic', return_type='trimesh'),
                      trimesh_pkg.Trimesh)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        generate_cell('NoSuchTopology')
    with pytest.raises(ValueError):
        generate_cell('Cubic', n=0)
    with pytest.raises(ValueError):
        generate_cell('Cubic', return_type='stl')


def test_sphere_ratio_far_from_one_no_perturbation():
    """ratio 明显偏离 1 时不应触发扰动(行为可预期)。"""
    cm = generate_cell('Cubic', sphere_ratio=1.2)
    assert cm.is_watertight
