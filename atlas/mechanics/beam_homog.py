"""P2-1a:Timoshenko 空间梁周期均质化(Tier-B 裁判核心)。

数学:u(x) = ε̄·x + ũ(x),ũ 周期 → ũ 的自由度恰好 = 商图节点自由度
(同一商图节点的所有周期像共享 ũ —— 周期性内建于商图表示,无需
主从约束)。affine 部分对每条边(含 shift 像)给出已知端位移
d_aff = [ε̄·x_i, 0, ε̄·x_j, 0],组装为载荷 f = −Σ K_e d_aff;
解 K ũ = f(固定一个节点平动消刚体),能量法提 6×6 等效刚度:
U(ε̄) = ½ ε̄ᵀC ε̄ V → 6 个单位应变 + 15 个对组合,21 次小规模求解。

Timoshenko 剪切:φ = 12EI/(G A_s L²),A_s = κA(圆截面 κ=0.9)——
低 l/d 时剪切变形不可忽略,这正是自家库所在区间。

诚实边界:线弹性;节点刚化未修正(P2-1c 用自家 DB 标定);
l/d<5 输出 certified=False(Zhong 2023 失效区,红线拒绝认证)。
"""
import numpy as np

E_S = 1700.0
NU = 0.3
G_S = E_S / (2 * (1 + NU))
KAPPA = 0.9  # 圆截面剪切修正

# Voigt 顺序:e11,e22,e33,g23,g13,g12(工程剪应变)
_VOIGT = [(0, 0), (1, 1), (2, 2), (1, 2), (0, 2), (0, 1)]


def _strain_tensor(voigt):
    eps = np.zeros((3, 3))
    for k, (i, j) in enumerate(_VOIGT):
        v = voigt[k] if i == j else voigt[k] / 2
        eps[i, j] = eps[j, i] = v
    return eps


def _beam_k_timoshenko(E, G, A, I, J, L, kappa=KAPPA):
    """12×12 Timoshenko 空间梁局部刚度(圆截面 Iy=Iz=I)。"""
    phi = 12 * E * I / (G * kappa * A * L ** 2)
    k = np.zeros((12, 12))
    a_ = E * A / L
    t = G * J / L
    b = 12 * E * I / (L ** 3 * (1 + phi))
    c = 6 * E * I / (L ** 2 * (1 + phi))
    d = (4 + phi) * E * I / (L * (1 + phi))
    e = (2 - phi) * E * I / (L * (1 + phi))
    k[0, 0] = k[6, 6] = a_
    k[0, 6] = k[6, 0] = -a_
    k[3, 3] = k[9, 9] = t
    k[3, 9] = k[9, 3] = -t
    # v–rz 平面
    k[1, 1] = k[7, 7] = b
    k[1, 7] = k[7, 1] = -b
    k[1, 5] = k[5, 1] = k[1, 11] = k[11, 1] = c
    k[5, 7] = k[7, 5] = k[7, 11] = k[11, 7] = -c
    k[5, 5] = k[11, 11] = d
    k[5, 11] = k[11, 5] = e
    # w–ry 平面(符号镜像)
    k[2, 2] = k[8, 8] = b
    k[2, 8] = k[8, 2] = -b
    k[2, 4] = k[4, 2] = k[2, 10] = k[10, 2] = -c
    k[4, 8] = k[8, 4] = k[8, 10] = k[10, 8] = c
    k[4, 4] = k[10, 10] = d
    k[4, 10] = k[10, 4] = e
    return k


def _rotation12(p1, p2):
    ex = p2 - p1
    L = float(np.linalg.norm(ex))
    ex = ex / L
    ref = np.array([0.0, 0.0, 1.0])
    if abs(ex @ ref) > 0.999:
        ref = np.array([0.0, 1.0, 0.0])
    ey = np.cross(ref, ex)
    ey /= np.linalg.norm(ey)
    ez = np.cross(ex, ey)
    R = np.vstack([ex, ey, ez])
    T = np.zeros((12, 12))
    for blk in range(4):
        T[3 * blk:3 * blk + 3, 3 * blk:3 * blk + 3] = R
    return T, L


def homogenize(doc, E=E_S, G=G_S, nu=NU):
    """商图 → 6×6 等效刚度 C*(MPa)与工程常数。返回信封 dict。"""
    a = float(doc['cell']['size_mm'])
    V = a ** 3
    pos = {nd['id']: np.asarray(nd['frac'], float) * a
           for nd in doc['nodes']}
    ids = list(pos)
    idx = {n: i for i, n in enumerate(ids)}
    N = len(ids)
    ndof = 6 * N
    default_r = float(doc['default_radius_mm'])

    elems = []
    K = np.zeros((ndof, ndof))
    lds = []
    for e in doc['edges']:
        r = float(e.get('radius_mm', default_r))
        x1 = pos[e['n1']]
        x2 = pos[e['n2']] + np.asarray(e['shift'], float) * a
        A = np.pi * r ** 2
        I = np.pi * r ** 4 / 4
        J = np.pi * r ** 4 / 2
        T, L = _rotation12(x1, x2)
        kl = _beam_k_timoshenko(E, G, A, I, J, L)
        kg = T.T @ kl @ T
        i, j = idx[e['n1']], idx[e['n2']]
        dofs = np.r_[6 * i:6 * i + 6, 6 * j:6 * j + 6]
        K[np.ix_(dofs, dofs)] += kg
        elems.append((i, j, x1, x2, kg, dofs))
        lds.append(L / (2 * r))

    # 固定节点 0 的平动(消 3 个刚体平动;周期场无刚体转动模式)
    fixed = [0, 1, 2]
    free = np.setdiff1d(np.arange(ndof), fixed)
    Kff = K[np.ix_(free, free)]

    def solve_energy(voigt):
        eps = _strain_tensor(voigt)
        f = np.zeros(ndof)
        d_affs = []
        for i, j, x1, x2, kg, dofs in elems:
            d_aff = np.zeros(12)
            d_aff[0:3] = eps @ x1
            d_aff[6:9] = eps @ x2
            f[dofs] -= kg @ d_aff
            d_affs.append(d_aff)
        u = np.zeros(ndof)
        u[free] = np.linalg.solve(Kff, f[free])
        U = 0.0
        for (i, j, x1, x2, kg, dofs), d_aff in zip(elems, d_affs):
            d = d_aff + u[dofs]
            U += 0.5 * d @ kg @ d
        return U

    base = np.eye(6)
    U1 = [solve_energy(base[i]) for i in range(6)]
    C = np.zeros((6, 6))
    for i in range(6):
        C[i, i] = 2 * U1[i] / V
    for i in range(6):
        for j in range(i + 1, 6):
            Uij = solve_energy(base[i] + base[j])
            C[i, j] = C[j, i] = (Uij - U1[i] - U1[j]) / V

    # 工程常数(柔度)
    eigs = np.linalg.eigvalsh((C + C.T) / 2)
    spd = bool(eigs.min() > -1e-8 * max(eigs.max(), 1.0))
    consts = {}
    if spd and eigs.min() > 1e-12:
        S = np.linalg.inv(C)
        consts = {'E_x': 1 / S[0, 0], 'E_y': 1 / S[1, 1],
                  'E_z': 1 / S[2, 2], 'G_yz': 1 / S[3, 3],
                  'G_xz': 1 / S[4, 4], 'G_xy': 1 / S[5, 5],
                  'nu_xy': -S[0, 1] / S[0, 0],
                  'nu_xz': -S[0, 2] / S[0, 0]}
        consts = {k: round(float(v), 6) for k, v in consts.items()}
    ld_med = float(np.median(lds)) if lds else 0.0
    certified = spd and ld_med >= 5.0
    caveats = ['Timoshenko 线弹性,节点刚化未修正(P2-1c 标定),'
               'screening only']
    if ld_med < 5.0:
        caveats.append(f'中位 l/d={ld_med:.2f} < 5:梁理论失效区'
                       '(Zhong 2023),拒绝认证(certified=False)')
    return {'C': C.tolist(), 'constants': consts, 'spd': spd,
            'ld_median': round(ld_med, 3), 'certified': certified,
            'n_nodes': N, 'n_edges': len(elems),
            'source': 'atlas.mechanics.beam_homog(Timoshenko PBC '
                      '均质化,能量法 6+15 解)',
            'status': 'computed' if spd else 'out_of_domain',
            'caveats': caveats}
