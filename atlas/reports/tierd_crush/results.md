# Phase 4:非线性/吸能 Tier-D —— 验证报告(NT-1…NT-6)

> GOAL:让物理终审能认证**非线性吸能**(SEA/comp_EA/平台/致密化),
> 经准静态显式压溃(大变形+自接触+致密化),硬门全过后成 margin 级。
> 代码:`atlas/mechanics/tier_d.py`(crush_metrics / results_to_checks_crush /
> generate_crush_job / patch_displacement_control / route_energy_spec_to_crush);
> 测试:`atlas/tests/test_tier_d.py`(22)+ `test_screen_estimate.py`(14)全绿。

## 1. 管线(复用已有显式基础设施 + 文本注入,不改 generator 源)

- 显式动力学步 + 自接触(GeneralContact)+ nlgeom + 质量缩放 + 单元删除:
  **script_generator 已有**;Tier-D 仅接线。
- **NT-1 注入**:① whole-model 能量历史(ALLKE/ALLIE/ALLAE/ALLVD/ALLFD,
  填补原 H-Output 只取板 U/RF 的缺口);② **位移控制斜坡**(SmoothStep)——
  原 DynaCompre 是「自由板+初速度冲击」,准静态低速下板几乎不压入、顶板
  RF2≈0;改为位移驱动顶板 → RF2=真实阻力。均文本注入,幂等、锚点缺失 fail-loud。

## 2. 指标提取(NT-2,ISO 13314 + Li 2006)

- 致密化 ε_d = 能量吸收效率 η(ε)=W/σ 的全局峰(限 ε>0.1);
- **comp_EA 积分严格截到 δ_d=ε_d·H0**(修掉积满全曲线导致 SEA 虚高的主坑);
- 平台应力 σ_pl = 20–40% 应变均值(或截到 ε_d);
- **SEA = comp_EA ÷ 实心杆质量**(m=ρ_material·V0·ρ̄,非包络质量);
- 载荷轴 Y:H0=CELL·ny、A0=CELL²·nx·nz(n>1 轴向约定已修正)。

## 3. 硬有效性门(NT-3)+ margin 接线(NT-4)

五硬门全过才 `margin_eligible`(abaqus_fea):① ALLKE/ALLIE≤5%(准静态)
② ALLAE/ALLIE≤5%(沙漏)③ 接触耗散(ALLVD+ALLFD)/ALLIE≤10% ④ 致密化已达
⑤ **SEA 在材料合理带内**(errata E4:PA12 0.3–8 kJ/kg)。任一不过 → screening,
留 caveat。judge 全链测试:门全过+带内+吸能 metric → PASS(margin>1);
否则 FAIL/SCREENING。

## 4. 本机验证(NT-5)—— dual_column_web,本机 ABAQUS 2023

| 量 | 标称 10/s | 半速 5/s | 判定 |
|---|---|---|---|
| ALLKE/ALLIE | 0.0096 | 0.010 | ✅ 准静态(≪5%)|
| ALLAE/ALLIE | 0.0 | 0.0 | ✅ |
| 致密化 ε_d | 0.620 | 0.616 | ✅ 检出 |
| 平台应力 σ_pl | 3.74 MPa | 3.73 MPa | — |
| comp_EA(截 ε_d)| 289.5 mJ | 284.9 mJ | — |
| SEA | 18.6 kJ/kg | 18.3 kJ/kg | ⚠ 见下 |

**三项验证通过**:① **半速不变性 |ΔSEA|=1.6%(<5%)→ 准静态稳健、rate-independent**
(准静态定论检验);② comp_EA(截致密化)289.5 ≈ 静态 StaCompre 276.8 mJ(差 5%,
**跨方法互验**);③ comp_EA 截断值 < 全曲线(483.6,截断修正生效)。

**诚实卡口生效**:SEA=18.6 kJ/kg **超 PA12 合理带(0.3–8)**——因 **n=1 单胞平台
直载边界效应高估**(非速率假象,已由 rate-invariance 排除)→ 系统正确判
`margin_eligible=False`、留「超带 + n=1 边界 + 须 n≥3」caveat。**物理计算有效 ≠
绝对值可信**:代表性 margin 级 SEA 须 n≥3 阵列(轴向约定已修正以支持)。

## 5. 闭环(NT-6)

screen_estimate 对 comp_EA/SEA spec **标 `escalate_tier_d` + `escalate_target=
crush_tier_d`**(beam 模量算不出吸能);`route_energy_spec_to_crush(doc,spec,out)`
为其落地(生成位移控制压溃作业)——补上 P3-D「吸能被推给 Tier-D 但无路径」的缺口。
全链:**生成(Tier-2 新图)→ 筛选(beam 排序+判吸能须升压)→ 压溃终审(硬门+SEA)→
判决**,在 dual_column_web 上端到端跑通;n=1 落 screening(诚实),margin 级待 n≥3。

## 6. 调试教训(均真跑暴露,非测试能抓)

① 生成脚本相对路径 `os.chdir` → 绝对 out_dir;② Abaqus XY 报表 "0." 格式 →
`_FLOAT_PAIR` 修正;③ 全零 Velocity 被 Abaqus 拒 → 整段删除初速度场;
④ 自由板初速度冲击 ≠ 准静态压溃 → 位移控制。

## 7. 结论

非线性/吸能 Tier-D **管线建成并验证**:能在任意拓扑(含新图/OOD)自身几何上
做准静态显式压溃,提 SEA/平台/致密化,五硬门把关,rate-invariance 实证。
吸能从此有了**物理终审通路**(补 beam/screen_estimate 的吸能盲区)。
**遗留(已记 backlog)**:n≥3 代表性 SEA 跑(去 n=1 边界,进合理带→可授 margin)。
