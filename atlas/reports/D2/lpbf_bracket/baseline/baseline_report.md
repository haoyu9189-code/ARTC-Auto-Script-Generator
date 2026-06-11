# 单 Agent 基线报告 — LPBF AlSi10Mg 航空支架点阵填充

- 工况 key:`lpbf_bracket`(高风险);spec:LPBF / AlSi10Mg / n_cells=3 / 裕度指标 = comp_EA(库内同单位代理)/ 设计值(含 FOS 1.5)= **60.0** / 置信级别 = screening
- 评估人:单 agent 基线(不属于多 agent 管线;未读取本目录已有管线产物 candidates.json / traces_*)
- 日期:2026-06-11
- 数据与工具:`atlas/data/cell_db.sqlite`(5304 结构,内部 Abaqus FEA 特征库)、`atlas.geometry.cells.generate_cell`(watertight 网格)、`atlas.printability.checks`(双引擎水密 / embree 射线测厚 / 面法向悬垂 / 体素 flood-fill 困粉)、阈值库 `.claude/skills/atlas/references/thresholds/dfam_rules.json`

---

## 1. 方法

1. **力学初筛(Tier-1 库内查表)**:`features.comp_EA(static_compression) ≥ 60.0`(FOS 已含),高风险工况另要求筛选裕度 ≥1.2×;按相对密度升序(航空支架轻量化优先)。
2. **可打印性几何筛(杆轴角判据)**:对 24 拓扑 × slider 0–8 网格,由 `parse_structure` 直接计算每根杆的轴线与水平面夹角。LPBF 自支撑带 = 35–45°(EOS/SLM 厂商共识,vendor 源);**淘汰含水平杆或 <35° 杆的构型**。全库仅 3 个构型全部杆 ≥35°:BCC(slider 8)、Diamond(slider 3)、Rhombic(slider 3),均为 35.26°(⟨111⟩ 族),与 LPBF 文献中最常用的免支撑拓扑一致。
3. **网格级核验(n=3 阵列,15 mm³ 块)**:水密双轨、最小特征(embree 射线测厚,p5 判据)、悬垂面积分数(面法向,45° 保守阈值 + 35° 厂商下限对照)、困粉(体素 flood-fill,pitch 0.25 mm)。
4. **杆径决策**:库内 r=0.5 mm(Ø1.0)恰好压在 LPBF 最小特征阈值 1.0 mm 上(网格面化后实测 0.991 mm,零裕度)→ 高风险工况**取 r=0.55 mm(Ø1.10)**,实测 p5=1.091 mm,留 ~9% 几何裕度;阈值本身相对文献能力(0.4–0.6 mm)已保守约 2×。
5. **力学合理性交叉核验(Gibson–Ashby 标度)**:BCC E∝ρ^1.79、Diamond E∝ρ^2.27(由 r=0.50→0.55 三点拟合),均 ≈2,符合弯曲主导拓扑预期,库内数据自洽。

## 2. 候选与评估结果

| # | 构型(cell 5 mm,n=3) | ρ_rel (DB) | comp_EA | 裕度 vs 60 | comp_刚度 | comp_屈服 | 杆角 min | 水平杆 | 最大跨距 | 最小特征 p5 | 悬垂<45° | 悬垂<35° | 困粉 | 判定 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | **BCC s8, r0.55** | 0.192 | **190.9** | **3.18×** | 62.3 | 2.22 | 35.3° | 0 | 4.33 mm | 1.091 ✔ | 16.6% ✘ | **0.2%** | 0 ✔ | **PASS**(附条件) |
| C2 | **Diamond s3, r0.55** | 0.182 | **162.6** | **2.71×** | 46.1 | 1.61 | 35.3° | 0 | **2.17 mm** | 1.091 ✔ | 16.5% ✘ | **0.4%** | 0 ✔ | **PASS**(附条件) |
| C3 | Truncated_cube s8, r0.5 | 0.131 | 119.8 | 2.00× | 45.7 | 1.05 | **0°** | **16** | 2.20 mm | 0.991 ✘ | 11.0% ✘ | 7.2% ✘ | **7.13 mm³ ✘** | **FAIL** |

补充(库内同单位代理):dyna_comp_EA C1=199.7 / C2=175.6 / C3=127.1;shear_EA C1=178.3 / C2=186.6 / **C3=57.8(<60,剪切代理亦不达标)**。

### 2.1 C1 — BCC slider 8, r=0.55(推荐)
- 力学:comp_EA 190.9 ≥ 60,裕度 3.18×;刚度 62.3、屈服 2.22 为三者最高。r=0.5 同构 'ok' 级样本(含完整曲线,BCC_5_0p5_8:EA 172.1)提供曲线级下界佐证,EA 随 r 单调增,结论稳健。
- 可打印性:水密双轨 ✔;最小特征 1.091 mm ≥ 1.0 ✔;无水平杆,全部 8 杆 35.3°,跨距 4.33 mm;困粉 0 ✔。
- 悬垂:严格面法向门(<45° 面积 ≤5%,内部 inference 容限)不通过(16.6%),但 **99.8% 的朝下面积落在 35–45° 厂商自支撑带内**(<35° 仅 0.2%,即节点球底盖)。BCC 是 AlSi10Mg LPBF 文献中打印最充分的免支撑拓扑,该带内配合 downskin 参数可免支撑成形。
- 判定:**PASS(附条件)** — 条件见 §3。

### 2.2 C2 — Diamond slider 3, r=0.55(轻量备选)
- 力学:comp_EA 162.6,裕度 2.71×;ρ_rel 0.182 为通过者中最轻(较 C1 −5% 质量),刚度/屈服低于 C1。
- 可打印性:同为全 35.3° 无水平杆;**跨距仅 2.17 mm(C1 的一半)**,downskin 下垂风险更低;<35° 面积 0.4%;困粉 0;最小特征 1.091 ✔。
- 判定:**PASS(附条件)**。若打样阶段 C1 的 4.33 mm 跨距 downskin 质量不达标,C2 为首选回退。

### 2.3 C3 — Truncated_cube slider 8, r=0.5(对照否决)
仅按库内 EA/重量比是最诱人的选择(ρ 0.131 即达 EA 119.8),但网格级核验四项全败:**16 根水平杆**(0°,远低于 35° 厂商下限,<35° 面积 7.2%);**困粉 7.13 mm³ ≫ 容差 0.125**(近闭合角隅);最小特征 0.991 < 1.0(零裕度);焊接形态水密失败(is_volume=False);剪切代理 57.8 < 60。
- 判定:**FAIL**(不可修复项:水平杆为拓扑固有)。

### 2.4 Rhombic s3(入围未列正式候选)
全 35.3° 同样可打印,EA 545(裕度 9.1×),但 ρ_rel 0.404 ≈ C1 的 2.1 倍质量,对航空支架轻量化目标不具竞争力;仅当需求升级到 EA ≥ ~400 时再启用。

## 3. 最终推荐与附带条件

**推荐:C1 = BCC,slider 8,r = 0.55 mm,cell 5 mm,3×3×3 填充**(备选 C2 Diamond s3 r0.55)。

高风险工况附带条件(两 PASS 候选共同适用):
1. **悬垂处置披露**:严格 45°/≤5% 面积门(容限为内部 inference 取值)两候选均不过;放行依据是杆轴角 35.3° 落在厂商 35–45° 自支撑带下缘 + 跨距短(≤4.33 mm)+ <35° 面积 ≤0.4%。**必须**采用 AlSi10Mg downskin 优化参数,且首件做打样验证(挂片 + 切片/CT 查 downskin 挂渣与杆径实测),否则降回"需支撑"处理。
2. 杆径实测验证:LPBF 实打杆径系统偏差(常见 +0.05~0.15 mm 过熔)需在首件实测后回标 ρ_rel 与 EA。
3. screening 置信级别:comp_EA 为库内同单位代理(内部 Abaqus FEA 管线,r=0.55 行无原始曲线,'csv_only_no_curves'),下一阶段建议对 C1 跑一次 n=3 全模型 FEA 复核(库内 r=0.5 'ok' 曲线样本可作标定锚点)。
4. 网格实测相对密度(n=3 含边界完整胞,0.220)高于库内 FEA 口径(0.192),质量估算请用网格口径:0.220 × 2.67 g/cm³ ≈ 0.59 g/cm³ 等效密度。

## 4. 证据与可追溯性

- 库查询:`atlas/data/cell_db.sqlite`,features.source = "internal FEA feature extraction: data_package/extracted_features_smoothed.csv (mtime 2026-01-21), Abaqus pipeline";Tier-1 数值查表,未做任何 rank fusion。
- 网格检查原始输出:`atlas/reports/D2/lpbf_bracket/baseline/_printability_raw.json`(本目录)。
- 阈值:`dfam_rules.json` LPBF 节 — min_strut_diameter 1.0 mm(inference,文献 0.4–0.6 的 ~2× 保守)、自支撑角 [35,45]°(vendor)、悬垂面积容限 5%(inference)、困粉容差 = 8 voxel(0.125 mm³ @ pitch 0.25)。
- 几何:`atlas.geometry.cells`(manifold3d 布尔 + 双轨水密判据);杆角由 `parse_structure` 节点坐标解析直接计算。
