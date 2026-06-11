# Tier-D ABAQUS 终审实测结果(2026-06-11,本地 ABAQUS 2023,8 核)

四作业全部求解成功;能量门(ALLKE/ALLIE≤5%,Abaqus 准静态准则)全过。
提取口径:E* = 0–0.10mm 位移窗线性拟合 ×H/A(与 P2-1c 标定同口径,
0–0.05mm 双窗校验一致);comp_EA = ∫F·dδ 全可用曲线(0–3mm,
与 DB comp_EA 窗口径对照前不可直接比绝对值,caveat 入 trace)。

## 实测 vs 筛选级预测

| 作业 | ρ̄(实测) | 能量门 | E* n=1 (MPa) | comp_EA (mJ) | 筛选 bulk E_y | 实测/frame-n1 预测 |
|---|---|---|---|---|---|---|
| dual_column_web | 0.1232 | 0.0016 | 73.2 | 276.8 | 129.9 | **1.10**(frame 比值 0.513 预测准确) |
| mid_braced_column | 0.0829 | 0.0128 | 33.1 | 57.1 | 64.6 | **0.51**(frame 比值 1.0 高估 2×) |
| twin_offset_web | 0.0836 | 0.0016 | 33.4 | 54.1 | 64.6 | **0.52**(同上) |
| PSCZ_pillar_steepcross | 0.2354 | 0.0024 | 5.4* | 115.2 | —(D2 新图,无筛选 E_y 记录) | — |

\* PSCZ E* 低是真实几何特征(陡交叉杆轴向刚度路径弱),其设计意图是
LPBF 自支撑 + 吸能(comp_EA),不是刚度。

## 发现(入 PROGRESS / P3 输入)

1. **frame n=1 梁模型类依赖偏差**:对「角柱+web」族(dual_column)
   预测准确(±10%);对「贯通柱+撑板」族(mid_braced/twin_offset)
   系统性高估 ~2×。P2-1c 分层修正拟合于 24 个库内拓扑——其中没有
   纯贯通柱+撑板族,此为 Tier-D 抓到的真 OOD 模型偏差,
   是 P3 节点刚化升级(slide-8 路线)的第一笔实测输入。
2. **冠军排名在 Tier-D 下保持**:dual_column_web 仍显著领先
   (E*/ρ̄ = 594 vs 399/400),但绝对优势倍数从筛选级 1.77× 收缩
   (注意:均匀半径作业,polish 组半径增益不在本测试内,见 job_meta)。
3. **PSCZ 终审判决 PASS(margin 1.92)**:第一条新拓扑全链闭环
   (LLM 提案 → C1–C9 → WL → 可打印性[E12 修正后 0.0103] →
   Tier-D 实测 → R 系引擎 PASS,R4 inference 降级留痕)。
   trace = `pscz_lpbf/final_trace.json`。
4. comp_EA 绝对单位映射(DB 代理 ↔ Tier-D 实测)对照条件已具备:
   同一拓扑(如 BCC)跑一个 Tier-D 作业即可标定窗口径差,归 backlog。

## 留痕

- 每作业:`<job>/feature_data.txt` + `energy_data.txt`(原始)、
  `tier_d_checks.json`(桥接产物)、`runlocal.log`
- PSCZ 终审:`pscz_lpbf/final_trace.json`(D2 可打印性证据 + Tier-D
  力学证据合并判决)
- 复跑:`run_local.ps1`(串行四作业;求解过程产物已 .gitignore)
