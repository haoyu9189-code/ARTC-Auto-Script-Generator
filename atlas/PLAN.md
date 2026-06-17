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

### Phase 2 任务清单(2026-06-12 启动,loop 按此执行)

| ID | 任务 | Definition of Done | 依赖 |
|----|------|--------------------|------|
| P2-1a | beam_homog.py 核心(Timoshenko PBC 均质化) | 商图直接做周期均质化(u=ε̄x+ũ,ũ 周期=商图 DOF,affine 部分作载荷):6+15 次解提取完整 6×6 C*;Timoshenko 剪切项(φ=12EI/GAsL²);解析锚:竖柱族 E_z=ρ̄_z·E_s 精确、立方拓扑 Ex=Ey=Ez、C* SPD;Octet 与 DFA (1/9)ρ̄Es 同量级(刚接偏硬有界);单胞 <100ms;信封含 caveat | — |
| P2-1b | Lumpe-Stanković 抽样金标准验证 | 解析 Unit_Cell_Catalog.txt 条目(节点+杆+E/G/ν+C,n);抽 ≥20 个立方对称条目(排除 * 与重复),beam_homog(归一 Es=1,ν=0.3)vs 目录 Ex/Ez:中位偏差与分布记录入 `atlas/references/beam_homog_validation.md`;偏差>30% 的条目逐个归因(l/d?非立方?) | P2-1a |
| P2-1c | 节点刚化修正 + 误差条入 Evaluator | 用自家 DB(24 拓扑 comp_stiffness)标定:beam_homog E_z vs DB 实测,按拓扑类(stretch/bending/hybrid)拟合修正系数与残差带;`atlas/references/beam_error_bars.json`(每类:correction, p50/p90 误差,l/d 域);Evaluator R7 margin 白名单加入 'beam_fem_calibrated'(带误差带折减);l/d<5 拒绝认证写入信封并有测试 | P2-1a |
| P2-2 | FunSearch 回路(LLM 提案 × CMA-ES × beam 裁判) | pycma 安装;回路:提案器(协议:输入 spec+失败史 → 输出 graph 编辑 JSON;实现 Claude-驱动接口 + 变异 fallback)→ 硬门 → WL 查重 → CMA-ES 抛光连续参数(radius/free_params,目标=beam 裁判分)→ 三道绝对门(C* SPD / Voigt-Reuss 界 / beam vs frame-block 跨档 ≤20% 差);产出 ≥3 个新拓扑比刚度超种子最优 ≥10% 且全链留痕;demo 更新 | P2-1a |
| P2-3 | Tier-1.75 目录三级筛 | 17,262 条目入 `catalog.sqlite`(provenance=DOI+CC BY-NC 标记,135 重复+40 星标 quality flag);三级筛管线:Maxwell/连通(毫秒)→ G-A 类预估(毫秒)→ beam_homog(top 切片);对一个 spec 演示:目录→top-10 → 与 24 种子同台比较;红线:称"枚举"不称"生成" | P2-1a |
| P2-4 | Material/Process 修正矩阵 | `thresholds/process_matrix.json`:SLS-PA12/MJF-PA12/LPBF-AlSi10Mg 三档(E_s,σ_ys,ρ_s,各向异性,表面/工艺折扣),逐条 source+source_type(无源标 inference);Mapper agent 提示词更新指向矩阵;测试断言全条目带源 | — |
| P2-5 | 动态/剪切特征提取扩展 | 从 cell_db curves(DynaCompre/DynaShear 3,946 条中的动态曲线)提取 dyna_stiffness/dyna_yield/dyna_peak + shear_peak 入 features 表(带 source);ingest 可复跑;动态验证维度从 informational 升级为真特征(verify.py 更新);缺曲线 43 条如实跳过 | — |
| P2-6 | LanceDB(条件触发) | 仅当 HANDOFF §9.4 五条件之一满足;每次 loop 迭代检查 retriever_log 的 miss 率,未触发则 skip 并留痕 | — |

执行顺序:P2-1a → (P2-1b ∥ P2-1c ∥ P2-4 ∥ P2-5) → P2-2 → P2-3;P2-6 条件检查每迭代捎带。

### Phase 3 任务清单(2026-06-11 启动,用户选定 ②→①→③ 顺序)

> 就绪度依据:4 路并行代码扫描(2026-06-11,见 PROGRESS 日志)。
> 大件 P3-1/P3-2/P3-3 转入 backlog(见下),不在本轮。

| ID | 任务 | Definition of Done | 依赖 |
|----|------|--------------------|------|
| P3-A | Tier-D ABAQUS 升压收口 | ① 生成的 postprocess 注入 ALLKE/ALLIE 能量提取(**文本注入生成产物,不改 script_generator 源**——用户工作区有未提交修改);② `atlas/mechanics/tier_d.py` 桥:feature_data/energy → checks(source_type=abaqus_fea),能量门 ALLKE/ALLIE≤5% 判据带源(Abaqus 准静态准则,vendor);③ trace schema enum + R7 白名单加入 abaqus_fea,正反用例;④ 三 FunSearch 冠军(polish 半径)作业目录生成(preprocess/postprocess/run.pbs+README),**提交求解由用户决定**;套件全绿 | — |
| P3-B | 真 agent 端到端 D2 | Orchestrator 协议落 SKILL(主会话驱动,不建 orchestrator subagent);atlas-generator / atlas-evaluator 经真实子代理派发重跑三 D1 案例;K=3 regenerate_fn 接真 LLM 重生成;判决仍由确定性引擎产出(agent 是载体不是裁判);真跑 trace 与 Python 直跑判决一致性对照;Evaluator PreToolUse hook 实际触发留痕 | — |
| P3-C | Benchmark 仪表 + 单 agent 基线 | stage 级计时聚合入报告;可溯源率%(带源 checks 占比)自动计算;单 agent 基线 harness 同三案例对跑;多 vs 单 agent 对照表(耗时/溯源率/判决质量)落 `atlas/reports/benchmark.md`(月报素材:traceability + time reduction 实测) | P3-B |

| P3-D | 新拓扑筛选估值器(beam 为体、文献为界) | done | screen_estimate.py:beam_homog 自身几何物理为核心排序值(非白名单→封顶 SCREENING_PASS)+ 文献标度律仅作误差带交叉校验(margin_eligible=False);量纲纪律(模量仅刚度类 spec 可作 margin);弯曲类/分歧/越域→escalate Tier-D;接入 verify.py OOD 分支(此前 graph_doc-only 零力学证据);+14 测试,套件 330 全绿 |

执行顺序:P3-A → P3-B → P3-C → P3-D(用户追加:"为什么不能生成结构 / 论文对比估测")。

### Phase 3 backlog(暂缓,启动须用户点名)

- **P3-1** Tier-C 体素裁判 benchmark——**Step 1 原型已做并 KILL 自研路**(2026-06-11,见 `atlas/reports/tierc_fft/results.md`):自研谱-CG FFT 均质化求解器正确(层合板 Backus 精确),但 solid/void 高对比度(≥1e3)下普通 CG 不收敛(1200 迭代/9min)、低对比度软空相污染信号 10–30%,且保守下界(对偶/自平衡空相零应力)未触及;beam_homog ~10ms 已给同量级合理数,原型性价比不成立。**改道**:若确需 margin 级保守 Tier-C,采用成熟 **Vondřejc-Zeman FFT-Galerkin 保证界**代码(预条件+对偶下界+精确积分,3D 弹性;arXiv:1404.3614 / PAMM 2023)——中期工程;否则 beam_homog+Tier-D 已足够,Tier-C 留此。`fft_homog.py` 保留为已验证点估交叉校验工具(仅 screening,非白名单)。原 PINN 候选(arXiv:2509.07579)已否决(2D 标量热,非 3D 弹性)。
- **P3-2** spinodoid 旗舰全链:NumPy GRF 自研(规避 GIBBON AGPL)→ marching cubes → 打印检查 → orphan-mesh INP → ABAQUS 打标 1–3k 样本 → CPU 训练 f-NN/i-NN;SEA 用 BO 直驱显式 FEA;RVE 收敛研究替代尺寸效应查表(spinodoid 无单胞,Agent 8 查表不适用)——估 6–10 周 + 千级求解小时
- **P3-3** 深度生成 inference-only(UnifyingTrussDesignSpace / DiffuMeta checkpoint;预测头只当启发,永不入 trace)
- **P3-4** ABAQUS 自动升压制度化(≤3/查询;显式准静态 1–6 h/次,实测日志校准)——P3-A 为其第一步

---

## 1bis. Phase 4 里程碑:非线性/吸能 Tier-D(2026-06-11 用户选定 + 设 loop)

### GOAL(北极星)

让 ATLAS 的物理终审(Tier-D)能认证**非线性吸能**:任何点阵(含新拓扑/OOD)经
**准静态显式压溃**(大变形 + 自接触 + 致密化)得到 **SEA / comp_EA / 平台应力 /
致密化应变**,并在通过**硬有效性门**后成为 **margin 级证据**(source_type=abaqus_fea)。
意义:吸能(comp_EA/SEA)是真实案例(汽车防撞盒、头盔内衬)的主导指标,当前
beam_homog/screen_estimate 与静态 Tier-D 均不能认证非线性压溃(P3-D 把吸能显式推给
Tier-D 留了缺口);本里程碑补上,并同时解锁 P3-2(spinodoid)/P3-3(壳/TPMS 生成)。

**已就绪基础(P3-A + 预读确认)**:`script_generator.py` 的 DynaCompre 路径已有
ExplicitDynamicsStep + GeneralContact(自接触)+ nlgeom + 质量缩放 + SmoothStep 加载 +
单元删除(SC-Solid 损伤);`tier_d.generate_job_for_doc(...,analysis_type=)` 已参数化;
能量门 ALLKE/ALLIE≤5% 框架已在。故本里程碑是**接线 + 提取压溃指标 + 有效性硬门 +
本机验证**,非从零写显式 FEA。

### HARNESS(执行框架 —— loop 每迭代遵守)

- **状态机**:PLAN(本表 DoD)+ PROGRESS(状态/日志)。每迭代:读 PROGRESS → 选依赖
  满足的最小 NT → 实现 → 按 DoD 验证 → 更新 PROGRESS → 本地 commit(带 NT-ID)。
- **分工纪律**:① 设计/调研/并行扫描 → workflow/subagent;② **正确性敏感的提取与判据
  代码(NT-2/NT-3)→ 主会话写 + 合成曲线/解析单测**(FFT 教训:界/指标最易"看着对其实错");
  ③ ABAQUS 结果迭代调试 → 主会话。能写代码的 subagent 只有 general-purpose/workflow
  (atlas-* 只读)。
- **ABAQUS 入 loop(Phase 4 覆写 §2 约束)**:本机 ABAQUS 2023 可用 + 用户授权本地跑 →
  验证 run 作**后台 job** 在 loop 内执行(~10 min/个),自定步(dynamic loop)等其完成。
  仍不向集群提交。
- **红线增补(细化 §3 #6)**:Tier-D 显式压溃的 SEA/comp_EA 成 margin 级**仅当 NT-3 硬门
  全过**;门未过/准静态不成立 → 降为 screening,绝不以 margin 泄出。质量缩放伪能量、
  单元删除能量损失、接触穿透必须各自有界并留痕。
- **停止条件**:NT-1..NT-6 全 done 且至少 1 个本机压溃验证 run 在容差内 → 停 loop,汇报。

### 任务清单(loop 按此执行;依赖:NT-1 →(NT-2∥NT-3)→ NT-4 →(NT-5∥NT-6))

| ID | 任务 | Definition of Done | 依赖 |
|----|------|--------------------|------|
| NT-1 | 准静态显式压溃作业生成 | tier_d 接 DynaCompre 准静态档(速率/质量缩放调到 ALLKE/ALLIE≤5%);postprocess **文本注入**补提取(应力-应变全程到致密化 + ALLKE/ALLIE + 质量缩放伪能量 ALLMW + 接触穿透代理);生成 1 个种子作业目录;**1 个本机 run 产出 feature+energy,能量门通过且跑到致密化**(不改 generator 源)| — |
| NT-2 | 压溃指标提取(SEA/平台/致密化) | `results_to_checks_crush`:SEA=能量到致密化÷质量(质量=ρ̄·V_cell·ρ_material)、平台应力(ISO 13314)、致密化应变(能量吸收效率 η(ε) 法);**合成曲线单测**(理想 plateau+densification 已知 SEA,提取在容差内);真实曲线跑通 | NT-1 |
| NT-3 | 硬有效性门 | 五门:① 能量平衡 ALLKE/ALLIE≤5% ② 致密化已达 ③ 接触穿透有界 ④ 质量缩放伪能量占比有界 ⑤ 单元删除能量损失有界;全过才 `margin_eligible=True`;任一不过→screening + caveat;正反单测 | NT-1 |
| NT-4 | margin 接线 | comp_EA/SEA 经显式压溃 → abaqus_fea margin 级(白名单已含),**仅 NT-3 全过 + metric 匹配**才进 margin;SEA 量纲/单位与 schema/evaluator 必要改动;judge 在通过门的压溃 SEA 上给 PASS、门未过给 SCREENING/FAIL,正反单测 | NT-2, NT-3 |
| NT-5 | 本机验证 run | 复现一个已知 cell_db DynaCompre 或静态 comp_EA 的种子能量/SEA 在容差内(本机 1 个 ABAQUS,E_s 与口径归一);留档 `atlas/reports/tierd_crush/results.md` | NT-4 |
| NT-6 | 闭环接线(补 P3-D 缺口) | verify.py/screen_estimate:comp_EA/SEA spec 的 OOD 新拓扑路由到非线性 Tier-D(此前吸能被推给 Tier-D 但无路径);对一个吸能 spec 新图演示「生成→筛选→压溃终审→margin」全链;报告 | NT-4 |

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
