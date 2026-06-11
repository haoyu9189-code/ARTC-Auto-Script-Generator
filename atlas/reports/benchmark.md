# ATLAS 多 agent vs 单 agent 基线(P3-C,3 案例指示性对照)

> 多 agent = 真子代理派发(D2);基线 = 同工具可达、无管线合同/确定性引擎/红线注入的单 agent。
> n=3 为指示性(indicative)非统计显著;conventional CAD+FEA 工作流基线未实现,不伪造。
> 溯源率口径:ATLAS source 列为 schema 强制(=100% 由构造保证,<100% 即违例);「类型化」= source_type 标注覆盖率(成熟度指标,缺口归 backlog);基线 = 自报 key_numbers 的 source 指向工具/库的占比(自由文本,无强制)。

| case | ATLAS 时(s) | ATLAS tok | ATLAS source(强制) | ATLAS 类型化 | 基线时(s) | 基线 tok | 基线溯源率 | 基线判决与引擎一致率 |
|---|---|---|---|---|---|---|---|---|
| sls_absorber | 931 | 124,008 | 100% | 33% | — | — | 58% | 100% (n=3) |
| lpbf_bracket | 864 | 99,189 | 100% | 43% | — | — | 59% | 33% (n=3) |
| mjf_auxetic_pad | 954 | 106,678 | 100% | 24% | 461.6 | 68,710 | 33% | 67% (n=3) |

## 判决分歧明细(基线自报 vs 确定性引擎 ground truth)

### sls_absorber
- ✓ BCC_5_0p5_3: 基线 PASS vs 引擎 PASS(全维度通过,margin 4.157 >= 1.0)
- ✓ Kelvin_5_0p5_3: 基线 PASS vs 引擎 PASS(全维度通过,margin 4.410 >= 1.0)
- ✓ WeairePhelan_5_0p4_6: 基线 FAIL vs 引擎 FAIL(硬性检查未过: printability/printability.measure_min_feature)

### lpbf_bracket
- ✗ C1_BCC_s8_r0.55: 基线 PASS vs 引擎 FAIL(硬性检查未过: printability/printability.check_overhangs)
- ✗ C2_Diamond_s3_r0.55: 基线 PASS vs 引擎 FAIL(硬性检查未过: printability/printability.check_overhangs)
- ✓ C3_Truncated_cube_s8_r0.5: 基线 FAIL vs 引擎 FAIL(硬性检查未过: printability/printability.measure_min_feature; 硬性检查未过: printability/printability.check_overhangs)

### mjf_auxetic_pad
- ✗ C1_max_auxetic: 基线 FAIL vs 引擎 PASS(全维度通过,margin 12.090 >= 1.0)
- ✓ C2_balanced: 基线 PASS vs 引擎 PASS(全维度通过,margin 12.090 >= 1.0)
- ✓ C3_stiff_backup: 基线 PASS vs 引擎 PASS(全维度通过,margin 12.090 >= 1.0)

## 留痕

- 多 agent 原始计量:`atlas/reports/D2/agent_run_metrics.json`(harness usage)+ 各 case `timings.json`(perf_counter)
- 一致性对照:各 case `consistency.json`(agent 载体 ↔ 引擎直跑 22/22 全等)
- 基线产物:各 case `baseline/baseline_{report.md,result.json}`
- 引擎直跑耗时 ~0.1–0.2 s/案例:agent 的价值在证据编组与自治,不在算得快——这正是判决必须留在确定性引擎里的理由。