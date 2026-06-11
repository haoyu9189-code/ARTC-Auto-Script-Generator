"""P3-C 单测:benchmark 仪表纯函数。"""
from atlas.orchestration.bench import (baseline_traceability,
                                       traceability_of_trace)


def test_traceability_two_axis():
    trace = {'checks': [
        {'source': 'a', 'source_type': 'internal_fea'},
        {'source': 'b'},                       # 有 source 无类型
        {'source': 'c', 'source_type': 'vendor'},
        {'source': 'd'},
    ]}
    src, typed = traceability_of_trace(trace)
    assert src == 1.0          # schema 强制位:全有
    assert typed == 0.5        # 类型化覆盖率


def test_baseline_traceability_tool_hints():
    result = {'candidates': [{'key_numbers': [
        {'name': 'EA', 'value': 1, 'source': 'cell_db.sqlite 查表'},
        {'name': 'rho', 'value': 2, 'source': '工程经验估算'},
        {'name': 'min_mm', 'value': 3,
         'source': 'atlas.printability 实测'},
        {'name': 'E', 'value': 4, 'source': '手册典型值'},
    ]}]}
    tr, n = baseline_traceability(result)
    assert n == 4
    assert tr == 0.5           # 工具/库指向 2/4,自由文本不算


def test_empty_trace_zero():
    assert traceability_of_trace({'checks': []}) == (0.0, 0.0)
    assert baseline_traceability({'candidates': []}) == (0.0, 0)
