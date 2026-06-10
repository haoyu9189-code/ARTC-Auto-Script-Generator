"""P2-2 预演:生成式拓扑搜索(变异 → 硬门 → WL 查重 → beam-FEM 裁判)。

「LLM 提案、工具裁决」回路的无 LLM 版本:确定性随机变异当提案器,
其余链路与生产版完全相同 —— 产物是真正词汇表外的新拓扑,
每个都带完整 lineage 与 screening 级力学分。

诚实边界:score = E*/ρ̂(比刚度,beam-FEM screening only);
新颖性 = ATLAS 索引范围内 WL 查重未命中;非全局最优主张。
"""
import copy
import json
import os
import random

import numpy as np

from atlas.gates import run_gates
from atlas.geometry import list_topologies
from atlas.mechanics.frame_fem import solve_compression
from atlas.schema import SEEDS_DIR
from atlas.schema.novelty import NoveltyIndex, wl_hash

_GRID = [0.0, 0.25, 0.5, 0.75]


def _load_seed(t):
    with open(os.path.join(SEEDS_DIR, f'{t}.json'), encoding='utf-8') as f:
        return json.load(f)


def _periodic_dist(p, q):
    d = np.abs(np.asarray(p) - np.asarray(q))
    d = np.minimum(d, 1 - d)
    return float(np.linalg.norm(d))


def _mutate(doc, rng):
    """一次变异:加边(60%)或加节点+连边(40%)。失败返回 None。"""
    new = copy.deepcopy(doc)
    nodes = new['nodes']
    edges = new['edges']
    existing = {(e['n1'], e['n2'], tuple(e['shift'])) for e in edges}
    existing |= {(e['n2'], e['n1'], tuple(-s for s in e['shift']))
                 for e in edges}
    if rng.random() < 0.6 or len(nodes) >= 40:
        # 加边:随机节点对 + 随机 shift
        for _ in range(20):
            a = rng.choice(nodes)['id']
            b = rng.choice(nodes)['id']
            s = tuple(rng.choice((-1, 0, 1)) for _ in range(3))
            if a == b and not any(s):
                continue
            if (a, b, s) in existing:
                continue
            edges.append({'n1': a, 'n2': b, 'shift': list(s)})
            return new
        return None
    # 加节点:对称网格点,连 4 个周期最近邻
    pos = {nd['id']: nd['frac'] for nd in nodes}
    for _ in range(20):
        p = [rng.choice(_GRID) for _ in range(3)]
        if any(_periodic_dist(p, q) < 0.05 for q in pos.values()):
            continue
        nid = f'G{len(nodes)}'
        nodes.append({'id': nid, 'frac': p})
        近 = sorted(pos, key=lambda q: _periodic_dist(p, pos[q]))[:4]
        for q in 近:
            edges.append({'n1': nid, 'n2': q, 'shift': [0, 0, 0]})
        return new
    return None


def search(bases=('BCC', 'FCC', 'Octet_truss', 'Kelvin', 'Auxetic',
                  'Diamond'),
           per_base=25, keep=2, seed=20260611, n_block=2, strain=0.05):
    """返回 top-k 新拓扑:[{doc, parent, E_star, rho_est, score, ...}]"""
    rng = random.Random(seed)
    idx = NoveltyIndex.from_seeds()
    seen = set()
    survivors = []
    stats = {'proposed': 0, 'gate_killed': 0, 'dup': 0, 'fem_failed': 0}
    for base in bases:
        base_doc = _load_seed(base)
        for k in range(per_base):
            stats['proposed'] += 1
            cand = _mutate(base_doc, rng)
            if cand is None:
                stats['gate_killed'] += 1
                continue
            cand['name'] = f'gen_{base}_{k}'
            cand['lineage'] = {'tier': 'tier2',
                               'generator': 'atlas.mechanics.gen_search'
                                            '(变异提案×工具裁决)',
                               'source': f'mutated from seed {base}',
                               'parents': [base]}
            g = run_gates(cand)
            if not g['passed']:
                stats['gate_killed'] += 1
                continue
            h = wl_hash(cand)
            if idx.check(cand)['duplicate_of'] or h in seen:
                stats['dup'] += 1
                continue
            seen.add(h)
            try:
                fem = solve_compression(cand, n=n_block, strain=strain)
            except Exception:
                stats['fem_failed'] += 1
                continue
            rho = g['gates']['C5']['value']['rho_estimate_at_default_r']
            survivors.append({
                'doc': cand, 'parent': base,
                'E_star': fem['E_star'], 'rho_est': rho,
                'score': fem['E_star'] / max(rho, 1e-6),
                'wl_hash': h,
                'n_nodes': len(cand['nodes']),
                'n_edges': len(cand['edges'])})
    survivors.sort(key=lambda s: -s['score'])
    # 参照:各 base 自身的比刚度
    refs = {}
    for base in bases:
        d = _load_seed(base)
        g = run_gates(d)
        fem = solve_compression(d, n=n_block, strain=strain)
        rho = g['gates']['C5']['value']['rho_estimate_at_default_r']
        refs[base] = {'E_star': fem['E_star'], 'rho_est': rho,
                      'score': fem['E_star'] / max(rho, 1e-6)}
    return {'top': survivors[:keep], 'n_survivors': len(survivors),
            'stats': stats, 'seed_refs': refs}


if __name__ == '__main__':
    r = search()
    print(f"stats={r['stats']}  survivors={r['n_survivors']}")
    best_ref = max(v['score'] for v in r['seed_refs'].values())
    print(f"种子最优比刚度 = {best_ref:.1f}")
    for s in r['top']:
        print(f"  {s['doc']['name']:<22} parent={s['parent']:<12} "
              f"E*={s['E_star']:8.2f} rho={s['rho_est']:.3f} "
              f"score={s['score']:7.1f} "
              f"({s['score']/r['seed_refs'][s['parent']]['score']:.2f}x 亲本)")
