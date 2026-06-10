"""B8:Retriever MCP server(FastMCP STDIO,四工具薄壳)。

启动:python atlas/retriever/server.py
注册:claude mcp add atlas-retriever -- python atlas/retriever/server.py
"""
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastmcp import FastMCP

from atlas.retriever import core

mcp = FastMCP(
    'atlas-retriever',
    instructions=(
        'ATLAS 统一检索入口(引用层)。规则:'
        f'(1) {core.RANK_FUSION_RULE};'
        '(2) OOD 拓扑禁用最近邻 surrogate(nearest_by_density 会显式拒绝,'
        '改走物理计算裁判);'
        '(3) 所有调用留痕 retriever_log.jsonl,供 trace 审计;'
        '(4) source_type=inference 的结果必须降级标注。'))


@mcp.tool
def query_cell_db(topology: str = '', rho_min: float = -1.0,
                  rho_max: float = -1.0, feature: str = '',
                  load_mode: str = '', limit: int = 20) -> dict:
    """过滤式查 cell DB(5304 结构);数值带源原样返回,不参与 rank fusion。"""
    return core.query_cell_db(
        topology=topology,
        rho_min=None if rho_min < 0 else rho_min,
        rho_max=None if rho_max < 0 else rho_max,
        feature=feature, load_mode=load_mode, limit=limit)


@mcp.tool
def get_structure(sample_name: str) -> dict:
    """单结构全档(身份/双密度/质量旗标/曲线与特征,全部带源)。"""
    return core.get_structure(sample_name)


@mcp.tool
def nearest_by_density(topology: str, rho_rel: float, k: int = 3) -> dict:
    """库内同拓扑密度最近邻 + applicability 距离;OOD 拓扑显式拒绝。"""
    return core.nearest_by_density(topology, rho_rel, k=k)


@mcp.tool
def retrieve_reference(query: str, limit: int = 5) -> dict:
    """文献笔记关键词检索(YAML front-matter 加权);返回 doi/适用域。"""
    return core.retrieve_reference(query, limit=limit)


if __name__ == '__main__':
    mcp.run()  # STDIO transport
