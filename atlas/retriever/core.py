"""B8:统一检索核心(纯函数层,MCP server 是薄壳)。

红线实现(非提示词约定,代码强制):
1. 数值查表结果带源原样返回,**永不参与 rank fusion**(RANK_FUSION_RULE
   写入 server instructions;数值与文本是两个独立工具,无融合路径)。
2. OOD 禁最近邻:nearest_by_density 对 DB 外拓扑显式拒绝并指引
   物理计算裁判(beam-FEM/FEA),不静默退化。
3. 全调用留痕:JSONL 日志(tool/query/n_hits/sources),供 verification
   trace 审计与 LanceDB 升级触发条件 ② 的检索 miss 统计。
"""
import json
import os
import re
import sqlite3
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
DB_PATH = os.path.join(_ROOT, 'atlas', 'data', 'cell_db.sqlite')
REFS_DIR = os.path.join(_ROOT, 'atlas', 'references')
LOG_PATH = os.path.join(_ROOT, 'atlas', 'data', 'retriever_log.jsonl')

RANK_FUSION_RULE = ('数值查表结果是权威事实,带源原样返回,'
                    '永不参与 rank fusion;RRF 仅限同条目空间的'
                    '文本排序融合(Cormack 2009 原义)')

LOAD_MODES = ('static_compression', 'static_shear',
              'dynamic_compression', 'dynamic_shear', 'general')


def _log(tool, query, n_hits, sources, log_path=None):
    entry = {'ts': round(time.time(), 3), 'tool': tool, 'query': query,
             'n_hits': n_hits, 'sources': sorted(set(sources))[:3]}
    path = log_path or LOG_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return entry


def _connect(db_path):
    con = sqlite3.connect(db_path or DB_PATH)
    con.row_factory = sqlite3.Row
    return con


# ------------------------------------------------------------- 数值侧

def query_cell_db(topology='', rho_min=None, rho_max=None,
                  feature='', load_mode='', limit=20,
                  db_path=None, log_path=None):
    """过滤式查表:结构 + 可选特征值,每行带 source 原样返回。"""
    con = _connect(db_path)
    try:
        sql = ('SELECT s.sample_name, s.topology, s.strut_radius, s.slider,'
               ' s.density, s.density_source, s.topology_class,'
               ' s.quality_flag, s.source AS structure_source')
        joins, conds, args = '', [], []
        if feature:
            sql += ', f.feature, f.value AS feature_value,' \
                   ' f.load_mode, f.source AS feature_source'
            joins = ' JOIN features f ON f.sample_name = s.sample_name'
            conds.append('f.feature = ?')
            args.append(feature)
            if load_mode:
                conds.append('f.load_mode = ?')
                args.append(load_mode)
        if topology:
            conds.append('s.topology = ?')
            args.append(topology)
        if rho_min is not None:
            conds.append('s.density >= ?')
            args.append(rho_min)
        if rho_max is not None:
            conds.append('s.density <= ?')
            args.append(rho_max)
        sql += ' FROM structures s' + joins
        if conds:
            sql += ' WHERE ' + ' AND '.join(conds)
        sql += ' ORDER BY s.sample_name LIMIT ?'
        args.append(int(limit))
        rows = [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()
    out = {'rows': rows, 'n_hits': len(rows),
           'policy': RANK_FUSION_RULE,
           'tier': 'Tier-1 库内检索(可信度最高层级)'}
    _log('query_cell_db',
         dict(topology=topology, rho_min=rho_min, rho_max=rho_max,
              feature=feature, load_mode=load_mode, limit=limit),
         len(rows), [r.get('structure_source', '') for r in rows],
         log_path)
    return out


def get_structure(sample_name, db_path=None, log_path=None):
    """单结构全档:身份/密度双列/质量旗标/曲线可用性,全部带源。"""
    con = _connect(db_path)
    try:
        s = con.execute('SELECT * FROM structures WHERE sample_name=?',
                        (sample_name,)).fetchone()
        if s is None:
            out = {'found': False, 'sample_name': sample_name}
            _log('get_structure', {'sample_name': sample_name}, 0, [],
                 log_path)
            return out
        curves = [dict(r) for r in con.execute(
            'SELECT load_case, n_points, source FROM curves '
            'WHERE sample_name=?', (sample_name,))]
        feats = [dict(r) for r in con.execute(
            'SELECT feature, value, load_mode, source FROM features '
            'WHERE sample_name=?', (sample_name,))]
    finally:
        con.close()
    out = {'found': True, 'structure': dict(s), 'curves': curves,
           'features': feats, 'policy': RANK_FUSION_RULE}
    _log('get_structure', {'sample_name': sample_name}, 1,
         [s['source']], log_path)
    return out


def nearest_by_density(topology, rho_rel, k=3, db_path=None,
                       log_path=None):
    """库内同拓扑密度最近邻(带 applicability 距离)。

    红线强制:topology 不在 DB → 显式拒绝(OOD 禁最近邻,
    必须改用物理计算裁判),绝不静默跨拓扑退化。"""
    con = _connect(db_path)
    try:
        known = {r[0] for r in con.execute(
            'SELECT DISTINCT topology FROM structures')}
        if topology not in known:
            out = {'rejected': True,
                   'reason': f'拓扑 {topology!r} 不在 cell DB(OOD)——'
                             '红线:禁用最近邻 surrogate,请走物理计算'
                             '裁判(Tier-B beam-FEM / Tier-D FEA)',
                   'known_topologies': sorted(known)}
            _log('nearest_by_density',
                 {'topology': topology, 'rho_rel': rho_rel}, 0, [],
                 log_path)
            return out
        rows = [dict(r) for r in con.execute(
            'SELECT sample_name, topology, strut_radius, slider, density,'
            ' density_source, quality_flag, source,'
            ' ABS(density - ?) AS density_distance'
            ' FROM structures WHERE topology=? AND density IS NOT NULL'
            ' ORDER BY density_distance LIMIT ?',
            (rho_rel, topology, int(k)))]
    finally:
        con.close()
    caveats = ['applicability: density_distance 为库内插值距离;'
               '凸包外(distance 大于该拓扑密度覆盖带)即外推,须降级']
    out = {'rejected': False, 'rows': rows, 'n_hits': len(rows),
           'caveats': caveats, 'policy': RANK_FUSION_RULE}
    _log('nearest_by_density',
         {'topology': topology, 'rho_rel': rho_rel, 'k': k},
         len(rows), [r['source'] for r in rows], log_path)
    return out


# ------------------------------------------------------------- 文本侧

def _parse_front_matter(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).split('\n'):
        if ':' in line and not line.startswith((' ', '-')):
            k, v = line.split(':', 1)
            fm[k.strip()] = v.strip().strip('"')
    return fm


def retrieve_reference(query, limit=5, refs_dir=None, log_path=None):
    """文献笔记关键词检索(front-matter 命中加权 2×)。零向量库
    (HANDOFF §9.4 修订);升级触发条件之一 = 本日志中的检索 miss。"""
    d = refs_dir or REFS_DIR
    terms = [t for t in re.split(r'\s+', query.strip()) if t]
    hits = []
    for fname in sorted(os.listdir(d)):
        if not fname.endswith('.md'):
            continue
        path = os.path.join(d, fname)
        text = open(path, encoding='utf-8').read()
        m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
        fm_text = m.group(1) if m else ''
        body = text[m.end():] if m else text
        score = 0
        matched = []
        for t in terms:
            tl = t.lower()
            c_fm = fm_text.lower().count(tl)
            c_body = body.lower().count(tl)
            score += 2 * c_fm + c_body
            if c_fm + c_body:
                matched.append(t)
        if score > 0:
            fm = _parse_front_matter(text)
            hits.append({'file': fname, 'score': score,
                         'matched_terms': matched,
                         'title': fm.get('title', fname),
                         'doi': fm.get('doi', ''),
                         'source_type': fm.get('source_type', ''),
                         'validity_domain': fm.get('validity_domain', '')})
    hits.sort(key=lambda h: (-h['score'], h['file']))
    hits = hits[:int(limit)]
    out = {'hits': hits, 'n_hits': len(hits), 'query': query,
           'policy': RANK_FUSION_RULE,
           'miss': len(hits) == 0}
    _log('retrieve_reference', {'query': query, 'limit': limit},
         len(hits), [h['doi'] for h in hits], log_path)
    return out
