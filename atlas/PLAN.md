# ATLAS 构建计划(v1.0, 2026-06-10)

> 由两轮多智能体调研合成(22 agents,全部关键结论经对抗性核查):
> - `atlas/research/RESEARCH.md` — 架构映射 / 工具选型 / 物理勘误 / 仓库盘点 / 同类对标
> - `atlas/research/RESEARCH_NOVEL_TOPO.md` — Tier-2 新拓扑生成 / 快速物理裁判 / 表示与约束
>
> 上游决策依据:`atlas/HANDOFF.md`(含 §11 新拓扑增补)。冲突时以本计划与 RESEARCH 报告的**修正后数值**为准。

---

## 0. 已定稿的关键决策(loop 执行时不得重新辩论)

| 主题 | 决策 |
|------|------|
| Orchestrator | 留主会话(skill 驱动),不建 orchestrator subagent(subagent 不能再派生 subagent) |
| 9-agent 映射 | 6 worker = `.claude/agents/*.md` + tools 白名单;DB/RAG Retriever = 纯 MCP server;4 验证器 = background subagents;Evaluator = 白名单 + disallowedTools + PreToolUse hook(exit 2) + trace schema 校验 |
| K=3 回路 | skill(context fork)+ 文件计数器 + CAX 恢复阶梯(参数修补→LLM 重生成→上下文增强),K 耗尽出 Pareto 前沿 |
| 几何生成 | 主:仓内 `structure_set.py` 24 拓扑 + 自研 `tpms_generator.py`(manifold3d.level_set,Apache-2.0);辅:microgen 2.0.0b1 经适配层(GPL 隔离,法向反置已知);除名:MSLattice / TPMS Designer / FLatt Pack / lattpy / Open3D(无 cp313 轮子) |
| Printability 栈 | trimesh[easy](rtree+embreex 必装,缺则 fail loudly)+ manifold3d + scipy;FastMCP >=3.4,<4 STDIO;禁 VTK 静默回退、禁 GPL localthickness |
| 存储/RAG | Phase 1 **零向量库**:references/*.md(YAML front-matter 带 doi/source_type)+ thresholds/*.json + cell_db.sqlite(stdlib);Phase 2 触发后用嵌入式 LanceDB ≥0.33(BM25+向量 hybrid + RRFReranker);否决 Qdrant local / pgvector |
| RRF 边界 | 仅融合同条目空间排序;精确数值查表带源原样返回,**永不参与 rank fusion** |
| Generator 分层 | Tier-1 库内检索 / Tier-1.5 变形插值(slider→free_params)/ Tier-1.75 目录枚举(Lumpe-Stanković 17,087,如实称"枚举")/ Tier-2 生成(spinodoid 4 参数 GRF 旗舰 + LLM 提案×CMA-ES 抛光,零训练) |
| 验证升压链 | C1–C9 生成期硬门(确定性,先于一切 FEM)→ Tier-A 解析(G-A+Maxwell 倾向+平衡矩阵 SVD)→ Tier-B 自研 Timoshenko beam-FEM PBC 均质化(弃 Pynite,无周期 MPC)→ Tier-C FFT/共形体素均质化(GooseFFT+Willot vs fedoo+microgen,benchmark 后定)→ Tier-D ABAQUS 终审(≤3 finalist/查询,ALLKE/ALLIE 能量门) |
| 数据库角色 | "库不生成,库管裁判":24 拓扑 DB 不训练生成模型,用作快速裁判误差条的标定锚 + 约束门 24/24 回归套件 |
| OOD 纪律 | OOD 候选**禁用** cell-DB 最近邻 surrogate;l/d<5 拒绝 beam 认证(5–10 标修正估计);SEA/plateau 只有 Tier-D 是合法来源,快档数字一律 screening only;只有 Tier-D 可对 OOD 授予设计参考级 |

**物理数值勘误(全部落地时用修正值,出处见 RESEARCH.md §4 核实表):**
- Zhong 2023 = *Curr. Opin. Solid State Mater. Sci.* 27:101081(非 Composite Structures);300% 偏差仅限金属;"聚合物 ±10–30%"**无源**,标 inference
- TPMS 指数 1.31/1.39 仅限 SLM Ti-6Al-4V(转引,疑似一手 Yan 2015);PA12 锚点改 Chen 2023(DOI 10.1039/D2MA00972B,m≈1.17–1.29)
- PA12 lattice SEA 理性带:**0.3–8 kJ/kg**(典型 0.5–4;>8 implausible;>10 是金属);原 2–15 过乐观
- LPBF ×0.92 折扣无源 → 标"内部工程假设";PA12 σys=45 是 HP 数据表 48 MPa 拉伸强度的保守代理;AlSi10Mg 230 = 保守 Z 向(XY 270/Z 240)
- cell DB 实况:999 结构总计(非每拓扑 1000+),93 条缺曲线,**全库无 provenance 字段**(引用层阻断项),watertight 23/24(Cuboctahedron_Z 失败)
- C3 周期连通性正确条件 = quotient graph 单连通 + 圈 shift 矩阵 Smith 标准形 diag(1,1,1),与 3×3×3 超胞实算双轨互验(rank-3 条件已被驳回:互穿网反例)

---

## 1. Phase 1 任务清单(loop 按此执行)

状态记录在 `atlas/PROGRESS.md`,本表只定义任务。ID 前缀:A=零依赖地基,B=几何/验证工具链,C=agent 编排,D=验收。

### A 系列(无依赖,可立即开工)

| ID | 任务 | Definition of Done | 依赖 |
|----|------|--------------------|------|
| A1 | 修复 Cuboctahedron_Z watertight + 24 拓扑生成器函数化 | `test_manifold_all_cells.py` 24/24 两次重复运行全 OK;新 API `generate_cell(topology, slider, radius, n)` 返回 Manifold/Trimesh 且有单测 | — |
| A2 | cell DB 摄入 SQLite + provenance 列 | `atlas/data/cell_db.sqlite` schema 含 CHECK 约束;每条记录 source 非空(FEA 记录源=仓库管线+config 材性);93 条缺曲线带 quality flag;摄入脚本可复跑 | — |
| A3 | skill 文件结构落地(SKILL.md + references/ + scripts/) | scripts(gibson_ashby.py / maxwell_check.py / rel_density.py 等)返回 `{value, status, inputs_echo, source}` 且有解析值回归测试;所有阈值带 source 字段;**零勘误前数值出现**(SEA 带 0.3–8、Zhong 引文、TPMS 限定、×0.92/±10–30% 标 inference) | — |
| A4 | 双轨表示 schema + 24 种子转换 | `atlas-cell-graph/1.0` JSON schema(分数坐标+整数 shift 向量+free_params+lineage)与 `atlas-implicit/1.0` 定稿;24 种子拓扑转换为 schema 实例并通过 jsonschema 校验,构成永久回归套件 | — |
| A5 | 勘误写回 + 目录准备 | HANDOFF §9.4 改写为"零向量库+五条升级触发条件";Lumpe-Stanković 17,087 目录数据下载/格式确认;`atlas/references/errata.md` 列全部勘误及依据 | — |

### B 系列(几何/验证工具链)

| ID | 任务 | Definition of Done | 依赖 |
|----|------|--------------------|------|
| B1 | Printability MCP server v1 | 收编 `atlas/bench_printability{,2,3}.py`(已本机验证);五工具契约(validate_mesh / measure_min_feature / check_overhangs / check_powder_escape / measure_clearance)对 BCC 正负对照全过;单候选 <5 s;每响应含 `{value, threshold, pass, source}`;Raz 七点排粉表内插(跨拓扑标 inference);dfam_rules.json 版本化;embreex 缺失 fail loudly 有测试 | A1 |
| B2 | TPMS 生成模块 tpms_generator.py | ≥5 拓扑 × sheet/skeletal 全 watertight;密度二分定标误差 <2%;3×3×3 块 <5 s;t–密度标定曲线对照文献存档 references/ | A1 |
| B3 | 生成期硬门 C1–C8 | C3 = Smith 标准形 + 3×3×3 超胞双轨且一致;C4 = Maxwell 仅倾向标志 + 平衡矩阵 SVD;含节点碰撞/密度可解性/对称/图级 DfAM 预检;24 种子全过、注入的劣化反例全被杀;毫秒级 | A4 |
| B4 | C9 实现器 realize_graph.py | 任意合法 schema 图 → manifold3d watertight mesh;失败显式入 trace(防搜索偏置);与 A1 API 同栈 | A1, A4 |
| B5 | Novelty WL 哈希 | schema 图 → Weisfeiler-Lehman 哈希;24 种子互不碰撞;同构图改标号后哈希不变;查重接口 ready | A4 |
| B6 | strut 图 → ABAQUS 适配器 | schema 图(跨界边经 frac 0/1 边界节点)→ 现有 script_generator 管线可消费的输入;以一个词汇表外测试图端到端生成 preprocess 脚本验证 | A4 |
| B7 | 引用层 Phase 1:种子文献库 | ≥10 篇核心 + 6 篇尺寸效应文献(含 Kirchhof 2024 J Elasticity、Nasim 2021、Chen 2023)以 YAML front-matter(doi/source_type/validated_claims/validity_domain)入 `atlas/references/`;Grep front-matter 可命中 | A3 |
| B8 | Retriever + cell_db MCP server | `query_cell_db` + `retrieve_reference`;数值带源原样返回;全调用留痕(query/工具/命中数/返回源);"数值不参与 rank fusion"写入提示词并有测试 | A2, B7 |

### C 系列(agent 编排)

| ID | 任务 | Definition of Done | 依赖 |
|----|------|--------------------|------|
| C1 | 6 worker subagent 定义 | Interpreter / Generator / Printability / Surrogate / Mapper / Corrector 各为 `.claude/agents/*.md` + tools 白名单;白名单外调用被拒有验证;Interpreter 追问经主会话回环;Generator 工具行 = A1 API + B2 TPMS | A3, B1, B2, B8 |
| C2 | Evaluator + 证据强制 | PreToolUse hook 阻断非白名单(测试覆盖);输出不合 verification_trace schema 被拒;判决规则表(任何单项检查不得授予 PASS / margin≥1.0 含 FoS 不二次乘 / n<3 强警示 / inference 自动降级 / 最近邻 applicability 距离标志 / OOD 禁最近邻)逐条有正反用例 | B8, C1 |
| C3 | K=3 重生回路 skill | 注入必败候选 → 观察到 ≤3 轮重生且阶梯顺序正确(参数修补→重生成→上下文增强);K 耗尽输出含全部候选 trace 的 Pareto 前沿 | C1, C2 |
| C4 | 4 并行验证 agent 接线(静态先行) | 4 验证器并行扇出 5–8 候选 ~30 s 回齐;dynamic/shear 验证器只返回数据可用性 + informational;Evaluator 汇总判决含各验证器证据 | C1 |

### D 系列(验收)

| ID | 任务 | Definition of Done | 依赖 |
|----|------|--------------------|------|
| D1 | 三 case 端到端验收 | LPBF 支架 / SLS 吸能块 / MJF auxetic 垫三案例中文报告齐(裕度列 / trace / 三类来源 / 免责页脚);每个数字可溯源到工具调用或带 inference 标注;红线零违例 | C3, C4 |

### Phase 2 预告(Phase 1 验收后启动,届时细化 DoD)

- **P2-1** 自研 `beam_homog.py`(Timoshenko PBC 均质化,~300–500 行 scipy)+ 三重回归验证(自家 DB / Bastek PNAS 2022 / Lumpe-Stanković 抽样)+ 节点刚化修正标定 + 每拓扑类误差条进 Evaluator;审计仓内既有 `compare_*frame*.py`
- **P2-2** FunSearch 模式回路:Claude 离散提案 × pycma CMA-ES 抛光 × beam 裁判,≤3 轮对齐 K=3;SPD / Voigt-Reuss-HS / 跨档 20% 三道绝对门
- **P2-3** Tier-1.75 目录三级筛(Maxwell→G-A→beam)→ ABAQUS 终审
- **P2-4** Material/Process 修正系数矩阵(SLS-PA12 / MJF-PA12 / LPBF-AlSi10Mg)
- **P2-5** 动态/剪切特征提取扩展(feature_extract.py,解除动态验证 agent 断粮)
- **P2-6** LanceDB(仅当五条升级触发条件满足)

### Phase 3 预告

- **P3-1** Tier-C 体素裁判 benchmark(GooseFFT-fork+Willot+双网格误差条 vs fedoo+microgen)定主备
- **P3-2** spinodoid 旗舰全链:NumPy GRF 自研(规避 GIBBON AGPL)→ marching cubes → 打印检查 → orphan-mesh INP → ABAQUS 打标 1–3k 样本 → CPU 训练 f-NN/i-NN;SEA 用 BO 直驱显式 FEA;RVE 收敛研究替代尺寸效应查表(spinodoid 无单胞,Agent 8 查表不适用)
- **P3-3** 深度生成 inference-only(UnifyingTrussDesignSpace / DiffuMeta checkpoint;预测头只当启发,永不入 trace)
- **P3-4** ABAQUS 自动升压制度化(≤3/查询;显式准静态 1–6 h/次,实测日志校准)

---

## 2. Loop 执行协议

每次迭代严格执行:

1. **读取状态**:`atlas/PROGRESS.md`(任务状态+上次日志)→ 必要时回查本文件与两份 RESEARCH 报告;不重读已固化决策的原始论据,不重新辩论 §0 决策
2. **选任务**:取依赖全满足、状态 todo 的最小 ID 任务;同级可并行的(如 A1–A5)一次迭代可推进多个,但**每个任务的 DoD 必须独立验证通过才算 done**
3. **实现 + 验证**:DoD 里写"有测试"的必须真跑测试并贴输出;装新依赖先查 cp313 Windows 轮子存在性;失败不静默——记录 PROGRESS.md 后换路径或标 blocked
4. **更新 `atlas/PROGRESS.md`**:状态流转(todo→in_progress→done/blocked)+ 日志行(日期/做了什么/验证证据/遗留)
5. **git commit**(本地,不 push):每完成一个任务一次 commit,message 带任务 ID
6. **结束迭代**:ScheduleWakeup 继续(任务间隔短取 60–270 s;等长任务取 1200 s+);Phase 1 全部 done 且 D1 验收通过 → 停 loop,向用户汇报并请示 Phase 2

**环境约束**:Python 3.13.5 / Windows;禁 Open3D(无 cp313)、禁裸 trimesh(必须 [easy])、禁 GPL 直链(microgen 只经适配层、localthickness 不引入、GIBBON 不链接);版本全部钉死;ABAQUS 任务非 loop 自动触发范围(只生成脚本,提交由用户决定)。

## 3. 红线(每次迭代自检,违例 = 该产出作废重做)

1. "全局最优"必须带 **database-wide / 数据库范围内**限定
2. margin 已含 FoS,任何地方不得二次乘
3. Maxwell 只说倾向,不说判定
4. 报告/demo 一律保留"须经实物压缩测试验证"免责;高风险场景标"仅作筛选"
5. **可信度四层(检索/插值/枚举/生成+验证)永不混层叙述**;Tier-2 产物永不以 Tier-1 口径呈现
6. 快速档(Tier-A/B/C)的 SEA/plateau 数字一律 screening only,永不通过 margin 门;OOD 禁用 cell-DB 最近邻
7. 无源数字必须标 inference 并自动降级,绝不以引用形式泄出
8. 新颖性措辞限定"ATLAS 词汇表/数据库范围外"并过 WL 哈希查重;Tier-1.75 称"枚举"不称"生成"
