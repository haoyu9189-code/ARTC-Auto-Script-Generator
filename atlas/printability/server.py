"""B1:Printability Checker MCP server(FastMCP STDIO,五工具薄壳)。

启动:python atlas/printability/server.py
注册:claude mcp add atlas-printability -- python atlas/printability/server.py
几何输入二选一:stl_path,或 (topology, slider, radius, n) 经
atlas.geometry.generate_cell 生成。所有响应 = checks.py 信封
{value, threshold, pass, source, status, caveats, applicable, elapsed_s}。
"""
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import trimesh
from fastmcp import FastMCP

from atlas.printability import checks

mcp = FastMCP('atlas-printability')


def _load_mesh(stl_path=None, topology=None, slider=4.0, radius=0.5,
               n=1, cell_size=5.0):
    if stl_path:
        m = trimesh.load(stl_path, force='mesh')
        if not isinstance(m, trimesh.Trimesh):
            raise ValueError(f'{stl_path} 不是单一网格')
        return m
    if topology:
        from atlas.geometry import generate_cell
        return generate_cell(topology, slider=int(slider), radius=radius,
                             n=n, cell_size=cell_size).trimesh
    raise ValueError('必须给 stl_path 或 topology')


@mcp.tool
def validate_mesh(stl_path: str = '', topology: str = '',
                  slider: float = 4, radius: float = 0.5, n: int = 1,
                  process: str = 'MJF') -> dict:
    """双引擎水密/流形验证(trimesh + manifold3d 往返)。"""
    m = _load_mesh(stl_path or None, topology or None, slider, radius, n)
    return checks.validate_mesh(m, process=process)


@mcp.tool
def measure_min_feature(stl_path: str = '', topology: str = '',
                        slider: float = 4, radius: float = 0.5, n: int = 1,
                        process: str = 'MJF') -> dict:
    """embree 射线测厚:最小特征 vs 工艺最小可打印杆径。"""
    m = _load_mesh(stl_path or None, topology or None, slider, radius, n)
    return checks.measure_min_feature(m, process=process)


@mcp.tool
def check_overhangs(stl_path: str = '', topology: str = '',
                    slider: float = 4, radius: float = 0.5, n: int = 1,
                    process: str = 'LPBF') -> dict:
    """面法向悬垂分类(SLS/MJF 自动跳过,applicable=false)。"""
    m = _load_mesh(stl_path or None, topology or None, slider, radius, n)
    return checks.check_overhangs(m, process=process)


@mcp.tool
def check_powder_escape(stl_path: str = '', topology: str = '',
                        slider: float = 4, radius: float = 0.5, n: int = 1,
                        process: str = 'MJF', pitch: float = 0.25,
                        rho_rel: float = -1.0,
                        n_cell_layers: float = -1.0) -> dict:
    """体素 flood-fill 困粉检测 + Raz 排粉深度内插(MJF)。"""
    m = _load_mesh(stl_path or None, topology or None, slider, radius, n)
    return checks.check_powder_escape(
        m, process=process, pitch=pitch,
        rho_rel=None if rho_rel < 0 else rho_rel,
        topology=topology or None,
        n_cell_layers=None if n_cell_layers < 0 else n_cell_layers)


@mcp.tool
def measure_clearance(stl_path_a: str = '', stl_path_b: str = '',
                      topology: str = '', gap_mm: float = 1.2,
                      slider: float = 4, radius: float = 0.5,
                      process: str = 'MJF') -> dict:
    """双体最小间隙(manifold3d.min_gap);单体内部净距归 B3 图级预检。"""
    if stl_path_a and stl_path_b:
        a = _load_mesh(stl_path_a)
        b = _load_mesh(stl_path_b)
    elif topology:
        from atlas.geometry import generate_cell
        cm = generate_cell(topology, slider=int(slider), radius=radius)
        a = cm.trimesh
        b = a.copy()
        b.apply_translation([cm.cell_size + gap_mm + 2 * radius, 0, 0])
    else:
        raise ValueError('必须给两个 stl_path 或 topology+gap_mm')
    return checks.measure_clearance(a, b, process=process)


if __name__ == '__main__':
    mcp.run()  # STDIO transport
