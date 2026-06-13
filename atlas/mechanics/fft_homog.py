"""P3-1(Step 1 原型):FFT 谱方法周期均质化 —— Tier-C 裁判候选。

目的(回应"保证下界"评估):测试 FFT 体素均质化能否给细长杆 solid/void
点阵一个**保守且足够紧**的有效刚度估计/下界,以判定其能否成为 margin 级
Tier-C(而非仅 screening)。

方法:谱(傅里叶)位移法。在傅里叶域做 grad/div,实空间逐体素乘各向同性
C(λ,μ),CG 解周期弹性平衡 div(C:sym(grad u)) = -div(C:ε̄)。
- 位移(运动学可容)解 → 能量上界口径:得到的 C* 是 **偏硬的点估/上界**
  (与 beam_homog 同性质,非保守)。
- 保守下界须对偶/余能(自平衡且 void 内为零的应力场)——solid/void 下这是
  公认难点(平凡 Reuss/HS 下界恒等于 0)。本模块如实测量下界松紧,
  让数据判 PASS/KILL。

诚实边界:线弹性;void 用 E_void_ratio 软化(默认 1e-4)避免奇异,
残余伪刚度已报告;谱梯度在 Nyquist 附近对尖锐界面有振铃(细长杆最坏),
分辨率敏感性如实记录。单元测试对解析解(单相精确回收 / 层合板精确 /
Voigt-Reuss 序)把关。
"""
import numpy as np

# 各向同性:Lamé from (E, nu)
def _lame(E, nu):
    lam = E * nu / ((1 + nu) * (1 - 2 * nu))
    mu = E / (2 * (1 + nu))
    return lam, mu


def voxelize_graph(doc, n_vox=48, radius_mm=None):
    """商图 → 周期 solid/void 体素占据网格(N³ bool)+ 实算密度。

    对每条边及其周期像,标记到线段距离 ≤ radius 的体素中心为 solid。
    坐标在单胞内,枚举 -1..1 邻胞像保证跨界杆与周期性正确。
    """
    nodes = {n['id']: np.asarray(n['frac'], float) for n in doc['nodes']}
    a = doc['cell']['size_mm']
    default_r = (radius_mm if radius_mm is not None
                 else doc['default_radius_mm'])
    N = n_vox
    # 体素中心(单位胞)
    c = (np.arange(N) + 0.5) / N
    gx, gy, gz = np.meshgrid(c, c, c, indexing='ij')
    P = np.stack([gx, gy, gz], axis=-1).reshape(-1, 3)   # (N³,3)
    occ = np.zeros(P.shape[0], bool)
    rng = (-1, 0, 1)
    for e in doc['edges']:
        p1 = nodes[e['n1']]
        p2 = nodes[e['n2']] + np.asarray(e['shift'], float)
        # 逐边半径(radii_groups/polish 的各向异性来源;统一半径会把
        # mid_braced/twin_offset 等柱-撑拓扑塌成简单立方)
        re = (e['radius_mm'] if (radius_mm is None
                                 and e.get('radius_mm') is not None)
              else default_r) / a
        for cx in rng:
            for cy in rng:
                for cz in rng:
                    o = np.array([cx, cy, cz], float)
                    a1, a2 = p1 + o, p2 + o
                    d = _pt_seg_dist(P, a1, a2)
                    occ |= d <= re
    occ = occ.reshape(N, N, N)
    rho = float(occ.mean())
    return occ, rho


def _pt_seg_dist(P, a, b):
    """点集 P 到线段 ab 的欧氏距离(向量化)。"""
    ab = b - a
    L2 = ab @ ab
    if L2 < 1e-18:
        return np.linalg.norm(P - a, axis=1)
    t = np.clip((P - a) @ ab / L2, 0.0, 1.0)
    proj = a + t[:, None] * ab
    return np.linalg.norm(P - proj, axis=1)


def _freqs(N):
    """整数波数 → 物理频率 ξ=2π k(单位胞 L=1;模量与胞尺寸无关)。

    偶数网格:Nyquist 模(k=N/2)的一阶导虚部未定义,标准做法置零
    (否则尖锐界面在该方向系统性偏硬——实测层合板 C11 偏 25%)。
    """
    k = np.fft.fftfreq(N) * N
    if N % 2 == 0:
        k[N // 2] = 0.0
    return 2 * np.pi * k


def _apply_operator(u_r, lam, mu, xi):
    """A(u) = div(C:sym(grad u)),实空间位移场 u_r (N,N,N,3) → (N,N,N,3)。"""
    N = u_r.shape[0]
    uh = np.fft.fftn(u_r, axes=(0, 1, 2))            # (N,N,N,3) complex
    Kx, Ky, Kz = np.meshgrid(xi, xi, xi, indexing='ij')
    K = np.stack([Kx, Ky, Kz], axis=-1)              # (N,N,N,3)
    # 应变 ε̂_{jk} = (i/2)(ξ_j û_k + ξ_k û_j)
    iKu = 1j * (K[..., :, None] * uh[..., None, :])  # (..,3,3): ξ_j û_k
    eh = 0.5 * (iKu + np.swapaxes(iKu, -1, -2))      # sym
    e_r = np.real(np.fft.ifftn(eh, axes=(0, 1, 2)))  # (N,N,N,3,3) 实应变
    # 应力 σ = λ tr(e) I + 2μ e(逐体素)
    tr = e_r[..., 0, 0] + e_r[..., 1, 1] + e_r[..., 2, 2]
    s_r = 2 * mu[..., None, None] * e_r
    for d in range(3):
        s_r[..., d, d] += lam * tr
    sh = np.fft.fftn(s_r, axes=(0, 1, 2))            # (N,N,N,3,3)
    # div: (div σ)_i = i ξ_j σ̂_{ij}
    divh = 1j * np.sum(K[..., None, :] * sh, axis=-1)  # sum over j → (..,3)
    return np.real(np.fft.ifftn(divh, axes=(0, 1, 2)))


def _rhs(Ebar, lam, mu, xi):
    """b = -div(C:ε̄)(ε̄ 均匀宏应变 3x3)。"""
    N = lam.shape[0]
    tr = Ebar[0, 0] + Ebar[1, 1] + Ebar[2, 2]
    s_r = np.zeros((N, N, N, 3, 3))
    for i in range(3):
        for j in range(3):
            s_r[..., i, j] = 2 * mu * Ebar[i, j]
        s_r[..., i, i] += lam * tr
    Kx, Ky, Kz = np.meshgrid(xi, xi, xi, indexing='ij')
    K = np.stack([Kx, Ky, Kz], axis=-1)
    sh = np.fft.fftn(s_r, axes=(0, 1, 2))
    divh = 1j * np.sum(K[..., None, :] * sh, axis=-1)
    return -np.real(np.fft.ifftn(divh, axes=(0, 1, 2)))


def _solve_macro(Ebar, lam, mu, xi, n_iter=400, tol=1e-6):
    """CG 解 -A(u)=-b → u;返回 <σ>(平均应力 3x3)与收敛信息。"""
    # 平衡 A(u)=b_eq;M=-A(SPD)→ CG 解 M(u) = -b_eq(符号关键:
    # 写成 +b_eq 会让涨落取反、能量不降反增 → C11>Voigt 的非物理结果)
    b = -_rhs(Ebar, lam, mu, xi)
    u = np.zeros_like(b)
    def M(x):
        return -_apply_operator(x, lam, mu, xi)
    r = b - M(u)
    # 投影掉常数模(零均值位移,消刚体平动)
    r -= r.mean(axis=(0, 1, 2), keepdims=True)
    p = r.copy()
    rs = np.vdot(r, r).real
    rs0 = rs
    rs_new = rs
    it = 0
    if rs0 < 1e-30:        # RHS≈0(均匀相):u=0 即精确解
        return _mean_stress(u, Ebar, lam, mu, xi), {'iters': 0,
                                                    'resid': 0.0}
    for it in range(1, n_iter + 1):
        Mp = M(p)
        alpha = rs / np.vdot(p, Mp).real
        u += alpha * p
        r -= alpha * Mp
        r -= r.mean(axis=(0, 1, 2), keepdims=True)
        rs_new = np.vdot(r, r).real
        if rs_new <= tol * tol * rs0:
            break
        p = r + (rs_new / rs) * p
        rs = rs_new
    return _mean_stress(u, Ebar, lam, mu, xi), {
        'iters': it, 'resid': float(np.sqrt(rs_new / rs0))}


def _mean_stress(u, Ebar, lam, mu, xi):
    """给定位移涨落 u 与宏应变 Ebar → 平均应力 <σ>(3x3)。"""
    uh = np.fft.fftn(u, axes=(0, 1, 2))
    Kx, Ky, Kz = np.meshgrid(xi, xi, xi, indexing='ij')
    K = np.stack([Kx, Ky, Kz], axis=-1)
    iKu = 1j * (K[..., :, None] * uh[..., None, :])
    eh = 0.5 * (iKu + np.swapaxes(iKu, -1, -2))
    e_r = np.real(np.fft.ifftn(eh, axes=(0, 1, 2)))
    for i in range(3):
        for j in range(3):
            e_r[..., i, j] += Ebar[i, j]
    tr = e_r[..., 0, 0] + e_r[..., 1, 1] + e_r[..., 2, 2]
    s_r = 2 * mu[..., None, None] * e_r
    for d in range(3):
        s_r[..., d, d] += lam * tr
    return s_r.mean(axis=(0, 1, 2))


def homogenize_normal(occ, E_s=1.0, nu=0.3, E_void_ratio=1e-4,
                      n_iter=400, tol=1e-6):
    """solid/void 网格 → 3x3 法向刚度块 + 轴向模量 E_x/E_y/E_z(点估,偏上)。

    返回 dict:Cn(3x3)、E(三轴)、rho、void 伪刚度估计、收敛信息。
    """
    lam_s, mu_s = _lame(E_s, nu)
    lam_v, mu_v = _lame(E_s * E_void_ratio, nu)
    lam = np.where(occ, lam_s, lam_v)
    mu = np.where(occ, mu_s, mu_v)
    xi = _freqs(occ.shape[0])
    Cn = np.zeros((3, 3))
    info = []
    for k in range(3):
        Ebar = np.zeros((3, 3))
        Ebar[k, k] = 1.0
        sig, cinfo = _solve_macro(Ebar, lam, mu, xi, n_iter, tol)
        Cn[:, k] = [sig[0, 0], sig[1, 1], sig[2, 2]]
        info.append(cinfo)
    Cn = 0.5 * (Cn + Cn.T)   # 对称化(数值)
    try:
        Sn = np.linalg.inv(Cn)
        E = [float(1.0 / Sn[i, i]) for i in range(3)]
    except np.linalg.LinAlgError:
        E = [float('nan')] * 3
    rho = float(occ.mean())
    void_spurious = E_s * E_void_ratio * (1 - rho)
    return {'Cn': Cn.tolist(), 'E_xyz': E, 'rho': rho,
            'void_spurious_MPa_per_Es': void_spurious / E_s,
            'iters': [c['iters'] for c in info],
            'resid': [round(c['resid'], 8) for c in info],
            'E_void_ratio': E_void_ratio, 'n_vox': occ.shape[0],
            'source': 'atlas.mechanics.fft_homog(谱位移法,运动学=偏上点估)',
            'caveat': '位移法→偏硬(上界口径,非保守);void 软化伪刚度见字段'}


# ---- 解析界(单元测试 + 报告对照用)----

def analytic_bounds(rho, E_s, nu, E_void_ratio=0.0):
    """两相 Voigt(上)/ Reuss(下)体分数界。solid/void 下 Reuss→0。"""
    Ev = E_s * E_void_ratio
    voigt = rho * E_s + (1 - rho) * Ev
    if Ev <= 0:
        reuss = 0.0
    else:
        reuss = 1.0 / (rho / E_s + (1 - rho) / Ev)
    return {'voigt_upper': voigt, 'reuss_lower': reuss}
