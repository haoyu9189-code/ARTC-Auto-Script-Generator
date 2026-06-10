"""ATLAS 物理脚本公共合同(A3)。

所有脚本返回统一信封,Evaluator 只认这种格式的工具证据:
    {
        'value':       主结果(数值或 dict)
        'status':      'computed' | 'estimate' | 'default' | 'out_of_domain'
                       | 'needs_input'
        'inputs_echo': 原样回显收到的输入(审计用,FEABench 教训:
                       默认值被当计算结果静默导出)
        'source':      数值/公式的出处(DOI / 厂商数据表 / 标记推测)
        'caveats':     适用域与降级警告列表(可空)
    }
status 语义:computed=确定性计算;estimate=有理论根基的估算;
default=使用了内置默认输入;out_of_domain=输入越出公式适用域,
value 仅供参考;needs_input=缺关键输入,value 为 None。
"""


def make_result(value, status, inputs_echo, source, caveats=None):
    assert status in ('computed', 'estimate', 'default', 'out_of_domain',
                      'needs_input'), f'illegal status: {status}'
    assert source and isinstance(source, str), 'source 必须非空'
    return {
        'value': value,
        'status': status,
        'inputs_echo': dict(inputs_echo),
        'source': source,
        'caveats': list(caveats or []),
    }
