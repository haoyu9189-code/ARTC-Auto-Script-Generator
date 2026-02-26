# -*- coding: utf-8 -*-
"""
Abaqus静态仿真模型模板
用于生成晶格结构的静态压缩/剪切仿真脚本

@author: Wang Haoyu
@date: 2025-12-06
@copyright: (c) 2025 Wang Haoyu. All rights reserved.
"""

from abaqus import *
from abaqusConstants import *
import numpy as np
from math import acos, degrees
from numpy.linalg import norm
from numpy import cross, dot
import regionToolset

# 圆柱体半径
radius = 0.3
cell_size = 5
# 定义关键点坐标
A  = [-2.5,  2.5,  2.5]
B  = [ 2.5,  2.5,  2.5]
C  = [ 2.5, -2.5,  2.5]
D  = [-2.5, -2.5,  2.5]
A_ = [-2.5,  2.5, -2.5]
B_ = [ 2.5,  2.5, -2.5]
C_ = [ 2.5, -2.5, -2.5]
D_ = [-2.5, -2.5, -2.5]
O  = [ 0, 0, 0]

# 定义圆柱体连接
cylinders = [
    (O, A), (O, B), (O, C), (O, D),
    (O, A_), (O, B_), (O, C_), (O, D_),
    (B, C), (D, A),
    (B_, C_), (D_, A_)
]

model = mdb.models['Model-1']
assembly = model.rootAssembly
inst_list = []

# 创建圆柱体

# 创建圆柱体
for i, (start, end) in enumerate(cylinders):
    start = np.array(start)
    end = np.array(end)
    vec = end - start
    length = norm(vec)

    # 跳过长度为0的圆柱体（两端点重合）
    if length < 1e-6:
        print("Warning: Skipping zero-length cylinder %d (start and end points coincide)" % (i+1))
        continue

    direction = vec / length

    sketch = model.ConstrainedSketch(name='circleSketch-%02d' % (i+1), sheetSize=20.0)
    sketch.CircleByCenterPerimeter(center=(0.0, 0.0), point1=(radius, 0.0))

    part_name = 'Cyl-%02d' % (i+1)
    part = model.Part(name=part_name, dimensionality=THREE_D, type=DEFORMABLE_BODY)
    part.BaseSolidExtrude(sketch=sketch, depth=length)

    inst_name = 'Inst-%02d' % (i+1)
    assembly.Instance(name=inst_name, part=part, dependent=ON)
    assembly.translate(instanceList=(inst_name,), vector=tuple(start))

    z_axis = np.array([0, 0, 1])
    rot_axis = cross(z_axis, direction)
    dot_product = dot(z_axis, direction)

    if norm(rot_axis) < 1e-6:
        if dot_product < 0:
            assembly.rotate(instanceList=(inst_name,),
                            axisPoint=tuple(start),
                            axisDirection=(1, 0, 0),
                            angle=180)
    else:
        angle = degrees(acos(dot_product))
        assembly.rotate(instanceList=(inst_name,),
                        axisPoint=tuple(start),
                        axisDirection=tuple(rot_axis),
                        angle=angle)

    inst_list.append(assembly.instances[inst_name])
# 创建球体（在每个关键点处）
# 收集所有定义的关键点坐标
def is_coord_list(val):
    """检查值是否为有效的3D坐标列表"""
    if type(val) != list or len(val) != 3:
        return False
    for x in val:
        if not isinstance(x, (int, float)):
            return False
    return True

all_node_coords = []
for var_name in dir():
    if var_name.startswith('N') and var_name[1:].isdigit():
        val = eval(var_name)
        if is_coord_list(val):
            all_node_coords.append((var_name, val))
    elif len(var_name) <= 3 and var_name.replace('_', '').isalpha():
        try:
            val = eval(var_name)
            if is_coord_list(val):
                all_node_coords.append((var_name, val))
        except:
            pass

for j, (node_name, node_coord) in enumerate(all_node_coords):
    # 创建球体草图 - 使用旋转生成球体
    sketch_name = 'sphereSketch-%02d' % (j+1)
    s_sphere = model.ConstrainedSketch(name=sketch_name, sheetSize=20.0)

    # 绘制半圆（用于旋转生成球体）
    s_sphere.ConstructionLine(point1=(0.0, -radius*2), point2=(0.0, radius*2))
    s_sphere.ArcByCenterEnds(center=(0.0, 0.0), point1=(0.0, radius),
                             point2=(0.0, -radius), direction=CLOCKWISE)
    s_sphere.Line(point1=(0.0, radius), point2=(0.0, -radius))

    # 创建球体零件
    sphere_part_name = 'Sphere-%02d' % (j+1)
    sphere_part = model.Part(name=sphere_part_name, dimensionality=THREE_D, type=DEFORMABLE_BODY)
    sphere_part.BaseSolidRevolve(sketch=s_sphere, angle=360.0, flipRevolveDirection=OFF)

    # 创建球体实例并定位到关键点
    sphere_inst_name = 'SphereInst-%02d' % (j+1)
    assembly.Instance(name=sphere_inst_name, part=sphere_part, dependent=ON)
    assembly.translate(instanceList=(sphere_inst_name,), vector=tuple(node_coord))

    inst_list.append(assembly.instances[sphere_inst_name])

print("Created %d spheres at key points" % len(all_node_coords))

# 合并几何体
merged_part = assembly.InstanceFromBooleanMerge(
    name='MergedStructure',
    instances=inst_list,
    keepIntersections=OFF,
    originalInstances=DELETE,
    domain=GEOMETRY
)

# 获取合并后的零件
p = model.parts['MergedStructure']

# 创建基准轴
datum_axis = p.DatumAxisByPrincipalAxis(principalAxis=YAXIS)
up_edge_id = datum_axis.id

# 创建顶部切割平面 (Z = +2.5位置)
datum_top = p.DatumPlaneByPrincipalPlane(principalPlane=XYPLANE, offset=3)
datum_top_id = datum_top.id

# 创建顶部切割草图
t1 = p.MakeSketchTransform(sketchPlane=p.datums[datum_top_id], 
                          sketchUpEdge=p.datums[up_edge_id], 
                          sketchPlaneSide=SIDE1, 
                          sketchOrientation=RIGHT, 
                          origin=(0.0, 0.0, 2.5))

s1 = model.ConstrainedSketch(name='cutTopSketch', sheetSize=20.0, transform=t1)
s1.setPrimaryObject(option=SUPERIMPOSE)
p.projectReferencesOntoSketch(sketch=s1, filter=COPLANAR_EDGES)

# 创建切割用的矩形
s1.rectangle(point1=(-2.5, -2.5), point2=(2.5, 2.5))
s1.rectangle(point1=(-5.0, -5.0), point2=(5.0, 5.0))

# 执行顶部切割
# 修正后的顶部切割
p.CutExtrude(sketchPlane=p.datums[datum_top_id], 
            sketchUpEdge=p.datums[up_edge_id], 
            sketchPlaneSide=SIDE1, 
            sketchOrientation=RIGHT, 
            sketch=s1, 
            depth=6,  # 向下切割2.5单位
            flipExtrudeDirection=OFF)

s1.unsetPrimaryObject()
del model.sketches['cutTopSketch']

# 创建侧面切割平面 (Y = +2.5位置)
datum_side = p.DatumPlaneByPrincipalPlane(principalPlane=XZPLANE, offset=3)
datum_side_id = datum_side.id

# 创建侧面基准轴
datum_axis2 = p.DatumAxisByPrincipalAxis(principalAxis=XAXIS)
side_edge_id = datum_axis2.id

# 创建侧面切割草图
t2 = p.MakeSketchTransform(sketchPlane=p.datums[datum_side_id], 
                          sketchUpEdge=p.datums[side_edge_id], 
                          sketchPlaneSide=SIDE1, 
                          sketchOrientation=RIGHT, 
                          origin=(0.0, 2.5, 0.0))

s2 = model.ConstrainedSketch(name='cutSideSketch', sheetSize=20.0, transform=t2)
s2.setPrimaryObject(option=SUPERIMPOSE)
p.projectReferencesOntoSketch(sketch=s2, filter=COPLANAR_EDGES)

# 复制之前的矩形形状
s2.rectangle(point1=(-2.5, -2.5), point2=(2.5, 2.5))
s2.rectangle(point1=(-5.0, -5.0), point2=(5.0, 5.0))

# 执行侧面切割
p.CutExtrude(sketchPlane=p.datums[datum_side_id], 
            sketchUpEdge=p.datums[side_edge_id], 
            sketchPlaneSide=SIDE1, 
            sketchOrientation=RIGHT, 
            sketch=s2, 
            depth=6,  # 向内切割2.5单位
            flipExtrudeDirection=OFF)

s2.unsetPrimaryObject()
del model.sketches['cutSideSketch']

# 创建刚性板（8.0 x 8.0，避免压缩时结构出界）
# 原尺寸: 6.0 x 6.0 → 新尺寸: 8.0 x 8.0
s3 = model.ConstrainedSketch(name='rigidPlateSketch', sheetSize=20.0)
s3.setPrimaryObject(option=STANDALONE)
s3.Line(point1=(-4.0, 0.0), point2=(4.0, 0.0))  # 长度 = 8.0
s3.HorizontalConstraint(entity=s3.geometry[2], addUndoState=False)

rigid_part = model.Part(name='RigidPlate',
                       dimensionality=THREE_D,
                       type=DISCRETE_RIGID_SURFACE)

rigid_part.BaseShellExtrude(sketch=s3, depth=8.0)  # 宽度 = 8.0
s3.unsetPrimaryObject()
del model.sketches['rigidPlateSketch']

# 创建刚性板实例
assembly.DatumCsysByDefault(CARTESIAN)
assembly.Instance(name='RigidPlate-1', part=rigid_part, dependent=ON)
assembly.translate(instanceList=('RigidPlate-1',), vector=(0.0, -2.5, -4.0))

assembly.Instance(name='RigidPlate-2', part=rigid_part, dependent=ON)
assembly.translate(instanceList=('RigidPlate-2',), vector=(0.0, 2.5, -4.0))

# 创建材料
material = model.Material(name='Material-1')
material.Density(table=((1.01e-09,),))
material.Elastic(table=((1554.5, 0.3),))
material.Plastic(table=(
    (33.97, 0.0),
    (36.71, 0.0014),
    (39.03, 0.0040),
    (41.13, 0.0071),
    (43.36, 0.0115),
    (45.09, 0.0162),
    (46.48, 0.0218),
    (47.74, 0.0279),
    (49.00, 0.0357),
    (50.21, 0.0456),
    (51.47, 0.0569),
    (52.48, 0.0718),
    (53.86, 0.0830),
    (55.07, 0.1041),
    (55.98, 0.1227),
    (56.31, 0.1376),
    (56.64, 0.1534),
    (56.80, 0.1633),
))

# ===== 新增:延性损伤 (SLS PA12材料 - 准静态) =====
# 材料: SLS打印PA12 (聚酰胺12)
# 准静态加载: 应变率~0.033 s⁻¹ (30秒压缩100%)
# 拉伸断裂伸长率: 14-27% (文献上限值，准静态更韧性)
# 压缩断裂应变: >60% (文献值，准静态更韧性)
# 参考文献: 同动态模板，见 task_log/documentation/DAMAGE_PARAMETERS_GUIDE.md

# 损伤起始准则(考虑应力三轴度)
# IMPORTANT: triaxiality 必须按升序排列!
material.DuctileDamageInitiation(table=(
    (0.60, -0.333,0.033),  # 压缩：准静态取文献接近值60%
    (0.40, 0.0, 0.033),      # 剪切：中等韧性，插值估算
    (0.25, 0.333, 0.033),    # 拉伸：准静态取文献中值25% (14-27%)
))

# 损伤演化 - 失效位移 (准静态允许更大位移)
# 准静态加载: 应变率~0.033 s⁻¹
# 失效位移0.5mm: 增大以避免复杂结构(如WeairePhelan)在高应变时单元过度变形
# 计算依据: 网格尺寸0.3mm × 1.67 ≈ 0.5mm
material.ductileDamageInitiation.DamageEvolution(type=DISPLACEMENT, table=((0.5,),))
# ============================================

# 创建截面
model.HomogeneousSolidSection(name='Section-1', material='Material-1', thickness=None)
model.HomogeneousShellSection(name='Section-2', 
                             preIntegrate=OFF, 
                             material='Material-1', 
                             thicknessType=UNIFORM, 
                             thickness=0.05, 
                             thicknessField='', 
                             nodalThicknessField='', 
                             idealization=NO_IDEALIZATION, 
                             poissonDefinition=DEFAULT, 
                             thicknessModulus=None, 
                             temperature=GRADIENT, 
                             useDensity=OFF, 
                             integrationRule=SIMPSON, 
                             numIntPts=5)

# 为刚性板分配截面属性
rigid_part = model.parts['RigidPlate']
f = rigid_part.faces
faces = f.getSequenceFromMask(mask=('[#1]',),)
region = regionToolset.Region(faces=faces)
rigid_part.SectionAssignment(region=region, 
                            sectionName='Section-2', 
                            offset=0.0, 
                            offsetType=MIDDLE_SURFACE, 
                            offsetField='', 
                            thicknessAssignment=FROM_SECTION)

# 为主结构分配截面属性
main_part = model.parts['MergedStructure']
c = main_part.cells
cells = c.getSequenceFromMask(mask=('[#1]',),)
region = regionToolset.Region(cells=cells)
main_part.SectionAssignment(region=region, 
                           sectionName='Section-1', 
                           offset=0.0, 
                           offsetType=MIDDLE_SURFACE, 
                           offsetField='', 
                           thicknessAssignment=FROM_SECTION)

# 重新生成装配体
assembly.regenerate()

print("Model creation completed successfully!")



# -*- coding: mbcs -*-
# Do not delete the following import lines
from abaqus import *
from abaqusConstants import *
import __main__
import section
import regionToolset
import displayGroupMdbToolset as dgm
import part
import material
import assembly
import step
import interaction
import load
import mesh
import optimization
import job
import sketch
import visualization
import xyPlot
import displayGroupOdbToolset as dgo
import connectorBehavior


def Macro1():

    # === 刚体板参考点 + 质量 ===
    p = mdb.models['Model-1'].parts['RigidPlate']
    v, e, d, n = p.vertices, p.edges, p.datums, p.nodes
    p.ReferencePoint(point=v[1])
    r = p.referencePoints
    refPoints = (r[3], )
    region = p.Set(referencePoints=refPoints, name='RefPlateSet')
    mdb.models['Model-1'].parts['RigidPlate'].engineeringFeatures.PointMassInertia(
        name='Inertia-1', region=region, mass=8.45e-07, alpha=0.0, 
        composite=0.0)

    a = mdb.models['Model-1'].rootAssembly
    a.regenerate()

    # === Explicit 准静态分析 ===
    # Static/Implicit 在屈曲+大变形+密集接触时失败，改用 Explicit
    mdb.models['Model-1'].ExplicitDynamicsStep(
        name='Step-1',
        previous='Initial',
        timePeriod=0.3,              # 准静态：0.3秒（增加加载时间减少震荡）
        massScaling=((SEMI_AUTOMATIC, MODEL, THROUGHOUT_STEP, 0.0, 1e-06, BELOW_MIN, 1, 0, 0.0, 0.0, 0, None), ),
        improvedDtMethod=ON,
        nlgeom=ON,
        linearBulkViscosity=0.25,    # 抑制低频振动
        quadBulkViscosity=2.0        # 抑制高频振动
    )

    # === 场变量输出设置 ===
    mdb.models['Model-1'].fieldOutputRequests['F-Output-1'].setValues(
        variables=('S', 'E', 'PE', 'PEEQ', 'PEMAG', 'LE', 'U', 'RF', 'CF', 'CSTRESS', 'CDISP', 'STATUS'),
        numIntervals=100
    )

    # === 定义反射点集 ===
    v1 = a.instances['MergedStructure-1'].vertices
    verts1 = v1.getSequenceFromMask(mask=('[#20000 ]', ), )
    a.Set(vertices=verts1, name='Reflection')

    # BotReflection
    r1 = a.instances['RigidPlate-1'].referencePoints
    refPoints1 = (r1[3], )
    a.Set(referencePoints=refPoints1, name='BotReflection')

    # TopReflection
    r1 = a.instances['RigidPlate-2'].referencePoints
    refPoints1 = (r1[3], )
    a.Set(referencePoints=refPoints1, name='TopReflection')

    # === 输出请求 ===
    regionDef = a.sets['TopReflection']
    mdb.models['Model-1'].HistoryOutputRequest(name='H-Output-2',
        createStepName='Step-1', variables=('U1', 'U2', 'RF1', 'RF2'),
        region=regionDef, sectionPoints=DEFAULT, rebar=EXCLUDE)

    # === Rigid body 约束 ===
    region2 = a.sets['TopReflection']
    r1 = a.instances['RigidPlate-2'].referencePoints
    refPoints1 = (r1[3], )
    region1 = regionToolset.Region(referencePoints=refPoints1)
    mdb.models['Model-1'].RigidBody(name='Constraint-1', refPointRegion=region1, 
        bodyRegion=region2)

    region2 = a.sets['BotReflection']
    r1 = a.instances['RigidPlate-1'].referencePoints
    refPoints1 = (r1[3], )
    region1 = regionToolset.Region(referencePoints=refPoints1)
    mdb.models['Model-1'].RigidBody(name='Constraint-2', refPointRegion=region1, 
        bodyRegion=region2)

    # === 接触属性 ===
    mdb.models['Model-1'].ContactProperty('IntProp-1')
    mdb.models['Model-1'].interactionProperties['IntProp-1'].TangentialBehavior(
        formulation=PENALTY, directionality=ISOTROPIC, slipRateDependency=OFF, 
        pressureDependency=OFF, temperatureDependency=OFF, dependencies=0, 
        table=((0.15, ), ), shearStressLimit=None, maximumElasticSlip=FRACTION, 
        fraction=0.005, elasticSlipStiffness=None)
    # Explicit 使用 HARD 接触（罚函数自动处理）
    mdb.models['Model-1'].interactionProperties['IntProp-1'].NormalBehavior(
        pressureOverclosure=HARD,
        allowSeparation=ON)

    # === 接触对（Explicit 版本）===
    s1 = a.instances['RigidPlate-2'].faces
    side1Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
    region1 = a.Surface(side1Faces=side1Faces1, name='m_Surf-1')

    s1 = a.instances['MergedStructure-1'].faces
    side1Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
    region2 = a.Surface(side1Faces=side1Faces1, name='s_Surf-1')
    mdb.models['Model-1'].SurfaceToSurfaceContactExp(name='Int-1',
        createStepName='Step-1', main=region1, secondary=region2,
        sliding=FINITE, interactionProperty='IntProp-1')

    s1 = a.instances['RigidPlate-1'].faces
    side1Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
    region1 = a.Surface(side1Faces=side1Faces1, name='m_Surf-3')

    s1 = a.instances['MergedStructure-1'].faces
    side1Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
    region2 = a.Surface(side1Faces=side1Faces1, name='s_Surf-3')
    mdb.models['Model-1'].SurfaceToSurfaceContactExp(name='Int-2',
        createStepName='Step-1', main=region1, secondary=region2,
        sliding=FINITE, interactionProperty='IntProp-1')
    
    mdb.models['Model-1'].interactions['Int-1'].move('Step-1', 'Initial')
    mdb.models['Model-1'].interactions['Int-2'].move('Step-1', 'Initial')
    session.viewports['Viewport: 1'].assemblyDisplay.setValues(step='Step-1')

    a = mdb.models['Model-1'].rootAssembly
    a.regenerate()
    session.viewports['Viewport: 1'].assemblyDisplay.setValues(loads=OFF, bcs=OFF, 
        predefinedFields=OFF, connectors=OFF)
    a = mdb.models['Model-1'].rootAssembly
    s1 = a.instances['RigidPlate-1'].faces
    side2Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
    a.Surface(side2Faces=side2Faces1, name='m_Surf-3')

    # === 约束条件（Explicit 版本）===
    # 底板固定：应用在参考点上（刚体控制）
    region = a.sets['BotReflection']
    mdb.models['Model-1'].EncastreBC(name='BC-1', createStepName='Initial',
        region=region, localCsys=None)

    u2=-0.8*cell_size  # 80%应变
    region = a.sets['TopReflection']
    mdb.models['Model-1'].DisplacementBC(name='BC-2', createStepName='Step-1',
        region=region, u1=0.0, u2=u2, u3=0.0, ur1=0.0, ur2=0.0, ur3=0.0,
        amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='',
        localCsys=None)
    # Explicit: 使用 SmoothStepAmplitude 避免冲击，时间匹配 timePeriod=0.3
    mdb.models['Model-1'].SmoothStepAmplitude(name='Amp-1', timeSpan=STEP,
        data=((0.0, 0.0), (0.3, 1.0)))
    mdb.models['Model-1'].boundaryConditions['BC-2'].setValuesInStep(
        stepName='Step-1', amplitude='Amp-1')

    # BC-1 已在 Initial 步创建，无需移动
    
    a = mdb.models['Model-1'].rootAssembly
    f1 = a.instances['RigidPlate-2'].faces
    faces1 = f1.getSequenceFromMask(mask=('[#1 ]', ), )
    region2=a.Set(faces=faces1, name='b_Set-8')
    a = mdb.models['Model-1'].rootAssembly
    r1 = a.instances['RigidPlate-2'].referencePoints
    refPoints1=(r1[3], )
    region1=regionToolset.Region(referencePoints=refPoints1)
    mdb.models['Model-1'].constraints['Constraint-1'].setValues(
        refPointRegion=region1, bodyRegion=region2)
    a = mdb.models['Model-1'].rootAssembly
    f1 = a.instances['RigidPlate-1'].faces
    faces1 = f1.getSequenceFromMask(mask=('[#1 ]', ), )
    region2=a.Set(faces=faces1, name='b_Set-9')
    a = mdb.models['Model-1'].rootAssembly
    r1 = a.instances['RigidPlate-1'].referencePoints
    refPoints1=(r1[3], )
    region1=regionToolset.Region(referencePoints=refPoints1)
    mdb.models['Model-1'].constraints['Constraint-2'].setValues(
        refPointRegion=region1, bodyRegion=region2)

    
    # === 网格划分 ===
    a.regenerate()
    p = mdb.models['Model-1'].parts['MergedStructure']
    c = p.cells
    pickedRegions = c.getSequenceFromMask(mask=('[#1 ]', ), )
    p.setMeshControls(regions=pickedRegions, elemShape=TET, technique=FREE)
    # Explicit 单元类型：C3D10M（修改四面体，适合大变形）
    elemType1 = mesh.ElemType(elemCode=C3D10M, elemLibrary=EXPLICIT)
    elemType2 = mesh.ElemType(elemCode=C3D10M, elemLibrary=EXPLICIT)
    elemType3 = mesh.ElemType(elemCode=C3D10M, elemLibrary=EXPLICIT)
    cells = c.getSequenceFromMask(mask=('[#1 ]', ), )
    pickedRegions = (cells, )
    p.setElementType(regions=pickedRegions, elemTypes=(elemType1, elemType2, elemType3))
    # 网格大小根据cell_size和radius动态调整（平方根关系）
    # 平方根关系：细杆网格不过密，粗杆网格不过稀
    # radius=0.3→0.17, 0.35→0.18, 0.4→0.20, 0.45→0.21, 0.5→0.2
    import math
    mesh_size_structure = 0.2 * math.sqrt(radius / 0.5) * (cell_size / 5.0)  # 结构网格
    mesh_size_plate = 0.5 * (radius / 0.5) * (cell_size / 5.0)      # 刚板网格
    p.seedPart(size=mesh_size_structure, deviationFactor=0.1, minSizeFactor=0.1)

    p = mdb.models['Model-1'].parts['MergedStructure']
    p.generateMesh()
    p = mdb.models['Model-1'].parts['RigidPlate']
    p.seedPart(size=mesh_size_plate, deviationFactor=0.1, minSizeFactor=0.1)
    p.generateMesh()


Macro1()

# === 自动识别底面并创建Tie约束 (Constraint-3) ===
print("\n========== Creating Bottom Tie Constraint ==========")
a = mdb.models['Model-1'].rootAssembly
instance = a.instances['MergedStructure-1']
faces = instance.faces

# 自动识别底面（法向量为(0,-1,0)）
bottom_face_objects = []
for face in faces:
    try:
        normal = face.getNormal()
        # 法向量(0,-1,0)，允许0.01的误差
        if (abs(normal[0]) < 0.01 and
            abs(normal[1] + 1.0) < 0.01 and
            abs(normal[2]) < 0.01):
            bottom_face_objects.append(face)
    except:
        pass

print("Found %d bottom faces for Tie constraint" % len(bottom_face_objects))

# 创建底面Tie约束
if bottom_face_objects:
    # Main region: 底部刚性板
    s1 = a.instances['RigidPlate-1'].faces
    side2Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
    region1 = regionToolset.Region(side2Faces=side2Faces1)

    # Secondary region: 结构底面（使用findAt重新获取face对象）
    s1 = a.instances['MergedStructure-1'].faces
    found_faces = []
    for face in bottom_face_objects:
        face_center = face.pointOn[0]
        found_face = s1.findAt((face_center,))
        found_faces.append(found_face)
    region2 = a.Surface(side1Faces=tuple(found_faces), name='s_Surf-BottomTie')

    # 创建Tie约束
    mdb.models['Model-1'].Tie(
        name='Constraint-3',
        main=region1,
        secondary=region2,
        positionToleranceMethod=COMPUTED,
        adjust=ON,
        tieRotations=ON,
        thickness=ON
    )
    print("SUCCESS: Bottom Tie constraint created (Constraint-3)")
else:
    print("WARNING: No bottom faces found, Tie constraint not created")

print("=" * 50)

# === 自动识别顶面并创建Tie约束 (Constraint-4) ===
print("\n========== Creating Top Tie Constraint ==========")
a = mdb.models['Model-1'].rootAssembly
instance = a.instances['MergedStructure-1']
faces = instance.faces

# 自动识别顶面（法向量为(0,+1,0)）
top_face_objects = []
for face in faces:
    try:
        normal = face.getNormal()
        # 法向量(0,+1,0)，允许0.01的误差
        if (abs(normal[0]) < 0.01 and
            abs(normal[1] - 1.0) < 0.01 and
            abs(normal[2]) < 0.01):
            top_face_objects.append(face)
    except:
        pass

print("Found %d top faces for Tie constraint" % len(top_face_objects))

# 创建顶面Tie约束
if top_face_objects:
    # Main region: 顶部刚性板
    s1 = a.instances['RigidPlate-2'].faces
    side2Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
    region1 = regionToolset.Region(side2Faces=side2Faces1)

    # Secondary region: 结构顶面（使用findAt重新获取face对象）
    s1 = a.instances['MergedStructure-1'].faces
    found_faces = []
    for face in top_face_objects:
        face_center = face.pointOn[0]
        found_face = s1.findAt((face_center,))
        found_faces.append(found_face)
    region2 = a.Surface(side1Faces=tuple(found_faces), name='s_Surf-TopTie')

    # 创建Tie约束
    mdb.models['Model-1'].Tie(
        name='Constraint-4',
        main=region1,
        secondary=region2,
        positionToleranceMethod=COMPUTED,
        adjust=ON,
        tieRotations=ON,
        thickness=ON
    )
    print("SUCCESS: Top Tie constraint created (Constraint-4)")
else:
    print("WARNING: No top faces found, Tie constraint not created")

print("=" * 50)

def Macro2():
    # === 添加General Contact处理内部自接触（防止穿模） ===
    # 上下已经用Tie约束固定，这里只处理结构内部的杆件接触

    a = mdb.models['Model-1'].rootAssembly

    print("\n========== Creating General Contact for Internal Self-Contact ==========")

    # 删除之前创建的Surface-to-Surface接触（如果存在）
    # 因为通用接触会自动处理所有接触对
    try:
        if 'Int-1' in mdb.models['Model-1'].interactions.keys():
            del mdb.models['Model-1'].interactions['Int-1']
            print("Deleted Int-1 (Surface-to-Surface contact)")
    except:
        pass

    try:
        if 'Int-2' in mdb.models['Model-1'].interactions.keys():
            del mdb.models['Model-1'].interactions['Int-2']
            print("Deleted Int-2 (Surface-to-Surface contact)")
    except:
        pass

    # 创建通用接触（Explicit分析使用ContactExp）
    mdb.models['Model-1'].ContactExp(
        name='GeneralContact',
        createStepName='Initial'
    )

    # 设置通用接触为全接触（自动检测所有可能的接触对）
    mdb.models['Model-1'].interactions['GeneralContact'].includedPairs.setValuesInStep(
        stepName='Initial',
        useAllstar=ON
    )

    # 为通用接触分配接触属性IntProp-1
    mdb.models['Model-1'].interactions['GeneralContact'].contactPropertyAssignments.appendInStep(
        stepName='Initial',
        assignments=((GLOBAL, SELF, 'IntProp-1'), )
    )

    print("SUCCESS: General Contact created for self-contact")
    print("  - Contact type: ContactExp (for Explicit analysis)")
    print("  - Mode: useAllstar=ON (automatic contact detection)")
    print("  - Contact property: IntProp-1 (friction=0.15, hard contact)")
    print("  - Purpose: Prevent penetration between internal struts")
    print("=" * 50)
    print("\nSummary:")
    print("  - Bottom: Tie constraint (Constraint-3) - fully bonded")
    print("  - Top: Tie constraint (Constraint-4) - fully bonded")
    print("  - Internal: General Contact - prevents strut penetration")
    print("  - Both top and bottom are tied (no separation)")
    print("  - Internal struts can contact but not penetrate")
    print("=" * 50)

Macro2()

mdb.models['Model-1'].fieldOutputRequests['F-Output-1'].setValues(frequency=3)



