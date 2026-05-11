import maya.cmds as cmds

from darn_that_yarn.core.state import STATE
import maya.api.OpenMaya as om
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import maya.mel as mel
import math
import re

MESH_RELAXATION_ITERATIONS = 40
MESH_RELAXATION_STEP = 0.35
MESH_RELAXATION_MAX_OFFSET_FRACTION = 0.25
TESSELLATED_EDGE_CURVE_LIMIT = 450


def _node_basename(node_name):
    return (node_name or "").split("|")[-1].split(":")[-1]


def _derived_node_name(node_name, suffix):
    base = _node_basename(node_name)
    return f"{base}{suffix}" if base else suffix.lstrip("_")


def _mesh_dag_path(mesh):
    sel = om.MSelectionList()
    sel.add(mesh)
    dag_path = sel.getDagPath(0)
    if not dag_path.hasFn(om.MFn.kMesh):
        dag_path.extendToShape()
    return dag_path


def set_course_edges(selected_edges):
    """
    Placeholder for Rose's edge-labeling implementation.
    For now, just store selected edges as course edges.
    """
    if not selected_edges:
        cmds.warning("No edges selected.")
        return

    for edge in selected_edges:
        STATE.course_edges.add(edge)

    cmds.inViewMessage(
        amg=f"Set <hl>{len(selected_edges)}</hl> edge(s) as course edges.",
        pos="topCenter",
        fade=True
    )


def set_stitch_type(selected_faces, stitch_type):
    """
    Placeholder for Beta pattern customization.
    For now, assign the stitch type to selected faces.
    """
    if not selected_faces:
        cmds.warning("No faces selected.")
        return

    for face in selected_faces:
        STATE.face_stitch_types[face] = stitch_type
        STATE.active_faces.add(face)

    cmds.inViewMessage(
        amg=f"Assigned stitch type <hl>{stitch_type}</hl> to {len(selected_faces)} face(s).",
        pos="topCenter",
        fade=True
    )


def flip_row_direction(selected_faces):
    """
    Placeholder for row-based direction logic.
    For alpha GUI work, this proves the button wiring.
    """
    if not selected_faces:
        cmds.warning("No stitch faces selected.")
        return

    for face in selected_faces:
        current = STATE.row_directions.get(face, 1)
        STATE.row_directions[face] = -current

    cmds.inViewMessage(
        amg=f"Flipped direction for {len(selected_faces)} selected face(s).",
        pos="topCenter",
        fade=True
    )


def get_edge_midpoint(dag_path, edge_index):
    mesh_fn = om.MFnMesh(dag_path)
    edge_it = om.MItMeshEdge(dag_path)
    
    edge_it.setIndex(edge_index)
    vtx_ids = edge_it.vertexId(0), edge_it.vertexId(1)
    
    p1 = mesh_fn.getPoint(vtx_ids[0], om.MSpace.kWorld)
    p2 = mesh_fn.getPoint(vtx_ids[1], om.MSpace.kWorld)
    
    # FIX: manually compute midpoint
    mid = om.MPoint(
        (p1.x + p2.x) * 0.5,
        (p1.y + p2.y) * 0.5,
        (p1.z + p2.z) * 0.5
    )
    
    return mid

def checkAligned(dag_pathA, edge_indexA, dag_pathB, edge_indexB):
    mesh_fnA = om.MFnMesh(dag_pathA)
    edge_itA = om.MItMeshEdge(dag_pathA)
    
    edge_itA.setIndex(edge_indexA)
    vtx_idsB = edge_itA.vertexId(0), edge_itA.vertexId(1)
    
    p1A = mesh_fnA.getPoint(vtx_idsB[0], om.MSpace.kWorld)
    p2A = mesh_fnA.getPoint(vtx_idsB[1], om.MSpace.kWorld)

    mesh_fnB = om.MFnMesh(dag_pathB)
    edge_itB = om.MItMeshEdge(dag_pathB)
    
    edge_itB.setIndex(edge_indexB)
    vtx_idsB = edge_itB.vertexId(0), edge_itB.vertexId(1)
    
    p1B = mesh_fnB.getPoint(vtx_idsB[0], om.MSpace.kWorld)
    p2B = mesh_fnB.getPoint(vtx_idsB[1], om.MSpace.kWorld)

    dirA = p2A - p1A
    dirB = p2B - p1B
    tol = 0.01
    # --- 1. Parallel check ---
    if (dirA ^ dirB).length() > tol:
        return False

    # --- 2. Collinearity check ---
    dirA1toB2 = p2B - p1A
    dirB1toA2 = p2A - p1B
    if (dirA1toB2 ^ dirA).length() > tol:
        return False
    if (dirB1toA2 ^ dirA).length() > tol:
        return False

    dirA_norm = dirA.normal()
    dirAB_norm = dirA1toB2.normal()
    if (dirA_norm - dirAB_norm).length() > tol:
        return False
    # if(dirA_norm != dirAB_norm):
    #     return False

    return True


def _edge_records(dag_path):
    mesh_fn = om.MFnMesh(dag_path)
    points = mesh_fn.getPoints(om.MSpace.kWorld)
    edge_it = om.MItMeshEdge(dag_path)
    records = []

    while not edge_it.isDone():
        edge_index = edge_it.index()
        v0 = edge_it.vertexId(0)
        v1 = edge_it.vertexId(1)
        p0 = points[v0]
        p1 = points[v1]
        direction = om.MVector(p1 - p0)
        length = direction.length()
        if length > 1e-8:
            records.append((
                edge_index,
                v0,
                v1,
                om.MPoint(
                    (p0.x + p1.x) * 0.5,
                    (p0.y + p1.y) * 0.5,
                    (p0.z + p1.z) * 0.5,
                ),
                direction / length,
                length,
            ))
        edge_it.next()

    return records


def _edges_are_aligned(mid_a, dir_a, mid_b, dir_b, tol=0.01):
    if (dir_a ^ dir_b).length() > tol:
        return False
    return ((mid_b - mid_a) ^ dir_a).length() <= tol

def spreadEdgeAssignment():
    
    # Get all edges marked as 'course'
    course_edges = [e for e, t in STATE.t_edge_map.items() if t == EdgeType.COURSE]
    if not course_edges:
        cmds.warning("No 'course' edges in the map.")
        return

    preview_sel = om.MSelectionList()
    preview_sel.add(STATE.preview_mesh)
    dagPath = preview_sel.getDagPath(0)
    edge_iter = om.MItMeshEdge(dagPath)

    while (course_edges):
        connected_vertices = set()
        connected_faces = set()

        #SET PERP EDGES TO WALE
        for edge_id in course_edges:
            edge_iter.setIndex(edge_id)
            v0 = edge_iter.vertexId(0)
            v1 = edge_iter.vertexId(1)

            connected_vertices.add(v0)
            connected_vertices.add(v1)

            # faces
            faces = edge_iter.getConnectedFaces()
            for f in faces:
                connected_faces.add(f)
        
        vert_iter = om.MItMeshVertex(dagPath)
        unnassignedFound = False
        for v in connected_vertices:
            vert_iter.setIndex(v)
            connected_edges = vert_iter.getConnectedEdges()
            
            for e in connected_edges:
                if STATE.t_edge_map[e] ==  EdgeType.UNASSIGNED:
                    STATE.t_edge_map[e] = EdgeType.WALE
                    unnassignedFound = True
        if unnassignedFound == False:
            return

        #CLOSE FACES BY SETTING LAST EDGE TO COURSE
        # empty course edges so you can add newly assigned course edges here
        course_edges = []

        poly_iter = om.MItMeshPolygon(dagPath)
        for face_id in connected_faces:
            poly_iter.setIndex(face_id)

            edge_ids = poly_iter.getEdges()
            numAssignedEdges = 0
            unassignedEdgeId = -1
            for e_id in edge_ids:
                edge_type = STATE.t_edge_map.get(e_id)
                if edge_type != EdgeType.UNASSIGNED:
                    numAssignedEdges = numAssignedEdges + 1
                else:
                    unassignedEdgeId = e_id
            if numAssignedEdges == 3 and unassignedEdgeId != -1:
                STATE.t_edge_map[unassignedEdgeId] = EdgeType.COURSE
                course_edges.append(unassignedEdgeId)
        
    


def _assign_tslt_edges_from_base():
    if not STATE.preview_mesh or not STATE.base_mesh:
        return

    dag_a = _mesh_dag_path(STATE.preview_mesh)
    dag_b = _mesh_dag_path(STATE.base_mesh)

    preview_edges = _edge_records(dag_a)
    base_edges = [
        record
        for record in _edge_records(dag_b)
        if STATE.edge_map.get(record[0], EdgeType.UNASSIGNED) != EdgeType.UNASSIGNED
    ]
    if not base_edges:
        return

    for edge_a_index, _v0, _v1, mid_a, dir_a, _length_a in preview_edges:
        closest_edge = None
        min_dist = float("inf")

        for edge_b_index, _bv0, _bv1, mid_b, dir_b, _length_b in base_edges:
            if not _edges_are_aligned(mid_a, dir_a, mid_b, dir_b):
                continue
            dist = (mid_a - mid_b).length()
            if dist < min_dist:
                min_dist = dist
                closest_edge = edge_b_index

        if closest_edge is not None:
            STATE.t_edge_map[edge_a_index] = STATE.edge_map[closest_edge]

def _color_preview_mesh_from_base():
    """
    Colors the tessellated preview mesh by projecting each preview face centroid
    onto the base mesh to inherit the original face's stitch type color.
    """
    if not STATE.preview_mesh or not cmds.objExists(STATE.preview_mesh):
        return
    if not STATE.base_mesh or not cmds.objExists(STATE.base_mesh):
        return
    if not STATE.face_stitch_map:
        return

    # Build dag paths directly — avoids triggering SelectionChanged script jobs.
    preview_sel = om.MSelectionList()
    preview_sel.add(STATE.preview_mesh)
    preview_dag = preview_sel.getDagPath(0)
    if not preview_dag.hasFn(om.MFn.kMesh):
        preview_dag.extendToShape()

    base_sel = om.MSelectionList()
    base_sel.add(STATE.base_mesh)
    base_dag = base_sel.getDagPath(0)
    if not base_dag.hasFn(om.MFn.kMesh):
        base_dag.extendToShape()

    preview_fn = om.MFnMesh(preview_dag)
    base_fn = om.MFnMesh(base_dag)

    face_iter = om.MItMeshPolygon(preview_dag)
    colors = []
    face_ids = []
    vert_ids = []

    while not face_iter.isDone():
        face_id = face_iter.index()
        # center() is unstable on freshly-tessellated meshes in Maya 2025 API 2.0;
        # compute centroid manually from vertex positions instead.
        verts = face_iter.getVertices()
        cx = cy = cz = 0.0
        for v in verts:
            p = preview_fn.getPoint(v, om.MSpace.kWorld)
            cx += p.x; cy += p.y; cz += p.z
        centroid = om.MPoint(cx / len(verts), cy / len(verts), cz / len(verts))
        _, base_face_id = base_fn.getClosestPoint(centroid, om.MSpace.kWorld)
        face_data = STATE.face_stitch_map.get(base_face_id)
        if face_data:
            STATE.t_face_stitch_map[face_id] = FaceStitchData(
                face_data.stitch_type,
                face_data.stitch_dir,
                face_iter.polygonVertexCount(),
            )
        color = (
            stitch_color_map[face_data.stitch_type]
            if face_data
            else stitch_color_map[StitchType.NOTASSIGNED]
        )
        for v_id in face_iter.getVertices():
            colors.append(color)
            face_ids.append(face_id)
            vert_ids.append(v_id)
        face_iter.next()

    if colors:
        preview_fn.setFaceVertexColors(colors, face_ids, vert_ids)

    cmds.setAttr(preview_dag.fullPathName() + ".displayColors", 1)

def shrinkwrap_preview_to_smoothed():
    # # Get selected objects
    # sel = cmds.ls(selection=True, long=True)
    
    # if len(sel) != 2:
    #     cmds.error("Please select exactly two meshes: [target, wrapper]")
    
    target = STATE.smoothed_mesh
    wrapper = STATE.base_mesh
    if STATE.is_tessellated:
        wrapper = STATE.preview_mesh
    if not target or not wrapper:
        cmds.warning("Cannot shrinkwrap: missing smoothed target or preview mesh.")
        return
    
    # Create shrinkWrap deformer
    shrink_node = cmds.deformer(wrapper, type='shrinkWrap')[0]
    
    # Connect target mesh to shrinkWrap
    cmds.connectAttr(target + ".worldMesh[0]", shrink_node + ".targetGeom", force=True)
    
    # Set projection type to closest point
    # 4 = Closest Point
    cmds.setAttr(shrink_node + ".projection", 4)
    
    # Optional useful defaults
    cmds.setAttr(shrink_node + ".keepBorder", 1)
    cmds.setAttr(shrink_node + ".smoothUVs", 1)
    
    cmds.delete(wrapper, ch=True)

    cmds.delete(STATE.smoothed_mesh)
    STATE.smoothed_mesh = None
    cmds.select(wrapper)

def create_smoothed_stitch_mesh(level):
    """
    creates catmull clark smoothed mesh so tessellated mesh can be projected onto it
    """
    if not STATE.base_mesh:
        cmds.warning("No mesh selected. Select a polygon mesh first.")
        return

    if not cmds.objExists(STATE.base_mesh):
        cmds.warning(f"Mesh '{STATE.base_mesh}' no longer exists.")
        return

    # Clean up any existing smoothed mesh before creating a new one.
    if STATE.smoothed_mesh and cmds.objExists(STATE.smoothed_mesh):
        cmds.delete(STATE.smoothed_mesh)
        STATE.smoothed_mesh = None

    # Ensure the original is visible before duplicating so the duplicate inherits
    # the correct visibility state.
    cmds.showHidden(STATE.base_mesh)

    duplicates = cmds.duplicate(STATE.base_mesh, returnRootsOnly=True)
    smoothedM = cmds.rename(duplicates[0], _derived_node_name(STATE.base_mesh, "_smooth_target"))
    STATE.smoothed_mesh = smoothedM

    # Subdivide all faces of the preview mesh.
    # mode=1 (linear): divisions=N splits each edge into N segments → N×N faces per quad.
    # We use level+1 so level=1 gives 2×2=4 stitch faces (minimum meaningful tessellation).
    cmds.polySmooth(
            smoothedM,
            mth=0,              # 0 = Catmull-Clark
            dv=level + 1,       # divisions
            c=1,                # continuity
            kb=0,               # keep borders
            ksb=0,              # keep selection borders
            khe=0,              # keep hard edges (0 = smooth them)
            kt=1,               # keep topology
            suv=1,              # smooth UVs
            peh=0,              # propagate edge hardness
            ps=0.1,             # smoothness
            ro=1,               # keep original (construction history)
            ch=1
        )
    # face_count = cmds.polyEvaluate(preview, face=True)
    # all_faces = [f"{preview}.f[{i}]" for i in range(face_count)]
    # cmds.polySubdivideFacet(all_faces, divisions=level + 1, mode=0)'

def stretch_force(dagPath, vtx_id_a, vtx_id_b, resting_length, space=om.MSpace.kWorld):
    k_stretch = .01
    mesh_fn = om.MFnMesh(dagPath)

    p1 = mesh_fn.getPoint(vtx_id_a, space)
    p2 = mesh_fn.getPoint(vtx_id_b, space)
    
    length = (p1 - p2).length()
    if length < 1e-8:
        return om.MVector(0.0, 0.0, 0.0)
    
    diff_vector = p1 - p2

    return k_stretch * ((resting_length/length)-1) * (diff_vector/length)

def wale_strut_force(dagPath, vtx_id_i, vtx_id_j, vtx_id_k, resting_length, space=om.MSpace.kWorld):
    k_wale_strut = .01
    mesh_fn = om.MFnMesh(dagPath)

    p_i = om.MVector(mesh_fn.getPoint(vtx_id_i, space))
    p_j = om.MVector(mesh_fn.getPoint(vtx_id_j, space))
    p_k = om.MVector(mesh_fn.getPoint(vtx_id_k, space))

    i_k_length = (p_i-p_k).length()
    i_j_length = (p_i-p_j).length()
    k_j_length = (p_k-p_j).length()

    r = max(resting_length, i_j_length+k_j_length)
    if i_k_length < 1e-8 or r < 1e-8:
        return om.MVector(0.0, 0.0, 0.0)

    return -1 * k_wale_strut * ((i_k_length/r) -1 ) * ((p_i-p_k)/i_k_length)

def shear_force(dagPath, vtx_id_i, vtx_id_j, vtx_id_k, space=om.MSpace.kWorld):
    k_shear = .01
    mesh_fn = om.MFnMesh(dagPath)

    p_i = om.MVector(mesh_fn.getPoint(vtx_id_i, space))
    p_j = om.MVector(mesh_fn.getPoint(vtx_id_j, space))
    p_k = om.MVector(mesh_fn.getPoint(vtx_id_k, space))
    

    return -1 * k_shear * (p_i - p_j) * (p_k - p_j) * (p_j - ((p_i + p_k) / 2))

def add_to_map(key, map, val):
    if key in map:
        map[key] += val
    else:
        map[key] = val

def apply_vertex_offsets(
    dagPath,
    vertex_offset_map,
    space=om.MSpace.kWorld,
    step_scale=1.0,
    max_offset=None,
):
    """
    Moves vertices by per-vertex offsets stored in a map:
    {vertex_id: om.MVector}
    """
    mesh_fn = om.MFnMesh(dagPath)
    points = mesh_fn.getPoints(space)

    for vtx_id, offset in vertex_offset_map.items():
        if step_scale != 1.0:
            offset = offset * step_scale
        if max_offset is not None:
            offset_len = offset.length()
            if offset_len > max_offset and offset_len > 1e-8:
                offset = (offset / offset_len) * max_offset

        # current position
        p = points[vtx_id]

        # apply offset
        points[vtx_id] = om.MPoint(
            p.x + offset.x,
            p.y + offset.y,
            p.z + offset.z
        )

    mesh_fn.setPoints(points, space)

def stitchMeshRelaxation(mesh, edge_data):
    mesh_sel = om.MSelectionList() 
    mesh_sel.add(mesh)
    dagPath = mesh_sel.getDagPath(0)
    
    # Create mesh function set
    mesh_fn = om.MFnMesh(dagPath)

    # Dictionary: vertex index -> count
    vertex_force = {}

    # Iterate over all polygons (faces)
    num_faces = mesh_fn.numPolygons
    
    # Total surface area
    total_area = 0.0
    poly_iter = om.MItMeshPolygon(dagPath)
    
    for face_id in range(num_faces):
        # --- Area accumulation ---
        poly_iter.setIndex(face_id)
        area = poly_iter.getArea()  # returns area of this face
        total_area += area

    
    if num_faces == 0 or total_area <= 1e-12:
        return

    course_rest = math.sqrt(total_area / num_faces)
    
    poly_iter = om.MItMeshPolygon(dagPath)
    
    
    # CALCULATE STRETCH FORCE FOR EACH EDGE
    edge_iter = om.MItMeshEdge(dagPath)
    while not edge_iter.isDone():
        edge_id = edge_iter.index()
        v1 = edge_iter.vertexId(0)
        v2 = edge_iter.vertexId(1)
        
        add_to_map(v1, vertex_force, stretch_force(dagPath, v1, v2, course_rest))
        add_to_map(v2, vertex_force, stretch_force(dagPath, v2, v1, course_rest))

        edge_iter.next()
        
        
    # CALCULATE DIAGONAL STRETCH FORCE AND SHEAR FOR EACH FACE VERT
    diag_rest_length = math.sqrt(course_rest*course_rest + course_rest*course_rest)
    for face_id in range(num_faces):
        # Get vertex indices for this face
        poly_iter.setIndex(face_id)
        vertex_ids = poly_iter.getVertices()
        v_count = len(vertex_ids)
    
        vert_iter = om.MItMeshVertex(dagPath)
        for i, v_id in enumerate(vertex_ids):
            # calculate diagonal stretch force (only add to current vert since we go around the quad)
            diag_v = vertex_ids[(i + 2) % v_count]
            add_to_map(v_id, vertex_force, stretch_force(dagPath, v_id, diag_v, diag_rest_length))
            
            # calculate shear force
            prev_v = vertex_ids[(i - 1) % v_count]
            next_v = vertex_ids[(i + 1) % v_count]
            shear_force_val = shear_force(dagPath, prev_v, v_id, next_v)
            add_to_map(prev_v, vertex_force, -0.5 * shear_force_val)
            add_to_map(next_v, vertex_force, -0.5 * shear_force_val)
            
    #ITERATE THROUGH EVERY VERT FOR WALE STRUT FORCE
    # find two wales touching vert and calculate wale strut
    vert_iter = om.MItMeshVertex(dagPath)

    while not vert_iter.isDone():
        vtx_id = vert_iter.index()
        
        connected_edges = vert_iter.getConnectedEdges()
        wale1_v = None
        wale2_v = None
        num_wales_found = 0
        for connecting_edge in connected_edges:
            if edge_data.get(connecting_edge, EdgeType.UNASSIGNED) == EdgeType.WALE:
                wale_edge_iter = om.MItMeshEdge(dagPath)
                wale_edge_iter.setIndex(connecting_edge)
                v0 = wale_edge_iter.vertexId(0)
                v1 = wale_edge_iter.vertexId(1)
                non_central_vertex = None
                if v0 != vtx_id:
                    non_central_vertex = v0
                elif v1 != vtx_id:
                    non_central_vertex = v1
                if num_wales_found == 0:
                    wale1_v = non_central_vertex
                else:
                    wale2_v = non_central_vertex
                num_wales_found += 1
        if num_wales_found == 2 and wale1_v != None and wale2_v != None:
            wale_strut_force_val = wale_strut_force(dagPath, wale1_v, vtx_id, wale2_v, course_rest)
            add_to_map(wale1_v, vertex_force, wale_strut_force_val)
            add_to_map(wale2_v, vertex_force, -1* wale_strut_force_val)

        vert_iter.next()
    apply_vertex_offsets(
        dagPath,
        vertex_force,
        step_scale=MESH_RELAXATION_STEP,
        max_offset=course_rest * MESH_RELAXATION_MAX_OFFSET_FRACTION,
    )


def apply_stitch_relaxation_forces():
    preview_sel = om.MSelectionList() 
    preview_sel.add(STATE.preview_mesh)
    dagPath = preview_sel.getDagPath(0)

    # Create mesh function set
    mesh_fn = om.MFnMesh(dagPath)

    # Dictionary: vertex index -> count
    vertex_face_count = {}

    # Iterate over all polygons (faces)
    num_faces = mesh_fn.numPolygons

    for face_id in range(num_faces):
        # Get vertex indices for this face
        vertex_ids = mesh_fn.getPolygonVertices(face_id)
        
        for v_id in vertex_ids:
            if v_id not in vertex_face_count:
                vertex_face_count[v_id] = 0
            
            vertex_face_count[v_id] += 1

    return vertex_face_count

def tessellate_stitch_mesh(level):
    """
    Subdivides all stitch faces on the selected mesh by the given tessellation level.
    The original mesh is preserved and remains visible. A duplicate (the
    tessellated preview) is shown in the viewport. Re-calling with a new level
    replaces the previous preview without touching the original.
    """
    if not STATE.selected_mesh:
        cmds.warning("No mesh selected. Select a polygon mesh first.")
        return

    if not cmds.objExists(STATE.selected_mesh):
        cmds.warning(f"Mesh '{STATE.selected_mesh}' no longer exists.")
        return

    # Clean up any existing preview before creating a new one.
    if STATE.preview_mesh and cmds.objExists(STATE.preview_mesh):
        cmds.delete(STATE.preview_mesh)
        STATE.preview_mesh = None
    STATE.t_mesh = None
    STATE.t_edge_map.clear()
    STATE.t_face_stitch_map.clear()

    # Ensure the original is visible before duplicating so the duplicate inherits
    # the correct visibility state.
    cmds.showHidden(STATE.selected_mesh)

    duplicates = cmds.duplicate(STATE.selected_mesh, returnRootsOnly=True)
    preview = cmds.rename(duplicates[0], _derived_node_name(STATE.selected_mesh, "_tess_preview"))
    STATE.preview_mesh = preview
    STATE.preview_mesh_relaxed = False

    # Subdivide all faces of the preview mesh.
    # mode=1 (linear): divisions=N splits each edge into N segments → N×N faces per quad.
    # We use level+1 so level=1 gives 2×2=4 stitch faces (minimum meaningful tessellation).
    face_count = cmds.polyEvaluate(preview, face=True)
    all_faces = [f"{preview}.f[{i}]" for i in range(face_count)]
    cmds.polySubdivideFacet(all_faces, divisions=level + 1, mode=0)

    STATE.tessellation_level = level
    STATE.is_tessellated = True

    cmds.select(preview)
    init_t_stitch_mesh_data_structures()
    init_t_stitch_face_data_structure()

    # Color the preview before hiding the base — getClosestPoint needs the base visible.
    _color_preview_mesh_from_base()

    _assign_tslt_edges_from_base()

    # set course edge touching edges to wale
    spreadEdgeAssignment()

    draw_t_course_edges_as_curves()


    cmds.inViewMessage(
        amg=f"Tessellated stitch mesh at level <hl>{level}</hl> ({level + 1}×{level + 1} stitches per face).",
        pos="topCenter",
        fade=True
    )


def restore_stitch_mesh():
    """
    Removes the tessellated preview and shows the original un-tessellated mesh.
    Safe to call even if no tessellation has been applied.
    """
    if STATE.preview_mesh and cmds.objExists(STATE.preview_mesh):
        cmds.delete(STATE.preview_mesh)
    if STATE.smoothed_mesh and cmds.objExists(STATE.smoothed_mesh):
        cmds.delete(STATE.smoothed_mesh)

    STATE.preview_mesh = None
    STATE.preview_mesh_relaxed = False
    STATE.smoothed_mesh = None
    STATE.is_tessellated = False
    STATE.t_mesh = None
    STATE.t_edge_map.clear()
    STATE.t_face_stitch_map.clear()

    if STATE.selected_mesh and cmds.objExists(STATE.selected_mesh):
        cmds.showHidden(STATE.selected_mesh)
        cmds.inViewMessage(
            amg="Restored original stitch mesh.",
            pos="topCenter",
            fade=True
        )
    else:
        cmds.warning("Original mesh not found; nothing to restore.")


def generate_knit_mesh():
    """
    End-to-end pipeline: generates yarn curves for every knitting row and
    optionally wraps each curve in a tube mesh to represent physical yarn.
    Optionally relaxes the stitch mesh immediately before yarn generation.
    """
    from darn_that_yarn.commands.yarn_curve import generate_yarn_curves

    validation = validate_stitch_mesh()
    if not validation.can_generate:
        cmds.warning(validation.summary())
        return

    cmds.progressWindow(
        title="Generate Knit Mesh",
        progress=0,
        max=100,
        status="Starting yarn generation",
        isInterruptable=True,
    )
    nodes = []

    def _progress(progress, status):
        if cmds.progressWindow(query=True, isCancelled=True):
            raise RuntimeError("Generate Knit Mesh cancelled.")
        cmds.progressWindow(
            edit=True,
            progress=max(0, min(100, int(progress))),
            status=status,
        )

    try:
        _progress(3, "Preparing stitch mesh")
        apply_stitch_mesh_relaxation_before_generation(
            progress_callback=lambda p, status: _progress(5 + int(p * 0.25), status)
        )
        _progress(30, "Generating yarn paths")
        nodes = generate_yarn_curves(
            add_tubes=True,
            yarn_radius=STATE.yarn_radius,
            tube_segments=8,
            progress_callback=lambda p, status: _progress(30 + int(p * 0.68), status),
        )
        _progress(100, "Done")
    except RuntimeError as exc:
        cmds.warning(str(exc))
        return
    finally:
        cmds.progressWindow(endProgress=True)

    cmds.inViewMessage(
        amg=(
            f"Generated <hl>{len(nodes)}</hl> yarn path(s). "
            f"(mesh relax={STATE.mesh_relaxation_enabled}, "
            f"yarn relax={STATE.yarn_relaxation_enabled})"
        ),
        pos="topCenter",
        fade=True
    )


def apply_stitch_mesh_relaxation_before_generation(progress_callback=None):
    if not STATE.mesh_relaxation_enabled:
        return
    if STATE.preview_mesh_relaxed:
        return
    # if not STATE.is_tessellated or not STATE.preview_mesh or not cmds.objExists(STATE.preview_mesh):
    #     cmds.warning("Stitch mesh relaxation requires a tessellated preview mesh.")
    #     return

    if not STATE.is_tessellated or not STATE.preview_mesh or not cmds.objExists(STATE.preview_mesh):
        duplicates = cmds.duplicate(STATE.base_mesh, returnRootsOnly=True)
        preview = cmds.rename(duplicates[0], _derived_node_name(STATE.base_mesh, "_base_relaxed_preview"))
        STATE.t_mesh = preview
        STATE.t_edge_map = STATE.edge_map.copy()
        STATE.preview_mesh = preview
        STATE.t_face_stitch_map = STATE.face_stitch_map.copy()
        # meshToRelax = STATE.base_mesh
        # meshToRelaxEdgeMap = STATE.edge_map
    meshToRelax = STATE.t_mesh
    meshToRelaxEdgeMap = STATE.t_edge_map

    if progress_callback:
        progress_callback(0, "Building smooth stitch target")

    cmds.refresh(suspend=True)
    try:
        create_smoothed_stitch_mesh(STATE.tessellation_level)
        if progress_callback:
            progress_callback(12, "Projecting tessellated mesh")
        shrinkwrap_preview_to_smoothed()
        for i in range(MESH_RELAXATION_ITERATIONS):
            if progress_callback:
                progress_callback(
                    12 + int((i + 1) * 88 / MESH_RELAXATION_ITERATIONS),
                    f"Relaxing stitch mesh {i + 1} of {MESH_RELAXATION_ITERATIONS}",
                )
            stitchMeshRelaxation(meshToRelax, meshToRelaxEdgeMap)
    finally:
        cmds.refresh(suspend=False)
        cmds.refresh()

    STATE.preview_mesh_relaxed = True


def set_yarn_thickness(radius):
    STATE.yarn_radius = max(0.001, float(radius))

    from darn_that_yarn.commands.yarn_curve import update_yarn_tube_radius

    updated_nodes = update_yarn_tube_radius(
        STATE.yarn_radius,
        tube_segments=8,
    )
    if updated_nodes:
        cmds.inViewMessage(
            amg=f"Updated yarn thickness to <hl>{STATE.yarn_radius:.3f}</hl>.",
            pos="topCenter",
            fade=True
        )


def reset_stitch_mesh():
    active_mesh = STATE.selected_mesh or STATE.base_mesh

    for node in (
        STATE.preview_mesh,
        STATE.smoothed_mesh,
        "edge_type_indicator_grp",
        "t_edge_type_indicator_grp",
    ):
        if node and cmds.objExists(node):
            cmds.delete(node)

    try:
        from darn_that_yarn.commands.yarn_curve import _delete_existing_yarn_nodes
        _delete_existing_yarn_nodes()
    except Exception:
        pass

    STATE.reset()
    if active_mesh and cmds.objExists(active_mesh):
        STATE.selected_mesh = active_mesh
        STATE.base_mesh = active_mesh
        cmds.showHidden(active_mesh)
        cmds.select(active_mesh, replace=True)

    cmds.inViewMessage(
        amg="Darn that Yarn state reset.",
        pos="topCenter",
        fade=True
    )



class EdgeType(Enum):
    UNASSIGNED = 0
    COURSE = 1
    WALE = 2
    
class StitchType(Enum):
    NOTASSIGNED = 0
    KNIT = 1
    PURL = 2
    YARNOVER = 3
    INCREASE = 4
    DECREASE = 5
    
class StitchDir(Enum):
    UP = 0
    DOWN = 1
    
@dataclass
class FaceStitchData:
    stitch_type: StitchType
    stitch_dir: StitchDir
    edge_count: int


@dataclass
class StitchMeshValidation:
    mesh: Optional[str]
    face_count: int = 0
    assigned_faces: int = 0
    stitch_faces: int = 0
    unassigned_faces: int = 0
    invalid_faces: int = 0
    invalid_edges: int = 0
    connected_components: int = 0
    messages: List[str] = field(default_factory=list)

    @property
    def can_generate(self):
        return self.mesh is not None and self.stitch_faces > 0 and self.invalid_faces == 0

    def summary(self):
        if not self.mesh:
            return "Mesh check: select an active mesh."
        if self.can_generate:
            return (
                f"Mesh check: ready. {self.stitch_faces}/{self.face_count} stitch faces, "
                f"{self.connected_components} island(s)."
            )
        if self.messages:
            return "Mesh check: " + self.messages[0]
        return "Mesh check: not ready."


def _edge_type_name(edge_type):
    return getattr(edge_type, "name", str(edge_type))


def _stitch_type_name(stitch_type):
    return getattr(stitch_type, "name", str(stitch_type))


def _get_mesh_adjacency(mesh, face_map):
    dag_path = _mesh_dag_path(mesh)
    edge_to_faces: Dict[int, List[int]] = {}
    face_edges: Dict[int, Tuple[int, ...]] = {}

    face_iter = om.MItMeshPolygon(dag_path)
    while not face_iter.isDone():
        face_id = face_iter.index()
        if face_id in face_map:
            edges = tuple(face_iter.getEdges())
            face_edges[face_id] = edges
            for edge_id in edges:
                edge_to_faces.setdefault(edge_id, []).append(face_id)
        face_iter.next()

    face_adj = {face_id: [] for face_id in face_map}
    for edge_id, face_ids in edge_to_faces.items():
        if len(face_ids) == 2:
            f0, f1 = face_ids
            face_adj[f0].append((f1, edge_id))
            face_adj[f1].append((f0, edge_id))

    return dag_path, face_edges, face_adj


def validate_stitch_mesh(mesh=None, face_map=None, edge_map=None):
    mesh = mesh or (
        STATE.preview_mesh
        if STATE.preview_mesh and STATE.t_face_stitch_map
        else STATE.base_mesh
    )
    face_map = face_map if face_map is not None else (
        STATE.t_face_stitch_map
        if mesh == STATE.preview_mesh and STATE.t_face_stitch_map
        else STATE.face_stitch_map
    )
    edge_map = edge_map if edge_map is not None else (
        STATE.t_edge_map
        if mesh == STATE.preview_mesh and STATE.t_edge_map
        else STATE.edge_map
    )

    result = StitchMeshValidation(mesh=mesh)

    if not mesh or not cmds.objExists(mesh):
        result.messages.append("active mesh is missing.")
        return result
    if not face_map:
        result.messages.append("stitch face data is missing.")
        return result

    try:
        _dag_path, face_edges, face_adj = _get_mesh_adjacency(mesh, face_map)
    except Exception:
        result.messages.append("active object is not a polygon mesh.")
        return result

    result.face_count = len(face_map)
    visited = set()
    for face_id in face_map:
        if face_id in visited:
            continue
        result.connected_components += 1
        stack = [face_id]
        visited.add(face_id)
        while stack:
            current = stack.pop()
            for nbr_face, _shared_edge in face_adj.get(current, []):
                if nbr_face not in visited:
                    visited.add(nbr_face)
                    stack.append(nbr_face)

    for face_id, face_data in face_map.items():
        edge_ids = face_edges.get(face_id, ())
        if not edge_ids:
            result.invalid_faces += 1
            continue

        missing_edges = [
            edge_id for edge_id in edge_ids
            if _edge_type_name(edge_map.get(edge_id, EdgeType.UNASSIGNED)) == "UNASSIGNED"
        ]
        if missing_edges:
            result.unassigned_faces += 1
            continue

        result.assigned_faces += 1
        wale_count = sum(
            _edge_type_name(edge_map.get(edge_id, EdgeType.UNASSIGNED)) == "WALE"
            for edge_id in edge_ids
        )
        course_count = sum(
            _edge_type_name(edge_map.get(edge_id, EdgeType.UNASSIGNED)) == "COURSE"
            for edge_id in edge_ids
        )
        stitch_name = _stitch_type_name(face_data.stitch_type)

        if wale_count != 2:
            result.invalid_faces += 1
            continue
        if course_count < 1:
            result.invalid_faces += 1
            continue
        if stitch_name == "NOTASSIGNED":
            result.unassigned_faces += 1
            continue
        if stitch_name in ("KNIT", "PURL", "YARNOVER") and face_data.edge_count != 4:
            result.invalid_faces += 1
            continue
        if stitch_name in ("INCREASE", "DECREASE") and face_data.edge_count != 5:
            result.invalid_faces += 1
            continue

        result.stitch_faces += 1

    result.invalid_edges = sum(
        1
        for edge_type in edge_map.values()
        if _edge_type_name(edge_type) not in ("UNASSIGNED", "COURSE", "WALE")
    )

    if result.invalid_faces:
        result.messages.append(f"{result.invalid_faces} invalid face(s); check wale/course labels and stitch types.")
    elif result.stitch_faces == 0:
        result.messages.append("no valid stitch faces; assign a pattern or stitch type first.")
    elif result.unassigned_faces:
        result.messages.append(f"ready with {result.unassigned_faces} unassigned/skipped face(s).")

    return result

stitch_color_map = {
    StitchType.NOTASSIGNED: om.MColor((0.25, 0.25, 0.28)),  # soft charcoal
    StitchType.KNIT:        om.MColor((0.30, 0.65, 0.42)),  # sage green
    StitchType.PURL:        om.MColor((0.75, 0.32, 0.32)),  # muted coral
    StitchType.YARNOVER:    om.MColor((0.30, 0.58, 0.82)),  # dusty blue
    StitchType.INCREASE:    om.MColor((0.85, 0.68, 0.22)),  # warm amber
    StitchType.DECREASE:    om.MColor((0.68, 0.35, 0.65)),  # soft plum
}


def init_stitch_face_data_structure():
    if not STATE.base_mesh:
        return
    STATE.face_stitch_map.clear()

    sel = om.MSelectionList()
    sel.add(STATE.base_mesh)
    dag = sel.getDagPath(0)
    if not dag.hasFn(om.MFn.kMesh):
        dag.extendToShape()

    it = om.MItMeshPolygon(dag)

    while not it.isDone():
        face_id = it.index()
        edge_count = it.polygonVertexCount()
        STATE.face_stitch_map[face_id] = FaceStitchData(
            StitchType.NOTASSIGNED,
            StitchDir.UP,
            edge_count
        )
        it.next()

def init_t_stitch_face_data_structure():
    if not STATE.t_mesh:
        return
    STATE.t_face_stitch_map.clear()

    dag = _mesh_dag_path(STATE.t_mesh)
    it = om.MItMeshPolygon(dag)

    while not it.isDone():
        face_id = it.index()
        edge_count = it.polygonVertexCount()
        STATE.t_face_stitch_map[face_id] = FaceStitchData(
            StitchType.NOTASSIGNED,
            StitchDir.UP,
            edge_count
        )
        it.next()

def init_t_stitch_mesh_data_structures():
    if STATE.preview_mesh and cmds.objExists(STATE.preview_mesh):
        STATE.t_mesh = STATE.preview_mesh
    else:
        selectedMeshes = cmds.ls(selection=True, long=True)
        if not selectedMeshes:
            om.MGlobal.displayError("Select a mesh object first.")
            return
        STATE.t_mesh = selectedMeshes[0]

    STATE.t_edge_map.clear()

    try:
        dagPath = _mesh_dag_path(STATE.t_mesh)
    except Exception:
        om.MGlobal.displayError("Selected object is not a mesh.")
        return

    mesh_fn = om.MFnMesh(dagPath)
    STATE.t_edge_map.update(
        dict.fromkeys(range(mesh_fn.numEdges), EdgeType.UNASSIGNED)
    )

def init_stitch_mesh_data_structures():
    sel = om.MGlobal.getActiveSelectionList()

    if sel.length() == 0:
        om.MGlobal.displayError("Select a mesh object first.")
        return
    selectedMeshes = cmds.ls(selection=True, long=True)
    STATE.base_mesh = selectedMeshes[0]
    STATE.edge_map.clear()

    dagPath = sel.getDagPath(0)

    # Ensure we are working with the mesh shape
    if not dagPath.hasFn(om.MFn.kMesh):
        try:
            dagPath.extendToShape()
        except Exception:
            om.MGlobal.displayError("Selected object is not a mesh.")
            return

    edge_iter = om.MItMeshEdge(dagPath)

    while not edge_iter.isDone():
        edge_index = edge_iter.index()
        v0 = edge_iter.vertexId(0)
        v1 = edge_iter.vertexId(1)
        
        STATE.edge_map[edge_index] = EdgeType.UNASSIGNED

        #print(f"Edge {edge_index}: vertices ({v0}, {v1})")

        edge_iter.next()

def assign_knit_to_fully_assigned_faces(mesh=None, face_map=None, edge_map=None, color=True):
    mesh = mesh or STATE.base_mesh
    face_map = face_map if face_map is not None else STATE.face_stitch_map
    edge_map = edge_map if edge_map is not None else STATE.edge_map

    if not mesh or not cmds.objExists(mesh):
        om.MGlobal.displayError("Select a mesh.")
        return

    try:
        dagPath = _mesh_dag_path(mesh)
    except Exception:
        om.MGlobal.displayError("Selection is not a mesh.")
        return

    face_iter = om.MItMeshPolygon(dagPath)

    updated_faces = []

    while not face_iter.isDone():
        face_id = face_iter.index()
        edge_ids = face_iter.getEdges()
        if face_id not in face_map:
            face_iter.next()
            continue

        # Check if all edges are assigned (not UNASSIGNED) AND 2 Wale Edges
        all_assigned = all(
            edge_map.get(e, EdgeType.UNASSIGNED) != EdgeType.UNASSIGNED
            for e in edge_ids
        )
        wale_count = sum(edge_map.get(e) == EdgeType.WALE for e in edge_ids)

        if all_assigned and face_map[face_id].stitch_type == StitchType.NOTASSIGNED:
            if wale_count == 2:
                if face_map[face_id].edge_count == 4:
                    face_data = face_map[face_id]
                    face_data.stitch_type = StitchType.KNIT
                    updated_faces.append(face_id)
                if face_map[face_id].edge_count == 5:
                    face_data = face_map[face_id]
                    face_data.stitch_type = StitchType.INCREASE
                    updated_faces.append(face_id)

        # IF ANY FACES NO LONGER HAVE 2 WALE EDGES OR ARE NOT ASSIGNED, SET UNNASSIGNED
        if not all_assigned:
            face_data = face_map[face_id]
            face_data.stitch_type = StitchType.NOTASSIGNED
            updated_faces.append(face_id)

        face_iter.next()

    om.MGlobal.displayInfo(f"{len(updated_faces)} faces set to KNIT.")
    if color:
        if face_map is STATE.face_stitch_map:
            cmds.select(mesh, replace=True)
            color_knit_faces()
        else:
            color_faces(mesh, face_map)

def color_faces(mesh, face_map):
    try:
        dagPath = _mesh_dag_path(mesh)
    except Exception:
        om.MGlobal.displayError("Selection is not a mesh.")
        return

    mesh_fn = om.MFnMesh(dagPath)
    face_iter = om.MItMeshPolygon(dagPath)

    colors = []
    face_ids = []
    vert_ids = []

    knit_count = 0

    while not face_iter.isDone():
        face_id = face_iter.index()

        if face_id in face_map:
            vertex_indices = face_iter.getVertices()

            for v_id in vertex_indices:
                colors.append(stitch_color_map[face_map[face_id].stitch_type])
                face_ids.append(face_id)
                vert_ids.append(v_id)
                
            if face_map[face_id].stitch_type != StitchType.NOTASSIGNED:
                knit_count += 1

        face_iter.next()

    if colors:
        mesh_fn.setFaceVertexColors(colors, face_ids, vert_ids)

    # Enable display of vertex colors
    import maya.cmds as cmds
    mesh_name = dagPath.fullPathName()
    cmds.setAttr(mesh_name + ".displayColors", 1)

    om.MGlobal.displayInfo(f"Colored {knit_count} KNIT faces.")


def color_knit_faces():
    if not STATE.base_mesh:
        om.MGlobal.displayError("Select a mesh.")
        return
    color_faces(STATE.base_mesh, STATE.face_stitch_map)


def is_face_fully_assigned(dagPath, face_id):
    face_iter = om.MItMeshPolygon(dagPath)

    try:
        face_iter.setIndex(face_id)
    except Exception:
        om.MGlobal.displayError(f"Invalid face_id: {face_id}")
        return False

    edge_ids = face_iter.getEdges()

    # Check all edges assigned
    all_assigned = all(
        STATE.edge_map.get(e, EdgeType.UNASSIGNED) != EdgeType.UNASSIGNED
        for e in edge_ids
    )

    # Count WALE edges
    wale_count = sum(
        STATE.edge_map.get(e) == EdgeType.WALE
        for e in edge_ids
    )

    # Final condition
    return all_assigned and wale_count == 2

def are_selected_faces_active():
    sel = om.MGlobal.getActiveSelectionList()

    for i in range(sel.length()):
        dagPath, component = sel.getComponent(i)

        if component.isNull():
            continue

        if component.apiType() != om.MFn.kMeshPolygonComponent:
            continue
            

        face_comp = om.MFnSingleIndexedComponent(component)
        face_ids = face_comp.getElements()

        for face_id in face_ids:

            # Check if all edges are assigned (not UNASSIGNED)
            if not is_face_fully_assigned(dagPath, face_id):
                return False
    return True

def get_selected_faces_edge_num():
    selected_faces_edgecount = -1
    sel = om.MGlobal.getActiveSelectionList()

    for i in range(sel.length()):
        dagPath, component = sel.getComponent(i)

        if component.isNull():
            continue

        if component.apiType() != om.MFn.kMeshPolygonComponent:
            continue
            

        face_comp = om.MFnSingleIndexedComponent(component)
        face_ids = face_comp.getElements()

        for face_id in face_ids:
            if face_id not in STATE.face_stitch_map:
                return -1

            # Check if this face has same number of edges as other selected faces
            if selected_faces_edgecount == -1:
                selected_faces_edgecount = STATE.face_stitch_map[face_id].edge_count
            elif selected_faces_edgecount != STATE.face_stitch_map[face_id].edge_count:
                return -1
    return selected_faces_edgecount

def set_selected_faces_stitch_type(stitch_type: StitchType):
    sel = om.MGlobal.getActiveSelectionList()

    if sel.length() == 0:
        om.MGlobal.displayError("Select mesh faces.")
        return

    updated_faces = []

    for i in range(sel.length()):
        dagPath, component = sel.getComponent(i)

        if component.isNull():
            continue

        if component.apiType() != om.MFn.kMeshPolygonComponent:
            continue
            

        face_comp = om.MFnSingleIndexedComponent(component)
        face_ids = face_comp.getElements()

        for face_id in face_ids:

            # Check if all edges are assigned (not UNASSIGNED)
            all_assigned = is_face_fully_assigned(dagPath, face_id)
            if (face_id in STATE.face_stitch_map) and all_assigned:
                if (stitch_type == StitchType.PURL or stitch_type == StitchType.KNIT or stitch_type == StitchType.YARNOVER) and STATE.face_stitch_map[face_id].edge_count != 4:
                    continue

                if (stitch_type == StitchType.INCREASE or stitch_type == StitchType.DECREASE) and STATE.face_stitch_map[face_id].edge_count != 5:
                    continue
                STATE.face_stitch_map[face_id].stitch_type = stitch_type
                updated_faces.append(face_id)

    if updated_faces:
        om.MGlobal.displayInfo(
            f"Updated {len(updated_faces)} faces to {stitch_type.name}."
        )
        color_knit_faces()
    else:
        om.MGlobal.displayWarning("No valid faces were updated.")

def flip_selected_faces_stitch_type():
    sel = om.MGlobal.getActiveSelectionList()

    if sel.length() == 0:
        om.MGlobal.displayError("Select mesh faces.")
        return

    updated_faces = []

    for i in range(sel.length()):
        dagPath, component = sel.getComponent(i)

        if component.isNull():
            continue

        if component.apiType() != om.MFn.kMeshPolygonComponent:
            continue
            

        face_comp = om.MFnSingleIndexedComponent(component)
        face_ids = face_comp.getElements()

        for face_id in face_ids:

            # Check if all edges are assigned (not UNASSIGNED)
            all_assigned = is_face_fully_assigned(dagPath, face_id)
            if (face_id in STATE.face_stitch_map) and all_assigned:

                if STATE.face_stitch_map[face_id].stitch_type == StitchType.YARNOVER: continue

                #flip to opposite direction stitch type
                if STATE.face_stitch_map[face_id].stitch_type == StitchType.INCREASE : STATE.face_stitch_map[face_id].stitch_type = StitchType.DECREASE
                elif STATE.face_stitch_map[face_id].stitch_type == StitchType.DECREASE : STATE.face_stitch_map[face_id].stitch_type = StitchType.INCREASE
                elif STATE.face_stitch_map[face_id].stitch_type == StitchType.KNIT : STATE.face_stitch_map[face_id].stitch_type = StitchType.PURL
                elif STATE.face_stitch_map[face_id].stitch_type == StitchType.PURL : STATE.face_stitch_map[face_id].stitch_type = StitchType.KNIT
                updated_faces.append(face_id)

    if updated_faces:
        om.MGlobal.displayInfo(
            f"Flipped {len(updated_faces)} faces."
        )
        color_knit_faces()
    else:
        om.MGlobal.displayWarning("No valid faces were updated.")

def set_selected_edges_to_course():
    sel = om.MGlobal.getActiveSelectionList()

    if sel.length() == 0:
        om.MGlobal.displayError("Select mesh edges.")
        return

    selected_edges = set()
    connected_vertices = set()

    dagPath = None

    # Collect selected edges
    for i in range(sel.length()):
        dagPath, component = sel.getComponent(i)

        if component.isNull():
            continue

        if component.apiType() != om.MFn.kMeshEdgeComponent:
            continue

        edge_comp = om.MFnSingleIndexedComponent(component)
        edge_ids = edge_comp.getElements()

        edge_iter = om.MItMeshEdge(dagPath)

        for edge_id in edge_ids:
            selected_edges.add(edge_id)

            edge_iter.setIndex(edge_id)
            v0 = edge_iter.vertexId(0)
            v1 = edge_iter.vertexId(1)

            connected_vertices.add(v0)
            connected_vertices.add(v1)

            STATE.edge_map[edge_id] = EdgeType.COURSE

    if dagPath is None or not selected_edges:
        om.MGlobal.displayError("Select mesh edges.")
        return

    # Find perpendicular edges (edges sharing vertices but not selected)
    vert_iter = om.MItMeshVertex(dagPath)

    for v in connected_vertices:
        vert_iter.setIndex(v)
        connected_edges = vert_iter.getConnectedEdges()

        for e in connected_edges:
            if e not in selected_edges:
                STATE.edge_map[e] = EdgeType.WALE

    draw_course_edges_as_curves()
    om.MGlobal.displayInfo("Selected edges set to COURSE and perpendicular edges set to WALE.")



def apply_pattern_fill(pattern_type="checker"):
    """
    Floods all fully-assigned quad faces with an alternating k/p pattern.
    Uses BFS over the face adjacency graph, stepping across COURSE edges to
    advance the row coordinate and across WALE edges to advance the column.

    pattern_type:
        "stockinette" - all knit
        "checker" - alternates k/p in both row and column (row+col parity)
        "rib"     - alternates k/p by column only (col parity)
        "wide_rib" - two-column knit/purl ribbing
        "garter" - alternates k/p by row only
        "basket" - two-by-two checker blocks
    """
    from collections import deque

    if not STATE.face_stitch_map:
        om.MGlobal.displayError("No stitch faces. Initialize the stitch mesh first.")
        return

    if not STATE.base_mesh:
        om.MGlobal.displayError("No base mesh. Select a mesh first.")
        return

    # check if there are selected faces, only apply pattern to selected faces if so
    selection = cmds.ls(selection=True, flatten=True)
    # Filter for polygon faces
    selected_faces = []
    for sel in selection:
        match = re.search(r'\.f\[(\d+)\]', sel)
        if match:
            face_id = int(match.group(1))
            selected_faces.append(face_id)

    cmds.select(STATE.base_mesh, replace=True)
    sel = om.MGlobal.getActiveSelectionList()
    if sel.length() == 0:
        om.MGlobal.displayError("Could not select base mesh.")
        return

    dagPath = sel.getDagPath(0)
    if not dagPath.hasFn(om.MFn.kMesh):
        dagPath.extendToShape()

    # Build edge -> [face_ids] so we can find shared edges efficiently.
    edge_to_faces = {}
    face_iter = om.MItMeshPolygon(dagPath)
    while not face_iter.isDone():
        face_id = face_iter.index()
        if face_id in STATE.face_stitch_map:
            for edge_id in face_iter.getEdges():
                edge_to_faces.setdefault(edge_id, []).append(face_id)
        face_iter.next()

    # Build face adjacency: face_id -> list of (neighbor_face_id, shared_edge_id)
    face_adj = {fid: [] for fid in STATE.face_stitch_map}
    for edge_id, face_list in edge_to_faces.items():
        if len(face_list) == 2:
            f0, f1 = face_list
            face_adj[f0].append((f1, edge_id))
            face_adj[f1].append((f0, edge_id))

    # BFS: assign (row, col) to every reachable face.  Run one BFS per
    # connected component so cylinders, caps, or separated mesh islands do not
    # leave later rows untouched.
    # Crossing a COURSE edge advances the row; crossing a WALE edge advances the column.
    face_coords = {}
    component_offset = 0
    for start_face in STATE.face_stitch_map:
        if start_face in face_coords:
            continue

        queue = deque([(start_face, component_offset, 0)])
        face_coords[start_face] = (component_offset, 0)

        while queue:
            fid, row, col = queue.popleft()
            for nbr_face, shared_edge in face_adj.get(fid, []):
                if nbr_face in face_coords:
                    continue
                edge_type = STATE.edge_map.get(shared_edge, EdgeType.UNASSIGNED)
                if edge_type == EdgeType.COURSE:
                    new_coords = (row + 1, col)
                elif edge_type == EdgeType.WALE:
                    new_coords = (row, col + 1)
                else:
                    new_coords = (row, col + 1)  # treat unassigned as wale
                face_coords[nbr_face] = new_coords
                queue.append((nbr_face, new_coords[0], new_coords[1]))

        component_rows = [
            row
            for face_id, (row, _col) in face_coords.items()
            if face_id in STATE.face_stitch_map
        ]
        component_offset = (max(component_rows) + 2) if component_rows else component_offset + 2

    # Assign stitch types based on pattern parity.
    updated = 0
    for face_id, (row, col) in face_coords.items():
        if face_id not in STATE.face_stitch_map:
            continue
        if not is_face_fully_assigned(dagPath, face_id):
            continue
        if selected_faces and face_id not in selected_faces:
            continue
        if STATE.face_stitch_map[face_id].edge_count != 4:
            continue  # increase/decrease faces (5-sided) keep their type

        if pattern_type == "stockinette":
            parity = 0
        elif pattern_type == "rib":
            parity = col % 2
        elif pattern_type == "wide_rib":
            parity = (col // 2) % 2
        elif pattern_type == "garter":
            parity = row % 2
        elif pattern_type == "basket":
            parity = ((row // 2) + (col // 2)) % 2
        else:
            parity = (row + col) % 2
        STATE.face_stitch_map[face_id].stitch_type = StitchType.KNIT if parity == 0 else StitchType.PURL
        updated += 1

    om.MGlobal.displayInfo(f"Pattern fill '{pattern_type}' applied to {updated} faces.")
    color_knit_faces()


def print_edge_map():
    for edge, edge_type in STATE.edge_map.items():
        print(f"Edge {edge}: {edge_type.name}")

def create_knit_gui():
    window_name = "knitEdgeTool"

    # Delete window if it already exists
    if cmds.window(window_name, exists=True):
        cmds.deleteUI(window_name)

    cmds.window(window_name, title="Knit Edge Tool", widthHeight=(200, 100))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=10)

    cmds.button(
        label="Set Selected Edges to COURSE",
        height=40,
        command=lambda x: set_selected_edges_to_course()
    )

    cmds.button(
        label="Set Sel Faces to PURL",
        height=40,
        command=lambda x: set_selected_faces_stitch_type(StitchType.PURL)
    )

    cmds.showWindow(window_name)


def draw_t_course_edges_as_curves(offset=0.0):
    mel.eval('selectType -nurbsCurve false;')
    debug_grp = "t_edge_type_indicator_grp"
    assigned_edge_count = sum(
        1 for edge_type in STATE.t_edge_map.values()
        if edge_type in (EdgeType.COURSE, EdgeType.WALE)
    )

    if assigned_edge_count > TESSELLATED_EDGE_CURVE_LIMIT:
        if cmds.objExists(debug_grp):
            cmds.delete(debug_grp)
        if STATE.preview_mesh and cmds.objExists(STATE.preview_mesh):
            cmds.select(STATE.preview_mesh, replace=True)
        assign_knit_to_fully_assigned_faces(
            mesh=STATE.preview_mesh,
            face_map=STATE.t_face_stitch_map,
            edge_map=STATE.t_edge_map,
        )
        om.MGlobal.displayInfo(
            f"Skipped {assigned_edge_count} tessellated edge guide curves for speed."
        )
        return

    # Create group if it doesn't exist
    if not cmds.objExists(debug_grp):
        debug_grp = cmds.group(empty=True, name=debug_grp)
    else:
        # Delete existing curves under the group
        children = cmds.listRelatives(debug_grp, allDescendents=True, fullPath=True) or []
        curve_shapes = cmds.ls(children, type="nurbsCurve", long=True) or []
        curve_transforms = cmds.listRelatives(curve_shapes, parent=True, fullPath=True) or []
        if curve_transforms:
            cmds.delete(list(set(curve_transforms)))

    cmds.select(STATE.preview_mesh, replace=True)
    
    sel = om.MGlobal.getActiveSelectionList()

    if sel.length() == 0:
        om.MGlobal.displayError("Select a mesh.")
        return

    dagPath = sel.getDagPath(0)

    if not dagPath.hasFn(om.MFn.kMesh):
        try:
            dagPath.extendToShape()
        except Exception:
            om.MGlobal.displayError("Selection is not a mesh.")
            return

    mesh_fn = om.MFnMesh(dagPath)
    edge_iter = om.MItMeshEdge(dagPath)

    created_curves = []

    while not edge_iter.isDone():
        edge_id = edge_iter.index()
        edge_type = STATE.t_edge_map.get(edge_id)

        if edge_type not in [EdgeType.COURSE, EdgeType.WALE]:
            edge_iter.next()
            continue

        v0 = edge_iter.vertexId(0)
        v1 = edge_iter.vertexId(1)

        p0 = mesh_fn.getPoint(v0, om.MSpace.kWorld)
        p1 = mesh_fn.getPoint(v1, om.MSpace.kWorld)

        n0 = mesh_fn.getVertexNormal(v0, True, om.MSpace.kWorld)
        n1 = mesh_fn.getVertexNormal(v1, True, om.MSpace.kWorld)

        # Offset
        p0_offset = p0 + (n0 * offset)
        p1_offset = p1 + (n1 * offset)

        curve = cmds.curve(
            p=[(p0_offset.x, p0_offset.y, p0_offset.z),
               (p1_offset.x, p1_offset.y, p1_offset.z)],
            d=1,
            name=f"t_edge_{edge_id}_crv"
        )

        shape = cmds.listRelatives(curve, shapes=True)[0]
        cmds.setAttr(shape + ".overrideEnabled", 1)
        cmds.setAttr(shape + ".overrideRGBColors", 1)

        if edge_type == EdgeType.COURSE:
            cmds.setAttr(shape + ".overrideColorRGB", 0.18, 0.65, 0.72)
            cmds.setAttr(shape + ".lineWidth", 10)

        elif edge_type == EdgeType.WALE:
            cmds.setAttr(shape + ".overrideColorRGB", 0.62, 0.45, 0.78)
            cmds.setAttr(shape + ".lineWidth", 4)

        # Make curves unselectable
        cmds.setAttr(curve + ".overrideEnabled", 1)
        cmds.setAttr(curve + ".overrideDisplayType", 2)  # Reference

        # Parent to debug group instead of mesh
        cmds.parent(curve, debug_grp)

        created_curves.append(curve)

        edge_iter.next()

    om.MGlobal.displayInfo(f"Created {len(created_curves)} edge curves.")
    assign_knit_to_fully_assigned_faces(
        mesh=STATE.preview_mesh,
        face_map=STATE.t_face_stitch_map,
        edge_map=STATE.t_edge_map,
    )

def draw_course_edges_as_curves(offset=0.0):
    mel.eval('selectType -nurbsCurve false;')
    debug_grp = "edge_type_indicator_grp"

    # Create group if it doesn't exist
    if not cmds.objExists(debug_grp):
        debug_grp = cmds.group(empty=True, name=debug_grp)
    else:
        # Delete existing curves under the group
        children = cmds.listRelatives(debug_grp, allDescendents=True, fullPath=True) or []
        curve_shapes = cmds.ls(children, type="nurbsCurve", long=True) or []
        curve_transforms = cmds.listRelatives(curve_shapes, parent=True, fullPath=True) or []
        if curve_transforms:
            cmds.delete(list(set(curve_transforms)))

    cmds.select(STATE.base_mesh, replace=True)
    
    sel = om.MGlobal.getActiveSelectionList()

    if sel.length() == 0:
        om.MGlobal.displayError("Select a mesh.")
        return

    dagPath = sel.getDagPath(0)

    if not dagPath.hasFn(om.MFn.kMesh):
        try:
            dagPath.extendToShape()
        except Exception:
            om.MGlobal.displayError("Selection is not a mesh.")
            return

    mesh_fn = om.MFnMesh(dagPath)
    edge_iter = om.MItMeshEdge(dagPath)

    created_curves = []

    while not edge_iter.isDone():
        edge_id = edge_iter.index()
        edge_type = STATE.edge_map.get(edge_id)

        if edge_type not in [EdgeType.COURSE, EdgeType.WALE]:
            edge_iter.next()
            continue

        v0 = edge_iter.vertexId(0)
        v1 = edge_iter.vertexId(1)

        p0 = mesh_fn.getPoint(v0, om.MSpace.kWorld)
        p1 = mesh_fn.getPoint(v1, om.MSpace.kWorld)

        n0 = mesh_fn.getVertexNormal(v0, True, om.MSpace.kWorld)
        n1 = mesh_fn.getVertexNormal(v1, True, om.MSpace.kWorld)

        # Offset
        p0_offset = p0 + (n0 * offset)
        p1_offset = p1 + (n1 * offset)

        curve = cmds.curve(
            p=[(p0_offset.x, p0_offset.y, p0_offset.z),
               (p1_offset.x, p1_offset.y, p1_offset.z)],
            d=1,
            name=f"edge_{edge_id}_crv"
        )

        shape = cmds.listRelatives(curve, shapes=True)[0]
        cmds.setAttr(shape + ".overrideEnabled", 1)
        cmds.setAttr(shape + ".overrideRGBColors", 1)

        if edge_type == EdgeType.COURSE:
            cmds.setAttr(shape + ".overrideColorRGB", 0.18, 0.65, 0.72)
            cmds.setAttr(shape + ".lineWidth", 10)

        elif edge_type == EdgeType.WALE:
            cmds.setAttr(shape + ".overrideColorRGB", 0.62, 0.45, 0.78)
            cmds.setAttr(shape + ".lineWidth", 4)

        # Make curves unselectable
        cmds.setAttr(curve + ".overrideEnabled", 1)
        cmds.setAttr(curve + ".overrideDisplayType", 2)  # Reference

        # Parent to debug group instead of mesh
        cmds.parent(curve, debug_grp)

        created_curves.append(curve)

        edge_iter.next()

    om.MGlobal.displayInfo(f"Created {len(created_curves)} edge curves.")
    assign_knit_to_fully_assigned_faces()
