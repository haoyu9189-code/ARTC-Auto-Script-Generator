"""P2-1 预演:3D 空间梁直接刚度法(Euler-Bernoulli 圆截面)。

用途:压缩工况下的变形场可视化 + 等效模量 E* 提取 + 每杆轴力/弯曲
能量占比(拉压主导 vs 弯曲主导的逐杆证据)+ 生成式搜索的快速裁判。

诚实边界(报告必须带):线弹性小变形;Euler-Bernoulli 梁理想化,
未含节点体积刚化修正 —— 自家库 l/d≈4–7 处于梁理论失效区边缘
(Zhong 2023:l/d<5 偏差可达 300%),数值仅 screening only,
P2-1 完整版将用自家 DB 标定节点刚化修正。
"""
import numpy as np

# PA12 基准材性(.claude/skills/atlas/references/thresholds,vendor)
E_S = 1700.0   # MPa
NU = 0.3
G_S = E_S / (2 * (1 + NU))


def block_from_graph(doc, n=2, tol=1e-6):
    """商图 → n³ 开边界块(节点坐标 mm + 单元 (i, j, r))。

    仅保留两端都落在块盒内的边实例(悬挑出界的杆不参与承载路径,
    对压缩工况 E* 影响为保守略偏软)。"""
    a = float(doc['cell']['size_mm'])
    pos = {nd['id']: np.asarray(nd['frac'], float) for nd in doc['nodes']}
    default_r = float(doc['default_radius_mm'])

    key2idx, coords = {}, []

    def node_at(p_mm):
        key = tuple(np.round(p_mm, 5))
        if key not in key2idx:
            key2idx[key] = len(coords)
            coords.append(np.asarray(key, float))
        return key2idx[key]

    elements = []
    seen = set()
    lo, hi = -tol, n * a + tol
    for e in doc['edges']:
        r = float(e.get('radius_mm', default_r))
        base1 = pos[e['n1']]
        base2 = pos[e['n2']] + np.asarray(e['shift'], float)
        for cx in range(-1, n + 1):
            for cy in range(-1, n + 1):
                for cz in range(-1, n + 1):
                    c = np.array([cx, cy, cz], float)
                    p1 = (base1 + c) * a
                    p2 = (base2 + c) * a
                    if not (lo <= min(p1.min(), p2.min())
                            and max(p1.max(), p2.max()) <= hi):
                        continue
                    k = tuple(sorted((tuple(np.round(p1, 5)),
                                      tuple(np.round(p2, 5)))))
                    if k in seen:
                        continue
                    seen.add(k)
                    elements.append((node_at(p1), node_at(p2), r))
    return np.array(coords), elements


def _beam_k_local(E, G, A, Iy, Iz, J, L):
    """12×12 Euler-Bernoulli 空间梁局部刚度(标准形)。"""
    k = np.zeros((12, 12))
    a_ = E * A / L
    t = G * J / L
    bz = 12 * E * Iz / L ** 3
    by = 12 * E * Iy / L ** 3
    cz = 6 * E * Iz / L ** 2
    cy = 6 * E * Iy / L ** 2
    dz = 4 * E * Iz / L
    dy = 4 * E * Iy / L
    ez = 2 * E * Iz / L
    ey = 2 * E * Iy / L
    idx = lambda m: m  # 可读性
    # 轴向 u
    k[0, 0] = k[6, 6] = a_
    k[0, 6] = k[6, 0] = -a_
    # 扭转 rx
    k[3, 3] = k[9, 9] = t
    k[3, 9] = k[9, 3] = -t
    # 弯曲 v–rz
    k[1, 1] = k[7, 7] = bz
    k[1, 7] = k[7, 1] = -bz
    k[1, 5] = k[5, 1] = k[1, 11] = k[11, 1] = cz
    k[5, 7] = k[7, 5] = k[7, 11] = k[11, 7] = -cz
    k[5, 5] = k[11, 11] = dz
    k[5, 11] = k[11, 5] = ez
    # 弯曲 w–ry(符号镜像)
    k[2, 2] = k[8, 8] = by
    k[2, 8] = k[8, 2] = -by
    k[2, 4] = k[4, 2] = k[2, 10] = k[10, 2] = -cy
    k[4, 8] = k[8, 4] = k[8, 10] = k[10, 8] = cy
    k[4, 4] = k[10, 10] = dy
    k[4, 10] = k[10, 4] = ey
    return k


def _rotation(p1, p2):
    ex = p2 - p1
    L = np.linalg.norm(ex)
    ex = ex / L
    ref = np.array([0.0, 0.0, 1.0])
    if abs(ex @ ref) > 0.999:
        ref = np.array([0.0, 1.0, 0.0])
    ey = np.cross(ref, ex)
    ey /= np.linalg.norm(ey)
    ez = np.cross(ex, ey)
    R = np.vstack([ex, ey, ez])
    T = np.zeros((12, 12))
    for b in range(4):
        T[3 * b:3 * b + 3, 3 * b:3 * b + 3] = R
    return T, L


def solve_compression(doc, n=2, strain=0.05, E=E_S, G=G_S):
    """n³ 块压缩(底面全约束,顶面压 uz=-strain·H,横向锁定)。

    返回 dict:nodes/elements/u(位移场)/per-element 轴向应力与弯曲
    能量占比/E_star(等效模量)/总反力。"""
    coords, elements = block_from_graph(doc, n=n)
    N = len(coords)
    ndof = 6 * N
    lo_b = coords.min(axis=0)
    hi_b = coords.max(axis=0)

    def share_weight(p1, p2):
        """开块周期修正:元素整体躺在 k 个外边界面上 → 被 2^k 个相邻
        块共享,刚度权重 1/2^k(角柱 1/4、面内杆 1/2;实测锚点
        竖柱阵不加权时 E* 高估恰为 9/4)。"""
        k = 0
        for ax in range(3):
            for b in (lo_b[ax], hi_b[ax]):
                if abs(p1[ax] - b) < 1e-6 and abs(p2[ax] - b) < 1e-6:
                    k += 1
        return 0.5 ** k

    K = np.zeros((ndof, ndof))
    elem_data = []
    for i, j, r in elements:
        A = np.pi * r ** 2
        I = np.pi * r ** 4 / 4
        J = np.pi * r ** 4 / 2
        T, L = _rotation(coords[i], coords[j])
        w = share_weight(coords[i], coords[j])
        kl = _beam_k_local(E, G, A, I, I, J, L)
        kg = w * (T.T @ kl @ T)
        dofs = np.r_[6 * i:6 * i + 6, 6 * j:6 * j + 6]
        K[np.ix_(dofs, dofs)] += kg
        elem_data.append((i, j, r, T, kl, L, A))

    z = coords[:, 2]
    zmin, zmax = z.min(), z.max()
    H = zmax - zmin
    bottom = np.where(z < zmin + 1e-6)[0]
    top = np.where(z > zmax - 1e-6)[0]
    delta = strain * H

    u = np.zeros(ndof)
    fixed = {}
    for nd in bottom:
        for d in range(6):
            fixed[6 * nd + d] = 0.0
    for nd in top:
        fixed[6 * nd + 0] = 0.0
        fixed[6 * nd + 1] = 0.0
        fixed[6 * nd + 2] = -delta
    known = np.array(sorted(fixed))
    vals = np.array([fixed[k] for k in known])
    free = np.setdiff1d(np.arange(ndof), known)
    # 分块求解 K_ff u_f = −K_fk u_k
    u[known] = vals
    rhs = -K[np.ix_(free, known)] @ vals
    u[free] = np.linalg.solve(K[np.ix_(free, free)], rhs)

    # 顶面反力 → 等效模量
    F = K @ u
    Fz_top = float(sum(F[6 * nd + 2] for nd in top))
    area = (coords[:, 0].max() - coords[:, 0].min()) * \
           (coords[:, 1].max() - coords[:, 1].min())
    sigma = -Fz_top / area
    E_star = sigma / strain

    per_elem = []
    for i, j, r, T, kl, L, A in elem_data:
        d_g = np.r_[u[6 * i:6 * i + 6], u[6 * j:6 * j + 6]]
        d_l = T @ d_g
        f_l = kl @ d_l
        axial_force = f_l[6]                      # 轴力(j 端)
        axial_stress = axial_force / A            # MPa,+拉 −压
        U_total = 0.5 * d_l @ f_l
        d_ax = d_l.copy()
        d_ax[[1, 2, 4, 5, 7, 8, 10, 11]] = 0      # 只留轴向+扭转
        U_ax = 0.5 * d_ax @ kl @ d_ax
        bend_frac = float(1 - U_ax / U_total) if U_total > 1e-12 else 0.0
        per_elem.append({'i': i, 'j': j, 'r': r, 'L': L,
                         'axial_stress': float(axial_stress),
                         'bend_frac': max(0.0, min(1.0, bend_frac))})

    return {'coords': coords, 'elements': elements, 'u': u,
            'per_elem': per_elem, 'E_star': float(E_star),
            'sigma': float(sigma), 'strain': strain, 'H': float(H),
            'n_nodes': N, 'n_elems': len(elements),
            'caveat': 'Euler-Bernoulli 线弹性,无节点刚化修正,'
                      'screening only(P2-1 完整版做 DB 标定)'}
