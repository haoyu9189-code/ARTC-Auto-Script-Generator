"""B5:Novelty WL 哈希与查重(红线 8:新颖性措辞必须过查重)。

不变性(已测试):
- 节点重标号 / 节点列表顺序 / 边定向翻转(shift 取 ±字典序规范形)
- 半径与 free_params 不入哈希(Tier-1.5 连续自由度,不是新拓扑)
- 边长(几何量)入标签:同连接不同几何 = 不同结构

已知局限(诚实声明,novelty 措辞须带限定):
- WL 是图同构的必要非充分判据,WL 等价的非同构图理论上可碰撞
- 不识别"换原点/换胞基"的同一晶体网重表示(shift 向量随 wrap 改变;
  完整网同构需 Systre 式重心规范化,归 Phase 2+)
→ duplicate_of=None 只能解读为"ATLAS 词汇表/索引范围内未发现重复"。
"""
import hashlib
import json

_WL_ROUNDS = 3
_LEN_DECIMALS = 4


def _canon_shift(shift):
    s = tuple(int(x) for x in shift)
    neg = tuple(-x for x in s)
    return min(s, neg)


def _edge_attr(doc, e, pos):
    import numpy as np
    p1 = pos[e['n1']]
    p2 = pos[e['n2']] + np.asarray(e['shift'], float)
    length = round(float(np.linalg.norm(p2 - p1)), _LEN_DECIMALS)
    return (length, _canon_shift(e['shift']))


def wl_hash(doc):
    """atlas-cell-graph/1.0 → 拓扑+几何 WL 哈希(hex)。"""
    import numpy as np
    pos = {n['id']: np.asarray(n['frac'], float) for n in doc['nodes']}
    ids = list(pos)
    # 邻接:node -> [(neighbor, edge_attr)]
    adj = {nid: [] for nid in ids}
    edge_attrs = []
    for e in doc['edges']:
        attr = _edge_attr(doc, e, pos)
        edge_attrs.append(attr)
        adj[e['n1']].append((e['n2'], attr))
        adj[e['n2']].append((e['n1'], attr))

    label = {nid: str(len(adj[nid])) for nid in ids}  # 初始 = 度
    for _ in range(_WL_ROUNDS):
        new = {}
        for nid in ids:
            neigh = sorted(f'{label[v]}|{a}' for v, a in adj[nid])
            sig = label[nid] + '#' + ';'.join(neigh)
            new[nid] = hashlib.sha256(sig.encode()).hexdigest()[:16]
        label = new

    payload = json.dumps({
        'n_nodes': len(ids),
        'n_edges': len(doc['edges']),
        'cell_size': round(float(doc['cell']['size_mm']), 6),
        'node_labels': sorted(label.values()),
        'edge_attrs': sorted(map(str, edge_attrs)),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


class NoveltyIndex:
    """查重索引:种子(+ 后续目录)哈希注册表。"""

    def __init__(self):
        self._index = {}  # hash -> name

    @classmethod
    def from_seeds(cls):
        import os
        from atlas.schema import SEEDS_DIR
        from atlas.geometry import list_topologies
        idx = cls()
        for ct in list_topologies():
            with open(os.path.join(SEEDS_DIR, f'{ct}.json'),
                      encoding='utf-8') as f:
                idx.register(json.load(f), ct)
        return idx

    def register(self, doc, name):
        h = wl_hash(doc)
        self._index.setdefault(h, name)
        return h

    def check(self, doc):
        """返回 novelty 块(可直接写回 doc['novelty'])。"""
        h = wl_hash(doc)
        return {'wl_hash': h, 'duplicate_of': self._index.get(h)}

    def __len__(self):
        return len(self._index)
