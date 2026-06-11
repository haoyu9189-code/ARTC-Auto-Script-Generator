# Baseline 报告:MJF PA12 auxetic 缓冲垫(单 agent 基线)

- 工况:`atlas/reports/D2/mjf_auxetic_pad/spec.json` — MJF / PA12 / n_cells=2,
  screening 级,裕度指标 comp_EA(库内同单位代理),设计值(FOS=1.3 已含)= **40.0**。
- 日期:2026-06-11;方法与判据由本 agent 自行选定(无外部判决规则)。

## 1. 方法

1. **力学(screening 代理)**:直接取 `atlas/data/cell_db.sqlite`(5304 样本,
   24 拓扑 × slider 0–8 × r 0.25–0.55,胞元 5 mm)中 `static_compression` 特征
   `comp_EA / comp_stiffness / comp_yield / comp_densified` 及 `dyna_comp_EA`。
   判据:comp_EA ≥ 40.0(设计值已含 FOS,不再叠加)。
2. **可打印性(MJF, PA12)**:阈值取
   `.claude/skills/atlas/references/thresholds/dfam_rules.json` v1.1:
   最小杆径 0.8 mm、最小间隙 1.0 mm(HP MJF vendor 指南)、悬垂不适用(粉末床
   自支撑)、排粉深度按 Raz et al. 2025(DOI 10.3390/polym17202804)ρ_rel→可清
   层数内插。实跑 `atlas/printability/checks.py`(2×2×2 阵列网格,segments=48):
   双引擎水密验证、embree 射线测厚、体素 flood-fill 困粉;杆间净距另用图级
   线段-线段解析计算(精确,无网格离散误差)。
3. **auxetic 性**:库内 24 拓扑中唯一 auxetic 类为 `Auxetic`(3D 内凹沙漏/
   re-entrant)。库无泊松比特征,故以几何内凹角(腰部内收角,越大越 auxetic)
   作代理:slider s 控制腰半宽 w = 0.7 + 0.04·s(mm),内凹角 = atan((2.5−2w)/2.5)。

候选全部取自 Auxetic 族(工况明确要求 auxetic 行为,其余 23 拓扑泊松比非负,
不满足"缓冲垫横向内缩、贴合冲击体"的设计意图);三个候选覆盖
"最大 auxetic ↔ 可打印性裕度" 的权衡两端与中间。

## 2. 候选与评估结果

| 项目 | C1 max-auxetic | C2 balanced(推荐) | C3 stiff-backup |
|---|---|---|---|
| 几何 (topology/slider/r) | Auxetic / 0.0 / 0.45 mm | Auxetic / 6.0 / 0.425 mm | Auxetic / 7.0 / 0.45 mm |
| 内凹角(auxetic 强度) | 23.7°(最强) | 13.9° | 12.2° |
| 相对密度 ρ_rel | 0.270 | 0.188 | 0.192 |
| comp_EA(判据 ≥40) | 332.7(8.3×) | **229.2(5.7×)** | 281.2(7.0×) |
| comp_stiffness | 75.3 | **92.7** | 116.9 |
| comp_yield / 致密化应变 | 2.11 / 0.60 | 2.19 / 0.58 | 2.73 / 0.58 |
| dyna_comp_EA(参考) | 221.6 | 214.4 | 251.3 |
| 杆径 2r vs ≥0.8 mm(射线实测 p5) | 0.898 ✔ | 0.848 ✔ | 0.898 ✔ |
| 杆间净距 vs ≥1.0 mm(图级解析) | **0.50 ✘** | 1.03 ✔(薄裕度) | 1.06 ✔ |
| 困粉体积(2×2×2,体素 flood-fill) | 0 mm³ ✔ | 0 mm³ ✔ | 0 mm³ ✔ |
| 排粉深度:可清层数 vs 需 2 层 | 2.94 ✔ | 3.78 ✔ | 3.74 ✔ |
| 网格水密(双引擎) | welded 轨不水密 ⚠ | ✔ | ✔ |
| 库内质量旗标 | ok | csv_only_no_curves ⚠ | ok |
| **判定** | **FAIL** | **PASS** | **PASS** |

### 判定依据

- **C1 FAIL**:腰部两侧斜杆(T_TL–T_WL 与 T_TR–T_WR)净距仅 0.50 mm,为 HP MJF
  最小间隙 1.0 mm 的一半——深内凹(s=0)把沙漏腰收得太窄,打印时近邻杆面热
  渗连接 + 腰部窄缝排粉风险高,硬性不可接受;其 2×2×2 网格在 welded 轨亦不水密
  (近距杆面焊接退化的旁证)。力学全部达标但不能救可打印性。
- **C2 PASS**:全部门槛通过;EA 裕度 5.7×;三候选中密度最低(0.188)、压缩刚度
  最低(92.7)——缓冲垫希望柔顺、峰值传递力低,低刚度正是优点;内凹角 13.9°
  为通过者中最强 auxetic。薄弱点:杆间净距 1.03 mm 仅 +3% 裕度(见 §4 风险)。
- **C3 PASS**:全部门槛通过且各项裕度略好(净距 1.06、杆径 0.898、qflag=ok 且
  有原始曲线),但刚度高 26%、内凹角更浅(auxetic 更弱)、密度略高,作为
  C2 的稳健备选。

## 3. 最终推荐

**首选 C2:Auxetic, slider=6.0, r=0.425 mm(5 mm 胞元)**;备选 C3(Auxetic,
slider=7.0, r=0.45)用于对打印间隙/数据可靠性更保守的场景。不推荐 C1。

理由:在通过全部 MJF DfAM 硬门的前提下,C2 同时给出最低刚度(缓冲柔顺性)、
最低材料用量与通过者中最强的 auxetic 内凹,comp_EA=229.2 对设计值 40.0 留有
5.7× 裕度,排粉可清 3.78 层 ≫ 所需 2 层。

## 4. 风险与缓解(screening 级,须在下一阶段确认)

1. **C2 间隙裕度仅 0.03 mm**,而 MJF 尺寸公差约 ±0.2 mm 量级;1.0 mm 阈值本身
   是含工艺余量的 vendor 指南值,但建议:整体放大胞元(几何线性缩放,如
   5→6.25 mm,净距 1.29 mm、杆径 1.06 mm,两门均获舒适裕度;ρ_rel 不变,EA
   代理排序近似保持——此外推属 inference,需复核)或首件实测腰部缝隙。
2. **comp_EA 为库内同单位代理**,非物理 J 值;仅支持库内排序与 ≥40 门槛判断,
   绝对吸能需 Tier-D/实验标定。库低 r(≤0.275)区段出现负 EA,系拟合伪影,
   选型时已整体回避该区段。
3. **C2 qflag=csv_only_no_curves**(特征来自 CSV、无原始曲线复核);C1/C3 为
   ok。若需曲线级核验,可改用近邻 ok 样本(slider=6, r=0.45,EA=273.0)交叉印证,
   趋势一致。
4. **排粉内插的适用域**为 BCC/5 mm 胞(Raz 2025),跨拓扑用于 Auxetic 属
   inference 降级;但本工况仅 2 层深且体素困粉为 0,结论稳健。
5. 库无泊松比数据,auxetic 强度用内凹角几何代理;如需 ν<0 的定量值,建议
   下一步对 C2/C3 做单胞均质化或实测。
