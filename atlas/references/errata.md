# ATLAS 勘误登记(errata)

> 所有 HANDOFF/调研报告中被独立核实推翻或修正的事实,统一在此登记。
> 任何下游产物(skill/references/报告)出现勘误前数值 = 红线违例。
> 核实过程见 `atlas/research/RESEARCH.md` §4 与 `atlas/PROGRESS.md` 日志。

## 文献勘误

| # | 原表述(错) | 修正(对) | 依据 |
|---|-----------|---------|------|
| E1 | Zhong et al. 2023 发表于 Composite Structures | 实为 **Current Opinion in Solid State and Materials Science** 27:101081,DOI 10.1016/j.cossms.2023.101081 | 一手核对 |
| E2 | "G-A 对 AM as-built 偏乐观:聚合物 ±10–30%" | 该数字**不在 Zhong 2023 中,查无文献来源** → 降级为内部工程估计(source_type=inference);可从 Nasim 2021 / Chen 2023 拟合残差重推导 | 全文检索 |
| E3 | TPMS 指数 gyroid≈1.31 / diamond≈1.39(笼统引用 Abdulhadi 2023) | 该数字是 Abdulhadi 2023(Engineering Reports 5(2):e12566,**5(2) 非 5(5)**,在线 2022)综述中**转引的 SLM Ti-6Al-4V 结果,不适用 PA12**;疑似一手 Yan 2015(DOI 10.1016/j.jmbbm.2015.06.024)待核;PA12 锚点改用 Chen 2023(DOI 10.1039/D2MA00972B,m≈1.17–1.29) | 一手核对 |
| E4 | PA12 lattice SEA 合理区间 2–15 kJ/kg | **0.3–8 kJ/kg**(典型 0.5–4);实测 MJF PA12 octet @ρ̄=0.30 仅 0.63–0.92;>8 implausible;>10 文献值属金属点阵 | 实测+G-A 能量上限 |
| E5 | LPBF 表面缺陷折扣 ×0.92(当作常数引用) | 查无文献出处 → "内部工程假设"(inference);中期用 Zhong 2023 effective-strut-diameter 框架替代 | 全文检索 |
| E6 | PA12 σys = 45 MPa(当作屈服值) | 是 HP 数据表 **48 MPa 拉伸强度**的保守代理,非屈服值;报告须注明 | 数据表核对 |
| E7 | AlSi10Mg σys = 230 MPa(单值) | 保守 Z 向取值;EOS 给 XY 270 / Z 240(M290 表 230±20);**XY/Z 各向异性必须显式记录** | 数据表核对 |
| E8 | LPBF 最小杆 1.0 mm(当作文献标准) | 较文献设计指南(0.4–0.6 mm)**保守约 2 倍**;记录在案,后续可论证放宽 | 文献对照 |
| E9 | Lumpe-Stanković 目录 = 17,087 条 | 论文**分析**了 17,087 个 unit cells;ETH 存档目录实际含 **17,262** 个结构(基于 RCSR + EPINET);引用时区分"分析数"与"目录数" | ETH 存档元数据 |
| E10 | 调研报告引"Kirchhof et al., J Elasticity 2024"(尺寸效应-Poisson 文献) | **查无此文**(Crossref 检索无果);实际相关文献为 **Li & Guo 2024, JMBBM, DOI 10.1016/j.jmbbm.2024.106532**("Size effect in polymeric lattice materials with size-dependent Poisson's ratio caused by Cosserat elasticity")——调研 agent 引文张冠李戴 | Crossref API 核对(B7) |

## 数据实况勘误(盘面 vs 文档)

| # | 原表述(错) | 修正(对) | 依据 |
|---|-----------|---------|------|
| D1 | cell DB = 24 种 × 每种约 1000 变形 | feature_data.json 为 **999 结构总计**;extracted_features_smoothed.csv 为 **5,304 = 24 拓扑 × 13 半径 × 17 滑块**整格;999 个 JSON 结构物理上全部 ⊂ CSV | A2 摄入实测 |
| D2 | 调研报告:93 条缺至少一条四工况曲线 | 实为 **43 条**(18 缺 DynaShear / 18 缺 DynaCompre / 7 双缺,全部动态工况) | A2 深度统计 |
| D3 | (隐含)样本名可作身份键 | CSV 样本名带浮点累积伪影(`0p30000000000000004`),按名合并会身份分裂;身份 = 物理键 (topology, size, round(r,6), slider) | A2 摄入实测 |
| D4 | (隐含)density 单值 | JSON FEA 密度与 CSV smoothed 密度是**两种量**(中位差 1.5%,最大 22%);442 行 CSV 无密度,432 结构完全无密度 | A2 摄入实测 |
| D5 | watertight 23/24,Cuboctahedron_Z 失败 | 已修复(A1):根因 = 球-柱等半径整圆相切 + 布尔零厚度翻盖对;现 24/24 双轨水密 | A1 修复 |
| D6 | (调研补充)sphere_r 默认 1.2 | Config.SPHERE_RADIUS_RATIO_SCRIPT 实际默认 **1.0**(env 可覆盖);1.2 会废掉 Auxetic 铰链机制 | config.py 核对 |

## 工具/选型勘误

| # | 原表述(错) | 修正(对) |
|---|-----------|---------|
| T1 | Generator 工具行:microgen / MSLattice / TPMS Designer / PyScaffolder | MSLattice、TPMS Designer 为 MATLAB GUI/工具箱**无脚本接口**,除名;主选 = 仓内 structure_set + manifold3d level_set TPMS;辅 = microgen 2.0.0b1 经适配层(GPL-3.0 隔离);PyScaffolder 仅零件级填充 |
| T2 | Printability:trimesh / Open3D | Open3D **无 Python 3.13 轮子**(本机 3.13.5 不可 import),除名;改 trimesh[easy](rtree+embreex 必装)+ manifold3d + scipy |
| T3 | §9.4 向量库选型(Qdrant 或 pgvector) | 已改写(见 HANDOFF §9.4):Phase 1 零向量库;五条升级触发条件;触发后用嵌入式 LanceDB ≥0.33 |

## 许可登记(关键边界)

| 资产 | 许可 | 边界 |
|------|------|------|
| Lumpe-Stanković Unit Cell Catalog | **CC BY-NC 4.0** | 非商用!研究使用 OK;ATLAS 商业化部署前必须重审或替换 |
| microgen 2.0.0b1 | GPL-3.0 | 只经适配层内部使用,不得静态链接进分发物 |
| GIBBON(spinodoid 参考实现) | AGPL | **不得链接**;GRF 生成 NumPy 自研重写 |
| manifold3d | Apache-2.0 | 无限制 |
| localthickness | GPL | 不引入 |
