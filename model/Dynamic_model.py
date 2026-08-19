# -*- coding: utf-8 -*-
"""
Abaqus动态冲击仿真模型模板
用于生成晶格结构的动态压缩/剪切仿真脚本 (Explicit)

参数与 Static_model.py / array 路径保持一致:
  - sphere_radius = radius * 1.2 (SLM节点修正)
  - mass scaling dt = 5e-06
  - linearBulkViscosity = 0.25, quadBulkViscosity = 2.0 (NS3; tried defaults — no benefit)
  - contactStiffnessScaleFactor = 5.0 (HARD, locked across N for trend consistency)
  - C3D10M + distortionControl=ON, lengthRatio=0.1
  - mesh_size = 0.3 * sqrt(radius/0.5) * (cell_size/5)
  - Ductile damage + element deletion (INP patch)

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

sphere_radius = radius * 1.2  # 由 script_generator._generate_script_content 按 Config.SPHERE_RADIUS_RATIO_SCRIPT 重写

for j, (node_name, node_coord) in enumerate(all_node_coords):
    sketch_name = 'sphereSketch-%02d' % (j+1)
    s_sphere = model.ConstrainedSketch(name=sketch_name, sheetSize=20.0)

    s_sphere.ConstructionLine(point1=(0.0, -sphere_radius*2), point2=(0.0, sphere_radius*2))
    s_sphere.ArcByCenterEnds(center=(0.0, 0.0), point1=(0.0, sphere_radius),
                             point2=(0.0, -sphere_radius), direction=CLOCKWISE)
    s_sphere.Line(point1=(0.0, sphere_radius), point2=(0.0, -sphere_radius))

    sphere_part_name = 'Sphere-%02d' % (j+1)
    sphere_part = model.Part(name=sphere_part_name, dimensionality=THREE_D, type=DEFORMABLE_BODY)
    sphere_part.BaseSolidRevolve(sketch=s_sphere, angle=360.0, flipRevolveDirection=OFF)

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

s1.rectangle(point1=(-2.5, -2.5), point2=(2.5, 2.5))
s1.rectangle(point1=(-5.0, -5.0), point2=(5.0, 5.0))

p.CutExtrude(sketchPlane=p.datums[datum_top_id],
            sketchUpEdge=p.datums[up_edge_id],
            sketchPlaneSide=SIDE1,
            sketchOrientation=RIGHT,
            sketch=s1,
            depth=6,
            flipExtrudeDirection=OFF)

s1.unsetPrimaryObject()
del model.sketches['cutTopSketch']

# 创建侧面切割平面 (Y = +2.5位置)
datum_side = p.DatumPlaneByPrincipalPlane(principalPlane=XZPLANE, offset=3)
datum_side_id = datum_side.id

datum_axis2 = p.DatumAxisByPrincipalAxis(principalAxis=XAXIS)
side_edge_id = datum_axis2.id

t2 = p.MakeSketchTransform(sketchPlane=p.datums[datum_side_id],
                          sketchUpEdge=p.datums[side_edge_id],
                          sketchPlaneSide=SIDE1,
                          sketchOrientation=RIGHT,
                          origin=(0.0, 2.5, 0.0))

s2 = model.ConstrainedSketch(name='cutSideSketch', sheetSize=20.0, transform=t2)
s2.setPrimaryObject(option=SUPERIMPOSE)
p.projectReferencesOntoSketch(sketch=s2, filter=COPLANAR_EDGES)

s2.rectangle(point1=(-2.5, -2.5), point2=(2.5, 2.5))
s2.rectangle(point1=(-5.0, -5.0), point2=(5.0, 5.0))

p.CutExtrude(sketchPlane=p.datums[datum_side_id],
            sketchUpEdge=p.datums[side_edge_id],
            sketchPlaneSide=SIDE1,
            sketchOrientation=RIGHT,
            sketch=s2,
            depth=6,
            flipExtrudeDirection=OFF)

s2.unsetPrimaryObject()
del model.sketches['cutSideSketch']

# 创建刚性板
s3 = model.ConstrainedSketch(name='rigidPlateSketch', sheetSize=20.0)
s3.setPrimaryObject(option=STANDALONE)
s3.Line(point1=(-4.0, 0.0), point2=(4.0, 0.0))
s3.HorizontalConstraint(entity=s3.geometry[2], addUndoState=False)

rigid_part = model.Part(name='RigidPlate',
                       dimensionality=THREE_D,
                       type=DISCRETE_RIGID_SURFACE)

rigid_part.BaseShellExtrude(sketch=s3, depth=8.0)
s3.unsetPrimaryObject()
del model.sketches['rigidPlateSketch']

# 创建刚性板实例
assembly.DatumCsysByDefault(CARTESIAN)
assembly.Instance(name='RigidPlate-1', part=rigid_part, dependent=ON)
assembly.translate(instanceList=('RigidPlate-1',), vector=(0.0, -2.5, -4.0))

assembly.Instance(name='RigidPlate-2', part=rigid_part, dependent=ON)
assembly.translate(instanceList=('RigidPlate-2',), vector=(0.0, 2.5, -4.0))

# ----------------------------------------------------------------
# MATERIAL CARD — NS3 plastic + 校准 E
#   E = 1010 (NS3 ×0.65 — 校准实验 compliance / 延长弹性段)
#   σ_y0=33.97, σ_ult=56.80 (NS3 unchanged)
#   Magnitude 修正在后处理：×0.6 (Auxetic) / ×0.4 (BCC) at lattice frame
# Keep IN SYNC with: model/Static_model.py, script_generator.py
# ----------------------------------------------------------------
material = model.Material(name='Material-1')
material.Density(table=((1.01e-09,),))
material.Elastic(table=((1010, 0.3),))
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

# 延性损伤 — NS3 原值（避免 Auxetic 峰后假塌陷）
material.DuctileDamageInitiation(table=(
    (0.60, -0.333, 0.033),
    (0.40,  0.0,   0.033),
    (0.25,  0.333, 0.033),
))
material.ductileDamageInitiation.DamageEvolution(type=DISPLACEMENT, table=((0.5,),))

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

assembly.regenerate()
print("Model creation completed successfully!")


# -*- coding: mbcs -*-
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

    # === Explicit 动态分析步 ===
    mdb.models['Model-1'].ExplicitDynamicsStep(
        name='Step-1',
        previous='Initial',
        timePeriod=0.01,
        massScaling=((SEMI_AUTOMATIC, MODEL, THROUGHOUT_STEP, 0.0, 5e-06, BELOW_MIN, 1, 0, 0.0, 0.0, 0, None), ),
        improvedDtMethod=ON,
        nlgeom=ON,
        linearBulkViscosity=0.25, quadBulkViscosity=2.0
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
    # NormalBehavior: HARD contact, scale=5.0 (locked across all N for cross-N trend consistency).
    mdb.models['Model-1'].interactionProperties['IntProp-1'].NormalBehavior(
        pressureOverclosure=HARD, allowSeparation=ON,
        contactStiffnessScaleFactor=5.0)

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

    # === 边界条件 ===
    # 底板固定
    region = a.sets['BotReflection']
    mdb.models['Model-1'].EncastreBC(name='BC-1', createStepName='Initial',
        region=region, localCsys=None)

    # 顶板: 固定除Y方向外所有自由度 (Y方向由速度场控制)
    region = a.sets['TopReflection']
    mdb.models['Model-1'].DisplacementBC(name='BC-2', createStepName='Step-1',
        region=region, u1=0.0, u2=UNSET, u3=0.0, ur1=0.0, ur2=0.0, ur3=0.0,
        amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='',
        localCsys=None)

    # === 初始速度场 ===
    r1 = a.instances['RigidPlate-2'].referencePoints
    refPoints1 = (r1[3], )
    region = regionToolset.Region(referencePoints=refPoints1)
    mdb.models['Model-1'].Velocity(
        name='Predefined Field-1',
        region=region,
        field='',
        distributionType=MAGNITUDE,
        velocity1=0.0,
        velocity2=-1000.0,
        omega=0.0
    )

    # === 刚体约束更新 ===
    a = mdb.models['Model-1'].rootAssembly
    f1 = a.instances['RigidPlate-2'].faces
    faces1 = f1.getSequenceFromMask(mask=('[#1 ]', ), )
    region2=a.Set(faces=faces1, name='b_Set-8')
    r1 = a.instances['RigidPlate-2'].referencePoints
    refPoints1=(r1[3], )
    region1=regionToolset.Region(referencePoints=refPoints1)
    mdb.models['Model-1'].constraints['Constraint-1'].setValues(
        refPointRegion=region1, bodyRegion=region2)

    f1 = a.instances['RigidPlate-1'].faces
    faces1 = f1.getSequenceFromMask(mask=('[#1 ]', ), )
    region2=a.Set(faces=faces1, name='b_Set-9')
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
    # distortionControl=ON with lengthRatio=0.1: prevent element inversion
    elemType1 = mesh.ElemType(elemCode=C3D10M, elemLibrary=EXPLICIT,
        secondOrderAccuracy=OFF, distortionControl=ON, lengthRatio=0.1)
    elemType2 = mesh.ElemType(elemCode=C3D10M, elemLibrary=EXPLICIT,
        secondOrderAccuracy=OFF, distortionControl=ON, lengthRatio=0.1)
    elemType3 = mesh.ElemType(elemCode=C3D10M, elemLibrary=EXPLICIT,
        secondOrderAccuracy=OFF, distortionControl=ON, lengthRatio=0.1)
    cells = c.getSequenceFromMask(mask=('[#1 ]', ), )
    pickedRegions = (cells, )
    p.setElementType(regions=pickedRegions, elemTypes=(elemType1, elemType2, elemType3))

    import math
    mesh_size_structure = 0.3 * math.sqrt(radius / 0.5) * (cell_size / 5.0)  # 结构网格
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

print("Found %d bottom faces for Tie constraint" % len(bottom_face_objects))

if bottom_face_objects:
    s1 = a.instances['RigidPlate-1'].faces
    side2Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
    region1 = regionToolset.Region(side2Faces=side2Faces1)

    s1 = a.instances['MergedStructure-1'].faces
    found_faces = []
    for face in bottom_face_objects:
        face_center = face.pointOn[0]
        found_face = s1.findAt((face_center,))
        found_faces.append(found_face)
    region2 = a.Surface(side1Faces=tuple(found_faces), name='s_Surf-BottomTie')

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

print("=" * 50)

# === 自动识别顶面并创建Tie约束 (Constraint-4) ===
print("\n========== Creating Top Tie Constraint ==========")
a = mdb.models['Model-1'].rootAssembly
instance = a.instances['MergedStructure-1']
faces = instance.faces

top_face_objects = []
for face in faces:
    try:
        normal = face.getNormal()
        if (abs(normal[0]) < 0.01 and
            abs(normal[1] - 1.0) < 0.01 and
            abs(normal[2]) < 0.01):
            top_face_objects.append(face)
    except:
        pass

print("Found %d top faces for Tie constraint" % len(top_face_objects))

if top_face_objects:
    s1 = a.instances['RigidPlate-2'].faces
    side2Faces1 = s1.getSequenceFromMask(mask=('[#1 ]', ), )
    region1 = regionToolset.Region(side2Faces=side2Faces1)

    s1 = a.instances['MergedStructure-1'].faces
    found_faces = []
    for face in top_face_objects:
        face_center = face.pointOn[0]
        found_face = s1.findAt((face_center,))
        found_faces.append(found_face)
    region2 = a.Surface(side1Faces=tuple(found_faces), name='s_Surf-TopTie')

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

print("=" * 50)

# === General Contact ===
print("\n========== Creating General Contact ==========")

try:
    if 'Int-1' in mdb.models['Model-1'].interactions.keys():
        del mdb.models['Model-1'].interactions['Int-1']
except:
    pass
try:
    if 'Int-2' in mdb.models['Model-1'].interactions.keys():
        del mdb.models['Model-1'].interactions['Int-2']
except:
    pass

mdb.models['Model-1'].ContactExp(
    name='GeneralContact',
    createStepName='Initial'
)
mdb.models['Model-1'].interactions['GeneralContact'].includedPairs.setValuesInStep(
    stepName='Initial',
    useAllstar=ON
)
mdb.models['Model-1'].interactions['GeneralContact'].contactPropertyAssignments.appendInStep(
    stepName='Initial',
    assignments=((GLOBAL, SELF, 'IntProp-1'), )
)

print("SUCCESS: General Contact created")
print("=" * 50)

mdb.models['Model-1'].fieldOutputRequests['F-Output-1'].setValues(frequency=3)
