"""D1 端到端验收:三案例报告齐 + 红线零违例 + 数字可溯源。"""
import pytest

from atlas.data import ingest_cell_db as ing
from atlas.orchestration.acceptance import (run_all, CASES, DISCLAIMER,
                                            audit_report)


@pytest.fixture(scope='module')
def outputs(tmp_path_factory):
    d = tmp_path_factory.mktemp('d1')
    db = str(d / 'cell_db.sqlite')
    ing.build(db_path=db)
    return run_all(db_path=db, out_dir=str(d / 'reports'))


def test_three_reports_generated_with_zero_violations(outputs):
    assert set(outputs) == {c['key'] for c in CASES}
    for key, out in outputs.items():
        assert out['violations'] == [], f'{key} 红线违例: {out["violations"]}'
        text = open(out['report_path'], encoding='utf-8').read()
        for section in ('## 推荐表', '## 验证 trace', '## 来源清单',
                        'margin(pred/design)', DISCLAIMER):
            assert section in text, f'{key} 缺 {section}'


def test_sls_case_has_db_backed_pass(outputs):
    judged = outputs['sls_absorber']['judged']
    passing = [j for j in judged if j['trace']['verdict'] == 'PASS']
    assert passing, 'SLS 案例应有 PASS 候选'
    for j in passing:
        m = j['trace']['margin']
        assert m['ratio'] >= 1.0
        assert m['evidence_source']  # margin 数字可溯源


def test_mjf_case_tier2_honest_fail_and_layering(outputs):
    judged = outputs['mjf_auxetic_pad']['judged']
    tier2 = next(j for j in judged if j['trace']['tier'] == '2')
    assert tier2['trace']['verdict'] == 'FAIL'  # OOD 无白名单 margin 证据
    text = open(outputs['mjf_auxetic_pad']['report_path'],
                encoding='utf-8').read()
    assert 'Tier-2' in text and '分层' in text


def test_lpbf_case_honest_zero_pass_with_pathways(outputs):
    judged = outputs['lpbf_bracket']['judged']
    assert all(j['trace']['verdict'] == 'FAIL' for j in judged)
    text = open(outputs['lpbf_bracket']['report_path'],
                encoding='utf-8').read()
    assert '无候选通过' in text and '出路' in text
    assert '仅作筛选' in text  # 高风险标注


def test_every_check_in_traces_has_source(outputs):
    for out in outputs.values():
        for j in out['judged']:
            for ch in j['trace']['checks']:
                assert ch['source'], f"无源检查: {ch['tool']}"


def test_audit_catches_violations():
    """审计器本身的正反用例。"""
    bad = '# 报告\n这是绝对全局最优。Maxwell 判定为 stretch。'
    v = audit_report(bad, high_risk=True)
    assert any('免责' in x for x in v)
    assert any('Maxwell' in x for x in v)
    assert any('仅作筛选' in x for x in v)
