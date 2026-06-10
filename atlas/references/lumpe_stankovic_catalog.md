---
doi: 10.3929/ethz-b-000457598
paper_doi: 10.1073/pnas.2003504118
title: Unit Cell Catalog (Lumpe & Stankovic, PNAS 2021)
source_type: academic_doi
license: CC BY-NC 4.0
license_boundary: 非商用!研究使用 OK;ATLAS 商业化部署前必须重审或替换
validated_claims:
  - 目录含 17,262 个周期胞元结构(基于 RCSR + EPINET 数据库)
  - 其中 135 个重复项 + 40 个含极小杆件(标 * 号)的数值问题结构,论文分析时剔除 → 论文口径 17,087
  - 每条目含:唯一名/别名/归一化胞参数(a,b,c,α,β,γ)/平均连通度 Z_avg/均质化 Ex,y,z Gyz,xz,xy ν(6 项)/标度常数 Cx,y,z 与指数 nx,y,z(E/Es=C·ρ̄^n)/杆重叠指示/节点分数坐标/杆连接表
  - 均质化基材 Es=1 MPa, νs=0.3,模量单位 MPa(归一化)
validity_domain: 线弹性均质化(刚度/泊松比);无屈服/SEA/非线性数据;非立方胞占比待统计
local_file: atlas/data/external/Unit_Cell_Catalog.txt (58.7 MB, 不入 git)
sha256: D4E7A754C5E46847E4912543D474C33785E26BB6714DCB1BB695DC1B706C50F2
download: https://www.research-collection.ethz.ch/server/api/core/bitstreams/8d9435c1-5d45-4e9b-be3a-56e88fc4efd5/content
date_downloaded: 2026-06-10
---

# Lumpe-Stanković Unit Cell Catalog — ATLAS Tier-1.75 数据源

**ATLAS 用途**:
1. **Tier-1.75 目录枚举扩容**(P2-3):17k+ 晶体网 truss,把 database-wide
   搜索空间扩 ~700 倍,零 ML 风险。红线:如实称"枚举"不称"生成";
   引用时区分论文分析数(17,087)与目录总数(17,262),见 errata E9。
2. **beam-FEM 裁判三重验证之一**(P2-1):条目自带均质化 E/G/ν 与 C,n
   标度,可作自研 Timoshenko 均质化器的独立金标准抽样对照。
3. **格式 → atlas-cell-graph/1.0**:节点为分数坐标 + 杆连接表,与 A4
   schema 同构;注意条目是"装饰表示"(边界节点重复,如 pcu 为 8 节点
   12 杆),需走 seeds.py 同款商图规范化;非立方胞(a,b,c,α,β,γ ≠ 立方)
   需 schema 的 lattice_vectors 扩展。

**解析要点**:条目以 89 个 `-` 分隔;字段名行 + 值行;标 `*` 的 40 条
数值问题结构与 135 条重复项需在摄入时打 quality flag(P2-3 摄入任务)。

**许可红线**:CC BY-NC 4.0(非商用)。已登记 errata.md 许可表。
