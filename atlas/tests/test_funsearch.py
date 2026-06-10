"""P2-2 单测:FunSearch 运行工件、自我执法案例、绝对门、提案器冒烟。"""
import json
import os

import pytest

from atlas.mechanics.funsearch import (RUN_OUT, mutation_proposals,
                                       absolute_gates, score_doc)

pytestmark = pytest.mark.skipif(
    not os.path.exists(RUN_OUT),
    reason='funsearch_run.json 未生成(python -m atlas.mechanics.funsearch)')


@pytest.fixture(scope='module')
def run():
    with open(RUN_OUT, encoding='utf-8') as f:
        return json.load(f)


def test_dod_three_winners_over_110pct(run):
    assert run['n_winners_110pct'] >= 3
    winners = [a for a in run['accepted'] if a['vs_best_seed'] >= 1.10]
    assert len(winners) >= 3
    for w in winners:
        assert len(w['wl_hash']) == 16
        ag = w['absolute_gates']
        assert ag['G1_spd'] and ag['G2_voigt'] and ag['G3_consistent']
        assert w['doc']['lineage']['tier'] == 'tier2'


def test_claude_proposals_carry_rationale(run):
    claude = [a for a in run['accepted'] if a['proposer'] == 'claude']
    assert claude
    for a in claude:
        assert a['rationale'].startswith('rationale')


def test_self_policing_graded_radius_killed_as_dup(run):
    """验证链对设计者执法:梯度半径不改拓扑(Tier-1.5),WL 正确击杀。"""
    k = next(x for x in run['killed']
             if x['name'] == 'graded_column_frame')
    assert 'WL' in k['killed']


def test_novelty_wording_red_line(run):
    assert 'ATLAS 索引范围内' in run['novelty_wording']
    assert 'screening' in run['novelty_wording']
    assert 'Tier-D' in run['novelty_wording']


def test_top_winner_revalidates_live(run):
    """冠军文档现场复跑硬门 + 绝对门(工件非伪造)。"""
    from atlas.gates import run_gates
    from atlas.mechanics.beam_homog import homogenize
    top = run['accepted'][0]
    doc = top['doc']
    assert run_gates(doc)['passed']
    h = homogenize(doc)
    ok, det = absolute_gates(doc, h)
    assert ok
    s, rho, _ = score_doc(doc)
    assert abs(s - top['score']) / top['score'] < 0.02


def test_mutation_fallback_smoke():
    props = mutation_proposals(history=[], n=4, seed=11)
    assert props
    for p in props:
        assert p['proposer'] == 'mutation'
        assert p['doc']['lineage']['generator'] == 'mutation-fallback'
