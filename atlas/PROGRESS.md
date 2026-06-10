# ATLAS 构建进度(loop 状态文件)

> 任务定义与 DoD 见 `atlas/PLAN.md`;决策依据见 `atlas/research/RESEARCH.md` 与 `atlas/research/RESEARCH_NOVEL_TOPO.md`。
> 状态:todo / in_progress / done / blocked(blocked 必须写明阻塞原因与解除条件)。

## Phase 1 任务状态

| ID | 任务 | 状态 | 备注 |
|----|------|------|------|
| A1 | Cuboctahedron_Z 修复 + generate_cell API | done | 24/24×2 确定性通过;34 项单测全过 |
| A2 | cell DB → SQLite + provenance | done | 5304 结构物理键归并;41 项测试全过 |
| A3 | skill 文件结构(修正后数值) | todo | |
| A4 | 双轨 schema + 24 种子转换 | todo | |
| A5 | 勘误写回 + Lumpe-Stanković 目录准备 | todo | |
| B1 | Printability MCP v1 | todo | 收编 atlas/bench_printability{,2,3}.py |
| B2 | TPMS 生成模块 | todo | |
| B3 | 硬门 C1–C8 | todo | |
| B4 | realize_graph.py(C9) | todo | |
| B5 | Novelty WL 哈希 | todo | |
| B6 | strut 图 → ABAQUS 适配器 | todo | |
| B7 | 种子文献库(≥10+6) | todo | |
| B8 | Retriever + cell_db MCP | todo | |
| C1 | 6 worker subagents | todo | |
| C2 | Evaluator + 证据强制 | todo | |
| C3 | K=3 重生回路 skill | todo | |
| C4 | 4 并行验证 agent 接线 | todo | |
| D1 | 三 case 端到端验收 | todo | Phase 1 完成判据 |

## 日志

- **2026-06-10**:两轮多智能体调研完成(22 agents,对抗核查全过):`RESEARCH.md` + `RESEARCH_NOVEL_TOPO.md` 落盘;HANDOFF §11 增补(新拓扑主攻);PLAN v1.0 建立;loop 启动。关键勘误已固化:Zhong 2023 出处、TPMS 指数适用域、PA12 SEA 带 0.3–8、cell DB 实况 999 总计/无 provenance/23-24 watertight、C3 连通性 Smith 标准形条件。
- **2026-06-10 A2 done**:`atlas/data/ingest_cell_db.py` → `cell_db.sqlite`(structures 5304 / curves 3946 / features 47736,全表 source 非空 CHECK + 枚举 CHECK,可复跑确定性)。**数据实况修正(供 A5 errata)**:① 调研报告"93 条缺曲线"为误,实为 **43 条**(18 缺 DynaShear / 18 缺 DynaCompre / 7 双缺,全部是动态工况);② CSV 样本名带浮点累积伪影(0p30000000000000004),按名合并会身份分裂——已按物理键 (topology,size,round(r,6),slider) 归并,**999 个 JSON 结构全部物理存在于 CSV**(JSON ⊂ CSV,5304 = 24×13×17 整格);③ JSON FEA 密度与 CSV smoothed 密度是两种量(中位差 1.5%、最大 22%),双列并存(density_fea/density_smoothed),canonical 取 FEA 优先;④ 442 行 CSV density 为空,其中 432 结构完全无密度值;⑤ classify_topology 对全名(Octet_truss)会误判,ingest 内做前缀适配(Octet→stretch 等)。测试 41 项全过(约束强制/计数独立重算/已知值抽查/曲线往返/可复跑)。遗留:无。
- **2026-06-10 A1 done**:Cuboctahedron_Z 根因 = 两个叠加退化:(1) 球-柱等半径整圆相切(SPHERE_RADIUS_RATIO_SCRIPT=1.0,采样相位敏感:seg23 过/24/32 挂)→ 网格实现层节点球 +0.1% 扰动(TANGENCY_EPS,不碰仿真 config);(2) manifold3d 布尔三角化在 45° 对称杆系的精确重合切线上产生顶点全同零面积翻盖对(法向 [0,0,0],焊接后 4 面共享边)→ welded 形态成对删除重复面(注意:不能删全部零面积面,非重复退化 sliver 承担连通性,实测 Auxetic 删之开洞)。新 API `atlas.geometry.generate_cell(topology, slider, radius, n, ...)` 返回 CellMesh(.manifold/.trimesh/.trimesh_raw/.is_watertight 双轨判据);`test_manifold_all_cells.py` 改用 API + 双运行确定性检查:24/24×2 deterministic 通过;`atlas/tests/test_generate_cell.py` 34 项全过(含 seg 16/23/24/32 回归、n=2 阵列、确定性)。验证证据:pytest 34 passed;回归脚本输出 "24/24 watertight x2 runs, deterministic"。遗留:无。
