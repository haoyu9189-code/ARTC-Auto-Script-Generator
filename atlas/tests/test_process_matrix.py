"""P2-4 单测:工艺矩阵全条目带源、口径区分、Mapper 指向。"""
import json
import pathlib

THRESH = (pathlib.Path(__file__).resolve().parents[2] / '.claude' /
          'skills' / 'atlas' / 'references' / 'thresholds')
AGENTS = pathlib.Path(__file__).resolve().parents[2] / '.claude' / 'agents'


def load():
    return json.loads((THRESH / 'process_matrix.json')
                      .read_text(encoding='utf-8'))


def test_three_process_tiers_present():
    m = load()
    assert {'MJF_PA12', 'SLS_PA12', 'LPBF_AlSi10Mg'} <= set(m)


def test_every_leaf_has_source_and_type():
    m = load()
    for proc, entries in m.items():
        if proc == '_meta':
            continue
        for key, leaf in entries.items():
            assert leaf.get('source'), f'{proc}.{key} 缺 source'
            assert leaf.get('source_type') in (
                'academic_doi', 'vendor', 'inference', 'internal_fea'), \
                f'{proc}.{key} source_type 非法'


def test_inference_entries_flagged():
    m = load()
    kd = m['LPBF_AlSi10Mg']['surface_knockdown']
    assert kd['source_type'] == 'inference' and 'E5' in kd['source']
    sls = m['SLS_PA12']['Es_MPa']
    assert sls['source_type'] == 'inference' and '待核录' in sls['source']


def test_fea_basis_vs_datasheet_separation():
    """口径纪律:DB 数值实验基材(1010)与真实材性(1700)分列且标注。"""
    m = load()['MJF_PA12']
    assert m['E_fea_basis_MPa']['value'] == 1010
    assert m['E_fea_basis_MPa']['source_type'] == 'internal_fea'
    assert m['Es_MPa_datasheet']['value'] == 1700
    assert '非真实材性' in m['E_fea_basis_MPa']['source']


def test_mapper_agent_points_to_matrix():
    body = (AGENTS / 'atlas-mapper.md').read_text(encoding='utf-8')
    assert 'process_matrix.json' in body
    assert 'E_fea_basis' in body  # 口径纪律入提示词
