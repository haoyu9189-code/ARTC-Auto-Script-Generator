# -*- coding: utf-8 -*-
"""
Abaqus动态仿真模型模板
用于生成晶格结构的动态冲击仿真脚本

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
        name='Inertia-1', region=region, mass=1.0e-06, alpha=0.0,
        composite=0.0)

    a = mdb.models['Model-1'].rootAssembly
    a.regenerate()

    # === 分析步设置（与Static_model.py保持一致） ===
    # 优化参数专门针对接触密集型结构（如Auxetic）
    mdb.models['Model-1'].StaticStep(
        name='Step-1',
        previous='Initial',
        initialInc=0.005,        # 降低初始增量，更平缓启动
        minInc=1e-06,            # 降低最小增量，允许更精细步长
        maxInc=0.5,              # 降低最大增量，避免接触时步长过大
        maxNumInc=2000,          # 增加最大步数，应对接触密集场景
        nlgeom=ON,
        stabilizationMethod=DISSIPATED_ENERGY_FRACTION,
        stabilizationMagnitude=0.0005,  # 降低阻尼，减少人工耗散
        continueDampingFactors=False,
        adaptiveDampingRatio=0.05
    )

    # === 定义反射点集 ===
    # 自动选择Y最大面上X、Z都最大的顶点
    v1 = a.instances['MergedStructure-1'].vertices
    max_y = -999999.0

    # 第一步：找到最大Y坐标
    for v in v1:
        coord = v.pointOn[0]
        if coord[1] > max_y:
            max_y = coord[1]

    # 第二步：筛选Y坐标接近最大值的所有顶点（容差0.01）
    top_verts = []
    for v in v1:
        coord = v.pointOn[0]
        if abs(coord[1] - max_y) < 0.01:
            top_verts.append(v)

    # 第三步：在这些顶点中找到X和Z都最大的
    if top_verts:
        max_x = max([v.pointOn[0][0] for v in top_verts])
        max_z = max([v.pointOn[0][2] for v in top_verts])

        # 找到同时满足X和Z最大的顶点（容差0.01）
        target_vert = None
        for v in top_verts:
            coord = v.pointOn[0]
            if abs(coord[0] - max_x) < 0.01 and abs(coord[2] - max_z) < 0.01:
                target_vert = v
                break

        if target_vert:
            # 使用findAt通过坐标重新获取vertex（返回Abaqus序列对象）
            coord = target_vert.pointOn[0]
            verts1 = v1.findAt((coord,))
            a.Set(vertices=(verts1,), name='Reflection')
            print("Selected Reflection vertex at: (%f, %f, %f)" % coord)
        else:
            # 兜底：选择第一个顶部顶点
            coord = top_verts[0].pointOn[0]
            verts1 = v1.findAt((coord,))
            a.Set(vertices=(verts1,), name='Reflection')
            print("Fallback: Selected first top vertex at: (%f, %f, %f)" % coord)
    else:
        raise ValueError("Cannot find top vertices in MergedStructure-1")

    # BotReflection
    r1 = a.instances['RigidPlate-1'].referencePoints
    refPoints1 = (r1[3], )
    a.Set(referencePoints=refPoints1, name='BotReflection')

    # TopReflection
    r1 = a.instances['RigidPlate-2'].referencePoints
    refPoints1 = (r1[3], )
    a.Set(referencePoints=refPoints1, name='TopReflection')

    # === 输出请求 (简化版) ===
    # Reflection: 结构位移 (U1用于剪切, U2用于压缩)
    regionDef = a.sets['Reflection']
    mdb.models['Model-1'].HistoryOutputRequest(name='H-Output-2',
        createStepName='Step-1', variables=('U1', 'U2'),
        region=regionDef, sectionPoints=DEFAULT, rebar=EXCLUDE)

    # BotReflection: 底板反力 (RF1用于剪切, RF2用于压缩)
    regionDef = a.sets['BotReflection']
    mdb.models['Model-1'].HistoryOutputRequest(name='H-Output-3',
        createStepName='Step-1', variables=('RF1', 'RF2'),
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
    # 针对Auxetic结构：使用TABULAR软化接触
    # 关键：定义压力-间隙曲线，允许控制的穿透，避免过约束
    mdb.models['Model-1'].interactionProperties['IntProp-1'].NormalBehavior(
        pressureOverclosure=TABULAR,
        table=((0.0, 0.0), (10.0, 1.0), (30.0, 3.0), (50.0, 5.0)),  # (压力MPa, 穿透mm)
        allowSeparation=ON,
        constraintEnforcementMethod=DEFAULT)

    # === 接触对 ===
    s1 = a.instances['RigidPlate-2'].faces
    side1Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
    region1 = a.Surface(side1Faces=side1Faces1, name='m_Surf-1')

    s1 = a.instances['MergedStructure-1'].faces
    side1Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
    region2 = a.Surface(side1Faces=side1Faces1, name='s_Surf-1')
    mdb.models['Model-1'].SurfaceToSurfaceContactStd(name='Int-1',
        createStepName='Step-1', main=region1, secondary=region2,
        sliding=FINITE, thickness=ON, interactionProperty='IntProp-1',
        adjustMethod=NONE, initialClearance=OMIT, datumAxis=None,
        clearanceRegion=None)

    s1 = a.instances['RigidPlate-1'].faces
    side1Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
    region1 = a.Surface(side1Faces=side1Faces1, name='m_Surf-3')

    s1 = a.instances['MergedStructure-1'].faces
    side1Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
    region2 = a.Surface(side1Faces=side1Faces1, name='s_Surf-3')
    mdb.models['Model-1'].SurfaceToSurfaceContactStd(name='Int-2', 
        createStepName='Step-1', main=region1, secondary=region2, 
        sliding=FINITE, thickness=ON, interactionProperty='IntProp-1', 
        adjustMethod=NONE, initialClearance=OMIT, datumAxis=None, 
        clearanceRegion=None)
    
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

    # === 约束条件 ===
    f1 = a.instances['RigidPlate-1'].faces
    faces1 = f1.getSequenceFromMask(mask=('[#1 ]', ), )
    region = a.Set(faces=faces1, name='Set-8')
    mdb.models['Model-1'].EncastreBC(name='BC-1', createStepName='Step-1', 
        region=region, localCsys=None)

    region = a.sets['TopReflection']
    mdb.models['Model-1'].DisplacementBC(name='BC-2', createStepName='Step-1', 
        region=region, u1=0.0, u2=-0.5, u3=0.0, ur1=0.0, ur2=0.0, ur3=0.0, 
        amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='', 
        localCsys=None)
    mdb.models['Model-1'].TabularAmplitude(name='Amp-1', timeSpan=STEP, 
        smooth=SOLVER_DEFAULT, data=((0.0, 0.0), (0.6, 1.0)))
    mdb.models['Model-1'].boundaryConditions['BC-2'].setValuesInStep(
        stepName='Step-1', amplitude='Amp-1')


    a = mdb.models['Model-1'].rootAssembly
    session.viewports['Viewport: 1'].setValues(displayedObject=a)
    session.viewports['Viewport: 1'].assemblyDisplay.setValues(loads=ON, bcs=ON, 
        predefinedFields=ON, connectors=ON, optimizationTasks=OFF, 
        geometricRestrictions=OFF, stopConditions=OFF)
    mdb.models['Model-1'].boundaryConditions['BC-2'].suppress()
    del mdb.models['Model-1'].boundaryConditions['BC-2']
    mdb.models['Model-1'].boundaryConditions['BC-1'].move('Step-1', 'Initial')
    a = mdb.models['Model-1'].rootAssembly
    r1 = a.instances['RigidPlate-2'].referencePoints
    refPoints1=(r1[3], )
    region = a.Set(referencePoints=refPoints1, name='Set-7')
    mdb.models['Model-1'].DisplacementBC(name='BC-2', createStepName='Initial',
        region=region, u1=SET, u2=UNSET, u3=SET, ur1=SET, ur2=SET, ur3=SET,
        amplitude=UNSET, distributionType=UNIFORM, fieldName='',
        localCsys=None)
    session.viewports['Viewport: 1'].assemblyDisplay.setValues(step='Step-1')
    # COMPRESSION_MODE_PLACEHOLDER: u2=-0.5
    mdb.models['Model-1'].boundaryConditions['BC-2'].setValuesInStep(
        stepName='Step-1', u2=-0.5, amplitude='Amp-1')
    
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
    elemType1 = mesh.ElemType(elemCode=C3D20R)
    elemType2 = mesh.ElemType(elemCode=C3D15)
    elemType3 = mesh.ElemType(elemCode=C3D10)
    cells = c.getSequenceFromMask(mask=('[#1 ]', ), )
    pickedRegions = (cells, )
    p.setElementType(regions=pickedRegions, elemTypes=(elemType1, elemType2, elemType3))
    # 网格大小根据cell_size和radius动态调整（平方根关系）
    # 平方根关系：细杆网格不过密，粗杆网格不过稀
    # 动态模型网格比静态大1.5倍（减少计算量）
    # radius=0.3→0.26, 0.35→0.28, 0.4→0.30, 0.45→0.31, 0.5→0.33
    import math
    mesh_size_structure = 0.22 * 1.5 * math.sqrt(radius / 0.5) * (cell_size / 5.0)  # 结构网格
    mesh_size_plate = 0.5 * 1.5 * (radius / 0.5) * (cell_size / 5.0)      # 刚板网格
    p.seedPart(size=mesh_size_structure, deviationFactor=0.1, minSizeFactor=0.1)

    p = mdb.models['Model-1'].parts['MergedStructure']
    p.generateMesh()
    p = mdb.models['Model-1'].parts['RigidPlate']
    p.seedPart(size=mesh_size_plate, deviationFactor=0.1, minSizeFactor=0.1)
    p.generateMesh()

    # # ============================================================
    # # 周期性边界条件 (Periodic Boundary Conditions) - X和Z方向
    # # 纯周期性: 模拟无限周期阵列,对面节点位移相等
    # # ============================================================
    # print("\n========== Creating Pure Periodic Boundary Conditions (X and Z directions) ==========")

    # # 识别X和Z方向边界上的节点
    # print("\nIdentifying boundary nodes...")
    # tolerance = 0.01
    # half_size = cell_size / 2.0

    # # 获取合并结构的实例
    # instance = a.instances['MergedStructure-1']

    # # 存储边界节点
    # xplus_nodes = []   # X = +2.5
    # xminus_nodes = []  # X = -2.5
    # zplus_nodes = []   # Z = +2.5
    # zminus_nodes = []  # Z = -2.5

    # # 遍历所有节点，识别边界节点
    # for node in instance.nodes:
    #     x, y, z = node.coordinates

    #     # X方向边界
    #     if abs(x - half_size) < tolerance:
    #         xplus_nodes.append((node.label, y, z))
    #     elif abs(x + half_size) < tolerance:
    #         xminus_nodes.append((node.label, y, z))

    #     # Z方向边界
    #     if abs(z - half_size) < tolerance:
    #         zplus_nodes.append((node.label, x, y))
    #     elif abs(z + half_size) < tolerance:
    #         zminus_nodes.append((node.label, x, y))

    # print("Boundary nodes found:")
    # print("  X+ face: %d nodes" % len(xplus_nodes))
    # print("  X- face: %d nodes" % len(xminus_nodes))
    # print("  Z+ face: %d nodes" % len(zplus_nodes))
    # print("  Z- face: %d nodes" % len(zminus_nodes))

    # # 3. 建立X方向的纯周期性边界条件方程
    # print("\nCreating X-direction pure PBC equations...")
    # equation_count = 0

    # # X方向纯周期性: U1(X+) = U1(X-) => U1(X+) - U1(X-) = 0
    # # 匹配Y和Z坐标相同的节点对
    # for label_plus, y_plus, z_plus in xplus_nodes:
    #     # 寻找对应的X-面节点（Y和Z坐标匹配）
    #     for label_minus, y_minus, z_minus in xminus_nodes:
    #         if (abs(y_plus - y_minus) < tolerance and
    #             abs(z_plus - z_minus) < tolerance):

    #             # 只对X方向位移(U1)建立周期性约束
    #             equation_name = 'PBC-X-U1-%d' % equation_count
    #             mdb.models['Model-1'].Equation(
    #                 name=equation_name,
    #                 terms=(
    #                     (1.0, 'MergedStructure-1.%d' % label_plus, 1),    # U1(X+)
    #                     (-1.0, 'MergedStructure-1.%d' % label_minus, 1)   # -U1(X-)
    #                 )
    #             )
    #             equation_count += 1
    #             break  # 找到匹配节点后跳出内层循环

    # print("X-direction PBC: %d node pairs, %d equations created" % (equation_count, equation_count))

    # # 4. 建立Z方向的纯周期性边界条件方程
    # print("\nCreating Z-direction pure PBC equations...")
    # equation_count_z = 0

    # # Z方向纯周期性: U3(Z+) = U3(Z-) => U3(Z+) - U3(Z-) = 0
    # # 匹配X和Y坐标相同的节点对
    # for label_plus, x_plus, y_plus in zplus_nodes:
    #     # 寻找对应的Z-面节点（X和Y坐标匹配）
    #     for label_minus, x_minus, y_minus in zminus_nodes:
    #         if (abs(x_plus - x_minus) < tolerance and
    #             abs(y_plus - y_minus) < tolerance):

    #             # 只对Z方向位移(U3)建立周期性约束
    #             equation_name = 'PBC-Z-U3-%d' % equation_count_z
    #             mdb.models['Model-1'].Equation(
    #                 name=equation_name,
    #                 terms=(
    #                     (1.0, 'MergedStructure-1.%d' % label_plus, 3),    # U3(Z+)
    #                     (-1.0, 'MergedStructure-1.%d' % label_minus, 3)   # -U3(Z-)
    #                 )
    #             )
    #             equation_count_z += 1
    #             break  # 找到匹配节点后跳出内层循环

    # print("Z-direction PBC: %d node pairs, %d equations created" % (equation_count_z, equation_count_z))

    # print("\nPure PBC setup completed successfully!")
    # print("=" * 70)
    # print("Summary:")
    # print("  - X-direction: %d node pairs with U1 periodic constraints (pure periodic)" % equation_count)
    # print("  - Z-direction: %d node pairs with U3 periodic constraints (pure periodic)" % equation_count_z)
    # print("  - Y-direction: Tie constraints control U2 (compression loading)")
    # print("  - Total equations: %d" % (equation_count + equation_count_z))
    # print("  - Simulating infinite periodic array")
    # print("=" * 70)

Macro1()

def Macro2():
    # === Model Setup and Step Definition ===
    a = mdb.models['Model-1'].rootAssembly
    a.regenerate()

    # Delete existing interactions (if any)
    del mdb.models['Model-1'].interactions['Int-1']
    del mdb.models['Model-1'].interactions['Int-2']

    # Delete existing step and create new explicit dynamics step
    del mdb.models['Model-1'].steps['Step-1']
    mdb.models['Model-1'].ExplicitDynamicsStep(
        name='Step-1',
        previous='Initial',
        timePeriod=0.01,  # Total time period: 0.01 seconds
        improvedDtMethod=ON
    )

    # === 重新创建 History Output Requests (因为 Step-1 被重建) ===
    a = mdb.models['Model-1'].rootAssembly

    # Reflection: 结构位移 (U1用于剪切, U2用于压缩)
    regionDef = a.sets['Reflection']
    mdb.models['Model-1'].HistoryOutputRequest(name='H-Output-2',
        createStepName='Step-1', variables=('U1', 'U2'),
        region=regionDef, sectionPoints=DEFAULT, rebar=EXCLUDE)

    # BotReflection: 底板反力 (RF1用于剪切, RF2用于压缩)
    regionDef = a.sets['BotReflection']
    mdb.models['Model-1'].HistoryOutputRequest(name='H-Output-3',
        createStepName='Step-1', variables=('RF1', 'RF2'),
        region=regionDef, sectionPoints=DEFAULT, rebar=EXCLUDE)

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
            if (abs(normal[0]) < 0.01 and
                abs(normal[1] + 1.0) < 0.01 and
                abs(normal[2]) < 0.01):
                bottom_face_objects.append(face)
        except:
            pass

    print("找到 %d 个底面，将自动Tie到底部刚性板" % len(bottom_face_objects))

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
        print("SUCCESS: 底面Tie约束已创建 (Constraint-3)")
    else:
        print("WARNING: No bottom faces detected, Constraint-3 not created")
        # Fallback to original hardcoded mask
        s1 = a.instances['RigidPlate-1'].faces
        side2Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
        region1 = regionToolset.Region(side2Faces=side2Faces1)

        s1 = a.instances['MergedStructure-1'].faces
        side1Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
        region2 = regionToolset.Region(side1Faces=side1Faces1)

        mdb.models['Model-1'].Tie(
            name='Constraint-3',
            main=region1,
            secondary=region2,
            positionToleranceMethod=COMPUTED,
            adjust=ON,
            tieRotations=ON,
            thickness=ON
        )

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

    print("找到 %d 个顶面，将自动Tie到顶部刚性板" % len(top_face_objects))

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
        print("SUCCESS: 顶面Tie约束已创建 (Constraint-4)")
    else:
        print("WARNING: No top faces detected, Constraint-4 not created")

    print("=" * 50)
    print("\nSummary:")
    print("  - Bottom: Tie constraint (Constraint-3) - fully bonded")
    print("  - Top: Tie constraint (Constraint-4) - fully bonded")
    print("  - Internal: General Contact (ContactExp) - prevents strut penetration")
    print("  - Both top and bottom are tied (no separation)")
    print("=" * 50)

    # === Contact Interactions Definition ===
    # 使用通用接触来自动处理大变形时的所有接触,避免穿透
    mdb.models['Model-1'].ContactExp(name='GeneralContact', createStepName='Initial')
    mdb.models['Model-1'].interactions['GeneralContact'].includedPairs.setValuesInStep(
        stepName='Initial', useAllstar=ON)
    mdb.models['Model-1'].interactions['GeneralContact'].contactPropertyAssignments.appendInStep(
        stepName='Initial',
        assignments=((GLOBAL, SELF, 'IntProp-1'), ))

    # 原有的面对面接触定义已注释,使用通用接触替代
    # # Contact Int-1
    # s1 = a.instances['RigidPlate-2'].faces
    # side1Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
    # region1 = regionToolset.Region(side1Faces=side1Faces1)

    # s1 = a.instances['MergedStructure-1'].faces
    # side1Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
    # region2 = regionToolset.Region(side1Faces=side1Faces1)

    # mdb.models['Model-1'].SurfaceToSurfaceContactExp(
    #     name='Int-1',
    #     createStepName='Initial',
    #     main=region1,
    #     secondary=region2,
    #     mechanicalConstraint=PENALTY,
    #     sliding=FINITE,
    #     interactionProperty='IntProp-1',
    #     initialClearance=OMIT,
    #     datumAxis=None,
    #     clearanceRegion=None
    # )

    # # Contact Int-2
    # s1 = a.instances['MergedStructure-1'].faces
    # side1Faces1 = s1.getSequenceFromMask(mask=('[#1000 ]', ), )
    # region2 = regionToolset.Region(side1Faces=side1Faces1)

    # mdb.models['Model-1'].SurfaceToSurfaceContactExp(
    #     name='Int-2',
    #     createStepName='Initial',
    #     main=region1,  # Same RigidPlate-2 face as before
    #     secondary=region2,
    #     mechanicalConstraint=PENALTY,
    #     sliding=FINITE,
    #     interactionProperty='IntProp-1',
    #     initialClearance=OMIT,
    #     datumAxis=None,
    #     clearanceRegion=None
    # )

    # # Contact Int-3
    # s1 = a.instances['MergedStructure-1'].faces
    # side1Faces1 = s1.getSequenceFromMask(mask=('[#1000 ]', ), )
    # # 2000000
    # region2 = regionToolset.Region(side1Faces=side1Faces1)

    # mdb.models['Model-1'].SurfaceToSurfaceContactExp(
    #     name='Int-3',
    #     createStepName='Initial',
    #     main=region1,  # Same RigidPlate-2 face
    #     secondary=region2,
    #     mechanicalConstraint=PENALTY,
    #     sliding=FINITE,
    #     interactionProperty='IntProp-1',
    #     initialClearance=OMIT,
    #     datumAxis=None,
    #     clearanceRegion=None
    # )

    # # Contact Int-4
    # s1 = a.instances['MergedStructure-1'].faces
    # side1Faces1 = s1.getSequenceFromMask(mask=('[#1000 ]', ), )

    # # 80000
    # region2 = regionToolset.Region(side1Faces=side1Faces1)

    # mdb.models['Model-1'].SurfaceToSurfaceContactExp(
    #     name='Int-4',
    #     createStepName='Initial',
    #     main=region1,  # Same RigidPlate-2 face
    #     secondary=region2,
    #     mechanicalConstraint=PENALTY,
    #     sliding=FINITE,
    #     interactionProperty='IntProp-1',
    #     initialClearance=OMIT,
    #     datumAxis=None,
    #     clearanceRegion=None
    # )

    # === Boundary Conditions ===
    # Update BC-1: Fix RigidPlate-1 reference point
    r1 = a.instances['RigidPlate-1'].referencePoints
    refPoints1 = (r1[3], )
    region = regionToolset.Region(referencePoints=refPoints1)
    mdb.models['Model-1'].boundaryConditions['BC-1'].setValues(region=region)

    # Update BC-2: Fix U2 in Initial step
    mdb.models['Model-1'].boundaryConditions['BC-2'].setValues(u2=SET)

    # Free U2 in Step-1
    mdb.models['Model-1'].boundaryConditions['BC-2'].setValuesInStep(
        stepName='Step-1',
        u2=FREED
    )

    # === Predefined Field: Initial Velocity ===
    # Apply initial velocity to RigidPlate-2
    r1 = a.instances['RigidPlate-2'].referencePoints
    refPoints1 = (r1[3], )
    region = regionToolset.Region(referencePoints=refPoints1)

    mdb.models['Model-1'].Velocity(
        name='Predefined Field-1',
        region=region,
        field='',
        distributionType=MAGNITUDE,
        velocity1=0.0,  # Velocity in X direction (for Shear mode)
        velocity2=-1000.0,  # Velocity in Y direction: -1000.0 mm/s (Auto mode default, for Compression)
        omega=0.0
    )

    # === Mesh Settings ===
    # Set element type for MergedStructure
    p = mdb.models['Model-1'].parts['MergedStructure']
    elemType1 = mesh.ElemType(elemCode=UNKNOWN_HEX, elemLibrary=EXPLICIT)
    elemType2 = mesh.ElemType(elemCode=UNKNOWN_WEDGE, elemLibrary=EXPLICIT)
    elemType3 = mesh.ElemType(
        elemCode=C3D10M,
        elemLibrary=EXPLICIT,
        secondOrderAccuracy=OFF,
        distortionControl=DEFAULT
    )

    c = p.cells
    cells = c.getSequenceFromMask(mask=('[#1 ]', ), )
    pickedRegions = (cells, )
    p.setElementType(regions=pickedRegions, elemTypes=(elemType1, elemType2, elemType3))

    # Delete section assignment for RigidPlate (making it rigid)
    p = mdb.models['Model-1'].parts['RigidPlate']
    del mdb.models['Model-1'].parts['RigidPlate'].sectionAssignments[0]

    # Regenerate assembly after modifications
    a1 = mdb.models['Model-1'].rootAssembly
    a1.regenerate()

    # History Output Requests 已在 Macro2() 中 Step-1 重建后重新创建



Macro2()
# 注释掉Int-5创建,因为已使用通用接触替代
# mdb.models['Model-1'].Interaction(name='Int-5',
#     objectToCopy=mdb.models['Model-1'].interactions['Int-4'],
#     toStepName='Initial')

# Macro2已移除: Constraint-3现在在初始化时一步到位创建，无需后续更新

# mdb.models['Model-1'].fieldOutputRequests['F-Output-1'].setValues(frequency=3)

# 解放自由度 改变方向增加tie约束改变int的  Penalty

