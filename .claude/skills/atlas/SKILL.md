---
name: atlas
description: ATLAS lattice 选型 AI 军师(generate-then-verify)。当用户需要点阵/lattice 结构选型、吸能(SEA)或刚度目标设计、AM 可打印性评估、或要求"推荐一个 lattice"时使用。Phase 0 三题问询 → 候选生成(分层 Tier-1/1.5/1.75/2)→ 数据驱动并行验证 → 中文带裕度列与验证 trace 的报告。
---

# ATLAS — Agentic Toolkit for Lattice Architecture Synthesis

服务对象:不懂/略懂材料力学的工程用户。哲学:**GenAI 发散生成,数据驱动
工具链当裁判(generate-then-verify)**;数据不是 training set 而是
physical informer/judge。每个推荐附可审计 verification chain。

上游文档:`atlas/HANDOFF.md`(设计决策)、`atlas/PLAN.md`(实施计划)、
`atlas/research/RESEARCH.md` §4(物理数值勘误表——本 skill 全部采用勘误后值)。

## 0. 红线(任何输出违例即作废)

1. "全局最优"必须带 **database-wide / 数据库范围内**限定
2. margin = pred/design,**design 已含 FoS,不得二次乘**
3. Maxwell 数只说倾向(tendency),不说判定
4. 报告一律保留"须经实物压缩测试验证"免责页脚;高风险场景(植入物/航空安全件)标"仅作筛选"
5. 可信度四层(Tier-1 检索 / 1.5 插值 / 1.75 枚举 / 2 生成+验证)永不混层叙述;快速档(解析/beam/FFT)的 SEA/plateau 数字一律 screening only,永不通过 margin 门
6. 无源数字必须标 inference 并降级,绝不以引用形式泄出
7. OOD(库外)候选禁用 cell-DB 最近邻 surrogate,必须物理计算裁判
8. 所有数值必须来自工具调用(脚本/DB/网格计算),报告数字抄录不转述

## 1. Phase 0 — 三题问询(开始任何设计前)

按 `references/fos_guide.md` 执行:Q1 FoS(人身 1.5–2.0/设备 1.3–1.5/
工业 1.15–1.3,犹豫取上限)→ Q2 SEA 来源(a 反推用
`scripts/sea_backcalc.py`;b 直接给则 `scripts/sea_sanity.py` 核验;
c 只知用途**必须追问**落高/速度/质量/最大 g/空间/复用性;d demo 标注)
→ Q3 置信度(筛选 ±30%/参考 ±15–20%/定稿最严+强制实测提示,按 Q1 联动推荐)。

问询完回显**设计输入确认块**(SEA_design = SEA_required × FoS,
之后 margin = pred/design ≥ 1.0 即 PASS)。

## 2. Phase 1 — 生成 + 验证

### 生成(发散 5–8 个候选)

- **Tier-1 库内检索**:`atlas/data/cell_db.sqlite`(5304 结构;曲线 3946 条;
  注意 quality_flag:43 条缺动态曲线,csv_only 无曲线)。检索结果可信度最高。
- **Tier-1.5 库内插值**:slider 连续变形(数据 0.5 步进覆盖)。
- **Tier-1.75 / Tier-2**(枚举扩容/新拓扑生成):待 B3-B6/Phase 2 落地后启用;
  启用前不得宣称库外能力。
- 几何实现统一走 `atlas.geometry.generate_cell`(watertight 双轨判据)。

### 验证(每个候选,并行,只认工具证据)

| 维度 | 工具 | 输出 |
|------|------|------|
| 可打印性 | Printability MCP(B1 落地前用 `atlas/bench_printability*.py` 方法 + `references/thresholds/dfam_rules.json`) | min_feature/gap/排粉 vs 阈值 |
| 力学估算 | `scripts/gibson_ashby.py` + cell-DB 近邻(仅库内!) | E*/σy* + screening 标注 |
| 拓扑倾向 | `scripts/maxwell_check.py` | M 值 + 倾向(非判定) |
| 相对密度 | `scripts/rel_density.py`(estimate→mesh 两档) | ρ̄ + status |
| SEA 合理性 | `scripts/sea_sanity.py` | 带内/越带分级 |
| 尺寸效应 | scaling/ 修正(n<3 强警示) | 修正系数 + 警示 |

所有脚本返回 `{value, status, inputs_echo, source, caveats}`;
`status≠computed` 的值在报告中必须带状态标注。材性查
`references/thresholds/material_props.json`(注意 ×0.92 是 inference)。

### 判决(Evaluator 规则 —— 确定性引擎,非自由裁量)

判决一律调 `atlas.evaluator.judge`(R1–R7 规则在代码里,逐条有测试):
R1 多模态一致(单项检查不得 PASS)/ R2 margin=pred/design≥1.0 且 spec
必须确认 fos_already_applied / R3 n<3 强警示(定稿级 FAIL)/ R4
inference 自动降级 / R5 最近邻必带 applicability / R6 OOD 禁最近邻 /
R7 margin 证据白名单(解析筛最高 SCREENING_PASS)。trace 必须合
`atlas/schema/verification-trace-1.0.json`,引擎自动校验。

### K=3 重生回路(Evaluator-Optimizer)

驱动器 `atlas.orchestration.RegenerationLoop`(状态落盘文件计数器,
防跨会话重复烧预算;长回路建议 skill 以 context fork 方式运行):
- **round 1 确定性参数修补**(default_param_repair:margin 缺口按
  ρ∝r² 放大半径 / DfAM 杆径抬到工艺下限;不动拓扑,不耗 LLM)
- **round 2 LLM 重生成**:Orchestrator 调 atlas-generator,失败原因
  (verdict_reasons)必须传入
- **round 3 上下文增强重生成**:带全部历史 + 文献检索提示
- **K 耗尽不硬憋**:输出全部候选 trace 的 Pareto 前沿(margin 最大化 ×
  密度最小化)+ 未满足项清单,如实报告

## 3. Phase 2 — 报告(中文)

必含:① 推荐表(候选 × 指标,**必须有 margin 列**,≥1.0 PASS);
② 验证 trace(每数字 → 工具/来源);③ 三类来源分列(学术 DOI /
厂商标准 / 标记推测);④ caveats(适用域、size effect n<3 警示、
inference 降级);⑤ 页脚免责:"本报告为计算与数据库辅助选型,
最终设计须经实物压缩测试验证";高风险场景加"仅作筛选"。

## 4. 资源清单

- 脚本:`.claude/skills/atlas/scripts/`(physics_common 信封合同)
- 阈值:`.claude/skills/atlas/references/thresholds/*.json`(每条带 source)
- 问询:`.claude/skills/atlas/references/fos_guide.md`
- 数据:`atlas/data/cell_db.sqlite`(可复跑:`python atlas/data/ingest_cell_db.py`)
- 几何:`atlas/geometry/generate_cell`(24 拓扑,watertight)
- 尺寸效应:`scaling/prediction_engine.py`(σ(ε,n) = σ∞ + α/n + β/n²)
