# ATLAS 项目交接文档(Claude Code 续接用)

> Agentic Toolkit for Lattice Architecture Synthesis
> NTU SC3DP · A*STAR ARTC 资助 · 负责人 Haoyu(RA,2026.08 起 PhD)
> 本文档固化了截至 2026-06 的全部设计决策,新会话读完即可接手。
>
> ⚠️ **勘误提示(2026-06-10 调研核实)**:§3 数据规模与 §5 部分数值/引文存在勘误(Zhong 2023 出处、TPMS 指数适用域、PA12 SEA 带应为 0.3–8 kJ/kg、×0.92 与"聚合物 ±10–30%"无源等),以 `atlas/research/RESEARCH.md` 核实表为准;§9.4 向量库选型已否决(Phase 1 零向量库,Phase 2 触发后 LanceDB),执行计划见 `atlas/PLAN.md`。

---

## 1. 项目一句话

面向增材制造(AM)的点阵结构选型 AI 军师:**GenAI 发散生成候选 lattice,数据驱动的工具链当裁判做验证(generate-then-verify)**,服务不懂/略懂材料力学的工程用户。

## 2. 核心设计哲学(所有开发决策的根)

- **数据角色翻转**:数据不是 training set("越准越好"已过时),而是 **physical informer / judge** —— 卡在 GenAI 输出口上筛掉不 make sense 的设计(含"0.0X nm 喷不到"这类可打印性约束)。
- **不 fine-tune,知识外置**:RAG 知识库 + Agent + Skill + MCP,model-agnostic。微调 = 锁死在固定基座上,基座迭代会吃掉微调收益。
- **护城河 = 可审计的 verification chain**:每个推荐都附"从哪些角度考虑 + 调用哪些工具 verify"的透明链路。回答"你的 AI 吐一个、别人的 AI 也吐一个,凭什么你的好?"的方式就是这条链。
- **全局 vs 局部最优(关键差异化论点)**:传统设计 = 经验先选定单一拓扑、再在其内部优化 → 局部最优;ATLAS 在整个数据库(24 拓扑 × 1000+ 变形)范围内搜索 → **database-wide 全局最优**(措辞必须限定"数据库范围内",不吹绝对全局)。全空间搜索在算力上可行,正是因为用秒级解析代理替代了逐候选 FEA —— 这两个论点是咬合的。
- 库内检索(retrieval,可信)与库外生成(generation,需验证链背书)是两个可信度层级,叙述时分开。

## 3. 数据与科研背景

- **单 cell 数据库**:24 种 cell type × 每种约 1000 变形 × 4 种加载(静/动 × 压缩/剪切),PA12/MJF FEA,已提取 SEA、刚度、峰值力等。
- **尺寸效应**:单 cell ≠ 工程现实;1→3 cell 跳变最剧烈;修正方式 = **runtime 叠加 correction factor**(不训练进模型)。
- **发文方向**:scaling 趋势的方向性(有的随 cell 数上升、有的下降、有的不变)→ 搞清驱动因素即可做可控设计。候选机理:Poisson ratio 符号 ↔ 正负尺寸效应(待坐实)。当前卡点:实验误差糊住趋势,需改进实验。
- **两条产出腿性质不同**:AI 应用腿把误差当原料(correction factor 吃掉它);论文腿把误差当敌人(要干净信号)。别让两边互相污染标准。

## 4. Sub-agent 架构(9 个,已经深度调研定稿)

编排:**Orchestrator-Worker 主架构 + Evaluator-Optimizer 校验循环**(不用 Plan-and-Execute,流程可预设无需动态规划)。

| # | Agent | 职责 | 关键工具/方法 |
|---|-------|------|--------------|
| 1 | Orchestrator | 需求拆解、调度、报告整合 | 不直接调外部工具 |
| 2 | Requirement Interpreter | 口语 → 结构化 spec;主动追问 | RAG 术语对照库 |
| 3 | Lattice Generator | 24 拓扑发散 5–8 候选 | microgen / MSLattice / TPMS Designer / PyScaffolder |
| 4 | Printability Checker | DfAM 几何硬校验 | trimesh / Open3D + 阈值查表 |
| 5 | Mechanics Surrogate | 不跑 FEA 的力学估算 | Gibson-Ashby + Maxwell + cell DB 最近邻 |
| 6 | Material/Process Mapper | SLS+PA12 基准 → 工艺/材料修正 | 修正系数矩阵查表 + RAG |
| 7 | DB/RAG Retriever | 统一检索入口 + 引用层 | 数值走 function-call 查表,文本走向量 RAG,RRF 融合 |
| 8 | Size-Effect Corrector | 单 cell → 多 cell 修正 | (topology, n_cells, ρ̄)→系数查表;n<3 强警示 |
| 9 | Evaluator/Verifier | pass/fail 判决,只认工具证据 | 重生预算 K=3,超出报 Pareto 前沿 |

流程:串行(Orchestrator→Interpreter→Material Mapper)→ Generator 发散 → **四验证 agent 并行** → Evaluator 判决 → fail 回传 Generator 重生(≤3 轮)→ 出报告。

**引用层(Citation Layer)— 不是独立 agent**:所有库记录入库时带 `source` 字段(DOI/厂商指南/标准号),取数即带源;查不到 source 的判断触发文献库 RAG 核实,找不到则标"无文献支撑的推测"降级。报告末尾分三类列来源(学术 DOI / 厂商标准 / 推测)。

## 5. 关键物理与阈值(写死在 skill/提示词里的)

- Maxwell:M = b − 3j + 6;M≥0 stretch,M<0 bending。**必要非充分**——FCCZ/FBCCZ 有垂直 strut 是反例,只输出"倾向性"。
- Stretch(octet):E*=(1/9)ρ̄·Es,σy*=(1/3)ρ̄·σys(Deshpande-Fleck-Ashby, JMPS 2001)。
- Bending:E*≈ρ̄²·Es,σy*≈0.3ρ̄^1.5·σys(Gibson & Ashby 1997)。
- TPMS 拟合:gyroid n≈1.31,diamond n≈1.39(Abdulhadi et al. 2023, DOI 10.1002/eng2.12566)。
- 材性:PA12 Es≈1700 MPa,σys≈45 MPa,ρs≈1010;AlSi10Mg Es≈75 GPa,σys≈230 MPa,ρs≈2670,LPBF 表面缺陷折扣 ×0.92。PA12 lattice SEA 合理区间 2–15 kJ/kg。
- DfAM:SLS/MJF 最小 strut 0.8 mm、间隙 ≥1.0 mm;LPBF 最小 strut ≈1.0 mm、自支撑 35–45°;MJF 排粉与 ρ̄ 强耦合(ρ̄=0.39–0.47 仅清 1.5–1.7 层,Raz et al. Polymers 2025, DOI 10.3390/polym17202804)。
- G-A 对 AM as-built 偏乐观:聚合物 ±10–30%,金属 l/d<5 时偏差可达 300%(Zhong et al. Composite Structures 2023)。

## 6. Phase 0 问询设计(skill 启动前,三题同构:都问 + 带依据选项 + 系统可推荐)

- **Q1 FoS(问用户)**:人身安全 1.5–2.0 / 设备防护 1.3–1.5 / 一般工业 1.15–1.3。犹豫取该档保守上限。
- **Q2 SEA 设计值来源(问 + 收集后推测)**:a) 给能量+最大力 → 反推;b) 直接给 SEA;c) 只知用途 → **不甩区间,主动追问**(落高/速度/对象重量/最大 g/空间/单次或复用)后由系统反推;d) demo 用示例。反推:SEA_required = E/(ρ̄·V·ρs);σ_plateau ≤ F_max/A;缺体积必追问几何包络。
- **Q3 置信度(问 + 按 Q1 联动推荐)**:筛选级 ±30% / 设计参考级 ±15–20% / 接近定稿级最严+强制 Size-Effect+必须实测提示。推荐联动:Q1 人身安全→定稿级;设备→参考级;工业→筛选级。
- **FoS 与置信度是独立维度**:FoS=物理裕量(改及格线),置信度=预测可信度(改修正严苛度),可自由组合,绝不互替。
- 问询完回显「设计输入确认块」:SEA_design = SEA_required × FoS(**已含 FoS,后续裕度 = pred/design ≥1 即过,不再二次乘 FoS**)。
- 报告推荐表必须有 **SEA/刚度裕度列**(margin = pred/design),≥1.0 才 PASS。

## 7. 报告叙事决策(年度报告 & 对外口径)

- **弱化 50% 加速指标**:不删(项目方要 quantifiable indicator),降级为方法式表述——给基线定义 + 测量方法,数字作 indicative target 一笔带过。基线 = 工程师用商业 CAD+FEA 人工选型逐候选迭代;测量 = 同 case、同验收标准(definition of done)下端到端 wall-clock 对比,3–5 个 case 取平均,记录迭代轮数;盯住隐藏变量"返工率"(不写进报告)。
- **主打"全局 vs 局部最优"**(见 §2),最简短版本已定稿可直接用。
- **静态先行**:验证范围老实圈定静态压缩("验证可行性");动态/剪切 = 数据已就绪、Phase 2/3 拓展(数据层面照常讲四工况,验证成熟度不吹)。
- 年度报告待修:Executive Summary 断句("...descriptors. demonstrated..."缺主语)、清除所有 `(Chen:)` 批注与内部留言、补空的 Reference 节(用 G-A 1997、DFA 2001、Maxwell、Abdulhadi 2023、Raz 2025)、related works 对比节待写。

## 8. 已产出资产(本轮交付物)

- **完整 skill 主提示词**(Phase 0 三题问询 → Phase 1 生成+验证 → Phase 2 中文报告含裕度列/trace/caveats/页脚免责)——在对话中有最终整稿,可直接落成 SKILL.md。
- **引用层提示词增量**(取数即带源 / 无源即核实 / 报告末尾三类来源)。
- **两张报告插图**(灰阶学术风,无标题无底注,PNG+PDF,pipeline 另有 SVG):`fig_design_report`(航空支架 case 概念输出,含验证 trace)、`fig_atlas_pipeline`(单箭头上下流,虚线容器包四并行验证,fail→regenerate 回环)。caption 已定稿(标准版:elicitation→generate→parallel data-grounded verify→ranked auditable report)。
- **Demo page** `atlas_demo.html`:暗色工程仪表盘风,canvas 旋转 octet 晶格,实时调 Claude API(claude-sonnet-4)生成报告,LIVE/CACHED 双模式(API 挂了自动 fallback 不翻车),三个预设 case(LPBF 支架 / SLS 吸能块 / MJF auxetic 垫)。

## 9. Claude Code 中的下一步(建议优先级)

**Phase 1(最短链路,2–4 周)**
1. 落地 skill 文件结构:`atlas/SKILL.md` + `references/`(fos-guide / dfam-rules-{sls,mjf,lpbf} / scaling-laws-by-topology / size-effect-tables)+ `scripts/`(gibson_ashby.py / maxwell_check.py / rel_density.py / check_overhang.py / check_min_feature.py)。
2. Printability Checker:trimesh+Open3D 封装 MCP server(watertight / manifold / min-feature / overhang / 排粉深度查表)。
3. Evaluator 判决规则表 + verification trace 模板(只认工具证据)。
4. 向量库选型落地(Qdrant 或 pgvector),seed 文献:G-A 1997、DFA 2001、Raz 2025、Abdulhadi 2023、Zhong 2023。

**Phase 2(4–8 周)**
5. 24 cell DB 封装为 MCP function-call(SQLite/Parquet,`query_cell_db(topology, rel_density, load_mode)`),每条记录带 source 字段。
6. Material/Process Mapper 修正系数矩阵(先 SLS-PA12 / MJF-PA12 / LPBF-AlSi10Mg 三档)。
7. Evaluator-Optimizer 重生回路打通(K=3)。

**Phase 3**
8. Size-Effect Corrector 接实测拟合表;Q2 追问做成选项式;可选 ML surrogate(HomoGenius 类)。

**触发架构调整的阈值**:重生平均 >2 轮 → 把 Printability 规则前置喂给 Generator;预测偏差投诉 >30% → 扩修正库而非切 FEA;token 超预算 → 减候选数 N,不减 sub-agent(验证链是护城河,不能砍)。

## 10. 红线提醒

- 所有"全局最优"表述必须带"database-wide / 数据库范围内"限定。
- margin 已含 FoS,任何地方不得二次乘。
- Maxwell 只说倾向,不说判定。
- 报告/demo 一律保留"须经实物压缩测试验证"免责。
- 高风险场景(植入物/航空安全件)输出必须标注"仅作筛选"。

## 11. 增补(2026-06-10,用户口述指示,扩展 §4 Generator 的职责定位)

- **库内线性查找只是 Tier-1,"太简单"**。ATLAS 的真正野心 = **可靠的新拓扑生成**:有理论基础、计算结果大概率正确、但可能从未被人设计出来的"外星拓扑"——类似拓扑优化 / AI 生成拓扑,但要完美匹配工况。
- 与 §2 可信度分层咬合:库外生成本就是第二层级,现在明确为主攻方向而非点缀。验证链随之升级——**OOD(分布外)新拓扑不得用 cell-DB 最近邻做 surrogate(那只对分布内插值有效),必须用物理计算当裁判**(beam-FEM / FFT 均质化等秒级方法),高价值候选升级到现有 ABAQUS 自动化管线(script_generator.py → 求解 → GeJsonl 特征提取)做全 FEA 终审。
- Generator 由此分层:**Tier-1** 库内检索(可信)→ **Tier-1.5** 库内拓扑变形/插值(slider 已有机制)→ **Tier-2** 新拓扑生成(graph/隐式场表示,生成期硬约束保证物理 sanity,验证链逐级升压)。报告叙述中三层可信度必须分开标注。
- 专项调研报告:`atlas/research/RESEARCH_NOVEL_TOPO.md`(生成方法 × 快速物理裁判 × 表示与约束)。
