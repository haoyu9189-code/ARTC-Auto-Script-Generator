"""B7 单测:文献库 front-matter 完备性与 Grep 可命中性。"""
import pathlib
import re

REFS = pathlib.Path(__file__).resolve().parents[1] / 'references'
REQUIRED_KEYS = ('doi:', 'source_type:', 'validated_claims:',
                 'validity_domain:')
# errata 是勘误登记非文献笔记,豁免 front-matter
EXEMPT = {'errata.md'}


def front_matter(path):
    text = path.read_text(encoding='utf-8')
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    return m.group(1) if m else None


def note_files():
    return [p for p in REFS.glob('*.md') if p.name not in EXEMPT]


def test_minimum_corpus_size():
    """DoD:≥10 核心 + 6 尺寸效应(实际 18 笔记 + 1 目录笔记)。"""
    assert len(note_files()) >= 16


def test_all_notes_have_complete_front_matter():
    for p in note_files():
        fm = front_matter(p)
        assert fm, f'{p.name} 缺 front-matter'
        for key in REQUIRED_KEYS:
            assert key in fm, f'{p.name} front-matter 缺 {key}'
        # doi 非空且非占位
        doi_line = next(line for line in fm.split('\n')
                        if line.startswith('doi:'))
        assert len(doi_line) > 8, f'{p.name} doi 为空'


def test_grepability():
    """Grep front-matter 可命中(检索层零向量库的工作方式)。"""
    hits = [p.name for p in note_files()
            if '10.1016/j.cossms.2023.101081' in p.read_text(encoding='utf-8')]
    assert 'zhong_2023.md' in hits
    size_effect = [p.name for p in note_files()
                   if '尺寸效应' in p.read_text(encoding='utf-8')
                   or 'Size effect' in p.read_text(encoding='utf-8')
                   or 'size effect' in p.read_text(encoding='utf-8').lower()]
    assert len(size_effect) >= 6, f'尺寸效应文献不足: {size_effect}'


def test_key_corrections_present():
    """勘误后的关键事实在笔记中固化。"""
    zhong = (REFS / 'zhong_2023.md').read_text(encoding='utf-8')
    assert '金属' in zhong  # 300% 仅限金属
    abdulhadi = (REFS / 'abdulhadi_2023.md').read_text(encoding='utf-8')
    assert 'PA12' in abdulhadi  # 不适用 PA12 的限定
    li_guo = (REFS / 'li_guo_2024_size_poisson.md').read_text(encoding='utf-8')
    assert 'Kirchhof' in li_guo  # E10 勘误溯源留痕
    errata = (REFS / 'errata.md').read_text(encoding='utf-8')
    assert 'E10' in errata
