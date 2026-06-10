"""B3:生成期硬门 C1–C8(确定性,毫秒级,先于一切 FEM/网格实现)。

输入 = atlas-cell-graph/1.0 文档。C9(网格实现器)在 B4。
硬门(fail 即杀):C1 schema/引用完整性,C2 节点碰撞,C3 周期连通性,
C5 密度可解性,C7 图级 DfAM,C8 实现预算。
信息门(只打 flag,不单独判死;红线:Maxwell 只说倾向):C4 Maxwell+
平衡矩阵 SVD,C6 杆-杆交叉(交叉=熔合,由 C4 的力学倾向间接反映)。

C3 数学(勘误后正确条件,见 errata/RESEARCH_NOVEL_TOPO):
  无限网连通 ⟺ 商图连通 且 圈-shift 整数矩阵的行格 = Z³。
  后者 ⟺ Smith 标准形 diag(1,1,1) ⟺ 3×3 Hermite 标准形 |det| = 1
  (避免大图上枚举全部 3×3 子式的组合爆炸)。
  反例:单节点三自环 shift=(2,0,0),(0,1,0),(0,0,1) → det=2 →
  两套互穿不连通网。与 3×3×3 超胞并查集双轨互验,不一致即保守判死。

C7 净距语义(实测校正):厂商 min_gap 是部件间规则;真实可打印种子
  (Octet/WeairePhelan 等)内部杆距天然 < 1mm,逐对硬判会全军覆没。
  故 C7 硬判仅杆径;净距打 flag,排粉权威裁决在 B1 网格级
  (体素 flood-fill + Raz ρ̄ 耦合)。gap ≤ 贴合容差 = 熔合(C6 flag)。

C3 双轨(实测校正):开边界超胞是错误实现(边界边被丢 → FCC 假阳性);
  正确有限实现 = 周期环面;单一 torus-3 漏 index-2(2⊥3),故
  torus-2 + torus-3 双探针,HNF 格指数为精确判据。
"""
import math
from itertools import product

import numpy as np

GATE_IDS = ('C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8')

# C8 预算
MAX_NODES = 500
MAX_EDGES = 2000
_GAP_CONTACT_TOL = 0.05  # mm,≤此值视为贴合/熔合


def _g(passed, value, reason=None, flags=None, hard=True):
    return {'pass': bool(passed), 'value': value, 'reason': reason,
            'flags': list(flags or []), 'hard': hard}


# ------------------------------------------------------------------ C1

def gate_c1_schema(doc):
    """schema 校验 + 引用完整性(边引用存在的节点、无重复节点 id/边)。"""
    from atlas.schema import validate_graph
    try:
        validate_graph(doc)
    except Exception as e:
        return _g(False, None, f'schema 不合法: {str(e)[:200]}')
    ids = [n['id'] for n in doc['nodes']]
    if len(ids) != len(set(ids)):
        return _g(False, None, '节点 id 重复')
    idset = set(ids)
    seen = set()
    for e in doc['edges']:
        if e['n1'] not in idset or e['n2'] not in idset:
            return _g(False, None, f"边引用未知节点 ({e['n1']},{e['n2']})")
        key = (e['n1'], e['n2'], tuple(e['shift']))
        rkey = (e['n2'], e['n1'], tuple(-s for s in e['shift']))
        if key in seen or rkey in seen:
            return _g(False, None, f'重复边 {key}')
        seen.add(key)
        if e['n1'] == e['n2'] and not any(e['shift']):
            return _g(False, None, f"零长自环 {e['n1']}")
    return _g(True, {'nodes': len(ids), 'edges': len(doc['edges'])})


# ------------------------------------------------------------------ 公共

def _positions(doc):
    return {n['id']: np.asarray(n['frac'], float) for n in doc['nodes']}


def _radius_of(doc, e):
    return float(e.get('radius_mm', doc['default_radius_mm']))


def _edge_segments_mm(doc):
    """边段端点(mm,基胞实例)+ 半径。"""
    a = doc['cell']['size_mm']
    pos = _positions(doc)
    segs = []
    for e in doc['edges']:
        p1 = pos[e['n1']] * a
        p2 = (pos[e['n2']] + np.asarray(e['shift'], float)) * a
        segs.append((p1, p2, _radius_of(doc, e), (e['n1'], e['n2'])))
    return segs


# ------------------------------------------------------------------ C2

def gate_c2_node_clash(doc):
    """节点身份重复检测:周期最小间距 < 0.5×r 硬判死(应已归并);
    < 2r(球互吞)只打 flag —— 实测 Iso_truss(1.5r)/WeairePhelan(1.4r)
    等合法种子节点球大幅重叠,2r 硬限会误杀。"""
    a = doc['cell']['size_mm']
    r = doc['default_radius_mm']
    pos = np.array([n['frac'] for n in doc['nodes']], float)
    ids = [n['id'] for n in doc['nodes']]
    min_d, pair = np.inf, None
    shifts = np.array(list(product((-1, 0, 1), repeat=3)), float)
    for i in range(len(pos)):
        for j in range(i, len(pos)):
            d = np.linalg.norm((pos[j] + shifts - pos[i]) * a, axis=1)
            if i == j:
                d = d[np.any(shifts != 0, axis=1)]  # 排除自身零移
            k = float(d.min()) if len(d) else np.inf
            if k < min_d:
                min_d, pair = k, (ids[i], ids[j])
    hard_limit = 0.5 * r
    ok = min_d >= hard_limit - 1e-9
    flags = ([f'节点对 {pair} 间距 {min_d:.3f} < 2r(球互吞,合法但提示)']
             if ok and min_d < 2 * r else [])
    return _g(ok, {'min_node_distance_mm': round(float(min_d), 6),
                   'closest_pair': pair, 'hard_limit_mm': hard_limit},
              None if ok else
              f'节点对 {pair} 间距 {min_d:.3f} < 0.5r={hard_limit}'
              '(疑似未归并的重复节点)', flags)


# ------------------------------------------------------------------ C3

def _hnf_det3(rows):
    """k×3 整数矩阵行格的指数 |det HNF|;格非满秩(≠Z³ 子格)返回 0。

    逐列 gcd 消元成列梯形:处理第 col 列时反复用最小非零元约化其余行,
    经典欧几里得下降保证收敛;收敛后除主元行外该列全零,主元行进 basis,
    余行进入下一列。rank=3 时 basis 为下梯形,|det| = 对角积。
    """
    B = [list(map(int, r)) for r in rows if any(r)]
    basis = []
    for col in range(3):
        guard = 0
        while True:
            guard += 1
            assert guard < 10000, 'HNF 消元未收敛(不应发生)'
            cand = [r for r in B if r[col] != 0]
            if len(cand) <= 1:
                break
            piv = min(cand, key=lambda r: abs(r[col]))
            for r in cand:
                if r is not piv:
                    q = r[col] // piv[col]
                    for k in range(3):
                        r[k] -= q * piv[k]
        cand = [r for r in B if r[col] != 0]
        if not cand:
            return 0  # 该方向缺失 → 格 rank < 3
        piv = cand[0]
        basis.append(piv)
        B = [r for r in B if r is not piv]
        # 此时 B 中所有行第 col 列已为 0(循环退出条件)
    det = 1
    for k in range(3):
        det *= basis[k][k]
    return abs(det)


def gate_c3_periodic_connectivity(doc):
    """商图连通 + 圈-shift 格指数=1(SNF diag(1,1,1))+ 3³ 超胞双轨。"""
    ids = [n['id'] for n in doc['nodes']]
    idx = {nid: i for i, nid in enumerate(ids)}
    V = len(ids)
    adj = [[] for _ in range(V)]
    for e in doc['edges']:
        i, j = idx[e['n1']], idx[e['n2']]
        s = tuple(int(x) for x in e['shift'])
        adj[i].append((j, s))
        adj[j].append((i, tuple(-x for x in s)))

    # 商图连通 + BFS 势(整数胞坐标)
    pot = {0: (0, 0, 0)}
    queue = [0]
    cycles = []
    while queue:
        u = queue.pop()
        for v, s in adj[u]:
            cand = tuple(pot[u][k] + s[k] for k in range(3))
            if v not in pot:
                pot[v] = cand
                queue.append(v)
            else:
                cyc = tuple(cand[k] - pot[v][k] for k in range(3))
                if any(cyc):
                    cycles.append(cyc)
    quotient_connected = len(pot) == V
    index = _hnf_det3(cycles) if quotient_connected else 0
    snf_ok = quotient_connected and index == 1

    # 双轨第二道:周期超胞(环面)并查集。开边界超胞是错误实现
    # (边界边被丢导致 FCC 等假阳性);单一 torus-3 又会漏 index-2
    # 互穿网(2 与 3 互素使其在 Z3 环面上连通)。故用 torus-2 +
    # torus-3 双探针:HNF 指数=1 ⟹ 两环面必连通(模 p 满射);
    # 指数>1 时其素因子 2 或 3 的情形被对应环面捕获。
    def torus_components(NS):
        parent = list(range(V * NS ** 3))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry

        def cid(i, c):
            return i * NS ** 3 + (c[0] * NS + c[1]) * NS + c[2]

        for e in doc['edges']:
            i, j = idx[e['n1']], idx[e['n2']]
            s = e['shift']
            for c in product(range(NS), repeat=3):
                c2 = tuple((c[k] + s[k]) % NS for k in range(3))
                union(cid(i, c), cid(j, c2))
        return len({find(x) for x in range(V * NS ** 3)})

    comps2 = torus_components(2)
    comps3 = torus_components(3)
    torus_connected = comps2 == 1 and comps3 == 1

    # 一致性:指数=1 ⟹ 环面必连通;不满足即实现 bug,保守判死
    consistent = (not snf_ok) or torus_connected
    value = {'quotient_connected': quotient_connected,
             'cycle_lattice_index': index,
             'snf_diag_111': snf_ok,
             'torus2_components': comps2,
             'torus3_components': comps3,
             'dual_track_consistent': consistent}
    if not quotient_connected:
        return _g(False, value, '商图不连通')
    if not snf_ok:
        return _g(False, value,
                  f'圈-shift 格指数 = {index} ≠ 1(互穿/低维网)')
    if not consistent:
        return _g(False, value, '双轨不一致(指数=1 但环面不连通),'
                                '保守判死待查')
    return _g(True, value)


# ------------------------------------------------------------------ C4

def gate_c4_maxwell_svd(doc):
    """Maxwell 倾向(红线:只说倾向)+ 周期 pin-jointed 平衡矩阵 SVD。

    信息门:只对孤立节点(degree=0)硬判死;悬挑(degree=1)打 flag。"""
    ids = [n['id'] for n in doc['nodes']]
    idx = {nid: i for i, nid in enumerate(ids)}
    V, E = len(ids), len(doc['edges'])
    deg = [0] * V
    a = doc['cell']['size_mm']
    pos = _positions(doc)
    A = np.zeros((3 * V, E))
    for k, e in enumerate(doc['edges']):
        i, j = idx[e['n1']], idx[e['n2']]
        deg[i] += 1
        deg[j] += 1
        u = ((pos[e['n2']] + np.asarray(e['shift'], float)
              - pos[e['n1']]) * a)
        u = u / np.linalg.norm(u)
        A[3 * i:3 * i + 3, k] += u
        A[3 * j:3 * j + 3, k] -= u
    isolated = [ids[i] for i in range(V) if deg[i] == 0]
    dangling = [ids[i] for i in range(V) if deg[i] == 1]
    M = E - 3 * V + 6
    sv = np.linalg.svd(A, compute_uv=False) if E else np.array([0.0])
    rank = int((sv > 1e-8 * (sv[0] if sv[0] > 0 else 1)).sum())
    mechanisms = max(0, 3 * V - 3 - rank)   # 周期胞:扣 3 个刚体平动
    self_stress = max(0, E - rank)
    flags = []
    if dangling:
        flags.append(f'悬挑节点(degree=1): {dangling}')
    if mechanisms > 0:
        flags.append(f'pin-jointed 机构数 ≈ {mechanisms}'
                     '(铰接估计,实杆有节点弯刚,仅倾向)')
    value = {'maxwell_M': M,
             'tendency': 'stretch-leaning' if M >= 0 else 'bending-leaning',
             'equilibrium_rank': rank, 'mechanisms_est': mechanisms,
             'self_stress_states': self_stress,
             'caveat': 'Maxwell/SVD 均为必要非充分,只输出倾向'}
    if isolated:
        return _g(False, value, f'孤立节点: {isolated}', flags)
    return _g(True, value, None, flags, hard=False)


# ------------------------------------------------------------------ C5

def gate_c5_density_solvable(doc, rho_target=None):
    """一阶密度可解性:ρ(r) = (πΣL/a³)·r²;默认半径的 ρ̂ ∈ (0,0.95);
    给 rho_target 时反解 r 并检查落在 free_params.radius_mm 范围内。"""
    a = doc['cell']['size_mm']
    segs = _edge_segments_mm(doc)
    total_L = sum(float(np.linalg.norm(p2 - p1)) for p1, p2, _, _ in segs)
    if total_L <= 0:
        return _g(False, None, '总杆长为 0')
    coef = math.pi * total_L / a ** 3   # rho ≈ coef * r²
    r0 = doc['default_radius_mm']
    rho_default = coef * r0 ** 2
    value = {'rho_estimate_at_default_r': round(rho_default, 4),
             'total_strut_length_mm': round(total_L, 3)}
    if not (0 < rho_default < 0.95):
        return _g(False, value,
                  f'默认半径下一阶密度 {rho_default:.3f} 不在 (0,0.95)')
    if rho_target is not None:
        r_need = math.sqrt(rho_target / coef)
        value['radius_for_target_mm'] = round(r_need, 4)
        fp = doc.get('free_params', {}).get('radius_mm')
        if fp and not (fp['min'] - 1e-9 <= r_need <= fp['max'] + 1e-9):
            return _g(False, value,
                      f"目标密度需 r={r_need:.3f},越出 free_params "
                      f"[{fp['min']},{fp['max']}]")
    return _g(True, value,
              flags=['一阶估算忽略节点重叠(高估),定稿密度用 mesh 模式'])


# ------------------------------------------------------------- seg-seg

def _seg_seg_distance_batch(P1, Q1, P2, Q2):
    """批量线段最小距离(Ericson 夹逼算法向量化)。"""
    d1, d2 = Q1 - P1, Q2 - P2
    r = P1 - P2
    a = (d1 * d1).sum(1)
    e = (d2 * d2).sum(1)
    f = (d2 * r).sum(1)
    c = (d1 * r).sum(1)
    b = (d1 * d2).sum(1)
    den = a * e - b * b
    safe_a = np.where(a > 1e-12, a, 1.0)
    safe_e = np.where(e > 1e-12, e, 1.0)
    safe_den = np.where(den > 1e-12, den, 1.0)
    s = np.where(den > 1e-12,
                 np.clip((b * f - c * e) / safe_den, 0.0, 1.0), 0.0)
    t = (b * s + f) / safe_e
    s = np.where(t < 0, np.clip(-c / safe_a, 0, 1),
                 np.where(t > 1, np.clip((b - c) / safe_a, 0, 1), s))
    t = np.clip(t, 0.0, 1.0)
    cp1 = P1 + s[:, None] * d1
    cp2 = P2 + t[:, None] * d2
    return np.linalg.norm(cp1 - cp2, axis=1)


def _pairwise_gaps(doc, margin=2.0):
    """非邻接杆对(含周期像)的表面净距数组 gap = 中心距 − (r_i+r_j)。

    向量化:候选对 = (i≤j) × 27 shift,排除自身零移与共节点零移对,
    AABB 粗筛后批量夹逼。只保留 gap < margin 的对。
    """
    a = doc['cell']['size_mm']
    segs = _edge_segments_mm(doc)
    E = len(segs)
    if E == 0:
        return np.zeros((0,)), []
    P = np.array([s[0] for s in segs])
    Q = np.array([s[1] for s in segs])
    R = np.array([s[2] for s in segs])
    nodes = [set(s[3]) for s in segs]
    shifts = np.array(list(product((-1, 0, 1), repeat=3)), float) * a
    ii, jj = np.triu_indices(E)
    n_pairs, n_shifts = len(ii), len(shifts)
    I = np.repeat(ii, n_shifts)
    J = np.repeat(jj, n_shifts)
    S = np.tile(shifts, (n_pairs, 1))
    zero_s = ~S.any(axis=1)
    share = np.array([bool(nodes[i] & nodes[j]) for i, j in zip(ii, jj)])
    share_full = np.repeat(share, n_shifts)
    mask = ~(zero_s & ((I == J) | share_full))
    I, J, S = I[mask], J[mask], S[mask]
    # AABB 粗筛
    lo1, hi1 = np.minimum(P, Q), np.maximum(P, Q)
    sep = np.maximum(lo1[J] + S - hi1[I], lo1[I] - (hi1[J] + S)).max(axis=1)
    keep = sep < (R[I] + R[J] + margin)
    I, J, S = I[keep], J[keep], S[keep]
    if not len(I):
        return np.zeros((0,)), []
    d = _seg_seg_distance_batch(P[I], Q[I], P[J] + S, Q[J] + S)
    gap = d - (R[I] + R[J])
    fine = gap < margin
    return gap[fine], list(zip(I[fine].tolist(), J[fine].tolist()))


# ------------------------------------------------------------------ C6

def gate_c6_crossings(doc, gaps=None):
    """杆-杆交叉/贴合检测(信息门):gap ≤ 贴合容差 = 熔合,打 flag。"""
    gap_vals, pairs = _pairwise_gaps(doc) if gaps is None else gaps
    n_contact = int((gap_vals <= _GAP_CONTACT_TOL).sum())
    flags = ([f'{n_contact} 对杆贴合/交叉(熔合,改变有效拓扑,'
              f'Maxwell/力学倾向按熔合后解读)'] if n_contact else [])
    return _g(True, {'contact_pairs': n_contact}, None, flags, hard=False)


# ------------------------------------------------------------------ C7

def gate_c7_dfam(doc, process='MJF', gaps=None):
    """图级 DfAM 预检。硬判:杆径 ≥ 工艺最小。

    杆间净距只打 flag 不硬判:实测 Octet(276 对)/WeairePhelan(1539 对)
    等真实可打印种子内部杆距天然 < 1mm —— 厂商 min_gap 是部件间规则;
    点阵内部排粉可行性由 B1 网格级检查(体素 flood-fill + Raz ρ̄ 耦合表)
    权威裁决,图级数字仅作生成期提示。
    """
    from atlas.printability import load_dfam_rules
    rules = load_dfam_rules()[process]
    min_d = rules['min_strut_diameter_mm']['value']
    min_gap = rules['min_gap_mm']['value']
    radii = [_radius_of(doc, e) for e in doc['edges']]
    d_min = 2 * min(radii)
    if d_min < min_d - 1e-9:
        return _g(False, {'min_strut_diameter_mm': d_min},
                  f'杆径 {d_min:.2f} < {process} 最小 {min_d}')
    gap_vals, pairs = _pairwise_gaps(doc) if gaps is None else gaps
    narrow = (gap_vals > _GAP_CONTACT_TOL) & (gap_vals < min_gap)
    n_narrow = int(narrow.sum())
    value = {'min_strut_diameter_mm': d_min, 'n_narrow_gaps': n_narrow,
             'min_gap_observed_mm': (round(float(gap_vals.min()), 3)
                                     if len(gap_vals) else None)}
    flags = ([f'{n_narrow} 对杆净距 ∈ ({_GAP_CONTACT_TOL}, {min_gap}) mm,'
              '排粉可行性以 B1 网格级检查为准'] if n_narrow else [])
    return _g(True, value, None, flags)


# ------------------------------------------------------------------ C8

def gate_c8_budget(doc):
    """实现预算:节点/边数上限,防退化提案 DOS 网格器。"""
    V, E = len(doc['nodes']), len(doc['edges'])
    ok = V <= MAX_NODES and E <= MAX_EDGES
    return _g(ok, {'nodes': V, 'edges': E,
                   'limits': [MAX_NODES, MAX_EDGES]},
              None if ok else f'超预算 V={V}/{MAX_NODES} E={E}/{MAX_EDGES}')


# ------------------------------------------------------------------ 入口

def run_gates(doc, process='MJF', rho_target=None):
    """顺序跑 C1–C8;C1 失败立即短路(后续门假设 schema 合法)。"""
    gates = {}
    gates['C1'] = gate_c1_schema(doc)
    if not gates['C1']['pass']:
        return {'passed': False, 'gates': gates,
                'flags': ['C1 失败,余门未执行']}
    gates['C2'] = gate_c2_node_clash(doc)
    gates['C3'] = gate_c3_periodic_connectivity(doc)
    gates['C4'] = gate_c4_maxwell_svd(doc)
    gates['C5'] = gate_c5_density_solvable(doc, rho_target=rho_target)
    gaps = _pairwise_gaps(doc)  # C6/C7 共享一次计算
    gates['C6'] = gate_c6_crossings(doc, gaps=gaps)
    gates['C7'] = gate_c7_dfam(doc, process=process, gaps=gaps)
    gates['C8'] = gate_c8_budget(doc)
    hard_fail = [k for k, g in gates.items() if g['hard'] and not g['pass']]
    flags = [f'{k}: {fl}' for k, g in gates.items() for fl in g['flags']]
    return {'passed': not hard_fail, 'gates': gates, 'flags': flags,
            'hard_failures': hard_fail}
