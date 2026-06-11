# ATLAS 选型报告:MJF PA12 auxetic 缓冲垫

工艺/材料:MJF / PA12;阵列 n=2;FoS=1.3(**设计值已含 FoS,margin = pred/design,任何环节不再二次乘**);置信度等级:screening(筛选级)。

搜索范围:候选在 cell DB(5,304 结构)+ 生成层内比较,推荐为 **database-wide(数据库范围内)最优**,不主张绝对全局最优。

## 推荐表

| 候选 | Tier | 拓扑 | ρ̄(实算) | margin(pred/design) | 判决 |
|------|------|------|----------|---------------------|------|
| ax1 | Tier-1 | Auxetic | 0.49553 | 12.09 | PASS |
| ax2 | Tier-1 | CBCC | 0.51216 | 7.86 | PASS |
| ax3 | Tier-2 | cubic_plus_diagonal | 0.13948 | 无可用证据 | FAIL |

margin 度量:comp_EA(库内同单位代理),设计值(含 FoS)= 40.0。注:库内 comp_EA 的绝对单位映射待 P2-5 标定,本列为同单位代理比较(source_type=inference 级别的单位假设,已降级)。

## 验证 trace(每个数字可溯源)

### 候选 ax1(Tier-1)

| 维度 | 工具 | 值 | 通过 | 来源 |
|------|------|----|------|------|
| printability | printability.validate_mesh | watertight=True; winding_consistent=True; is_volume=True | ✓ | trimesh 边-面计数 + manifold3d Mesh.merge 往返 status(双引擎,bench_pr |
| printability | printability.measure_min_feature | min_mm=0.980328094391314; p5_mm=0.9914447373862648; median_mm=0.9914448819526133 | ✓ | 阈值: HP Multi Jet Fusion PA12 design guidelines, min feature  |
| printability | printability.check_overhangs | overhang_area_fraction=0.0 | ✓ | 粉末床聚合物无需支撑,悬垂检查不适用(skip) |
| printability | printability.check_powder_escape | trapped_void_mm3=0.0; voxel_pitch_mm=0.25; tolerance_mm3=0.125 | ✓ | 困粉: embree 列射线奇偶填充 + scipy flood-fill(bench_printability3.py |
| density | rel_density.mesh(manifold3d) | 0.49553 | ✓ | manifold3d watertight 体积 / 胞体积 |
| mechanics | gibson_ashby.estimate | E_MPa=93.60092485839793; sigma_y_MPa=4.709169911892419; model=hybrid envelope (conservative min of bending/stretch) | ℹ️ | Gibson & Ashby, Cellular Solids, 2nd ed., Cambridge UP, 1997 |
| topology_tendency | maxwell_check | maxwell_M=-56; tendency=bending-leaning | ✓ | Maxwell 1864; Deshpande, Ashby & Fleck, Acta Mater. 49(6):10 |
| mechanics | retriever.nearest_by_density+comp_EA | 483.619329 | ✓ | internal FEA feature extraction: data_package/extracted_feat |
| material | material_props[PA12_MJF] | 1700 | ✓ | HP 3D HR PA12 datasheet, tensile modulus ~1700-1800 MPa |
| size_effect | scaling.n_cells_advisory | 2 | ℹ️ | Onck/Andrews 2001 边界层机制(atlas/references);修正引擎接线归 P2 |
| mechanics | dynamic_shear_features | n_dynamic_curves=88; dyna_peak=3.4591; dyna_stiffness=52.0381 | ℹ️ | P2-5 原始曲线自提(atlas/data/extract_dynamic.py):dyna_stiffness=5% |

判决依据:全维度通过,margin 12.090 >= 1.0

降级记录:R3: n<3,尺寸效应区强警示(1→3 胞跳变最剧烈),强烈建议 n>=3 或实测

拓扑倾向(Maxwell,必要非充分,只说倾向):M=-56,bending-leaning

### 候选 ax2(Tier-1)

| 维度 | 工具 | 值 | 通过 | 来源 |
|------|------|----|------|------|
| printability | printability.validate_mesh | watertight=True; winding_consistent=True; is_volume=True | ✓ | trimesh 边-面计数 + manifold3d Mesh.merge 往返 status(双引擎,bench_pr |
| printability | printability.measure_min_feature | min_mm=0.991444698503666; p5_mm=0.9914447450083298; median_mm=0.9914448397711875 | ✓ | 阈值: HP Multi Jet Fusion PA12 design guidelines, min feature  |
| printability | printability.check_overhangs | overhang_area_fraction=0.0 | ✓ | 粉末床聚合物无需支撑,悬垂检查不适用(skip) |
| printability | printability.check_powder_escape | trapped_void_mm3=0.0; voxel_pitch_mm=0.25; tolerance_mm3=0.125 | ✓ | 困粉: embree 列射线奇偶填充 + scipy flood-fill(bench_printability3.py |
| density | rel_density.mesh(manifold3d) | 0.51216 | ✓ | manifold3d watertight 体积 / 胞体积 |
| mechanics | gibson_ashby.estimate | E_MPa=445.9297917739204; sigma_y_MPa=4.94819656291687; model=Gibson-Ashby (bending) | ℹ️ | Gibson & Ashby, Cellular Solids, 2nd ed., Cambridge UP, 1997 |
| topology_tendency | maxwell_check | maxwell_M=-1; tendency=bending-leaning | ✓ | Maxwell 1864; Deshpande, Ashby & Fleck, Acta Mater. 49(6):10 |
| mechanics | retriever.nearest_by_density+comp_EA | 314.26514 | ✓ | internal FEA feature extraction: data_package/extracted_feat |
| material | material_props[PA12_MJF] | 1700 | ✓ | HP 3D HR PA12 datasheet, tensile modulus ~1700-1800 MPa |
| size_effect | scaling.n_cells_advisory | 2 | ℹ️ | Onck/Andrews 2001 边界层机制(atlas/references);修正引擎接线归 P2 |
| mechanics | dynamic_shear_features | n_dynamic_curves=90; dyna_peak=4.3501; dyna_stiffness=69.8338 | ℹ️ | P2-5 原始曲线自提(atlas/data/extract_dynamic.py):dyna_stiffness=5% |

判决依据:全维度通过,margin 7.857 >= 1.0

降级记录:R3: n<3,尺寸效应区强警示(1→3 胞跳变最剧烈),强烈建议 n>=3 或实测

拓扑倾向(Maxwell,必要非充分,只说倾向):M=-1,bending-leaning

### 候选 ax3(Tier-2)

| 维度 | 工具 | 值 | 通过 | 来源 |
|------|------|----|------|------|
| printability | printability.validate_mesh | watertight=True; winding_consistent=True; is_volume=True | ✓ | trimesh 边-面计数 + manifold3d Mesh.merge 往返 status(双引擎,bench_pr |
| printability | printability.measure_min_feature | min_mm=0.9914448449300887; p5_mm=0.9914448484310624; median_mm=0.9915974042857006 | ✓ | 阈值: HP Multi Jet Fusion PA12 design guidelines, min feature  |
| printability | printability.check_overhangs | overhang_area_fraction=0.0 | ✓ | 粉末床聚合物无需支撑,悬垂检查不适用(skip) |
| printability | printability.check_powder_escape | trapped_void_mm3=0.0; voxel_pitch_mm=0.25; tolerance_mm3=0.125 | ✓ | 困粉: embree 列射线奇偶填充 + scipy flood-fill(bench_printability3.py |
| density | rel_density.mesh(manifold3d) | 0.13948 | ✓ | manifold3d watertight 体积 / 胞体积 |
| material | material_props[PA12_MJF] | 1700 | ✓ | HP 3D HR PA12 datasheet, tensile modulus ~1700-1800 MPa |
| size_effect | scaling.n_cells_advisory | 2 | ℹ️ | Onck/Andrews 2001 边界层机制(atlas/references);修正引擎接线归 P2 |

判决依据:R2: 无可用 margin 证据(pred/design 缺失)

降级记录:R3: n<3,尺寸效应区强警示(1→3 胞跳变最剧烈),强烈建议 n>=3 或实测

## 来源清单(三类分列)

### 厂商标准/数据表
- HP 3D HR PA12 datasheet, tensile modulus ~1700-1800 MPa

### 内部 FEA 数据库
- internal FEA feature extraction: data_package/extracted_features_smoothed.csv (mtime 2026-01-21), derived from the same Abaqus pipeline

### 内部确定性计算
- Gibson & Ashby, Cellular Solids, 2nd ed., Cambridge UP, 1997 (bending: E*~rho^2, sigma_y*~0.3 rho^1.5)
- Gibson & Ashby, Cellular Solids, 2nd ed., Cambridge UP, 1997 (bending: E*~rho^2, sigma_y*~0.3 rho^1.5) + Deshpande, Fleck & Ashby, JMPS 49(8):1747-1769, 2001, DOI 10.1016/S0022-5096(01)00010-2 (octet pin-jointed: E*=(1/9) rho Es, sigma_y*=(1/3) rho sigma_ys)
- Maxwell 1864; Deshpande, Ashby & Fleck, Acta Mater. 49(6):1035-1040, 2001, DOI 10.1016/S1359-6454(00)00379-7
- Onck/Andrews 2001 边界层机制(atlas/references);修正引擎接线归 P2
- P2-5 原始曲线自提(atlas/data/extract_dynamic.py):dyna_stiffness=5% 应变割线(含惯性瞬态,非弹性模量,Phase 3 滤波后重提);dyna_yield=首个局部峰应力(落锤动态屈服代理);peak 取前 30% 应变窗;剪切面积=名义 25mm²(约定);曲线源=内部 Abaqus 显式管线(步长 ~0.1mm)
- manifold3d watertight 体积 / 胞体积
- trimesh 边-面计数 + manifold3d Mesh.merge 往返 status(双引擎,bench_printability.py 本机验证)
- 困粉: embree 列射线奇偶填充 + scipy flood-fill(bench_printability3.py 正负对照验证)
- 粉末床聚合物无需支撑,悬垂检查不适用(skip)
- 阈值: HP Multi Jet Fusion PA12 design guidelines, min feature ~0.8 mm;方法: embree 射线测厚(bench 验证 BCC d=1.0 误差 0.1-0.5%)

## 适用域与警示
- n=2 < 3:尺寸效应强警示(1→3 胞跳变最剧烈),建议 n≥3 或实测。
- Tier-2 候选(如有)为库外生成,其力学结论为 screening only,待物理计算裁判(Phase 2 beam-FEM / Tier-D FEA);与 Tier-1 检索结论分层呈现,不混叙。
- 动态/剪切维度仅报数据可用性,验证成熟度属 Phase 2/3。

---
本报告为计算与数据库辅助选型,最终设计须经实物压缩测试验证。
