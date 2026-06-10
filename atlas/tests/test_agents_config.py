"""C1 单测:6 worker subagent 配置静态验证 + MCP 注册。

运行期白名单强制由 Claude Code harness 执行;此处验证配置层:
frontmatter 完整、tools 严格等于设计白名单、合同与红线文句在提示词内。
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
AGENTS = ROOT / '.claude' / 'agents'

# 设计白名单(PLAN C1):worker 不得越权
EXPECTED = {
    'atlas-interpreter': {'Read', 'Grep', 'Glob'},
    'atlas-generator': {'Bash', 'Read', 'Grep', 'Glob'},
    'atlas-printability': {'Bash', 'Read', 'Grep'},
    'atlas-surrogate': {'Bash', 'Read', 'Grep'},
    'atlas-mapper': {'Read', 'Grep', 'Glob'},
    'atlas-corrector': {'Bash', 'Read', 'Grep'},
    'atlas-evaluator': {'Bash', 'Read', 'Grep'},
}
# 任何 worker 都不得拥有的工具(证据纪律/外联控制)
FORBIDDEN = {'Write', 'Edit', 'WebFetch', 'WebSearch', 'AskUserQuestion',
             'Skill', 'Agent'}


def frontmatter(path):
    text = path.read_text(encoding='utf-8')
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', text, re.S)
    assert m, f'{path.name} 缺 frontmatter'
    fm = {}
    for line in m.group(1).split('\n'):
        if ':' in line:
            k, v = line.split(':', 1)
            fm[k.strip()] = v.strip()
    return fm, m.group(2)


def test_six_workers_exist_with_exact_whitelists():
    for name, tools in EXPECTED.items():
        p = AGENTS / f'{name}.md'
        assert p.exists(), f'缺 {p}'
        fm, _ = frontmatter(p)
        assert fm['name'] == name
        assert fm['description']
        declared = {t.strip() for t in fm['tools'].split(',')}
        assert declared == tools, f'{name} 白名单偏离: {declared}'
        assert not (declared & FORBIDDEN), f'{name} 含禁用工具'


def test_interpreter_loopback_and_no_silent_defaults():
    _, body = frontmatter(AGENTS / 'atlas-interpreter.md')
    assert '追问经主会话回环' in body
    assert 'open_questions' in body
    assert 'inference' in body  # 默认值必须标注


def test_generator_tool_row_per_dod():
    """DoD:Generator 工具行 = A1 API + B2 TPMS(+ Tier-2 全链)。"""
    _, body = frontmatter(AGENTS / 'atlas-generator.md')
    for needle in ('generate_cell', 'generate_tpms_at_density',
                   'run_gates', 'realize_graph', 'NoveltyIndex'):
        assert needle in body, f'Generator 工具行缺 {needle}'
    assert 'killed' in body  # 失败提案留痕(防搜索偏置)


def test_red_lines_in_prompts():
    _, surrogate = frontmatter(AGENTS / 'atlas-surrogate.md')
    assert 'OOD 禁最近邻' in surrogate
    assert 'screening only' in surrogate
    _, corrector = frontmatter(AGENTS / 'atlas-corrector.md')
    assert 'n<3' in corrector and 'spinodoid' in corrector
    _, mapper = frontmatter(AGENTS / 'atlas-mapper.md')
    assert 'inference' in mapper and 'XY/Z' in mapper
    _, printability = frontmatter(AGENTS / 'atlas-printability.md')
    assert '抄录不转述' in printability


def test_mcp_servers_registered():
    cfg = json.loads((ROOT / '.mcp.json').read_text(encoding='utf-8'))
    servers = cfg['mcpServers']
    assert servers['atlas-printability']['args'] == \
        ['atlas/printability/server.py']
    assert servers['atlas-retriever']['args'] == \
        ['atlas/retriever/server.py']
    # server 文件真实存在
    for s in servers.values():
        assert (ROOT / s['args'][0]).exists()
