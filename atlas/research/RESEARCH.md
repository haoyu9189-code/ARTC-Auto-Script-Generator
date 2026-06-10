# ATLAS 基础调研综合报告(RESEARCH.md)

> Agentic Toolkit for Lattice Architecture Synthesis · 调研综合(synthesis)
> 基于 7 条调研线(cc-architecture / lattice-tools / printability / rag-stack / physics-lit / repo-audit / precedents)的已核实结论
> 上游文档:`atlas/HANDOFF.md`(2026-06);专项报告:`atlas/research/RESEARCH_NOVEL_TOPO.md`
> 日期:2026-06-10 · 状态:定稿,可直接驱动 Phase 1 执行

---

## 1. 执行摘要

本轮调研对 HANDOFF.md 固化的 9-agent 架构、工具选型、物理阈值与同类系统定位做了**逐项独立核实**(含本机复现实验与一手文献查证),总体结论:**架构方向全部成立,但若按 HANDOFF 字面执行会踩中四个具体的坑**,本报告已给出修正方案。

**成立的部分**:

1. **Claude Code 原语映射可行**:Orchestrator 留在主会话(subagent 不能再派生 subagent,官方文档确认),6 个 worker 用 `.claude/agents/*.md` 自定义 subagent + frontmatter `tools:` 白名单,4 个并行验证 agent 用 background subagents(Phase 1 不用实验性的 agent teams),Evaluator 的"只认工具证据"用工具白名单 + PreToolUse hook(exit code 2 阻断)强制执行,K=3 重生回路用 skill(context: fork)+ 文件计数器实现。
2. **可打印性检查全链路已在本机验证通过**:trimesh + manifold3d + scipy 五项检查(watertight/manifold、最小特征、悬垂、困粉逃逸、间隙)在 10 万–100 万三角面网格上单候选 <5 s(需 embreex),5–8 候选并行扇出约 30 s,基准代码已在 `atlas/bench_printability{,2,3}.py`。Raz 2025 的 MJF 排粉表逐字核实无误,可直接落为查表。
3. **核心物理公式全部核实**:Maxwell 公式、Deshpande-Fleck-Ashby octet 系数、Gibson-Ashby bending 标度律均与一手文献逐式对上;FCCZ/FBCCZ 反例溯源到 Nasim & Galvanetto 2021(恰好是 MJF PA12)。
4. **差异化定位经对标确认仍然成立**:generate-then-verify 与多 agent 编排已是平台级常规(MatterGen、A-Lab、AtomAgents、Microsoft Discovery),ATLAS 可辩护的新颖性在于"整库穷举 + 秒级解析裁判 + 面向力学小白的三级引用分级审计链"的**组合**,且 A-Lab 被 Nature 更正一事为"多模态证据、不信任单一自动裁判"提供了最有力的反面教材。

**必须修正的部分(详见 §4 与 corrections 清单)**:

1. **文献勘误**:Zhong et al. 2023 的期刊是 *Current Opinion in Solid State and Materials Science* 27:101081(非 Composite Structures),其 300% 偏差结论仅限金属;"聚合物 ±10–30%" 一句**无文献来源,标记待核实**。TPMS 指数 gyroid≈1.31 / diamond≈1.39 是 Abdulhadi 2023(Eng. Reports **5(2)**:e12566)综述里转引的 **SLM Ti-6Al-4V** 结果,不可用于 PA12;疑似一手来源 Yan 2015 尚未翻原文核对(待核实)。
2. **数值勘误**:PA12 lattice SEA 合理区间 2–15 kJ/kg 偏乐观,实测 MJF PA12 octet(ρ̄=0.30)仅 0.63–0.92 kJ/kg,准静态上限约 6–8 kJ/kg,修正为 **0.3–8 kJ/kg**;LPBF ×0.92 表面缺陷折扣**查无文献出处**,必须按引用层规则降级为"内部工程假设"。
3. **工具勘误**:MSLattice / TPMS Designer / FLatt Pack 均为 GUI/MATLAB、无脚本接口,从 Generator 工具行删除;Open3D 无 Python 3.13 轮子(本环境 3.13.5 无法 import),从 Printability 依赖中删除;HANDOFF §9.4 的 Qdrant/pgvector 均不适合单用户本地 Windows,Phase 1 **不上向量库**(语料 5–20 篇 << Anthropic 自家 20 万 token 阈值),Phase 2 触发条件满足后再上嵌入式 LanceDB。
4. **库存勘误**:仓库 cell DB 实为 **999 个结构总计**(每拓扑 ≤45 变形,非"每种约 1000"),其中 93 条缺至少一条 FEA 曲线;watertight 测试 **23/24 通过,Cuboctahedron_Z 失败**(可复现);特征 CSV 为 5,304 行 / 9–10 个力学量;全库记录**无 source/provenance 字段**——这是引用层的阻断项,Phase 1 必须补。

**最重要的单条行动建议**:Lattice Generator 不引外部重型工具——**复用仓内 structure_set.py(24 strut 拓扑)+ 在已装的 manifold3d(Apache-2.0)上加约 150–250 行 `level_set` TPMS 模块**(本机已验证 watertight、单 cell 0.09 s),microgen 2.0.0b1(GPL-3.0)经适配层作 fallback。这条路线零新依赖、许可证干净、与现有 watertight 管线同构。

---

## 2. 逐条调研线结论

> 体例说明:各线结论均为**核实后**版本;原结论被 refuted(证伪)的,此处只出现修正后表述;无法核实的标 **[待核实]**。

### 2.1 cc-architecture(Claude Code 原语映射)

**核实成立的结论:**

- **Orchestrator 留在主会话,不做成 subagent**。官方文档(code.claude.com/docs/en/sub-agents)明确 subagent 不能再派生 subagent(`Agent(agent_type)` 在 subagent 定义里无效),而 Orchestrator 要调度其余 8 个 worker(含 4 并行验证),只能是主线程。落地:不建 `.claude/agents/orchestrator.md`,编排逻辑放主 skill / 主 CLAUDE.md。
- **Requirement Interpreter = 只读 subagent + RAG 术语工具**。注意一个对抗性核实出的细节:**subagent 无法使用 AskUserQuestion**(即使写进 tools 字段也不生效),所以 HANDOFF 要求的"主动追问"必须经 Orchestrator/主会话回环——与 HANDOFF §6 把 Phase 0 问询放在"skill 启动前"的设计天然一致。
- **Printability Checker = MCP server(非裸 subagent)**,与 HANDOFF §9 Phase 1 第 2 项逐字吻合;stdio 本地 server 模式有官方文档支持。
- **Mechanics Surrogate = subagent + cell DB MCP + 本地 gibson_ashby.py / maxwell_check.py 脚本**,数据库走 MCP 的模式有官方 PostgreSQL 范例佐证(HANDOFF 用 SQLite/Parquet,模式同构)。
- **Evaluator 的"只认工具证据"三层强制**:(1) frontmatter `tools:` 白名单(仅验证类 MCP 工具 + 验证脚本);(2) `disallowedTools` 显式 deny WebFetch/AskUserQuestion/Skill/Write/Edit(权限优先级 Deny > Ask > Allow,官方确认);(3) PreToolUse hook 阻断白名单外调用(exit code 2)。**绝不只靠提示词**。输出再加 PostToolUse hook 按 JSON Schema 校验 verification trace(status/confidence/tool_calls/margin/rationale/caveats 必填)。
- **K=3 重生回路 = skill(context: fork)+ 文件计数器**(如 `.claude/tmp/atlas_regen_counter`),循环逻辑:spawn Evaluator → fail 且 K<3 → 带 fail_reasons spawn Generator → K++;K 耗尽出 Pareto 前沿。不用 /loop。
- **4 并行验证 agent:Phase 1 用 4 个 background subagents**(`verifier-{static,dynamic,shear,printability}.md`),agent teams 是实验特性(需环境变量开启、teammate 不能再派生),留作 Phase 2 可选升级。
- **Skills vs Subagents 分工**:可复用、多阶段、流程型 → skill(主编排、Phase 0 问询);隔离任务 + 受限工具 → subagent(各 worker)。skill 的动态注入 `` !`cmd` `` 只在加载时执行一次,运行期动态数据一律走 MCP 工具。
- **MCP 注册**:全部 ATLAS server 用项目级 `.mcp.json`(进版本库,团队共享);核心 server(cell_db、retriever)`alwaysLoad: true`;tool search 需模型支持 tool_reference(Haiku 不支持,Fable 支持)。
- **引用层在 MCP 工具输出内嵌 source 字段**(`{text, source, source_type, confidence}`),不做事后补注;报告生成端按 source_type 三分类(学术 DOI / 厂商标准 / 推测)。

**修正后表述(原结论已证伪,以下为唯一有效版本):**

- **Lattice Generator 的工具行**:subagent + Bash 的架构成立,但 **MSLattice 不可脚本化**——它是闭源 MATLAB GUI 独立程序,无 CLI、无 Python API,不能进 agent 管线;HANDOFF §4 行 3 所列四件工具中仅 microgen 与 PyScaffolder 可被 Bash 驱动。工具行替换方案见 §2.2(内部生成器 + manifold3d TPMS 为主)。
- **Material/Process Mapper 的查表通道**:HANDOFF 原文是"修正系数矩阵查表 + RAG",**不是 CLAUDE.md**(HANDOFF 全篇无 CLAUDE.md 字样);HANDOFF 明确指定 MCP 封装的只有 cell DB(§9.5)与 Printability(§9.2)。把修正矩阵也走同一 MCP 查询层是**合理的工程外推**(本报告决策表采纳之),但须知这是推断而非 HANDOFF 已定条款。

### 2.2 lattice-tools(点阵/TPMS 生成工具选型)

**核实成立的结论:**

- **TPMS 生成零新依赖**:已装的 manifold3d 3.4.1(requirements.txt 钉 >=3.0.0,Apache-2.0)自带 `Manifold.level_set`(Marching-Tetrahedra,构造即 manifold)。本机独立复现:solid-network gyroid 与 sheet gyroid 均 watertight(单 cell 0.09 s;3×3×3 sheet 块 563,724 面 2.67 s)。新模块约 150–250 行:gyroid / Schwarz-P / Schwarz-D / Schoen-IWP / Neovius 的隐式方程,sheet(|f|−t)与 skeletal(f−t)两变体,相对密度用对 t 二分(Manifold 体积,5–10 次求值)。
- **microgen 2.0.0b1(3MAH)是最强外部选项,已在本机干净 venv(Windows 11 / Python 3.13.5)装通跑通**:19 个 TPMS 面函数、精确密度定标(要 0.30 得 0.300)、梯度/柱面/球面 TPMS、spinodoid、12 种预置 strut 点阵、FEM 体网格。**三个实测缺陷**:GPL-3.0(对外分发软件会触发 copyleft)、beta 期 API 漂移(1.x→2.0 已删改接口)、**导出 STL 法向反置(trimesh 签名体积为负)且非 watertight**——任何消费方必须先 `fix_normals()`。定位:fallback / 功能扩展(梯度密度、混合 TPMS、spinodoid、均质化用周期四面体网格),钉死 `microgen==2.0.0b1`,置于适配层之后。
- **PyScaffolder 1.5.3(MIT,Windows cp38–cp313 轮子,2025-07 仍活跃)**:定位是"给任意输入 STL 做 TPMS 填充",不做单胞库生成——留作 Phase 2+ 零件级填充的小众选项。
- **被除名的工具**:MSLattice(闭源 MATLAB GUI,GitHub 仅 4.56 MB 编译 exe,无源码无许可证)、TPMS Designer(MATLAB-only,停滞)、FLatt Pack(非商用 + 内置过期机制,当前 build 2026-07-30 失效,复现性危害)——三者从 HANDOFF §4 行 3 删除;MSLattice 仅可作 TPMS 密度标定曲线的离线人工对照。lattpy 是凝聚态 Bravais 晶格包,领域错配,勿因名字混入文档。2024–2026 扫描的其余候选(ASLI/AGPL、LisbonTPMS-tool、TPMSgen、blender-tpms、Metafold 付费云 API)均不改变主次选型。
- **总决策"复用内部生成器 + manifold3d level_set 薄层,严格优于整体引入外部工具"成立**:外部工具无一覆盖仓内 24 种 strut 拓扑(microgen 预置约 12 种),整体切换等于扔掉已验证的 watertight 管线。

**修正后表述(原结论已证伪):**

- **仓内 24 种拓扑的 watertight 现状:23/24 通过,非全过**。独立两次运行 `test_manifold_all_cells.py`,**Cuboctahedron_Z**(15 节点 38 杆)布尔并集 `is_watertight=False`(体积 82.04 但 FAIL),脚本自身汇总行即打印 "SOME FAILED"。前半句成立:config.py 定义 24 种、structure_set.py 全部可生成、并集走 manifold3d。**Phase 1 第一项工程任务就是修这个 cell。**

### 2.3 printability(可打印性检查管线)

全部结论经本机复跑确认(数值复现一致或在运行间正常波动内):

- **双引擎校验**:trimesh(`is_watertight / is_winding_consistent / is_volume / euler_number / body_count`,诊断)+ manifold3d(`Mesh.merge() → Manifold.status()` 返回 Error 枚举,权威判决),0.03–1.2 s @ 100 万面;故意破坏的网格两引擎都能抓到。`Mesh.merge()` 能从 STL 顶点汤恢复 manifold(137,436 重复顶点 → Error.NoError,复现一致),**用户上传 STL 因此是受支持的摄入路径**;注意 merge 文档自述 "best-effort",不保证万能,残余 NotManifold 走 pymeshfix(已装)修复后复检。
- **genus/Euler 是免费拓扑签名**:3×3×3 BCC genus=126、6×6×6 genus=1170,与图论 cycle rank(E−V+1)解析值逐一吻合——同一拓扑重生成间 genus 变化即报警(杆件熔并或布尔破损)。
- **最小特征三分支**:ATLAS 自产参数化点阵 → **解析直接读杆径**(structure_set 已带节点+杆图,即时、精确、引用"generator parameters");上传网格 → ray 法厚度(SDF 式,BCC 上恢复 1.0 mm 真值误差 0.1–0.5%,偏差恰为多边形内切 cos(π/seg))为主 + **体素 EDT(scipy `distance_transform_edt`,230 万体素 <1 s)做全局交叉核验**(能抓 ray 采样漏掉的布尔结点细颈);medial axis 对生成点阵无必要。**硬性依赖陷阱**:默认 trimesh 装机缺 rtree/embreex,`proximity.thickness` 与 `ProximityQuery` 运行期直接 ModuleNotFoundError(本机复现)——**必须钉 `trimesh[easy]`**(rtree 1.4.1、embreex 4.4.0 均有 cp313 Windows 轮子)。
- **悬垂检查是毫秒级面法向分类**(14 ms @ 9.3 万面):BCC 35.26° 斜杆在 45° LPBF 阈值下被正确标出;工具必须带 `process` 参数——**只对 LPBF 设门禁,SLS/MJF 粉床自支撑,返回 informational**。参考实现 pyslm。
- **困粉检查端到端验证通过**:occupancy 栅格 + `scipy.ndimage.label` 自边界 flood fill;密封壳 + 开放点阵正负对照均正确(938 vs 期望 ~805 mm³,+16% 为 pitch=0.25 mm 量化偏置;开一个 2 mm 排粉孔后困粉降到 1 mm³)。**pitch ≤ 阈值/4,且工具输出必须报告量化容差**,否则 Evaluator 会误杀边界候选。Raz 2025 的 7 点密度–可清深度表直接内插落表(见 §4)。
- **间隙测量**:`manifold3d.Manifold.min_gap` 对双体精确返回 0.8000 mm(190 ms);多体场景先 `decompose()`;**重叠体返回 0,须配布尔交体积区分"设计贴合"与"干涉"**;连通点阵内部孔隙间隙走 void 相 EDT 或参数化解析。
- **性能预算(实测,无 GPU)**:有 embreex 时单候选 <5 s(occupancy 生成是唯一瓶颈);**绝不允许回退到 vtkSelectEnclosedPoints(350 s,不可用),embreex 缺失要 fail loudly**。5–8 候选并行扇出 ~30 s。预计算缓存(按网格哈希):manifold 状态、genus、体积/相对密度、面法向+面积、解析最小杆径、occupancy.npz;按需重算:逐 build 方向悬垂、逐工艺排粉深度、对外壳 min_gap。**注意:TPMS/level_set 网格与异构布尔会更慢,承诺 <5 s 预算前需对 TPMS 候选重新基准。**
- **依赖集(全部 cp313 Windows 轮子核实)**:`trimesh[easy]>=4.12, manifold3d>=3.4, scipy>=1.16, numpy>=2, fastmcp>=3.4,<4`。**排除 Open3D**(0.19.0 止步 cp312,issue #7318 未决,本环境 3.13.5 直接 import 失败)与 **GPL-3.0 的 localthickness**(用 porespy/MIT 或 ~30 行自研 EDT 替代)。FastMCP 现状:3.4.2(2026-06-06,Apache-2.0),STDIO 本地传输,注册 `claude mcp add atlas-printability -- uv run --with atlas-printability fastmcp run server.py`;**3.x 对 2.x 有破坏性变更,务必钉主版本**。
- **五工具契约**(逐项映射 HANDOFF §4 行 4 与 §5 阈值):`validate_mesh / measure_min_feature / check_overhangs / check_powder_escape / measure_clearance`,每个响应必含 `{value, threshold, pass, source}`(DOI / 厂商 URL / "generator parameters"),直接喂引用层与 Evaluator。阈值放版本化 `dfam_rules.json`(逐行带 source 字段),不硬编码。

### 2.4 rag-stack(检索与存储栈)

**核心判断(已核实):Phase 1 不上向量库,上了就是过度工程。**

- 5–20 篇种子文献 ≈ 250–3,000 chunks,远低于 Anthropic 官方"知识库 <20 万 token 直接放上下文、无需 RAG"的阈值(原文逐字核实于 anthropic.com/news/contextual-retrieval)。仓内已有零基建先例:material-assistant skill 直接 pandas 读 CSV(999 数据行)。
- **Phase 1 三件套**:(a) `atlas/references/*.md` 每篇文献一个结构化笔记,YAML front-matter 带 `doi / source_type / validated_claims / validity_domain`,skill 用 Grep/Read 检索;(b) `atlas/data/thresholds/*.json` 阈值表,逐条 `{value, unit, source_doi, source_type}`;(c) `atlas/data/cell_db.sqlite`(stdlib sqlite3,零新依赖)从现有 CSV 摄入并**补 provenance 列**,由唯一一个 MCP server 暴露 `query_cell_db(topology, rel_density, load_mode, k)`。SQLite 优于 Parquet+DuckDB:全库上限 ~9.6 万行(24×~1000×4,HANDOFF §3 算术),provenance/修正系数需事务性原地改,Parquet 不可变。
- **HANDOFF §9.4 "Qdrant 或 pgvector" 应改写**:Qdrant local mode 官方定位 dev/test-only(源码常量 <20,000 点告警、portalocker 排他锁在 Windows 有已知问题、落盘格式与 server 模式不兼容——文件级无升级路径,只能重灌);pgvector 在 Windows 要自己编译或用第三方二进制(andreiramani)外加常驻 PostgreSQL 服务,为 3 千 chunk 语料不值。两者对"单用户本地 Windows"都是错误默认值。
- **Phase 2 目标栈(触发后才上)**:嵌入式 **LanceDB ≥0.33**(Apache-2.0,win_amd64 轮子,原生 BM25 FTS `use_tantivy=False` + 向量 hybrid search,内置 RRFReranker 默认 RRF 融合);单文件备选 sqlite-vec(0.1.9 仍 pre-v1 alpha,存储格式可能破坏);Chroma 仅作 fallback。注意 LanceDB 自身 pre-1.0,钉版本并藏在 MCP server 接口后。
- **嵌入**:Anthropic 无 embeddings API,官方指向 Voyage AI——voyage-4-lite $0.02/1M(账户 200M 免费额度,ATLAS 全语料 <1M token,成本≈0);本地路线 fastembed 0.8.x(ONNX,无 torch,默认 bge-small-en-v1.5,384 维)。**先定知识库语言政策**:references 保持英文(推荐,源文献本就是英文)则 bge-small-en 够用;双语则 bge-m3 或 voyage-4。
- **RRF 设计纪律(对 HANDOFF §4 行 7 的关键修正性澄清)**:RRF(k=60,Cormack et al. SIGIR 2009,DOI 10.1145/1571941.1572114)只融合**同一条目空间**的排序列表——(a) 文本检索内部 BM25+向量(LanceDB 原生);(b) 可选:Orchestrator 层融合两份**拓扑候选排名**(cell DB k-NN vs 文本证据频次)。**精确数值查表结果是权威事实,带源原样返回,绝不与文本 chunk 做 rank fusion**——否则真值会被松散相关的文本淹没,直接腐蚀引用层。此规则写进 Retriever subagent 提示词。
- **单写者纪律**:所有文件/DB 访问(SQLite、未来 Lance 数据集)统一经唯一 MCP server 进程,skill 不直接开 DB 文件——绕开 Windows 上一切嵌入式锁问题。**Retriever server 从第一天起记录每次调用**(query / 工具 / 命中数 / 返回源),让升级触发条件 #2 可度量,同时本身就是项目卖点的审计链。
- **五条升级触发条件**(写回 HANDOFF §9.4):语料 >~100 文档或 >~5K chunks(~20 万+ token);verification-trace 审计发现关键词检索漏召;出现跨语查询;Grep 检索 >2 s 或 token 烧穿;多用户/服务器部署。当前一条都不满足。

### 2.5 physics-lit(物理与文献核实)

核实结果全部汇入 §4 物理与阈值核实表;此处只列超出表格的增量结论:

- **种子引文表(最终版)**——核心:Gibson & Ashby 1997(10.1017/CBO9781139878326)、Deshpande-Fleck-Ashby 2001 JMPS(10.1016/S0022-5096(01)00010-2)、Deshpande-Ashby-Fleck 2001 Acta Mater(10.1016/S1359-6454(00)00379-7)、Nasim & Galvanetto 2021(10.1016/j.mtcomm.2021.102902)、Abdulhadi 2023(10.1002/eng2.12566)+ Yan 2015(10.1016/j.jmbbm.2015.06.024,待翻原文)、Raz 2025(10.3390/polym17202804)、Zhong 2023(10.1016/j.cossms.2023.101081)、Chen 2023(10.1039/D2MA00972B,PA12 MJF octet 指数 m≈1.17–1.29,**聚合物锚点**)、Ashby 2006(10.1098/rsta.2005.1678)。
- **尺寸效应文献(论文腿弹药)**:Onck 2001 / Andrews 2001(边界层理论,模量/强度随试件-胞元比上升,6–8 胞饱和;修正函数形 property(n)=bulk·(1−c/n))、Tekoglu 2011(综述:尺寸效应**符号**取决于边界条件与加载类型)、Yoder 2018/2019(周期点阵尺寸效应,micropolar 连续体低估一个量级;edge-softening 逐拓扑机理)、**Kirchhof 2024(J. Elasticity 156:79–93,10.1007/s10659-023-10037-6)——直接命中"尺寸效应符号"开放问题**(CT 虚拟试验见一致负效应但散差大)、Carneiro 2018(auxetic 胞数研究,最近先行)。
- **文献空白确认(论文机会)**:截至 2026-06,**没有任何已索引文献把 Poisson ratio 符号与尺寸效应方向联系起来**——HANDOFF §3 的候选机理是未被占领的领域,论文定位应对标 Kirchhof 2024 的开放问题并明确声明该联系为本工作贡献。AM 点阵收敛佐证:EBM Ti64 BCC 在边长 ≥4 胞收敛 **[待核实:综述转引,需追一手]**,支持 "n<3 强警示" 规则。
- **核实方法学余量**:DFA 2001 与 Acta Mater 2001 已对到一手全文(fleckmech.org 存档),但 Gibson-Ashby 1997 书第 5 章、Yan 2015 原文仍在 paywall 后,系数核实部分依赖收敛的二手引用(COMSOL 文档、Ashby 2006 全文等)——若 ATLAS 报告要以一手引用输出这些指数,**须先开原文 PDF**。

### 2.6 repo-audit(仓库资产盘点)

**核实成立的可复用资产:**

- **Scaling 修正模型即用**:`scaling/scaling_analyzer.py` 实现 σ(ε,n) = σ∞ + α/n + β/n²(CurveScalingModel dataclass、逐应变点最小二乘、R²/RMSE/MAPE 质检),另有 `prediction_engine.py` 应用层;注意 n 值只有 2 个时退化为 2 参数拟合(β 强制 0)。Size-Effect Corrector 的运行期查表只欠 MCP 包装 + SQLite 后端。
- **Printability 种子代码**:`test_manifold_all_cells.py`(manifold3d+trimesh watertight 校验)与 `demo_remesh.py`(pyvista+manifold3d 布尔并 STL 导出)真实存在且可跑——均为演示/测试级,产品化要重构。
- **24 种拓扑生成器**:`structure_set.py` `get_crystal_structure(name, slider=8)` slider 0–8 参数化,24 种全可生成(Cubic/Octahedron 几何对 slider 不敏感,故各只有 5 个变形)。
- **Abaqus 模板**(`model/Static_model.py`、`Dynamic_model.py`)为 1×1×1 cell 原型——多胞阵列仿真未自动化(Phase 3 事项,亦是 §11 Tier-2 全 FEA 终审的前置)。
- material-assistant skill 的 `requirement_parser.py` 与 `confidence_scorer.py` 可作 Requirement Interpreter / Evaluator 的子组件复用;**其顶层 3-phase k-NN+PCA 编排与 ATLAS 多 agent 验证链正交,不可整体照搬**(混淆"找现有"与"生成+验证")。

**修正后表述(原结论已证伪):**

- **cell DB 实际规模**:`feature_data.json` 为 **999 个结构总计**(非每拓扑 1000+):21 种 ×45、Octet_truss 44、Cubic/Octahedron 各 5;且 **93/999 条缺至少一条四工况曲线**(102 条空/近空曲线)。HANDOFF §3 "每种约 1000 变形" 与盘面证据不符 **[待核实:是否另有未入库数据;按盘面证据执行]**。
- **特征 CSV 实际规模**:`extracted_features_smoothed.csv` = **5,304 条数据记录**(5,305 行含表头);15 列中 5 列是标识/几何输入,**力学响应量 9 个**(comp_EA/stiffness/densified/yield、shear_EA/stiffness/yield、dyna_comp_EA、dyna_shear_EA),算上 density 10 个——"15 个力学性能"是列数误读。**动态刚度/屈服/峰值与剪切峰值未提取**,4 工况只有 2 个全特征化,Phase 2/3 动态验证 agent 会断粮,需扩 `feature_extract.py`。

**确认的缺口(全部进 Phase 1/2 任务):**

1. **全库无 source/provenance 字段**(feature_data.json 与 CSV 皆无)——引用层阻断项,最高优先级。
2. 无 Material/Process 修正矩阵(SLS-PA12 / MJF-PA12 / LPBF-AlSi10Mg)。
3. 无 TPMS 拓扑代码(由 §2.2 的 manifold3d level_set 方案补)。
4. Scaling 模型未接 runtime 查表;`generate_script/consolidated/` 的 N=1–5 多胞实验数据未并入拟合管线。
5. 无拓扑分类字段(stretch/bending/hybrid,按 Maxwell M=b−3j+6 计算补列)。
6. DfAM 阈值仅在文档,未在生成/检查代码中强制。

### 2.7 precedents(同类系统对标)

详见 §6 对标表。核心结论:四个集群(材料发现回路 / LLM-超材料设计 / CAD-FEA agent / 工业平台)ATLAS 全部有交集、无一重合;六条**可直接采纳的设计模式**:

1. **SimAI 模式**:每次代理预测计算 (topology, ρ̄, load_mode) 空间最近邻距离,作 applicability-domain 标志映射到 Phase 0 置信度档;超出 DB 凸包显式标"外推"。这与 §11 的 OOD 规则(分布外不得用最近邻 surrogate)互为表里。
2. **CAX-Agent 恢复阶梯**:K=3 回路内先确定性参数修补(调 ρ̄ / 胞数)→ 再 LLM 重生成 → 再上下文增强(实证把完成率 69%→93%),省 token。
3. **CADCodeVerify 模式**:Evaluator 从 Phase 0 确认 spec 派生逐候选核验问题清单,而非只跑通用规则。
4. **A-Lab 教训(单一自动裁判过信)**:任何单项检查(G-A 单独 / DB 查表单独 / printability 单独)不得授予 PASS,须多模态一致;Evaluator 记录每个判决依赖哪些检查。A-Lab 43 项"新材料"被 Palgrave/Schoop 系统性证伪、Nature 2026-01 发更正——这是引用链卖点的最佳反面论据。
5. **FEABench 教训(静默默认值)**:所有验证脚本返回 `{value, status, inputs_echo, source}`,区分 computed 与 default/fallback——FEABench 记录了 agent 把 COMSOL 默认 20 °C 当计算结果导出;另:15 道金标 COMSOL 题无一被完整正确解出,佐证 ATLAS 用确定性解析脚本当裁判、LLM 只做路由的决策。
6. **ChemCrow 教训(LLM 裁判流利度偏好)**:EvaluatorGPT 实证偏好流利的幻觉答案胜过工具落地的正确答案——这是"Evaluator 只认工具证据"的可引用实证;同时报告文本必须**从 trace 生成、数字抄录不转述**,MCP server 边界做输入校验(单位/量程对 DfAM 表)。

**对 AtomAgents 的精确表述(修正后)**:AtomAgents(PNAS,10.1073/pnas.2414074122)= LLM 假设生成 + 知识检索 + **MD 物理仿真(人写 LAMMPS 脚本以 Python 函数集成)** + 多模态证据(数值 + 仿真图像);**不含深度代理模型作为工作组件**(深度学习模型在原文仅为"未来方向")。采纳其多模态证据呈现(报告 trace 含几何渲染图 + 裕度条形图)。

---

## 3. 决策表

| # | 决策项 | 选定方案 | 理由(核实依据) |
|---|--------|----------|------------------|
| D1 | Orchestrator 形态 | **主会话**(主 skill / 主 CLAUDE.md),不建 orchestrator.md | subagent 不能派生 subagent(官方文档);需调度 8 worker 含 4 并行 |
| D2 | 9-agent → 原语映射 | Interpreter/Generator/Checker/Surrogate/Mapper/Corrector = `.claude/agents/*.md` subagent(frontmatter `tools:` 白名单);Retriever = **纯 MCP server 非 subagent**;Evaluator = subagent + hooks;4 验证器 = background subagents | 工具白名单是基线限制的官方机制;Retriever 无自主推理需求;agent teams 实验性留 Phase 2 |
| D3 | Evaluator 证据强制 | `tools:` 白名单 + `disallowedTools`(WebFetch/AskUserQuestion/Skill/Write/Edit)+ PreToolUse hook(exit 2)+ PostToolUse JSON Schema 校验 trace | 提示词不可靠(ChemCrow 实证);Deny > Ask > Allow 优先级官方确认 |
| D4 | K=3 重生回路 | skill(context: fork)+ 文件计数器;回路内先**确定性参数修补**再重生成(CAX-Agent 阶梯) | 官方 skill 生命周期支持;阶梯实证 69%→93% 完成率、省 token |
| D5 | 点阵生成工具 | **主**:仓内 structure_set.py(24 strut)+ 新建 tpms_generator.py(manifold3d.level_set,~150–250 行,sheet+skeletal,密度二分);**辅**:microgen 2.0.0b1 经适配层(修法向,GPL 边界入档);**小众**:PyScaffolder(零件级 STL 填充);**除名**:MSLattice / TPMS Designer / FLatt Pack / lattpy | 零新依赖、Apache-2.0、本机验证 watertight 0.09 s/cell;外部工具无一覆盖 24 拓扑;MSLattice 等无脚本接口 |
| D6 | Printability 技术栈 | `trimesh[easy] + manifold3d + scipy + numpy`,**弃 Open3D**;FastMCP `>=3.4,<4` STDIO server;五工具契约,响应必含 `{value, threshold, pass, source}`;阈值入版本化 dfam_rules.json | Open3D 无 cp313 轮子(本环境 import 失败);五检查全部本机端到端验证;<5 s/候选实测 |
| D7 | 厚度/间隙方法 | 参数化点阵→解析杆径;上传网格→ray 厚度(embreex)为主 + 体素 EDT 交叉核验;间隙→min_gap(配布尔交检干涉)+ void EDT;**禁用** vtkSelectEnclosedPoints 与 GPL localthickness | ray 法 0.1–0.5% 精度实测;EDT <1 s;VTK 回退 350 s 不可用;GPL 污染许可证 |
| D8 | RAG/存储栈 Phase 1 | **不上向量库**:references/*.md(YAML front-matter 带源)+ thresholds/*.json + cell_db.sqlite(stdlib sqlite3,补 provenance 列)统一经唯一 MCP server;Retriever 全调用留痕 | 语料 << 20 万 token(Anthropic 官方阈值);仓内 CSV 直读先例;SQLite 事务改源字段,Parquet 不可变 |
| D9 | RAG/存储栈 Phase 2 | 触发条件满足后:嵌入式 LanceDB ≥0.33(原生 BM25+向量 hybrid,内置 RRFReranker);嵌入 fastembed/bge-small-en(英文库)或 voyage-4-lite(双语);**否决 Qdrant local 与 pgvector** | Qdrant local 官方 dev/test-only、<20K 点、Windows 锁问题、格式不兼容 server;pgvector 需第三方 Windows 二进制 + PG 服务 |
| D10 | RRF 使用边界 | 仅同条目空间融合:(a) 文本 BM25+向量;(b) 可选拓扑候选双排名融合(k=60);**数值查表结果带源原样返回,永不参与 fusion** | 真值被文本淹没会腐蚀引用层;Cormack 2009 原义即同空间列表融合 |
| D11 | 引用层实现 | source 字段内嵌于每个 MCP 工具输出(三类:DOI / 厂商标准 / 推测);无源判断触发 RAG 核实,查无则降级标注;报告页脚强制"须经实物压缩测试验证"免责 | HANDOFF §4 原义;A-Lab 更正事件证明审计链价值;红线 §10 |
| D12 | 判决多模态规则 | 任何单项检查不得授予 PASS;Evaluator 逐判决记录依赖的检查集合;预测附最近邻距离 applicability 标志;OOD 候选禁用 cell-DB 最近邻(§11) | A-Lab 单裁判失败;SimAI 工业先例;HANDOFF §11 |
| D13 | 模型分配 | Interpreter/Mapper/Corrector = 快速模型;Generator/Surrogate/Evaluator = Sonnet 级;经 subagent frontmatter `model:` 配置 | 任务推理深度差异;Evaluator 判决关键 |
| D14 | 工程组织 | `.claude/agents/`(subagent 定义)、`atlas/SKILL.md`、`atlas/servers/`(FastMCP)、`atlas/scripts/`、`atlas/references/`、`atlas/data/`、`.claude/.schema/`、`.mcp.json` 全进 git;排除 `.claude/tmp/` | 团队共享 + 可复现;MCP 项目级 scope 官方推荐 |

---

## 4. 物理与阈值核实表(HANDOFF §5 逐条)

> 状态:✅ 确认 / 🔧 已修正 / ⚠️ 待核实(无文献支撑,按引用层规则降级)

| HANDOFF §5 条目 | 状态 | 核实结果与修正 | 来源(DOI/URL) |
|---|---|---|---|
| Maxwell M = b − 3j + 6;M≥0 stretch,M<0 bending;必要非充分 | ✅ | 与一手全文逐式对上(Eq. 1b/2,含 "necessary not sufficient" 原文);建议补充区分 M=0(just-rigid)与 M>0(over-constrained,自应力) | DOI 10.1016/S1359-6454(00)00379-7(Deshpande-Ashby-Fleck, Acta Mater 49:1035) |
| FCCZ/FBCCZ 反例(垂直 strut) | ✅ | 溯源确认:Nasim & Galvanetto 2021,**MJF PA12** 八拓扑准静态压缩——恰是 ATLAS 基准材料/工艺;"只输出倾向性"规则保留 | DOI 10.1016/j.mtcomm.2021.102902 |
| Octet:E*=(1/9)ρ̄Es,σy*=(1/3)ρ̄σys | ✅ | 一手全文核对(Eq. 5a/5b/5c/18):s11=9/(ρ̄Es)、s12=−3/(ρ̄Es)、s44=12/(ρ̄Es) ⇒ E[100]=ρ̄Es/9、ν=1/3、G=ρ̄Es/12;ρ̄=6√2π(a/l)²。Caveat 入 source 字段:pin-jointed 细杆极限、立方轴向加载、低 ρ̄ 屈曲主导、AM as-built 低于理想值 | DOI 10.1016/S0022-5096(01)00010-2(JMPS 49:1747) |
| Bending:E*≈ρ̄²Es,σy*≈0.3ρ̄^1.5σys | ✅ | Ashby 2006 全文核对:指数 2 与 3/2,C1≈1、C5≈0.3 均数据拟合;有效域 ρ̄<0.3 须显式写入标度律参考文件(书第 5 章原文未直查,数值经多源收敛确认) | DOI 10.1017/CBO9781139878326;DOI 10.1098/rsta.2005.1678 |
| TPMS:gyroid n≈1.31,diamond n≈1.39(Abdulhadi 2023) | 🔧 | **已修正**:该数字在 Abdulhadi 2023 中仅为文献综述转引,语境是 **SLM Ti-6Al-4V TPMS**,该文自身主题是改型 BCC strut 点阵(117 个 ABAQUS 模型);**不得用于 PA12**。引文勘误:Engineering Reports **5(2)**:e12566(2023,在线 2022),非 5(5)。疑似一手 Yan et al. 2015 JMBBM 51:61–73 ⚠️ 待翻原文核对(paywall;且 Abdulhadi 原文用词 "scaling factor",指数解读存歧义)。**PA12 锚点改用** Chen 2023:MJF PA12 octet 指数 m≈1.17–1.29 | DOI 10.1002/eng2.12566;DOI 10.1016/j.jmbbm.2015.06.024(⚠️);DOI 10.1039/D2MA00972B |
| PA12:Es≈1700 MPa,σys≈45 MPa,ρs≈1010 kg/m³ | ✅ | HP 3D HR PA12 数据表:拉伸模量 1700(XY)/1800(Z) MPa、拉伸强度 48 MPa、密度 1.01 g/cm³。**σys=45 为 48 MPa 断裂拉伸强度的保守代理(数据表无屈服值),此性质须写入材料表 source 字段** | HP PA12 datasheet(cimquest-inc.com/resource-center/HP/Materials/HP-PA12-Datasheet.pdf);旁证 DOI 10.3390/polym17212817 |
| AlSi10Mg:Es≈75 GPa,σys≈230 MPa,ρs≈2670 kg/m³ | ✅ | EOS 数据表(as-built):E=75±10(XY)/70±10(Z) GPa;Rp0.2=270±10(XY)/240±10(Z) MPa(M290 表:Z 230±20)——**230 MPa 是保守 Z 向取值,XY/Z 各向异性须显式记录**;UTS≈460 MPa;ρ 2.67 g/cm³ | EOS Aluminium AlSi10Mg material datasheet(eos.info) |
| LPBF 表面缺陷折扣 ×0.92 | ⚠️ | **查无文献出处**,不是文献常数。按引用层规则降级为"内部工程假设(无文献支撑)";中期用 Zhong 2023 综述的 effective-strut-diameter 修正框架替代(文献显示杆强度随打印角变化 >12%) | 无(内部假设);替代框架 DOI 10.1016/j.cossms.2023.101081 |
| PA12 lattice SEA 合理区间 2–15 kJ/kg | 🔧 | **已修正(原值过乐观)**:实测 MJF PA12 octet @ρ̄=0.30 SEA=0.63–0.92 kJ/kg;FBCCZ≈0.281;G-A 能量估算准静态封顶 ~6–8 kJ/kg;文献 >10 kJ/kg 的是金属点阵。**新门禁:计算式核验(SEA≈σ_plateau·(ε_d−ε_y)/(ρ̄·ρs))+ 理性带 ~0.3–8 kJ/kg(典型 0.5–4 @ρ̄ 0.2–0.35),PA12 预测 >8 标 implausible**;SEA 应变端点约定写入 DB schema。注意该理性带本身是工程综合而非已发表共识 | DOI 10.3390/polym17212817;G-A 推算 |
| DfAM:SLS/MJF 最小 strut 0.8 mm、间隙 ≥1.0 mm | ✅ | 确认为**保守工程阈值**(非厂商最小值):HP/Materialise 指南点阵梁间隙 ≥1 mm(排粉)、<0.5 mm 杆易碎;共打印件间隙 ~0.7 mm;风道排粉建议 5 mm 开孔;最小壁 2 mm。逐条带厂商 URL 入 dfam-rules-{sls,mjf} | materialise.com/en/academy/industrial/design-am/pa12-mjf;facfox.com/docs/kb/hp-mjf-3d-printing-design-guidelines |
| DfAM:LPBF 最小 strut ≈1.0 mm、自支撑 35–45° | ✅ | 文献设计指南最小杆 0.4–0.6 mm(Ti64 可靠 >0.5)——**ATLAS 的 1.0 mm 保守约 2 倍,记录在案、后续可论证放宽**;45° 自支撑(316L)与 35–45° 带一致 | xometry.pro MJF/LPBF 设计指南;researchgate.net/publication/357380117 |
| MJF 排粉:ρ̄=0.39–0.47 仅清 1.5–1.7 层(Raz 2025) | ✅ | **逐字核实(PMC 全文 Table 2)**,并扩充为全 7 点表:ρ̄ 0.07→5.00 / 0.11→3.00 / 0.18→2.67 / 0.24→2.33 / 0.31→2.00 / 0.39→1.67 / 0.47→1.50 层(BCC、5 mm 胞、HP MJF 4200、4.4 bar 喷砂、X-ray 验证);单调内插落表。**跨拓扑/胞尺寸/工艺外推必须标 inference**。附加数据:构建中心位形偏差 ~0.25 mm vs 边缘 0.12 mm,中心收缩高 30–40% | DOI 10.3390/polym17202804(全文 PMC12567854) |
| G-A 对 AM as-built 偏乐观:金属 l/d<5 偏差至 300%(Zhong 2023) | 🔧 | **引文已修正**:Zhong, Song, Li, Das, Gu, Qian, *Current Opinion in Solid State and Materials Science* 27:101081(2023),**非 Composite Structures**;"l/d>5 适用 / 偏差至 300%" 确认,**仅限金属点阵** | DOI 10.1016/j.cossms.2023.101081 |
| G-A 对 AM as-built:聚合物 ±10–30% | ⚠️ | **该数字不在 Zhong 2023(金属综述)中,查无来源**。处理:要么从 Nasim & Galvanetto 2021 / Chen 2023 的 G-A 拟合残差重新推导并标 derived,要么标"工程估计(无源)"降级。**严禁带引用输出** | 无(待核实) |
| (§3 关联)cell DB 规模"24 × 每种约 1000 变形" | ⚠️ | 盘面证据:feature_data.json **999 结构总计**(每拓扑 ≤45),93 条缺曲线;特征 CSV 5,304 行。待核实是否另有未入库数据;Phase 1 按盘面证据执行 | 仓内 D:/ARTC/ARTC-Auto-Script/data_package/ |

---

## 5. 同类系统对标与差异化定位

### 5.1 对标表(2023–2026 generate-then-verify 全景)

| 集群 | 系统 | 生成 | 裁判(verify) | 与 ATLAS 的关键差异 |
|---|---|---|---|---|
| 材料发现回路 | MatterGen+MatterSim(Nature 2025,10.1038/s41586-025-08628-5) | 性质条件化扩散模型 | DFT + ML 模拟器 + 实物合成(TaCr2O6 实测 169 vs 目标 200 GPa,误差 <20% 如实报告) | 最佳诚实报告范本;采样潜空间而非穷举库;面向材料学家 |
| 材料发现回路 | A-Lab(Nature 2023,10.1038/s41586-023-06734-w;**2026-01 被更正**) | ML 配方建议 | **单一**自动 PXRD-Rietveld | 反面教材:单裁判过信,41–43 项声明被 PRX Energy 3:011002 系统性证伪 |
| 材料发现回路 | GNoME(novelty 被 Chem. Mater. 36:3837 挑战)、AtomAgents(PNAS,10.1073/pnas.2414074122)、Microsoft Discovery(2025) | GNN / LLM 假设 / 编排平台 | DFT / **MD(人写 LAMMPS 脚本集成,无深度代理组件)** / HPC 仿真 | 证明"编排专家 agent + 仿真裁判"已是平台商品;ATLAS 新颖性不可建立在 agent 拓扑上 |
| LLM-超材料 | **MetaScientist**(NAACL 2025 demo,arXiv:2412.16270)——最近学术邻居 | LoRA 微调 Llama3-8B(5,611 篇)+ 顶点坐标扩散 | **仅人类专家(3 人 11 题)+ 几何有效性**;无 FEA、无均质化、无解析力学裁判;严格阈值下胞内有效率仅 22–55% | ATLAS 槽位(数据落地验证 + 面向非专家选型)空置;其低几何有效率反证 Printability 硬门禁必要 |
| LLM-超材料 | ChatMetamaterials(arXiv:2601.17997,2026-01-25 提交) | 文本/手绘草图 → architecture code,推理式诊断 + 进化精修 | 自诊断 | **赛道正被抢占的实证**——审计链角度须尽快发表 |
| CAD/FEA agent | MechAgents(EML 2024,10.1016/j.eml.2024.102131)、FEABench(arXiv:2504.06260)、CADCodeVerify(ICLR 2025,arXiv:2410.05340)、CAX-Agent(arXiv:2605.15218) | LLM 写代码/CAD | 执行落地 + 自纠错 | FEABench:15 道金标无一全对、默认值 20 °C 被当答案静默导出 → 佐证 ATLAS"确定性脚本当裁判、LLM 只路由";贡献 checklist 模式与恢复阶梯 |
| 工业平台 | Ansys SimAI、PhysicsX LGM-Aero、nTop 5、Autodesk Assistant/Neural CAD、Leap71 Noyron(2025-12 双引擎热试车,>93% 燃烧效率) | 各异 | SimAI:**逐预测 applicability-domain 置信分**(训练几何潜空间最近邻距离);Noyron:确定性外置工程知识 + 实物测试终审;Autodesk:生成重、验证轻(甩给人) | 无一厂商向力学小白用户暴露引用分级的端到端审计链;SimAI 置信分与 Noyron 知识外置是两个直接可采纳模式 |

### 5.2 差异化定位声明(定稿,可直接入年报 related works)

Generate-then-verify 本身已是成熟实践(MatterGen 用 DFT 验证、A-Lab 用机器人 XRD、MechAgents 用 FEA 执行),编排专家 agent 调用仿真工具亦已是平台级商品(AtomAgents、Microsoft Discovery)——**ATLAS 在这两个原语上均不主张新颖性**。无任何已调研系统做到的是 ATLAS 的特定组合:对整个精选 AM 点阵数据库(24 拓扑 × 全部变形 × 4 工况)的**穷举搜索**,以秒级解析/经验裁判取代逐候选 FEA 而在算力上可行,产出可辩护的 **database-wide(明示非绝对)全局最优**——而先行系统或在生成潜空间采样、或在单一预选拓扑内优化;并将结果以**每个数字带三级来源分级(学术 DOI / 厂商标准 / 标记推测)的验证链**交付给力学小白工程师。其 model-agnostic 知识外置立场(skills + MCP + RAG,不微调)是被 Leap71 确定性 Noyron 独立验证的工程押注,与微调路线的近邻(MetaScientist 的 LoRA-Llama3、PhysicsX 的 LGM)形成对照——应作为可维护性/信任论点呈现,**而非新颖性主张**。

(注:HANDOFF §11 将 Tier-2 新拓扑生成升级为主攻方向后,本定位中"整库穷举"对应 Tier-1/1.5 的已验证叙事;Tier-2 的差异化叙事见 `RESEARCH_NOVEL_TOPO.md`,两者的可信度层级在报告中必须分开标注。)

### 5.3 定位纪律(红线对齐)

- "全局最优"措辞处处带 database-wide 限定(GNoME/A-Lab 的 novelty 翻车即未限定声明被公开拆解的先例)。
- 验收标准 = 用户工程判据(margin = pred/design ≥1.0,FoS 已含,不二次乘),不是代理指标。
- 每份报告/demo 保留"须经实物压缩测试验证"免责;高风险场景标"仅作筛选"。

---

## 6. 风险登记表

| # | 风险 | 等级 | 缓解措施 |
|---|------|------|----------|
| R1 | **引用层断供**:全库记录无 source/provenance 字段,数值答案全部降级为"无源" | 阻断 | P1-2 摄入时强制补列(FEA run ID/模型版本/日期/标准号);MCP schema 强制 source 必填 + 测试断言 |
| R2 | **无源数字带引用泄出**(聚合物 ±10–30%、×0.92):审计链卖点被自家报告反噬 | 高 | §4 两条 ⚠️ 写入 thresholds JSON 时 source_type=inference;Evaluator 对 inference 自动加降级标注 |
| R3 | **单裁判过信**(A-Lab 模式失败) | 高 | D12 多模态一致才 PASS;trace 记录判决依赖的检查集合;免责声明不可删 |
| R4 | **静默默认值/回退值**(FEABench 20 °C 模式) | 高 | 所有脚本/工具返回 status 字段区分 computed/default/fallback;embreex 缺失 fail loudly,禁 VTK 静默回退 |
| R5 | **代理外推**:G-A 对 AM as-built 偏乐观(金属 l/d<5 至 300%);DB 最近邻分布外静默退化;OOD 新拓扑(§11)误用最近邻 | 高 | SimAI 式最近邻距离标志;凸包外显式标外推;OOD 候选强制物理计算裁判(见 RESEARCH_NOVEL_TOPO.md) |
| R6 | **Python 3.13 依赖陷阱**:Open3D 不可装;裸 trimesh 运行期崩;libigl 轮子止步 cp312 | 高 | D6 依赖集已全部核实 cp313 轮子;CI 加 import 冒烟测试;万一需 Open3D 则 uv 隔离 3.12 venv 跑 MCP server |
| R7 | **Cuboctahedron_Z watertight 失败**(23/24):该拓扑候选会在 Printability 全军覆没 | 中高 | P1-1 修复(布尔顺序/半径/节点球重叠排查);修复前该拓扑在 Generator 列入黑名单 |
| R8 | **动态/剪切特征缺失**(4 工况仅 2 个全特征化):Phase 2/3 动态验证断粮 | 中高 | P2 扩 feature_extract.py;Phase 1 老实只验静态压缩(HANDOFF §7"静态先行"本就如此圈定) |
| R9 | **Raz 表外推**:仅 BCC/5 mm 胞/PA12/MJF4200/喷砂工况,跨拓扑使用是外推 | 中 | 查表工具输出自动附 inference 标注;后续自测补点 |
| R10 | **体素量化偏置**:困粉体积 +16% @pitch 0.25 mm;厚度/EDT 精度 ~±pitch | 中 | pitch ≤ 阈值/4;工具输出报告容差;Evaluator 边界判决参考容差带 |
| R11 | **GPL 边界**:microgen GPL-3.0、localthickness GPL-3.0、ASLI AGPL | 中 | microgen 藏适配层后、仅内部研究用、对外分发前重审;localthickness 不引入(porespy/自研替代);许可证清单入架构文档 |
| R12 | **beta 依赖漂移**:microgen 2.0.0b1、LanceDB pre-1.0、sqlite-vec pre-v1、FastMCP 3.x 破坏性变更 | 中 | 全部钉精确版本;FastMCP 钉 `>=3.4,<4`;嵌入缓存按 (model, content_hash) 键控,换模型强制可见重索引 |
| R13 | **赛道窗口收窄**:ChatMetamaterials(2026-01)、Microsoft Discovery、Buehler 组持续产出 | 中 | 护城河 = 带源 cell DB + DfAM 阈值 + 尺寸效应修正的内容资产(Phase 1/2 即建);审计链角度尽快发表;Poisson 符号 ↔ 尺寸效应方向的文献空白已确认,论文腿提速 |
| R14 | **LLM 流利度偏好**回潜入口:Orchestrator 撰写报告环节 | 中 | 报告从 trace 生成,数字抄录不转述;MCP 边界输入校验(单位/量程) |
| R15 | **token/成本**:K=3 分叉最坏 ~20 并行会话;skill 描述吃上下文预算 | 低中 | CAX 阶梯先修补后重生;监控用量;skill 描述 <100 字符;超预算时减候选数 N 不减 sub-agent(HANDOFF §9 阈值条款) |
| R16 | **TPMS 标定风险**:自研 level_set 模块的 t–密度标定与 sheet 厚度–最小特征映射若错,Printability 在错误几何假设上运行 | 中 | P1-5 逐拓扑独立标定(对照文献/MSLattice 离线曲线)后才接 Mechanics Surrogate;候选打 part_type(sheet/solid-network)标签——§4 的 TPMS 指数本就是形态特异的 |
| R17 | **HANDOFF §3 数据规模叙事与盘面不符**(999 总计 vs "每种约 1000"):对外口径若沿用旧数字会被质疑 | 中 | 年报/对外材料按盘面证据写;向数据所有者核实是否另有批量数据待入库 |

---

## 7. 对 Phase 1 计划的影响(任务清单,含依赖标注)

> 在 HANDOFF §9 Phase 1(4 项)基础上,按调研结论细化为 12 项;顺序即建议执行序;红线(§10)全程适用。
> 关键变更:① 修 Cuboctahedron_Z 与补 provenance 前置为第一批;② "向量库选型落地(Qdrant 或 pgvector)"替换为"无向量库引用层 + 升级触发条件";③ cell DB SQLite MCP 从 Phase 2 提前(它是引用层与 Surrogate 的共同地基);④ 新增 TPMS 模块与 3-case 端到端验收。

| ID | 任务 | 依赖 | Definition of Done |
|---|---|---|---|
| **P1-1** | 修复 Cuboctahedron_Z watertight 失败;将 structure_set.py 24 拓扑 + manifold3d 并集包成干净函数 API(替代文本格式解析) | — | `test_manifold_all_cells.py` 24/24 全 OK(两次重复运行);新 API `generate_cell(topology, slider, radius, n) -> Manifold/Trimesh` 有单测 |
| **P1-2** | cell DB 摄入 SQLite + provenance:从 feature_data.json / extracted_features_smoothed.csv 建 `atlas/data/cell_db.sqlite`,补 source/source_type/method/date 列(FEA run 标注),标记 93 条缺曲线记录,补 topology_class 列(Maxwell 计算) | — | schema 含 CHECK 约束;每条记录 source 非空;缺曲线记录带 quality flag;一次性摄入脚本入库可复跑 |
| **P1-3** | 落地 skill 文件结构(HANDOFF §9.1):`atlas/SKILL.md`(Phase 0 三题 → 生成+验证 → 中文报告)+ `references/`(fos-guide、dfam-rules-{sls,mjf,lpbf} 含逐行 source、scaling-laws-by-topology 含 ρ̄<0.3 有效域、size-effect-tables)+ `scripts/`(gibson_ashby.py、maxwell_check.py、rel_density.py 等,全部返回 `{value, status, inputs_echo, source}`)——**全部采用 §4 修正后数值**(SEA 带 0.3–8、Zhong 引文勘误、TPMS 指数限定 Ti64、×0.92 与 ±10–30% 标 inference) | — | references 每条阈值带 source 字段;脚本单测含已知解析值回归;无任何 §4 已修正条目以旧值出现 |
| **P1-4** | Printability MCP server v1:重构 `bench_printability{,2,3}.py` 为 `atlas/servers/printability/` 包,五工具契约(validate_mesh / measure_min_feature / check_overhangs / check_powder_escape / measure_clearance),Raz 7 点表内插,dfam_rules.json 版本化,按网格哈希缓存;**先取得用户批准安装 `trimesh[easy]`(rtree+embreex,本轮会话安装未获批)**;`.mcp.json` 注册,fastmcp 钉 `>=3.4,<4` | P1-1(测试夹具用其网格);依赖安装批准 | 五工具对 BCC 正负对照全过;单候选 <5 s(embreex);每响应含 {value, threshold, pass, source};embreex 缺失时 fail loudly 有测试覆盖 |
| **P1-5** | TPMS 生成模块:`atlas/scripts/tpms_generator.py`(manifold3d.level_set;gyroid/Schwarz-P/Schwarz-D/Schoen-IWP/Neovius;sheet+skeletal;密度二分定标);逐拓扑 t–密度标定曲线对照文献/MSLattice 离线核验;候选带 part_type 标签;面数预算控制(edgeLength 选型) | P1-1 | 全部拓扑×两变体 watertight;定标 ρ̄ 误差 <2%;3×3×3 块生成 <5 s;标定曲线存档 references/ |
| **P1-6** | 引用层 Phase 1(替代原"向量库选型"):`atlas/references/<author-year>.md` 模板 + §2.5 种子文献逐篇落笔记(YAML front-matter:doi/source_type/validated_claims/validity_domain);五条 Phase 2 升级触发条件写回 HANDOFF §9.4 | P1-3 | 种子文献(≥10 篇核心 + 6 篇尺寸效应)全部入库;Grep front-matter 字段可命中;HANDOFF §9.4 已改写 |
| **P1-7** | Retriever + cell_db MCP server:`query_cell_db(topology, rel_density, load_mode, k)` + `retrieve_reference(query)`(Grep references/ front-matter),数值结果带源原样返回(D10 规则),全调用留痕日志 | P1-2, P1-6 | 数值查询返回含 source;日志含 query/工具/命中数/返回源;"数值不参与 fusion"写入 Retriever 提示词并有测试 |
| **P1-8** | 6 worker subagent 定义(interpreter / generator / printability-checker / mechanics-surrogate / material-mapper / size-effect-corrector),frontmatter tools 白名单 + model 分配(D13);Generator 工具行 = P1-1 API + P1-5 TPMS(microgen 适配层列为可选扩展) | P1-3, P1-4, P1-5, P1-7 | 每 subagent 可独立调通其工具;白名单外调用被拒;Interpreter 追问经主会话回环验证 |
| **P1-9** | Evaluator subagent + 证据强制:tools 白名单 + disallowedTools + PreToolUse hook(exit 2)+ `.claude/.schema/verification_trace.json` + PostToolUse schema 校验;判决规则表(多模态一致才 PASS;margin=pred/design≥1.0 含 FoS 不二次乘;n<3 强警示;inference 源自动降级标注;applicability 最近邻距离标志) | P1-7, P1-8 | hook 阻断非白名单调用有测试;不合 schema 的 trace 被拒;规则表逐条有正反用例 |
| **P1-10** | K=3 重生回路 skill:context fork + 文件计数器;CAX 阶梯(确定性参数修补 → 重生成 → 上下文增强);K 耗尽出 Pareto 前沿 | P1-8, P1-9 | 注入必败候选可观察到 ≤3 轮重生与阶梯顺序;Pareto 输出含全部候选 trace |
| **P1-11** | 4 并行验证 agent(verifier-{static,dynamic,shear,printability})background subagents 接线——Phase 1 验证深度老实圈定静态压缩(§7 静态先行),dynamic/shear 验证器仅返回数据可用性 + informational | P1-8 | 4 验证器并行扇出 5–8 候选 ~30 s 内回齐;Evaluator 汇总判决含各验证器证据 |
| **P1-12** | 端到端验收:三个具体 case(LPBF 支架 / SLS 吸能块 / MJF auxetic 垫)全链路跑通(Phase 0 三题 → 生成 → 四验证 → 判决 → 中文报告含裕度列/trace/三类来源/免责页脚);对照红线清单逐条审查输出 | P1-10, P1-11 | 三 case 报告齐;每个数字可溯源到工具调用或带 inference 标注;无红线违例(database-wide 限定/不二次乘 FoS/Maxwell 只说倾向/免责保留) |

**执行批次建议**:第一批 P1-1/P1-2/P1-3(无依赖,可并行);第二批 P1-4/P1-5/P1-6;第三批 P1-7/P1-8;第四批 P1-9/P1-10/P1-11;收口 P1-12。预计 2–4 周与 HANDOFF 原估一致——任务变多但每项更小、可并行度更高。

---

## 附:对 HANDOFF.md 的修正/待核实清单(汇总)

1. 🔧 §5:Zhong et al. 2023 期刊勘误 → *Curr. Opin. Solid State Mater. Sci.* 27:101081(DOI 10.1016/j.cossms.2023.101081);300% 偏差限定金属。
2. ⚠️ §5:"聚合物 ±10–30%" 查无来源 → 标"工程估计(无源)"或从 PA12 文献重推导。
3. 🔧 §5:TPMS 指数 1.31/1.39 = Abdulhadi 2023(Eng. Reports **5(2)**:e12566)综述转引的 SLM Ti-6Al-4V 值,不适用 PA12;PA12 锚点改 Chen 2023(m≈1.17–1.29);⚠️ 一手 Yan 2015 待翻原文。
4. 🔧 §5:PA12 lattice SEA 区间 2–15 → **0.3–8 kJ/kg**(准静态),并改为计算式核验 + 理性带。
5. ⚠️ §5:LPBF ×0.92 折扣无文献出处 → 降级"内部工程假设"。
6. 🔧 §4 行 3:Generator 工具行删 MSLattice / TPMS Designer(及 FLatt Pack 类),改为"内部 structure_set + manifold3d level_set TPMS(主)/ microgen 适配层(辅)/ PyScaffolder(零件级填充)"。
7. 🔧 §4 行 4 与 §9.2:删 Open3D(无 cp313 轮子),改 "trimesh[easy] + manifold3d + scipy"。
8. 🔧 §9.4:删 "Qdrant 或 pgvector",改"Phase 1 无向量库(references + Grep + SQLite 查表)+ 五条升级触发条件,Phase 2 目标 LanceDB"。
9. ⚠️ §3:"24 × 每种约 1000 变形" 与盘面不符(999 总计、每拓扑 ≤45、93 条缺曲线)→ 核实数据来源或修正叙事。
10. 🔧 仓库事实:watertight 23/24(Cuboctahedron_Z 失败),修复列入 P1-1。
11. 补注 §5:σys(PA12)=45 为 48 MPa 数据表拉伸强度的保守代理;AlSi10Mg 230 MPa 为保守 Z 向值(XY 270 / Z 240,M290 表 230±20),各向异性入材料表。
12. 补注 §5:LPBF 最小杆 1.0 mm 较文献(0.4–0.6 mm)保守约 2 倍,留放宽论证空间。

> 本报告全部结论均要求经实物压缩测试验证后方可用于工程决策;高风险场景(植入物/航空安全件)输出仅作筛选。
