# Tier-D ABAQUS 终审作业(P3-A 生成)

冠军:dual_column_web, mid_braced_column, twin_offset_web(FunSearch P2-2)

## 提交(由用户决定,loop 协议)

- 集群:`qsub run.pbs`(config.py 当前为 PBS 口径)
- 本地:`abaqus cae noGUI=preprocess_*.py` → 求解 → `abaqus cae noGUI=postprocess_*.py`

## 产物回收

求解后目录内出现 `feature_data.txt` + `energy_data.txt`,运行:

```python
from atlas.mechanics.tier_d import results_to_checks
checks = results_to_checks(job_dir, spec)  # → judge() 可消费
```

能量门:ALLKE/ALLIE ≤ 0.05(Abaqus Analysis User's Guide — quasi-static energy balance criterion(ALLKE ≤ ~5% ALLIE));Standard 静力分析无 ALLKE 历史时门不适用(informational)。

## 已知限定

- 管线为单半径:CMA-ES polish 的 radii_groups 不可表示,按均匀 default_radius_mm=0.5 生成——冠军分数中的逐组半径增益不在本次 Tier-D 测试内
- 管线为单半径:CMA-ES polish 的 radii_groups 不可表示,按均匀 default_radius_mm=0.5 生成——冠军分数中的逐组半径增益不在本次 Tier-D 测试内
- 管线为单半径:CMA-ES polish 的 radii_groups 不可表示,按均匀 default_radius_mm=0.5 生成——冠军分数中的逐组半径增益不在本次 Tier-D 测试内