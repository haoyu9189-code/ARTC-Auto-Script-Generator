# ATLAS 选型报告:LPBF AlSi10Mg 航空支架点阵填充

⚠️ 高风险场景(航空结构件):本报告输出仅作筛选,不得直接用于定型设计。

工艺/材料:LPBF / AlSi10Mg;阵列 n=3;FoS=1.5(**设计值已含 FoS,margin = pred/design,任何环节不再二次乘**);置信度等级:screening(筛选级)。

搜索范围:候选在 cell DB(5,304 结构)+ 生成层内比较,推荐为 **database-wide(数据库范围内)最优**,不主张绝对全局最优。

## 推荐表

| 候选 | Tier | 拓扑 | ρ̄(实算) | margin(pred/design) | 判决 |
|------|------|------|----------|---------------------|------|
| lp1 | Tier-1 | Octet_truss | 0.60518 | 无可用证据 | FAIL |
| lp2 | Tier-1 | FCCZ | 0.49139 | 无可用证据 | FAIL |
| lp3 | Tier-1 | Kelvin | 0.41188 | 无可用证据 | FAIL |

margin 度量:comp_EA(库内同单位代理),设计值(含 FoS)= 60.0。注:库内 comp_EA 的绝对单位映射待 P2-5 标定,本列为同单位代理比较(source_type=inference 级别的单位假设,已降级)。

**结论:本轮无候选通过全部硬性检查**(详见各候选判决依据)。系统如实报告而非硬选:典型出路 = ① 接受支撑结构并复核排粉;② 换粉末床聚合物工艺(SLS/MJF 无悬垂约束);③ Phase 2 自支撑拓扑定向生成(45° 准则前置喂给 Generator)。

## 验证 trace(每个数字可溯源)

### 候选 lp1(Tier-1)

| 维度 | 工具 | 值 | 通过 | 来源 |
|------|------|----|------|------|
| printability | printability.validate_mesh | watertight=True; winding_consistent=True; is_volume=True | ✓ | trimesh 边-面计数 + manifold3d Mesh.merge 往返 status(双引擎,bench_pr |
| printability | printability.measure_min_feature | min_mm=1.0905892320783388; p5_mm=1.0905892920621563; median_mm=1.09058937841378 | ✓ | 阈值: 内部保守取值;文献设计指南给 0.4-0.6 mm(约保守 2 倍),记录在案后续可论证放宽;方法: embre |
| printability | printability.check_overhangs | overhang_area_fraction=0.3685094337974357; threshold_angle_deg=45; downward_face_count=2908 | ✗ | 自支撑角: LPBF 自支撑角行业共识区间(EOS/SLM Solutions 设计指南);容限: 内部工程容限:临界角 |
| printability | printability.check_powder_escape | trapped_void_mm3=0.953125; voxel_pitch_mm=0.25; tolerance_mm3=0.125 | ✗ | 困粉: embree 列射线奇偶填充 + scipy flood-fill(bench_printability3.py |
| density | rel_density.mesh(manifold3d) | 0.60518 | ✓ | manifold3d watertight 体积 / 胞体积 |
| mechanics | gibson_ashby.estimate | E_MPa=114.3110341148964; sigma_y_MPa=9.077640944418244; model=DFA octet (stretch) | ℹ️ | Deshpande, Fleck & Ashby, JMPS 49(8):1747-1769, 2001, DOI 10 |
| topology_tendency | maxwell_check | maxwell_M=0; tendency=stretch-leaning | ✓ | Maxwell 1864; Deshpande, Ashby & Fleck, Acta Mater. 49(6):10 |
| mechanics | retriever.nearest_by_density+comp_EA | 921.84603 | ✓ | internal FEA feature extraction: data_package/extracted_feat |
| material | material_props[AlSi10Mg_LPBF] | 75 | ✓ | EOS AlSi10Mg datasheet, as-built E ~75 GPa |
| material | surface_defect_knockdown | 0.92 | ✓ | 内部工程假设,查无文献出处(2026-06-10 调研);中期应以 Zhong 2023 effective-strut |
| size_effect | scaling.n_cells_advisory | 3 | ℹ️ | Onck/Andrews 2001 边界层机制(atlas/references);修正引擎接线归 P2 |
| mechanics | dynamic_data_availability | 88 | ℹ️ | cell_db.sqlite curves 表 |

判决依据:硬性检查未过: printability/printability.check_overhangs;硬性检查未过: printability/printability.check_powder_escape

降级记录:R4: material/surface_defect_knockdown 证据为 inference,结论降级一档

拓扑倾向(Maxwell,必要非充分,只说倾向):M=0,stretch-leaning

### 候选 lp2(Tier-1)

| 维度 | 工具 | 值 | 通过 | 来源 |
|------|------|----|------|------|
| printability | printability.validate_mesh | watertight=True; winding_consistent=True; is_volume=True | ✓ | trimesh 边-面计数 + manifold3d Mesh.merge 往返 status(双引擎,bench_pr |
| printability | printability.measure_min_feature | min_mm=1.0905892017641772; p5_mm=1.0905892856094304; median_mm=1.090589390512445 | ✓ | 阈值: 内部保守取值;文献设计指南给 0.4-0.6 mm(约保守 2 倍),记录在案后续可论证放宽;方法: embre |
| printability | printability.check_overhangs | overhang_area_fraction=0.31381023695799537; threshold_angle_deg=45; downward_face_count=2146 | ✗ | 自支撑角: LPBF 自支撑角行业共识区间(EOS/SLM Solutions 设计指南);容限: 内部工程容限:临界角 |
| printability | printability.check_powder_escape | trapped_void_mm3=0.0; voxel_pitch_mm=0.25; tolerance_mm3=0.125 | ✓ | 困粉: embree 列射线奇偶填充 + scipy flood-fill(bench_printability3.py |
| density | rel_density.mesh(manifold3d) | 0.49139 | ✓ | manifold3d watertight 体积 / 胞体积 |
| mechanics | gibson_ashby.estimate | E_MPa=92.81905277132871; sigma_y_MPa=7.370924778899632; model=DFA octet (stretch) | ℹ️ | Deshpande, Fleck & Ashby, JMPS 49(8):1747-1769, 2001, DOI 10 |
| topology_tendency | maxwell_check | maxwell_M=-10; tendency=bending-leaning | ✓ | Maxwell 1864; Deshpande, Ashby & Fleck, Acta Mater. 49(6):10 |
| mechanics | retriever.nearest_by_density+comp_EA | 436.535737 | ✓ | internal FEA feature extraction: data_package/extracted_feat |
| material | material_props[AlSi10Mg_LPBF] | 75 | ✓ | EOS AlSi10Mg datasheet, as-built E ~75 GPa |
| material | surface_defect_knockdown | 0.92 | ✓ | 内部工程假设,查无文献出处(2026-06-10 调研);中期应以 Zhong 2023 effective-strut |
| size_effect | scaling.n_cells_advisory | 3 | ℹ️ | Onck/Andrews 2001 边界层机制(atlas/references);修正引擎接线归 P2 |
| mechanics | dynamic_data_availability | 90 | ℹ️ | cell_db.sqlite curves 表 |

判决依据:硬性检查未过: printability/printability.check_overhangs

降级记录:R4: material/surface_defect_knockdown 证据为 inference,结论降级一档

拓扑倾向(Maxwell,必要非充分,只说倾向):M=-10,bending-leaning

### 候选 lp3(Tier-1)

| 维度 | 工具 | 值 | 通过 | 来源 |
|------|------|----|------|------|
| printability | printability.validate_mesh | watertight=True; winding_consistent=True; is_volume=True | ✓ | trimesh 边-面计数 + manifold3d Mesh.merge 往返 status(双引擎,bench_pr |
| printability | printability.measure_min_feature | min_mm=1.0905892680521319; p5_mm=1.090589320356246; median_mm=1.0905893750378715 | ✓ | 阈值: 内部保守取值;文献设计指南给 0.4-0.6 mm(约保守 2 倍),记录在案后续可论证放宽;方法: embre |
| printability | printability.check_overhangs | overhang_area_fraction=0.4118250883717007; threshold_angle_deg=45; downward_face_count=2832 | ✗ | 自支撑角: LPBF 自支撑角行业共识区间(EOS/SLM Solutions 设计指南);容限: 内部工程容限:临界角 |
| printability | printability.check_powder_escape | trapped_void_mm3=0.0; voxel_pitch_mm=0.25; tolerance_mm3=0.125 | ✓ | 困粉: embree 列射线奇偶填充 + scipy flood-fill(bench_printability3.py |
| density | rel_density.mesh(manifold3d) | 0.41188 | ✓ | manifold3d watertight 体积 / 胞体积 |
| mechanics | gibson_ashby.estimate | E_MPa=288.39225077296766; sigma_y_MPa=3.5684923276621503; model=Gibson-Ashby (bending) | ℹ️ | Gibson & Ashby, Cellular Solids, 2nd ed., Cambridge UP, 1997 |
| topology_tendency | maxwell_check | maxwell_M=-30; tendency=bending-leaning | ✓ | Maxwell 1864; Deshpande, Ashby & Fleck, Acta Mater. 49(6):10 |
| mechanics | retriever.nearest_by_density+comp_EA | 242.527283 | ✓ | internal FEA feature extraction: data_package/extracted_feat |
| material | material_props[AlSi10Mg_LPBF] | 75 | ✓ | EOS AlSi10Mg datasheet, as-built E ~75 GPa |
| material | surface_defect_knockdown | 0.92 | ✓ | 内部工程假设,查无文献出处(2026-06-10 调研);中期应以 Zhong 2023 effective-strut |
| size_effect | scaling.n_cells_advisory | 3 | ℹ️ | Onck/Andrews 2001 边界层机制(atlas/references);修正引擎接线归 P2 |
| mechanics | dynamic_data_availability | 89 | ℹ️ | cell_db.sqlite curves 表 |

判决依据:硬性检查未过: printability/printability.check_overhangs

降级记录:R4: material/surface_defect_knockdown 证据为 inference,结论降级一档

拓扑倾向(Maxwell,必要非充分,只说倾向):M=-30,bending-leaning

## 来源清单(三类分列)

### 厂商标准/数据表
- EOS AlSi10Mg datasheet, as-built E ~75 GPa

### 内部 FEA 数据库
- internal FEA feature extraction: data_package/extracted_features_smoothed.csv (mtime 2026-01-21), derived from the same Abaqus pipeline

### 内部确定性计算
- Deshpande, Fleck & Ashby, JMPS 49(8):1747-1769, 2001, DOI 10.1016/S0022-5096(01)00010-2 (octet pin-jointed: E*=(1/9) rho Es, sigma_y*=(1/3) rho sigma_ys)
- Gibson & Ashby, Cellular Solids, 2nd ed., Cambridge UP, 1997 (bending: E*~rho^2, sigma_y*~0.3 rho^1.5)
- Maxwell 1864; Deshpande, Ashby & Fleck, Acta Mater. 49(6):1035-1040, 2001, DOI 10.1016/S1359-6454(00)00379-7
- Onck/Andrews 2001 边界层机制(atlas/references);修正引擎接线归 P2
- cell_db.sqlite curves 表
- manifold3d watertight 体积 / 胞体积
- trimesh 边-面计数 + manifold3d Mesh.merge 往返 status(双引擎,bench_printability.py 本机验证)
- 困粉: embree 列射线奇偶填充 + scipy flood-fill(bench_printability3.py 正负对照验证)
- 自支撑角: LPBF 自支撑角行业共识区间(EOS/SLM Solutions 设计指南);容限: 内部工程容限:临界角以下面积占比 ≤5% 视为可接受(节点附近局部小面不可避免);无文献支撑;方法: 面法向分类(毫秒级,bench 验证)
- 阈值: 内部保守取值;文献设计指南给 0.4-0.6 mm(约保守 2 倍),记录在案后续可论证放宽;方法: embree 射线测厚(bench 验证 BCC d=1.0 误差 0.1-0.5%)

### 标记推测(inference,已降级)
- 内部工程假设,查无文献出处(2026-06-10 调研);中期应以 Zhong 2023 effective-strut-diameter 框架替代, DOI 10.1016/j.cossms.2023.101081

## 适用域与警示
- Tier-2 候选(如有)为库外生成,其力学结论为 screening only,待物理计算裁判(Phase 2 beam-FEM / Tier-D FEA);与 Tier-1 检索结论分层呈现,不混叙。
- 动态/剪切维度仅报数据可用性,验证成熟度属 Phase 2/3。

---
本报告为计算与数据库辅助选型,最终设计须经实物压缩测试验证。

⚠️ 高风险场景(航空结构件):本报告输出仅作筛选,不得直接用于定型设计。
