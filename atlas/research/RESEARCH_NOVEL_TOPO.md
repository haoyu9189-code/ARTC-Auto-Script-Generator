# ATLAS 专项调研报告:可靠的新拓扑生成(Novel Topology Generation)

> 生成方法 × 快速物理裁判 × 表示与约束
> 对应 `atlas/HANDOFF.md` §11(2026-06-10 增补);本文档自包含,可独立阅读。
> 标注约定:**[已证实]** = 经对抗式核查确认;**[已纠正]** = 原始论断有误,本文只呈现纠正后版本;**[待核实]** = 推测 / 文献锚点稀疏 / 尚未在本机标定,使用前须按文中方式校准。

---

## 1. 执行摘要

ATLAS 的真正野心(HANDOFF §11)不是库内查表,而是**可靠的"外星拓扑"**:有理论基础、计算结果大概率正确、但可能从未被人设计过的新拓扑,且完美匹配工况。本轮调研结论:这件事对一个 2 人、Windows 工作站、已有 ABAQUS 自动化管线的团队是**现实可行的**,但前提是三根支柱同时立起来,缺一根整个可信度叙事就塌:

**支柱一:生成方法(Generator)。** 不训练任何生成模型("不 fine-tune,知识外置",HANDOFF §2)。主攻方向是 **spinodoid 族**(Kumar/Tan/Zheng/Kochmann, npj Comput. Mater. 2020):仅 4 个设计参数(相对密度 ρ + 三个锥角 θ₁₋₃)的 Gaussian Random Field(GRF)参数化,产出非周期、从未被人手工设计、但完全有理论根基的拓扑——**构造上即 OOD,理论上却站得住**。辅以两条低成本路线:(a) Lumpe & Stankovic 的 17,087 个晶体网络 truss 目录(PNAS 2021)做"有原则的目录扩容"(Tier-1.75);(b) Kochmann 组预训练 checkpoint(truss-VAE、DiffuMeta)做 inference-only 的 generate-then-verify。对 truss 类拓扑,采用 FunSearch/AlphaEvolve 模式的 **LLM 离散提案 + CMA-ES 连续抛光** 混合回路,零训练、全程可审计。

**支柱二:快速物理裁判(Fast Physics Judge)。** OOD 拓扑**禁止**用 cell-DB 最近邻当 surrogate(HANDOFF §11 红线)。裁判链 = 解析筛(G-A/Maxwell,趋势级)→ 自研 Timoshenko beam-FEM 周期均质化(strut 图,毫秒级)→ FFT/共形网格体素均质化(隐式场,分钟级)→ 现有 ABAQUS 显式管线全 FEA 终审(小时级)→ "须经实物压缩测试验证"免责。关键诚实发现:**自家数据库就坐在 beam 理论失效区边缘**(cell 5 mm、半径 0.3–0.5 mm → 斜杆 l/d ≈ 4.3–7.2,而 beam/G-A 理想化要求 l/d ≥ 5,AM 金属点阵越界时偏差可达 300%,Zhong et al., COSSMS 27:101081, 2023)——所以 beam 裁判必须带数据库标定的节点刚化修正,并在 l/d<5 时拒绝认证。

**支柱三:表示与约束(Representation & Constraints)。** 双轨表示:(A) 周期节点-杆图 JSON(分数坐标 + 整数 shift 向量 = 晶体网理论的 labeled quotient graph),(B) 紧凑隐式场参数向量(TPMS 基组合 6–15 个浮点;spinodoid 4–5 个浮点)。两者都 token-紧凑到 LLM 可直接提案,且每一条物理 sanity 性质都有**毫秒级确定性检查**(9 级生成期硬门 C1–C9),在任何 FEM 调用之前就杀掉不 make sense 的候选。Neural SDF 被明确排除(需 GPU 训练解码器,违反团队约束)。

**结构性洞见(重新定位数据库角色):** 24 拓扑 × ~1000 变形 × 4 工况的 FEA 库,单拓扑采样密度高、但拓扑多样性只有 24——**训练任何生成模型都远远不够**(对比:17k 晶体网、~1M truss 图),但它恰好是**标定快速裁判误差带的理想锚**(beam-FEM vs ABAQUS 的每拓扑类误差条)+ 约束门的回归测试集(24/24 必须永远通过)。数据角色翻转(§2"数据是 judge 不是 training set")在 Tier-2 上具体化为:**库不生成,库管裁判。**

一句话:**ATLAS 实现"可靠外星拓扑"的方式 = 理论根基的参数化生成(不是黑箱采样)× 逐级升压的物理裁判(不是 ML 信仰)× 生成期硬约束的紧凑表示(不是事后修补),三层可信度(Tier-1/1.5/2)在报告里永远分开标注。**

---

## 2. Generator 分层设计与验证升压链

### 2.1 生成层(扩展 HANDOFF §11 三层为四层)

| 生成层 | 定义 | 机制 | 可信度叙述 |
|---|---|---|---|
| **Tier-1 库内检索** | 24 拓扑 × ~1000 变形数据库直查 | DB/RAG Retriever 查表 | 可信(FEA 实算数据,分布内) |
| **Tier-1.5 库内变形/插值** | 已有 slider 机制的连续化:slider 整数 0–8 → schema 中命名连续自由度 `free_params`,由内层优化器连续抛光 | CMA-ES/Nelder-Mead 在 free_params + 半径组上优化,beam-FEM 裁判打分 | 分布内插值,可用 DB 最近邻佐证 |
| **Tier-1.75 有原则的目录扩容** | Lumpe & Stankovic 17,087 晶体网络 truss 目录(PNAS 2021,数据 ETH DOI 10.3929/ethz-b-000457595)整体灌入 | Maxwell + G-A + beam-FEM 三级筛,幸存者走 ABAQUS 终审 | **是枚举不是生成**——叙述中必须如实标注,否则审稿必怼;但把"database-wide 全局最优"的搜索空间扩大约 700 倍,零 ML 风险 |
| **Tier-2 新拓扑生成** | graph / 隐式场表示 + 生成期硬约束 + 验证链逐级升压 | (a) spinodoid 4 参数族 ± BO;(b) LLM 提案 + CMA-ES 抛光的 truss 图进化;(c) 预训练 checkpoint inference-only | OOD,**只认物理裁判证据**,任何数字必须带验证档标签与误差条 |

### 2.2 验证升压链(Verification Escalation Ladder)

每个 Tier-2 候选在 verification trace 中携带**验证档标签**(Tier-A/B/C/D,与生成层 Tier-1/1.5/2 是两套正交编号,勿混):

```
生成期硬门(C1–C9,μs–s,确定性)
   │ pass
   ▼
Tier-A 解析筛:G-A 标度律 + Maxwell M=b−3j+6 倾向标志 + 平衡矩阵 SVD
   │ 仅趋势级,OOD 上只当量级 sanity
   ▼
Tier-B beam-FEM 周期均质化(strut 图,自研 scipy Timoshenko,毫秒级/cell)
Tier-C FFT/共形 FEM 体素均质化(隐式场/粗壮 strut,64³–128³,分钟级)
   │ 各向异性弹性张量 + 初始屈服估计 + 线性屈曲因子;SPD/界限/跨档一致性三道绝对门
   ▼
Tier-D ABAQUS 全 FEA 终审(现有管线 script_generator.py → 显式求解 → GeJsonl 特征提取)
   │ 非线性 plateau/SEA/致密化唯一合法来源;每查询 ≤3 个 finalist(对齐 K=3 重生预算)
   ▼
实测免责:任何 Tier-2 推荐一律保留"须经实物压缩测试验证"(HANDOFF §10 红线)
```

**硬规则(写进 Evaluator):**
- OOD 候选的 SEA / plateau / 致密化应变,来自 Tier-A/B/C 的一律标 "screening only",**永远不能**让其通过 margin ≥ 1.0 的设计判据门——只有 Tier-D 数字有资格。
- cell-DB 最近邻 surrogate 对 OOD 拓扑**硬封锁**(代码层面 block,不是提示词约定)。
- 只有 Tier-D 可对 OOD 候选授予"设计参考级(±15–20%)";"接近定稿级"额外要求 Size-Effect 修正 + 实测提示(对接 HANDOFF §6 Q3)。

### 2.3 各验证档的诚实误差带 **[待核实——文献锚点 + 推断,上线前必须用自家 24 拓扑 DB 一次性标定,标定前按保守值用]**

| 验证档 | 方法 | 弹性性质 | 屈服/强度 | SEA/plateau/致密化 | 有效域 |
|---|---|---|---|---|---|
| Tier-A | G-A + Maxwell | 分布内 ±30–50%;OOD 仅量级 | 同左 | 不可用 | 仅筛选;Maxwell 只输出倾向(FCCZ/FBCCZ 反例,HANDOFF §5) |
| Tier-B | beam-FEM + 节点刚化修正 | l/d≥10:±5–10%;5≤l/d<10:±15–25%(标"修正估计");**l/d<5:拒绝认证**(误差 30–100%+) | 首杆屈服 ±25–40% | 不可用 | strut 图;锚点:octet ρ̄=0.5 时未修正 beam 模型低估 E 达 40%、G 达 30%(DOI 10.3390/app15168969,**[待核实]** 须对自家 octet 固体 FEA 数据复算) |
| Tier-C | FFT(Willot 算子)/ 共形 FEM 体素 | ±2–10%,以 64³ vs 128³ 双网格差作误差条(>5% 即拒) | 初始屈服 ±15–30% | 不可用 | 任意 l/d、任意 ρ̄;隐式场原生 |
| Tier-D | 标定后显式 ABAQUS | 刚度 ±10–20%(vs 实验) | plateau ±10–20% | SEA ±10–20%,致密化应变 ±10% | 须过 ALLKE/ALLIE 能量比门(<5–10%) |

三道**无需数据库**的绝对 sanity 门(对任何外星拓扑都成立,违反即证明算错了):
1. 均质化刚度张量 C 必须对称正定(SPD);
2. 模量必须落在该 ρ̄ 下的 Voigt–Reuss(理想情况 Hashin–Shtrikman)界限内;
3. 跨档一致性:|E_beam − E_FFT|/E_FFT > 20% → 弃 beam 取连续介质档结果并降级标注。

---

## 3. 生成方法对标表

> 凡核查中被驳回的论断,本表只呈现纠正后版本;无法核实的工程估计标 **[待核实]**。

| 方法 | 出处(已核实引用) | 理论根基 | 代码/数据可得性 | 对本团队可行性判决 |
|---|---|---|---|---|
| **Spinodoid 族(旗舰)** | Kumar, Tan, Zheng, Kochmann, *Inverse-designed spinodoid metamaterials*, npj Comput. Mater. 6:73, 2020, DOI 10.1038/s41524-020-0341-6 **[已证实]** | 4 参数 Θ=(ρ, θ₁, θ₂, θ₃),ρ∈[0.3,1],θ∈{0}∪[15°,90°],各向异性波矢锥采样 GRF;非周期、对对称破缺缺陷鲁棒、无周期屈曲分岔 | 参考代码 github.com/mmc-group/inverse-designed-spinodoids,MIT,PyTorch,**明确测试过无 CUDA(CPU 可)**,含 data.csv;几何生成原版委托 GIBBON(MATLAB,**AGPL-3.0,勿链接**) | **采纳为 Tier-2 旗舰**。GRF 生成自研 NumPy 重写(~100 行:θ 锥内叠加 N≫1 余弦波,level-set 阈值,scikit-image marching cubes → trimesh,接现有 Printability Checker)。4 维空间小到可用自家 ABAQUS 管线打标(~10³–10⁴ 次),CPU 训练 Kumar 式 f-NN/i-NN MLP 对 |
| Spinodoid × SEA/吸能 | arXiv 2411.14508(spinodoid 压溃吸能多目标 BO);Zheng, Kumar, Kochmann, CMAME 383:113894, 2021(arXiv 2012.15744,梯度 spinodoid 两尺度 TO)**[已证实]** | BO 直接以吸能最大化/峰值力最小化为目标;两尺度数据驱动 TO | arXiv 公开 | SEA 工况 v1 路线:4 维空间包 BO(scikit-optimize/BoTorch-CPU),目标函数 = 显式 ABAQUS 实跑——**无需任何生成模型** |
| **晶体网络 truss 目录** | Lumpe & Stankovic, PNAS 118(7):e2003504118, 2021, DOI 10.1073/pnas.2003504118;数据 ETH DOI 10.3929/ethz-b-000457595 **[已证实]** | 晶体学网络(RCSR/EPINET/Systre 谱系)枚举,17,087 个独特 truss 单胞,对比方法中性质空间覆盖最广 | 目录公开下载 | **Tier-1.75 采纳,最便宜的可信度倍增器**。注意:是枚举不是生成,叙述分寸必须守住 |
| InvertibleTrussDesign | Bastek, Kumar, Telgen, Glaesener, Kochmann, PNAS 119(1):e2111505119, 2022, DOI 10.1073/pnas.2111505119 **[已证实]** | Timoshenko beam + PBC 均质化的 truss 结构-性质映射反演 | github.com/jhbastek/InvertibleTrussDesign,MIT;数据集含完整各向异性刚度张量 | Kochmann 组谱系第一篇,truss 参数化受限,被 2023 VAE 取代;**其数据集用作我方 beam 均质化器的免费回归测试套件** |
| UnifyingTrussDesignSpace(truss graph-VAE) | Zheng, Karapiperis, Kumar, Kochmann, Nat. Commun. 14:7563, 2023, DOI 10.1038/s41467-023-42068-x **[已证实]** | 统一 truss 图设计空间(节点 + 邻接),潜空间梯度反演;线性+非线性 | github.com/li-zhengz/UnifyingTrussDesignSpace,MIT;checkpoint + 数据 ETHZ DOI 10.3929/ethz-b-000618078 | **第二波:仅推理**。潜空间采样/插值产 OOD truss,直接落入现有 strut 管线;**其刚度预测头在 OOD 上不可信,只当提案启发,证据由我方裁判出**。注意其训练需 ~1M truss 数据集 + GPU——这正是我们不自训的理由 |
| DiffuMeta(代数语言扩散) | Zheng, Kumar, Kochmann, Nat. Mach. Intell. 2026, DOI 10.1038/s42256-026-01218-8(arXiv 2507.15753)**[已证实]** | 3D 壳几何编码为隐式曲面方程"数学句子",diffusion transformer;目标非线性应力-应变(屈曲+接触),有实验验证 | github.com/li-zhengz/DiffusionMetamaterials;数据+checkpoint 在 ETHZ Collection 与 Zenodo 18598195 | **第二波(壳/TPMS 类新颖性最契合 ATLAS 的深度生成选项)**:隐式方程紧凑、可审计、可直接走 TPMS 式网格化与打印检查。承诺前先在一台工作站验证预训练推理可跑 |
| VideoMetamaterials(视频扩散) | Bastek & Kochmann, Nat. Mach. Intell. 5:1466–1475, 2023, DOI 10.1038/s42256-023-00762-x **[已证实]** | 视频去噪扩散,以全非线性压缩应力-应变路径(含屈曲+摩擦自接触)为条件 | github.com/jhbastek/VideoMetamaterials,MIT,PyTorch 2.0.1 | **仅作先例引用,不采纳**:2D 96×96 像素网格设计;重训需 ETH Euler 集群 8×RTX 6000 ×70 h,桌面不可行。**[已纠正]** 原论断称"除 DiffuMeta/GraphMetaMat 外无他法以非线性曲线为条件"——不实:Ha et al., Nat. Commun. 14, 2023(DOI 10.1038/s41467-023-40854-1)、DiffMat(CMAME 2024)、arXiv 2312.11648(spinodal 有限应变反设计)均以目标非线性应力-应变曲线为条件。**对 ATLAS 的持久价值 = 其 eval_abaqus.py 的 generate-then-FEA-verify 自动回路先例**,与我方 Evaluator 设计同构 |
| GraphMetaMat(RL 图生成) | Maurizi et al., Nat. Mach. Intell. 2025, DOI 10.1038/s42256-025-01067-x(arXiv 2408.06300)| 自回归图生成,模仿+强化学习+树搜索;可编程跨 4 个数量级的应力-应变曲线 + 制造约束 | github.com/marcomau06/GraphMetaMat | **Phase 3 之后再议**:RL+树搜索训练需要仿真环境与大量工程;仅当需求从标量 SEA/刚度升级为"可编程完整非线性响应曲线"时重启 |
| deHomTop808(均质化 TO + 去均质化) | SMO 2024, DOI 10.1007/s00158-024-03880-1(arXiv 2405.14321,DTU/Sigmund 组)| Rank-2 微结构柔度最小化(理论谱系回溯 Bendsøe–Kikuchi 1988)+ 相量去均质化,性能距全尺度 TO ~10% 而成本低数量级 | github.com/peterdorffler/deHomTop808,808 行 MATLAB,普通工作站可解 | **Phase 3"构件模式"**:零数据、理论最优的"按工况定制外星几何",但 (a) 需 MATLAB license,(b) 优化目标是柔度/刚度**不是 SEA**——不带非线性 TO 机制硬套吸能工况会得到自信的错误答案,(c) 输入是边界条件级、输出是构件级梯度结构,部分超出当前单胞选型架构。商业对标 nTop(场驱动梯度点阵,Windows 原生闭源)仅在 related-work 提及 **[待核实——nTop 定位为推断]** |
| LLM 多智能体设计 | CrossMatAgent(Adv. Intell. Discov. 2025, DOI 10.1002/aidi.202500063, arXiv 2503.19889);LinguaMate(OpenReview);arXiv 2506.06935(光子超材料)**[已证实存在]** | GPT-4o + DALL-E 3 + SDXL 编排等;力学上科学含量薄(2D 图像图案) | 各 arXiv/OpenReview | **仅 related-work 定位**:证明 ATLAS 的 agentic generate-then-verify 架构踩在时代节点上;差异化 = 这些工作没有的可审计物理验证链 |
| Neural SDF / 自解码器 | DeepSDF 谱系(Park et al., CVPR 2019)| 网络权重 + 每形状潜码联合训练(标准解码器 ~10⁶ 权重,ShapeNet 级数据) | — | **明确排除**:LLM 无法以少量可读浮点提案;需 GPU 训练 + 策划数据集;解码器输出仍需同一套约束门。仅当出现宽松 license 的预训练点阵 SDF 模型时重审 |

**时间线基准 [待核实——工程估计]**:spinodoid 生成器 + 打印检查 1–2 周;spinodoid + ABAQUS 打标正/反 MLP 4–8 周;目录灌入 + beam 筛 2–4 周;预训练 VAE/DiffuMeta 推理接裁判各 2–6 周;deHomTop808 适配 2–6 周;视频扩散/GraphMetaMat 重训 = 数月 + GPU 农场(当下不可行)。

---

## 4. 快速物理裁判选型

### 4.1 Tier-B:strut 图 beam-FEM 周期均质化(自研,关键路径)

- **选型:自研** `atlas/scripts/beam_homog.py` —— numpy/scipy.sparse Timoshenko 空间框架求解器:12-DOF 圆截面梁单元、周期节点配对 MPC、6 个单位宏观应变工况 → 完整各向异性刚度张量 + 首杆屈服估计 + 线性化屈曲特征值。规模:每胞 6–70 节点(~6N DOF)直接稀疏求解,**目标 <0.1 s/cell [待核实——运行时为工程估计,第 1 周实测入 Evaluator 成本表]**;约 300–500 行。
- **方法学先例 [已证实]**:与 Kochmann 组 PNAS 2022 / Nat. Commun. 2023 完全同方法(线弹性 Timoshenko 梁 + PBC FE 均质化)。其官方实现 ae108(gitlab.ethz.ch/mechanics-and-materials/ae108,C++/PETSc,仅 Ubuntu 打包)对 2 人 Windows 团队部署成本高于 scipy 重写——**引用为先例,不当依赖**。
- **不选 Pynite [已证实]**(JWock82/Pynite,MIT,pip `PyNiteFEA` v3.0.0,纯 Python,维护活跃):无原生周期 MPC,只配做平板压缩 sanity 交叉检查,不能承载均质化。
- **节点刚化修正(必做)**:节点体积刚化是非细长点阵 beam 模型的主导误差机制(Portela, Greer & Kochmann, EML 2018, DOI 10.1016/j.eml.2018.06.004)。在自家 24 拓扑固体 FEA 库上一次性拟合修正(刚性端部偏置长度 ~r,系数随 l/d 与节点配位数变化)。**硬门:l/d<5 拒绝认证;5≤l/d<10 标"修正估计"**。自家库恰在 l/d ≈ 4.3–7.2(cell 5 mm,r=0.5 时 4.3,r=0.3 时 7.2),一部分在地板以下——这是裁判诚实性的核心。
- **验证集(三重免费回归)**:(a) 自家 24 拓扑固体 FEA 库;(b) Bastek PNAS 2022 数据集抽样;(c) Lumpe–Stankovic 17,087 目录抽样。复现误差超几个百分点即不准上岗。
- **动手前先审计**:`generate_script/consolidated/compare_corrected_frame.py` / `compare_lattice_frame.py` / `compare_frame_aux.py` —— 仓库内已有 beam-vs-lattice 对比实验,节点修正标定可能已部分完成 **[待核实]**。
- 可选 Tier-B+:OpenSeesPy(pip 有 Windows wheel)非线性共旋梁柱可做 plateau 起始筛,但抓不到自接触致密化 **[待核实——medium]**;仅当 Tier-D 吞吐成瓶颈再上,保持栈小。

### 4.2 Tier-C:隐式场/体素均质化(spinodoid、TPMS、粗壮 strut 的 fallback)

- **首选 A:fork GooseFFT**(github.com/tdegeus/GooseFFT,单文件 numpy/scipy Moulinec–Suquet 型求解器,Python 在哪 Windows 就在哪)。**必须从第一天加入 Willot 旋转离散 Green 算子**(DOI 10.1016/j.crme.2014.12.005)+ 有限对比度空腔相(E_void ≈ 1e-4·Es,复合体素)——**朴素 M-S 迭代对真空腔(无限对比度)不收敛且可能振荡而看似合理**(scheme 选择总图:Schneider 2021 综述,DOI 10.1007/s00707-021-02962-1)。**永远跑 64³+128³ 双网格,双网格弹性常数差 >5% 即拒,差值本身就是误差条**。注意:GooseFFT 的 license 再分发条款尚未确认 **[待核实——动手前查 license 头]**。
- **首选 B(并行评估后二选一)**:fedoo + microgen(3MAH 栈,pip 装,Windows 原生):共形周期网格 FEM,内建 PBC 与平均切线刚度提取,非线性能力(simcoon)。microgen 本就在 ATLAS Generator 短名单上——**裁判与生成器可共享同一几何栈**。第 2–3 周在 3 个 TPMS 胞上 benchmark 两者,选主用,留备胎。
- **第三意见**:unitcellengine(PyPI,Apache-2.0,UnitcellHub,Windows 支持,alpha)——beam 与 FFT 两档打架时的独立仲裁,**锁版本、不进关键路径** **[待核实——alpha 状态]**。
- **不选(Windows 不可用)[已证实]**:muSpectre(LGPL,仅文档 Linux/macOS)、FANS(LGPL,conda-forge 只有 linux-64/aarch64/ppc64le/macOS,无 win-64)。仅当 Tier-C 吞吐成限速再考虑 FANS-in-WSL2。
- **运行时包络 [待核实——推断,第 1 周实测]**:纯 numpy 64³ 线弹性全工况 ≈ 30 s–2 min;128³ ≈ 5–20 min 单进程(内存 <2 GB);编译型求解器 128³ 秒级-分钟级。64³ 对光滑 TPMS 弹性常数通常距收敛 ~5% 内,128³ ~1–2%。
- spinodoid GRF 场是体素原生的,天然 FFT-均质化原生——旗舰生成器与 Tier-C 裁判是同一种数据结构,这是 spinodoid 路线的隐藏红利。

### 4.3 Tier-D:ABAQUS 全 FEA 终审(已有资产 + 两个新适配器)

**现有管线(已核实,含两处精度修正):** 几何 = 每杆圆柱 + 每节点球(**注意:模板字面量是 `sphere_r=1.2*r`,但 `script_generator.py` 会改写为 `Config.SPHERE_RADIUS_RATIO_SCRIPT`,默认 1.0,环境变量可覆盖**)→ `InstanceFromBooleanMerge` → `CutExtrude` 裁到胞盒 → C3D10M(EXPLICIT 库,网格尺寸 `0.3*sqrt(r/0.5)*(cell/5)`)→ 离散刚性压板(**板-点阵接触用 `SurfaceToSurfaceContactExp`;`GeneralContact` 是给点阵内部自接触的**)→ 准静态显式(SmoothStep,timePeriod 0.3)→ 板参考点 RF/U 历史 → `feature_data.txt` → `GeJsonl.py` → `feature_data.json`(EA/SEA/致密化-v10)。多胞阵列 `lattice_array=(a,b,c)`;本地 .bat `cpus=8` 或 PBS/SLURM。

**适配器 1:strut 图注入(1–2 天)[机制已核实]**。管线消费的就是节点-杆图:`structure_set.get_crystal_structure` 返回 `{'coords': ["A = [x,y,z]"...], 'cylinders': ["(A, B)"...]}`,由 `_generate_script_content` 文本替换进 `model/Static_model.py`。新入口绕过命名拓扑查表、直接喂 `structure_data` 给 `_generate_single_script` 即可。生成侧硬约束(最小杆间角、最小节点间距、去重)+ Boolean merge 失败时自动 fallback 到 remesh 路线。

**适配器 2:体素/隐式 orphan-mesh INP 路线(1–2 周)[缺口已核实]**。当前管线无 STL/体素/orphan-mesh 输入路径。方案 (a) level-set → marching cubes(scikit-image)→ 水密 STL → gmsh/fTetWild 四面体 → 写 orphan-mesh INP + 压板/接触关键字,绕过 CAE 几何阶段;方案 (b) 直接从 level-set 写 C3D8R 体素六面体 INP(~200 行,接受阶梯伪影 + 网格收敛检查)。仓库已有部分起步:`demo_remesh.py`(pyvista 布尔并 + pymeshfix 修复 + manifold3d 组合,导出水密 STL)、`test_manifold_all_cells.py`(**用 manifold3d**——24 种胞全部水密通过)。保持实例/RP 命名约定即可让 postprocess/GeJsonl 零改动复用。

**吞吐预算与有效性门:**
- 单次显式准静态(0.3 mm 种子 C3D10M,5 mm 胞或 2×2×2 阵列,cpus=8)≈ **1–6 h 壁钟 [待核实——从现有作业日志实测入 Evaluator 成本模型]** → 裁判带宽 = 每机每天个位数候选 → **快档必须剪到每查询 ≤3 个 finalist**(对齐 K=3 重生预算)。
- **ALLKE/ALLIE 能量比门**:plateau 全程动能/内能 <5–10%,否则 plateau/SEA 是惯性伪影。外星柔顺/机构类拓扑是最可能的违规者——postprocess 模板必须自动提取并 pass/fail,先于把管线当 OOD ground truth 用。

### 4.4 选型一览

| 档 | 选型 | 替代/弃选 | 单候选成本 | 有效域 |
|---|---|---|---|---|
| Tier-A | 自家 gibson_ashby.py / maxwell_check.py + 平衡矩阵 SVD | — | μs–ms | 趋势级 |
| Tier-B | 自研 scipy Timoshenko PBC 均质化 + DB 标定节点修正 | Pynite(无 PBC,弃)/ ae108(C++/PETSc,弃)| ms–0.1 s [待核实] | strut 图,l/d≥5 |
| Tier-C | GooseFFT-fork + Willot 算子 vs fedoo+microgen(benchmark 后定主备);unitcellengine 第三意见 | muSpectre/FANS(无 win-64,弃;FANS-WSL2 仅限吞吐告急)| 64³ 半分钟–2 min;128³ 5–20 min [待核实] | 任意 l/d/ρ̄;隐式场原生 |
| Tier-D | 现有 ABAQUS 显式管线 + strut 图适配器 + orphan-INP 路线 + ALLKE/ALLIE 门 | — | 1–6 h [待核实] | 非线性 SEA/plateau 唯一合法来源 |

**勘误(需回写 HANDOFF §5):** "Zhong et al. Composite Structures 2023" 实为 **Zhong et al., Current Opinion in Solid State and Materials Science 27:101081, 2023, DOI 10.1016/j.cossms.2023.101081**(《The Gibson-Ashby model for additively manufactured metal lattice materials…》)。l/d≥5(细长比≥20)有效域与金属 AM 偏差可达 300% 的结论本身 **[已证实]**。

---

## 5. 表示与约束规范

### 5.1 双轨表示

**轨道 A:周期节点-杆图 JSON(`atlas-cell-graph/1.0`)** —— 分数坐标 + 每边整数 shift 向量,即晶体网理论的 **labeled quotient graph**(voltage-graph 形式化;谱系:Gross & Tucker;Delgado-Friedrichs/Systre;Eon。注:Zheng 2023 用的是固定 27 位点邻接矩阵编码,shift 向量约定来自晶体学网谱系,非 Lumpe & Stankovic 首创)。草案:

```json
{
  "schema": "atlas-cell-graph/1.0",
  "lattice_vectors": [[5.0,0,0],[0,5.0,0],[0,0,5.0]],
  "symmetry": { "point_group": "m-3m" },
  "nodes": [ { "id": "A", "frac": [0.5, 0.5, 0.5] },
             { "id": "B", "frac": [0.0, 0.0, 0.0] } ],
  "edges": [ { "n1": "B", "n2": "A", "shift": [0,0,0], "radius_group": "r0" },
             { "n1": "A", "n2": "B", "shift": [1,0,0], "radius_group": "r0" } ],
  "radius_groups": { "r0": 0.4 },
  "free_params": [ { "name": "node_A_y", "node_orbits": ["A"],
                     "direction": [0,1,0], "range": [0.0, 0.5] } ],
  "lineage": { "parent_seed": "BCC", "ops": ["splice_edge(...)"],
               "proposer": "tier2-llm", "round": 1 },
  "novelty_check": { "wl_hash": "…", "matched_seed": null }
}
```

要点:对称块允许 `{m-3m, 4/mmm, mmm, none}`,LLM 只提案非对称单元,代码用硬编码带符号置换矩阵展开轨道(提案空间缩小 8–48 倍,且保证均质化刚度张量的对称类);`lineage` 满足可审计链;**ABAQUS 模板兼容约束**:模板无 shift 概念,跨界边必须落在 frac 分量 ∈ {0,1} 的边界节点上(24 个现有胞全是这么做的)——该约束默默收窄可提案空间(如某些交错/手性周期连接),先文档化,若 binding 再扩模板支持显式 shift。

**轨道 B:隐式场参数向量(`atlas-implicit/1.0`)** ——
- TPMS 组合:Φ(x)=Σ wᵢ·φᵢ(x)−t,基 {Gyroid, Diamond, Primitive, IWP, Neovius, Fischer-Koch S},权重 + 各轴胞数 + 水平偏移 t(控体积分数)+ 可选 sigmoid 空间混合(位置、陡度 k),共 **6–15 个浮点**;sheet(|Φ|<t)/skeletal(Φ<t)变体。先例:P+G sigmoid 杂化已发表(Adv. Eng. Mater., DOI 10.1002/adem.202402360);六函数基是更广 TPMS 文献的标准件。
- Spinodoid:**4–5 个浮点**(ρ + θ₁₋₃;N≈1000 波、波数 β=10π/l 固定)——最紧凑的 OOD-capable 表示,光滑无节点几何(低应力集中),各向异性可调。
- 连通性门改用体素逐实现 percolation 检查(`scipy.ndimage.label`)——**ρ<0.3 的 GRF 逐实现可能不连通,参数合法≠实现连通**。

**明确非选项:Neural SDF**(训练依赖 + GPU 依赖 + 解码输出仍需同一套门)。

**种子词汇表:** `structure_set.py` 的 24 个拓扑机械转换为 schema JSON(`tools/convert_seeds.py`,frac=(xyz+2.5)/5;用 slider=4 规范形;当心 Diamond slider=8 退化特例)。实测规模:**每胞 6–70 节点、8–106 边**(最小:Octahedron 6 节点、BCC 8 边;最大:WeairePhelan 70 节点、106 边)——token-紧凑到 LLM 可整体读写,离散编辑(轨道上加节点、拼接边、改半径组)语义明确,每条 sanity 性质有确定性精确检查;这正是图表示优于网格/体素的发表过的论据(Zheng 2023 对细长梁的体素分辨率成本论证)。24 个种子同时是**约束门永久回归套件:任何门改动必须保持 24/24 通过**。slider 机制升格:slider 整数挡位 → `free_params` 命名连续自由度(Tier-1.5 = 只优化 free_params;Tier-2 = 还编辑拓扑)。

### 5.2 九级生成期硬门(C1–C9,全部先于任何 FEM,按最便宜在前排序)

| 门 | 检查 | 工具/成本 | 判据 |
|---|---|---|---|
| C1 | JSON schema 校验 | jsonschema,μs | 结构合法;LLM 首过拒绝率预算 10–30% **[待核实]**,有界重试 |
| C2 | 退化杆 | numpy,μs | L ≥ 2r + 0.2 mm,长径比合理 |
| C3 | **周期连通性 [已纠正]** | networkx + 整数线性代数,ms | quotient graph 单连通分量 **且** 圈 shift 向量整数矩阵的 **Smith 标准形 = diag(1,1,1)**(即圈 shift 必须生成整个 ℤ³)。**仅 rank=3 不充分**:rank 3 但子格指数 k>1 ⇒ k 套互穿不连通网(反例:单节点三自环 shift (1,1,0),(0,1,1),(1,0,1),rank 3、det 2 ⇒ 2 套网)。rank<3 ⇒ 退化为不连通的面/杆系。**同时跑 3×3×3 超胞实算**(合并重合边界节点 tol 1e-6,`scipy.sparse.csgraph.connected_components`==1)——这是更严的有限块检查、不是"等价方法",两者必须一致才放行 |
| C4 | Maxwell + 平衡矩阵 | numpy SVD,ms | M=b−3j+6 **只输出倾向标志,绝不自动拒绝**(HANDOFF §5/§10 红线:M<0 的 bending 主导可能正是吸能想要的);平衡矩阵 SVD(Pellegrino & Calladine 1986, DOI 10.1016/0020-7683(86)90014-4)给有限块的机构数 m 与自应力态数 s(最大胞 WeairePhelan 也只是 210×106 的 SVD) |
| C5 | 碰撞/楔形 | 向量化 numpy,ms(E≤106,O(E²) 平凡) | 不共节点边对(含 shift 相邻周期像)线段最小距 ≥ rᵢ+rⱼ+1.0 mm;共节点边夹角 ≥ 15°(楔形薄片 = 网格失败 + 应力集中) |
| C6 | ρ 可解性 | 解析预筛 + manifold3d 实测 brentq,s 级 | 解析 ρ(r)=Σπr²L/V 高估(节点重叠);并集体积对 r 单调不减 ⇒ brentq 反解保证收敛;预筛:ρ_target 超出 [ρ(r_min=0.4mm SLS), ρ(r_max)] 即拒;trace 同时记录解析值与实测值;缓存 (拓扑哈希, r)→ρ |
| C7 | 对称轨道展开 | 硬编码置换矩阵,μs | LLM 只提非对称单元;代码展开 + 容差去重 + 边按轨道映射;`none` 允许(真外星各向异性),但 C3 全条件照旧 |
| C8 | 图级 DfAM | C5 的距离计算复用,μs | 2r ≥ 0.8 mm(SLS/MJF)/ 1.0 mm(LPBF);间隙 ≥ 1.0 mm(阈值同 HANDOFF §5) |
| C9 | 水密可实现 | manifold3d batch_boolean,s 级(仅幸存者) | 水密 + 正体积;`make_strut`+`batch_boolean` 收编为 `atlas/scripts/realize_graph.py` 单一规范实现器(密度反解、打印检查、STL 导出共用);随后体素-EDT 打印检查(`bench_printability.py` 路线:最小壁/通道宽、flood-fill 困粉体积、<45° 悬垂分类) |

**新增依赖**(入 `requirements.txt`):`networkx`、`jsonschema`、`cma`(scipy 已有)。

### 5.3 候选抛光回路(LLM 提案 × 派生自由优化器 × 物理裁判)

FunSearch(Nature, DOI 10.1038/s41586-023-06924-6)/ AlphaEvolve(2025)验证过的 frozen-LLM 设计发现模式——**两者都没训练模型**:

```
种子词汇(24 个 schema 化拓扑 + free_params)+ 用户 spec
  → [Claude Tier-2 提案器:图 JSON | 隐式向量](离散拓扑动作:图编辑/基选择/对称选择;
     回喂结构化门失败诊断 + top-k 祖先裁判分)
  → [硬门 C1–C9](μs–s)
  → [内层抛光:冻结拓扑,x=(半径组, 对称自由节点坐标, TPMS 阈值/权重);
     ≤6 维 scipy Nelder-Mead,5–30 维 pycma CMA-ES(BSD-3),200–1000 evals + 2 restarts;
     目标 = beam-FEM 裁判分 + 门余量二次罚]
  → [实现:manifold3d → 水密 + 实测 ρ → brentq 半径修正] → [体素-EDT 打印检查]
  → top-K(≤3)→ [Tier-D ABAQUS 终审 → GeJsonl 特征 → Evaluator margin≥1.0]
  → fail/score 回传提案器(≤3 轮,对齐 K=3)
每级追加可审计 verification trace,三层可信度标签(Tier-1 检索 / Tier-1.5 插值 / Tier-2 生成+验证)分开标注
```

分工依据:LLM 在细粒度连续数值优化上弱、在离散/结构性动作上强(arXiv 2509.08269)——**数字交给 CMA-ES,拓扑交给 Claude**。对比自训生成模型(Zheng 2023 VAE 需 ~1M truss 标注 + GPU,潜空间只插值训练分布——恰是 HANDOFF §11 禁止依赖的分布内性质,且解码输出仍需同一套门):混合回路零训练、model-agnostic(§2"不 fine-tune"原则)、每个产物带 lineage。报告定位措辞:**"training-free generative design with auditable verification chain"**,最近发表系统对标 CrossMatAgent,差异化在硬物理 sanity 门 + ABAQUS 终审。

**新颖性防卫:** Lumpe & Stankovic 已编目 17,087 个晶体网胞,很多"外星" truss 是重新发现。`novelty_check` = networkx Weisfeiler-Lehman 图哈希(节点度 + 量化配位标签)对 24 种子 +(可行时)公开目录查重;**所有新颖性措辞限定为"ATLAS 词汇表/数据库范围外"**——与"database-wide 全局最优"同一措辞纪律(HANDOFF §10)。

---

## 6. 风险登记表

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R1 | **可信度层级红线(最高优先)**:Tier-2 产物被以 Tier-1 口径呈现。库内检索(可信)与库外生成(需验证链背书)是两个可信度层级(HANDOFF §2/§10/§11) | 项目护城河 = 可审计验证链;一次混层叙述即摧毁"凭什么你的好"的答案 | **报告语言强制分层标注**(Tier-1 检索 / Tier-1.5 插值 / Tier-1.75 目录枚举 / Tier-2 生成+验证);Evaluator 层面硬编码:无 Tier-D 证据的 OOD 数字一律 "screening only";所有 Tier-2 推荐保留实测免责;高风险场景标"仅作筛选" |
| R2 | beam 裁判在自家工作区间内悄悄出错:MJF/PA12 库在 ρ̄≈0.35–0.5、l/d≈4–7,正是 beam 模型误差 30–100% 区(octet ρ̄=0.5 低估 E 达 40%) | 快裁判系统性错排候选名次,且看起来权威 | 节点刚化修正在自家固体 FEA 库上标定;l/d<5 硬拒;Tier-C 体素档兜底;每拓扑类误差条进 trace |
| R3 | 朴素 FFT 对真空腔不收敛/振荡而看似合理 | 恰好对最关心的外星 TPMS/spinodoid 给出自信的错误弹性常数 | Willot 算子 + 有限对比度空腔相从第一天写入;双网格差 >5% 拒收;Voigt-Reuss/HS 界限门 |
| R4 | OOD 验证瓶颈:SEA/plateau 本质需要非线性 ABAQUS(1–6 h/次);提案洪水冲垮 FEA 队列 | Tier-2 吞吐塌缩到 FEA 排队 | 每查询 ≤3 finalist(复用 K=3);快档剪枝质量直接决定系统上限;实测运行时入成本模型 |
| R5 | spinodoid 低密度可打印性:Kumar 2020 只验证 ρ∈[0.3,1],典型 SEA 点阵在 0.3 以下,GRF level-set 壁厚可能破 0.8 mm 下限;且 ρ<0.3 逐实现可能不连通 | "外星"空间被截短;不连通候选漏网 | 参数盒截断或 shell-spinodoid 变体;percolation 逐实现检查强制;打印性主张一律走自家 trimesh/Open3D Printability Checker,**不引用文献的 self-supporting 说法**(Kumar 2020 本身不主张自支撑可打印;该说法谱系指向 Hsieh et al. JMPS 2019,其原文措辞 **[待核实]**) |
| R6 | 尺寸效应叙事对非周期拓扑断裂:单胞→多胞修正系数机制(Agent 8)假设周期胞,spinodoid 无单胞 | 现有修正查表不适用 | 改做 RVE 尺寸收敛研究(新验证任务,不是查表);报告中明示该差异 |
| R7 | C3 连通性检查的微妙失效模式(多分量 quotient 图仅通过像连通;rank-3-but-index-k 互穿网) | "连通"的候选实际是散件 | Smith 标准形 diag(1,1,1) 精确条件 + 3×3×3 超胞实算双轨并行,要求一致 |
| R8 | Maxwell 当判据用会错杀 bending 主导吸能候选,且有限块计数 ≠ 无限周期点阵(边界模式) | 违反 HANDOFF 红线 + 砍掉好设计 | C4 永远只输出倾向标志 + SVD 的 m/s 数;绝不自动拒绝 |
| R9 | License/工具链陷阱:GIBBON AGPL-3.0(勿链接,GRF 自研);deHomTop808 需 MATLAB;GooseFFT license 未确认;FFTHomPy/unitcellengine 低活跃/alpha;muSpectre/FANS LGPL 且 Linux-only;ETHZ checkpoint 各有条款 | 法律/维护暴露 | 引用层逐资产记录 license;关键路径全在自研代码;第三方锁版本 |
| R10 | 新颖性夸大:17,087 已编目晶体网在前,"never designed by a human" 可被文献检索证伪;目录扩容(枚举)被包装成"生成"招审稿反弹 | 项目头牌主张可证伪 | WL 哈希查重防卫;措辞限定"词汇表/数据库范围外";Tier-1.75 与 Tier-2 区别在所有叙述中显式 |
| R11 | 生成模型自带性质预测头(truss-VAE 刚度头、DiffuMeta 条件)训练于作者分布,非 PA12/MJF 非我方工况 | 把提案启发当证据 = 验证链污染 | 预测头输出只当提案启发,**永不进入 verification trace 作为证据**;一切数字由我方裁判产出 |
| R12 | 柔度最优 TO ≠ SEA 最优;TO 道硬套吸能工况 | 自信的错误"最优"设计 | deHomTop808 限定刚度驱动工况;SEA 工况走 spinodoid+BO/显式 FEA |
| R13 | 显式准静态伪影:外星柔顺/机构类拓扑动能占比高,plateau/SEA 变成惯性伪影 | Tier-D ground truth 失真 | ALLKE/ALLIE <5–10% 能量门写入 postprocess 模板,自动 pass/fail |
| R14 | 任意生成 strut 图的 Boolean merge/四面体化按一定比例失败或产薄片 | 裁判静默丢弃候选 → 搜索有偏 | 生成侧硬约束(C5 角度/间距)+ CAE merge 失败自动 fallback remesh 路线(demo_remesh.py 已起步);失败显式记入 trace 而非静默跳过 |
| R15 | 误差条表部分是推断:Tier-B/C 的 ±% 是稀疏文献锚点插值 | 误差条本身不诚实 | 上线前对自家固体 FEA 库一次性标定;标定前一律按保守值并标 provisional **[待核实]** |
| R16 | LLM JSON 不合规/幻觉节点引用是常态(首过拒绝 ~10–30% **[待核实]**);C6 的 manifold3d 反解秒级,提案洪水会堵在此级 | token 成本 + 门吞吐 | jsonschema + 有界重试;解析预筛收紧;(拓扑哈希,r)→ρ 缓存 |

---

## 7. Phase 放置建议

与 HANDOFF §9 的 Phase 1/2/3 骨架对齐;原则:**便宜的地基先行,裁判先于生成器,生成器先于深度模型**。

### Phase 1(2–4 周,廉价地基——零 ABAQUS 依赖,全部 μs–s 级)
1. `atlas/schemas/cell_graph_v1.json` + `atlas-implicit/1.0` 双轨 schema 定稿;`tools/convert_seeds.py` 把 24 个拓扑转为种子 JSON(slider → free_params),建立 **24/24 永久回归套件**。
2. 硬门 C1–C8 实现(C3 用 Smith 标准形 + 3×3×3 超胞双轨;C4 倾向标志 + SVD;C5–C6 碰撞/密度;C7 对称展开;C8 图级 DfAM)——全部不需要任何 FEM,与 §9 既定的 `maxwell_check.py / rel_density.py / check_min_feature.py` 自然合并。
3. C9:`realize_graph.py` 收编 manifold3d 实现器(`test_manifold_all_cells.py`/`bench_printability.py` 已验证的代码路径)。
4. **strut 图 ABAQUS 适配器(1–2 天)**:JSON → 旧版 coords+cylinders 文本 → `_generate_single_script`,跨界边经 frac 0/1 边界节点;novelty WL 哈希防卫。
5. 文档勘误:HANDOFF §5 Zhong 2023 出处改为 COSSMS 27:101081;审计 `generate_script/consolidated/compare_*frame*.py` 既有 beam 对比工作。
6. (并行廉价赢面)启动 Lumpe–Stankovic 目录下载与格式转换(Tier-1.75 的数据准备,筛选在 Phase 2 裁判就位后)。

**理由:** 这一层全是确定性、零外部依赖、马上能跑回归的代码;它同时服务 Tier-1.5(free_params)与 Tier-2,且不动现有管线一行。

### Phase 2(4–8 周,beam-FEM 裁判 + LLM-提案-优化回路)
1. `beam_homog.py` 自研 Timoshenko PBC 均质化器 → 三重回归验证(自家 24 拓扑 DB / Bastek PNAS 2022 / Lumpe–Stankovic 抽样)→ 节点刚化修正标定 → **每拓扑类误差条表进 Evaluator**(l/d 硬门同时生效)。
2. FunSearch 模式抛光回路打通:Claude 离散提案(结构化门诊断回喂)× pycma/Nelder-Mead 连续抛光 × beam 裁判打分,≤3 轮,对齐既有 Evaluator-Optimizer K=3 回路(HANDOFF §9 Phase 2 第 7 条)。
3. Tier-1.75 目录筛选实跑:Maxwell + G-A + beam-FEM 三级筛 17,087 → top 候选过 ABAQUS 终审 → "database-wide 全局最优"搜索空间扩容 ~700 倍的叙事落地。
4. 三道绝对 sanity 门(SPD / Voigt-Reuss–HS / 跨档 20%)+ ALLKE/ALLIE 能量门进 postprocess 模板;误差条查表 (tier × l/d × ρ̄) 进 Evaluator。

**理由:** beam 裁判是 truss 类 Tier-2 的限速步,也是目录扩容的筛子;回路所需的门(Phase 1)与裁判(本阶段)就位后,**第一批"词汇表外"truss 拓扑即可端到端产出**——这是最短路径的 Tier-2 首胜。

### Phase 3(2–4 个月,FFT/spinodoid/扩散 + ABAQUS 自动升压)
1. Tier-C 体素裁判:GooseFFT-fork(Willot 算子 + 有限对比度)vs fedoo+microgen benchmark 定主备;双网格误差条制度化。
2. **Spinodoid 旗舰**:NumPy GRF 重写(避 AGPL)→ marching cubes → 打印检查 → orphan-mesh INP 适配器(1–2 周)→ 用自家 ABAQUS 管线打标 1–3k 样本(静压先行,呼应"静态先行"叙事)→ CPU 训练 f-NN/i-NN 对;SEA 工况用 BO 包 4 维空间直驱显式 FEA(先例 arXiv 2411.14508)。RVE 收敛研究替代尺寸效应查表(R6)。
3. 第二波深度生成(inference-only):UnifyingTrussDesignSpace 与 DiffuMeta 预训练 checkpoint 工作站推理 → 候选全部过 C 门 + B/C 裁判 + D 终审;预测头永不入 trace。
4. **ABAQUS 自动升压制度化**:快档幸存者自动生成作业、排队、回收特征、回写 trace(VideoMetamaterials 的 eval_abaqus.py 回路先例),预算 ≤3/查询。
5. 延后项:deHomTop808 "构件模式"(刚度驱动工况,需 MATLAB);GraphMetaMat(仅当需求升级为可编程全曲线);视频扩散与 LLM 多智能体论文仅 related-work。

**理由:** 体素裁判是 spinodoid 的前置;spinodoid 是验证链最长(新 INP 路线 + RVE 研究)但回报最高的"外星"主张;深度模型推理放最后,因为它们的全部价值都依赖前两阶段建好的裁判与门。

---

## 8. 引用清单(按 HANDOFF 引用层三分类)

**学术(DOI,已核实):**
- Kumar, Tan, Zheng, Kochmann, npj Comput. Mater. 6:73 (2020), 10.1038/s41524-020-0341-6 — spinodoid 4 参数化
- Zheng, Kumar, Kochmann, CMAME 383:113894 (2021), arXiv 2012.15744 — 梯度 spinodoid 两尺度 TO
- Bastek et al., PNAS 119(1):e2111505119 (2022), 10.1073/pnas.2111505119 — truss 反演 + Timoshenko PBC 均质化
- Zheng et al., Nat. Commun. 14:7563 (2023), 10.1038/s41467-023-42068-x — truss graph-VAE
- Bastek & Kochmann, Nat. Mach. Intell. 5:1466 (2023), 10.1038/s42256-023-00762-x — 视频扩散(先例)
- Zheng, Kumar, Kochmann, Nat. Mach. Intell. (2026), 10.1038/s42256-026-01218-8, arXiv 2507.15753 — DiffuMeta
- Maurizi et al., Nat. Mach. Intell. (2025), 10.1038/s42256-025-01067-x — GraphMetaMat
- Lumpe & Stankovic, PNAS 118(7):e2003504118 (2021), 10.1073/pnas.2003504118 — 17,087 晶体网目录
- deHomTop808, SMO (2024), 10.1007/s00158-024-03880-1 — 去均质化 TO
- Zhong et al., COSSMS 27:101081 (2023), 10.1016/j.cossms.2023.101081 — G-A/beam 有效域(**HANDOFF §5 出处勘误**)
- Portela, Greer, Kochmann, EML (2018), 10.1016/j.eml.2018.06.004 — 节点刚化
- Willot, C. R. Mécanique (2015), 10.1016/j.crme.2014.12.005;Moulinec & Suquet, CMAME (1998), 10.1016/S0045-7825(97)00218-1;Schneider, Acta Mech. (2021), 10.1007/s00707-021-02962-1 — FFT 均质化
- Pellegrino & Calladine, IJSS 22:409 (1986), 10.1016/0020-7683(86)90014-4 — 平衡矩阵 SVD
- Romera et al. (FunSearch), Nature (2023), 10.1038/s41586-023-06924-6 — frozen-LLM + 评估器进化
- Ha et al., Nat. Commun. 14 (2023), 10.1038/s41467-023-40854-1;DiffMat, CMAME (2024);arXiv 2312.11648 — 非线性曲线条件反设计(纠正项)
- Li et al., Adv. Eng. Mater. (2025), 10.1002/adem.202402360 — sigmoid TPMS 杂化
- arXiv 2411.14508 — spinodoid 压溃吸能 BO;arXiv 2503.19889 / 2506.06935 — LLM 多智能体(related-work)

**代码/数据资产(license 已记录):**
- mmc-group/inverse-designed-spinodoids(MIT,CPU 可)· jhbastek/InvertibleTrussDesign(MIT)· jhbastek/VideoMetamaterials(MIT)· li-zhengz/UnifyingTrussDesignSpace(MIT;数据 ETHZ 10.3929/ethz-b-000618078)· li-zhengz/DiffusionMetamaterials(ETHZ/Zenodo 18598195)· marcomau06/GraphMetaMat · peterdorffler/deHomTop808(MATLAB)· Lumpe–Stankovic 目录(ETH 10.3929/ethz-b-000457595)· GIBBON(**AGPL-3.0,勿链接**)· tdegeus/GooseFFT(**license 待核实**)· FANS / muSpectre(LGPL,无 win-64)· fedoo+microgen(pip,Windows)· unitcellengine(Apache-2.0,alpha)· JWock82/Pynite(MIT)· ae108(ETH GitLab,GPL,C++/PETSc)

**推测/待核实(使用前须标定或查证):**
- 各档误差条 ±%(R15)· Tier-B <0.1 s 与 Tier-C/D 运行时包络 · Tier-D 1–6 h(从作业日志实测)· 时间线基准 · octet 40%/30% 低估锚点(对自家数据复算)· Hsieh 2019 self-supporting 原文措辞 · GooseFFT license · nTop 商业对标定位 · LLM 首过拒绝率 10–30%

---

*本报告由 ATLAS novel-topology 调研三车道(生成方法 / 快速物理裁判 / 表示与约束)的对抗式核查语料综合而成;所有被核查驳回的论断仅以纠正后形式出现。*
