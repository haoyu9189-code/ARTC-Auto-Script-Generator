# ATLAS 选型报告:SLS PA12 吸能缓冲块

工艺/材料:SLS / PA12;阵列 n=4;FoS=1.3(**设计值已含 FoS,margin = pred/design,任何环节不再二次乘**);置信度等级:screening(筛选级)。

搜索范围:候选在 cell DB(5,304 结构)+ 生成层内比较,推荐为 **database-wide(数据库范围内)最优**,不主张绝对全局最优。

## 推荐表

| 候选 | Tier | 拓扑 | ρ̄(实算) | margin(pred/design) | 判决 |
|------|------|------|----------|---------------------|------|
| sa1 | Tier-1 | BCC | 0.21729 | 4.16 | PASS |
| sa2 | Tier-1 | Diamond | 0.20598 | 4.47 | PASS |
| sa3 | Tier-1 | G7 | 0.41438 | 4.72 | PASS |

margin 度量:comp_EA(库内同单位代理),设计值(含 FoS)= 55.0。注:库内 comp_EA 的绝对单位映射待 P2-5 标定,本列为同单位代理比较(source_type=inference 级别的单位假设,已降级)。

## 验证 trace(每个数字可溯源)

### 候选 sa1(Tier-1)

| 维度 | 工具 | 值 | 通过 | 来源 |
|------|------|----|------|------|
| printability | printability.validate_mesh | watertight=True; winding_consistent=True; is_volume=True | ✓ | trimesh 边-面计数 + manifold3d Mesh.merge 往返 status(双引擎,bench_pr |
| printability | printability.measure_min_feature | min_mm=0.9709268047902837; p5_mm=0.9914447930595309; median_mm=0.9914448691316426 | ✓ | 阈值: EOS PA12 (PA 2200) design guidelines, min wall/feature ~ |
| printability | printability.check_overhangs | overhang_area_fraction=0.0 | ✓ | 粉末床聚合物无需支撑,悬垂检查不适用(skip) |
| printability | printability.check_powder_escape | trapped_void_mm3=0.0; voxel_pitch_mm=0.25; tolerance_mm3=0.125 | ✓ | 困粉: embree 列射线奇偶填充 + scipy flood-fill(bench_printability3.py |
| density | rel_density.mesh(manifold3d) | 0.21729 | ✓ | manifold3d watertight 体积 / 胞体积 |
| mechanics | gibson_ashby.estimate | E_MPa=80.26831479499671; sigma_y_MPa=1.3674302604874344; model=Gibson-Ashby (bending) | ℹ️ | Gibson & Ashby, Cellular Solids, 2nd ed., Cambridge UP, 1997 |
| topology_tendency | maxwell_check | maxwell_M=-13; tendency=bending-leaning | ✓ | Maxwell 1864; Deshpande, Ashby & Fleck, Acta Mater. 49(6):10 |
| mechanics | retriever.nearest_by_density+comp_EA | 228.638984 | ✓ | internal FEA feature extraction: data_package/extracted_feat |
| material | material_props[PA12_MJF] | 1700 | ✓ | HP 3D HR PA12 datasheet, tensile modulus ~1700-1800 MPa |
| size_effect | scaling.n_cells_advisory | 4 | ℹ️ | Onck/Andrews 2001 边界层机制(atlas/references);修正引擎接线归 P2 |
| mechanics | dynamic_shear_features | n_dynamic_curves=90; dyna_peak=2.5426; dyna_stiffness=39.7186 | ℹ️ | P2-5 原始曲线自提(atlas/data/extract_dynamic.py):dyna_stiffness=5% |

判决依据:全维度通过,margin 4.157 >= 1.0

拓扑倾向(Maxwell,必要非充分,只说倾向):M=-13,bending-leaning

### 候选 sa2(Tier-1)

| 维度 | 工具 | 值 | 通过 | 来源 |
|------|------|----|------|------|
| printability | printability.validate_mesh | watertight=True; winding_consistent=True; is_volume=True | ✓ | trimesh 边-面计数 + manifold3d Mesh.merge 往返 status(双引擎,bench_pr |
| printability | printability.measure_min_feature | min_mm=0.9816713826209567; p5_mm=0.9914447732690969; median_mm=0.9914448597150016 | ✓ | 阈值: EOS PA12 (PA 2200) design guidelines, min wall/feature ~ |
| printability | printability.check_overhangs | overhang_area_fraction=0.0 | ✓ | 粉末床聚合物无需支撑,悬垂检查不适用(skip) |
| printability | printability.check_powder_escape | trapped_void_mm3=0.0; voxel_pitch_mm=0.25; tolerance_mm3=0.125 | ✓ | 困粉: embree 列射线奇偶填充 + scipy flood-fill(bench_printability3.py |
| density | rel_density.mesh(manifold3d) | 0.20598 | ✓ | manifold3d watertight 体积 / 胞体积 |
| mechanics | gibson_ashby.estimate | E_MPa=72.13059350092884; sigma_y_MPa=1.2620794830261364; model=Gibson-Ashby (bending) | ℹ️ | Gibson & Ashby, Cellular Solids, 2nd ed., Cambridge UP, 1997 |
| topology_tendency | maxwell_check | maxwell_M=-20; tendency=bending-leaning | ✓ | Maxwell 1864; Deshpande, Ashby & Fleck, Acta Mater. 49(6):10 |
| mechanics | retriever.nearest_by_density+comp_EA | 246.042478 | ✓ | internal FEA feature extraction: data_package/extracted_feat |
| material | material_props[PA12_MJF] | 1700 | ✓ | HP 3D HR PA12 datasheet, tensile modulus ~1700-1800 MPa |
| size_effect | scaling.n_cells_advisory | 4 | ℹ️ | Onck/Andrews 2001 边界层机制(atlas/references);修正引擎接线归 P2 |
| mechanics | dynamic_shear_features | n_dynamic_curves=86; dyna_peak=3.1021; dyna_stiffness=52.3774 | ℹ️ | P2-5 原始曲线自提(atlas/data/extract_dynamic.py):dyna_stiffness=5% |

判决依据:全维度通过,margin 4.473 >= 1.0

拓扑倾向(Maxwell,必要非充分,只说倾向):M=-20,bending-leaning

### 候选 sa3(Tier-1)

| 维度 | 工具 | 值 | 通过 | 来源 |
|------|------|----|------|------|
| printability | printability.validate_mesh | watertight=True; winding_consistent=True; is_volume=True | ✓ | trimesh 边-面计数 + manifold3d Mesh.merge 往返 status(双引擎,bench_pr |
| printability | printability.measure_min_feature | min_mm=0.9914446818267799; p5_mm=0.9914447389808767; median_mm=0.9914448640321862 | ✓ | 阈值: EOS PA12 (PA 2200) design guidelines, min wall/feature ~ |
| printability | printability.check_overhangs | overhang_area_fraction=0.0 | ✓ | 粉末床聚合物无需支撑,悬垂检查不适用(skip) |
| printability | printability.check_powder_escape | trapped_void_mm3=0.0; voxel_pitch_mm=0.25; tolerance_mm3=0.125 | ✓ | 困粉: embree 列射线奇偶填充 + scipy flood-fill(bench_printability3.py |
| density | rel_density.mesh(manifold3d) | 0.41438 | ✓ | manifold3d watertight 体积 / 胞体积 |
| mechanics | gibson_ashby.estimate | E_MPa=78.27260091317252; sigma_y_MPa=6.215765366634289; model=DFA octet (stretch) | ℹ️ | Deshpande, Fleck & Ashby, JMPS 49(8):1747-1769, 2001, DOI 10 |
| topology_tendency | maxwell_check | maxwell_M=-5; tendency=bending-leaning | ✓ | Maxwell 1864; Deshpande, Ashby & Fleck, Acta Mater. 49(6):10 |
| mechanics | retriever.nearest_by_density+comp_EA | 259.378851 | ✓ | internal FEA feature extraction: data_package/extracted_feat |
| material | material_props[PA12_MJF] | 1700 | ✓ | HP 3D HR PA12 datasheet, tensile modulus ~1700-1800 MPa |
| size_effect | scaling.n_cells_advisory | 4 | ℹ️ | Onck/Andrews 2001 边界层机制(atlas/references);修正引擎接线归 P2 |
| mechanics | dynamic_shear_features | n_dynamic_curves=90; dyna_peak=3.5294; dyna_stiffness=46.1174 | ℹ️ | P2-5 原始曲线自提(atlas/data/extract_dynamic.py):dyna_stiffness=5% |

判决依据:全维度通过,margin 4.716 >= 1.0

拓扑倾向(Maxwell,必要非充分,只说倾向):M=-5,bending-leaning

## 来源清单(三类分列)

### 厂商标准/数据表
- HP 3D HR PA12 datasheet, tensile modulus ~1700-1800 MPa

### 内部 FEA 数据库
- internal FEA feature extraction: data_package/extracted_features_smoothed.csv (mtime 2026-01-21), derived from the same Abaqus pipeline

### 内部确定性计算
- Deshpande, Fleck & Ashby, JMPS 49(8):1747-1769, 2001, DOI 10.1016/S0022-5096(01)00010-2 (octet pin-jointed: E*=(1/9) rho Es, sigma_y*=(1/3) rho sigma_ys)
- Gibson & Ashby, Cellular Solids, 2nd ed., Cambridge UP, 1997 (bending: E*~rho^2, sigma_y*~0.3 rho^1.5)
- Maxwell 1864; Deshpande, Ashby & Fleck, Acta Mater. 49(6):1035-1040, 2001, DOI 10.1016/S1359-6454(00)00379-7
- Onck/Andrews 2001 边界层机制(atlas/references);修正引擎接线归 P2
- P2-5 原始曲线自提(atlas/data/extract_dynamic.py):dyna_stiffness=5% 应变割线(含惯性瞬态,非弹性模量,Phase 3 滤波后重提);dyna_yield=首个局部峰应力(落锤动态屈服代理);peak 取前 30% 应变窗;剪切面积=名义 25mm²(约定);曲线源=内部 Abaqus 显式管线(步长 ~0.1mm)
- manifold3d watertight 体积 / 胞体积
- trimesh 边-面计数 + manifold3d Mesh.merge 往返 status(双引擎,bench_printability.py 本机验证)
- 困粉: embree 列射线奇偶填充 + scipy flood-fill(bench_printability3.py 正负对照验证)
- 粉末床聚合物无需支撑,悬垂检查不适用(skip)
- 阈值: EOS PA12 (PA 2200) design guidelines, min wall/feature ~0.8 mm;方法: embree 射线测厚(bench 验证 BCC d=1.0 误差 0.1-0.5%)

## 适用域与警示
- Tier-2 候选(如有)为库外生成,其力学结论为 screening only,待物理计算裁判(Phase 2 beam-FEM / Tier-D FEA);与 Tier-1 检索结论分层呈现,不混叙。
- 动态/剪切维度仅报数据可用性,验证成熟度属 Phase 2/3。

---
本报告为计算与数据库辅助选型,最终设计须经实物压缩测试验证。
