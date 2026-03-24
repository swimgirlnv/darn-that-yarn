import maya.cmds as cmds

from darn_that_yarn.core.state import STATE
import maya.api.OpenMaya as om
from enum import Enum
from dataclasses import dataclass
import maya.mel as mel


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


def tessellate_stitch_mesh(level):
    """
    Subdivides all stitch faces on the selected mesh by the given tessellation level.
    The original mesh is hidden but preserved so it can be restored. A duplicate
    (the tessellated preview) is shown in the viewport. Re-calling with a new level
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

    # Ensure the original is visible before duplicating so the duplicate inherits
    # the correct visibility state.
    cmds.showHidden(STATE.selected_mesh)

    duplicates = cmds.duplicate(STATE.selected_mesh, returnRootsOnly=True)
    preview = cmds.rename(duplicates[0], STATE.selected_mesh + "_tess_preview")
    STATE.preview_mesh = preview

    # Subdivide all faces of the preview mesh.
    face_count = cmds.polyEvaluate(preview, face=True)
    all_faces = [f"{preview}.f[{i}]" for i in range(face_count)]
    # mode=1 (linear) so each edge is split into `level` segments, giving
    # predictable row counts that match the slider value directly.
    cmds.polySubdivideFacet(all_faces, divisions=level, mode=1)

    # Hide the original; the tessellated preview becomes the viewport representation.
    cmds.hide(STATE.selected_mesh)

    STATE.tessellation_level = level
    STATE.is_tessellated = True

    cmds.inViewMessage(
        amg=f"Tessellated stitch mesh at level <hl>{level}</hl>.",
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

    STATE.preview_mesh = None
    STATE.is_tessellated = False

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
    Placeholder for the end-to-end pipeline.
    """
    cmds.inViewMessage(
        amg=(
            f"Generate Knit Mesh called "
            f"(mesh relax={STATE.mesh_relaxation_enabled}, "
            f"yarn relax={STATE.yarn_relaxation_enabled})."
        ),
        pos="topCenter",
        fade=True
    )


def reset_stitch_mesh():
    STATE.reset()
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

stitch_color_map = {
    StitchType.NOTASSIGNED: om.MColor((0.25, 0.25, 0.28)),  # soft charcoal
    StitchType.KNIT:        om.MColor((0.30, 0.65, 0.42)),  # sage green
    StitchType.PURL:        om.MColor((0.75, 0.32, 0.32)),  # muted coral
    StitchType.YARNOVER:    om.MColor((0.30, 0.58, 0.82)),  # dusty blue
    StitchType.INCREASE:    om.MColor((0.85, 0.68, 0.22)),  # warm amber
    StitchType.DECREASE:    om.MColor((0.68, 0.35, 0.65)),  # soft plum
}


def init_stitch_face_data_structure():
    sel = om.MGlobal.getActiveSelectionList()
    dag, comp = sel.getComponent(0)
    
    mesh_fn = om.MFnMesh(dag)
    it = om.MItMeshPolygon(dag, comp)
    
    while not it.isDone():
        face_id = it.index()
        edge_count = it.polygonVertexCount()
    
        STATE.face_stitch_map[face_id] = FaceStitchData(
            StitchType.NOTASSIGNED,
            StitchDir.UP,
            edge_count
        )
    
        it.next()

def init_stitch_mesh_data_structures():
    sel = om.MGlobal.getActiveSelectionList()

    if sel.length() == 0:
        om.MGlobal.displayError("Select a mesh object first.")
        return
    selectedMeshes = cmds.ls(selection=True, long=True)
    STATE.base_mesh = selectedMeshes[0]

    dagPath = sel.getDagPath(0)

    # Ensure we are working with the mesh shape
    if not dagPath.hasFn(om.MFn.kMesh):
        try:
            dagPath.extendToShape()
        except:
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

def assign_knit_to_fully_assigned_faces():
    cmds.select(STATE.base_mesh, replace=True)
    sel = om.MGlobal.getActiveSelectionList()

    if sel.length() == 0:
        om.MGlobal.displayError("Select a mesh.")
        return

    dagPath = sel.getDagPath(0)

    if not dagPath.hasFn(om.MFn.kMesh):
        try:
            dagPath.extendToShape()
        except:
            om.MGlobal.displayError("Selection is not a mesh.")
            return

    face_iter = om.MItMeshPolygon(dagPath)

    updated_faces = []

    while not face_iter.isDone():
        face_id = face_iter.index()
        edge_ids = face_iter.getEdges()
        wale_count = sum(STATE.edge_map[e] == EdgeType.WALE for e in edge_ids)

        # Get all edge indices for this face
        edge_ids = face_iter.getEdges()

        # Check if all edges are assigned (not UNASSIGNED) AND 2 Wale Edges
        all_assigned = is_face_fully_assigned(dagPath, face_id)

        if all_assigned and STATE.face_stitch_map[face_id].stitch_type == StitchType.NOTASSIGNED:
            if face_id in STATE.face_stitch_map and wale_count == 2:
                if STATE.face_stitch_map[face_id].edge_count == 4:
                    face_data = STATE.face_stitch_map[face_id]
                    face_data.stitch_type = StitchType.KNIT
                    updated_faces.append(face_id)
                if STATE.face_stitch_map[face_id].edge_count == 5:
                    face_data = STATE.face_stitch_map[face_id]
                    face_data.stitch_type = StitchType.INCREASE
                    updated_faces.append(face_id)

        # IF ANY FACES NO LONGER HAVE 2 WALE EDGES OR ARE NOT ASSIGNED, SET UNNASSIGNED
        if not all_assigned:
            face_data = STATE.face_stitch_map[face_id]
            face_data.stitch_type = StitchType.NOTASSIGNED
            updated_faces.append(face_id)

        face_iter.next()

    om.MGlobal.displayInfo(f"{len(updated_faces)} faces set to KNIT.")
    color_knit_faces()

def color_knit_faces():
    sel = om.MGlobal.getActiveSelectionList()

    if sel.length() == 0:
        om.MGlobal.displayError("Select a mesh.")
        return

    dagPath = sel.getDagPath(0)

    # mesh shape
    if not dagPath.hasFn(om.MFn.kMesh):
        try:
            dagPath.extendToShape()
        except:
            om.MGlobal.displayError("Selection is not a mesh.")
            return

    if not dagPath.hasFn(om.MFn.kMesh):
        om.MGlobal.displayError("Selection is not a mesh shape.")
        return

    mesh_fn = om.MFnMesh(dagPath)
    face_iter = om.MItMeshPolygon(dagPath)

    colors = []
    face_ids = []
    vert_ids = []

    knit_count = 0

    while not face_iter.isDone():
        face_id = face_iter.index()

        if face_id in STATE.face_stitch_map:
            vertex_indices = face_iter.getVertices()

            for v_id in vertex_indices:
                colors.append(stitch_color_map[STATE.face_stitch_map[face_id].stitch_type]) 
                face_ids.append(face_id)
                vert_ids.append(v_id)
                
            if STATE.face_stitch_map[face_id].stitch_type != StitchType.NOTASSIGNED:
                knit_count += 1

        face_iter.next()

    if colors:
        mesh_fn.setFaceVertexColors(colors, face_ids, vert_ids)

    # Enable display of vertex colors
    import maya.cmds as cmds
    mesh_name = dagPath.fullPathName()
    cmds.setAttr(mesh_name + ".displayColors", 1)

    om.MGlobal.displayInfo(f"Colored {knit_count} KNIT faces.")


def is_face_fully_assigned(dagPath, face_id):
    face_iter = om.MItMeshPolygon(dagPath)

    try:
        face_iter.setIndex(face_id)
    except:
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
        "checker" - alternates k/p in both row and column (row+col parity)
        "rib"     - alternates k/p by column only (col parity)
    """
    from collections import deque

    if not STATE.face_stitch_map:
        om.MGlobal.displayError("No stitch faces. Initialize the stitch mesh first.")
        return

    if not STATE.base_mesh:
        om.MGlobal.displayError("No base mesh. Select a mesh first.")
        return

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

    # BFS: assign (row, col) to every reachable face.
    # Crossing a COURSE edge advances the row; crossing a WALE edge advances the column.
    face_coords = {}
    start_face = next(iter(STATE.face_stitch_map))
    queue = deque([(start_face, 0, 0)])
    face_coords[start_face] = (0, 0)

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

    # Assign stitch types based on pattern parity.
    updated = 0
    for face_id, (row, col) in face_coords.items():
        if face_id not in STATE.face_stitch_map:
            continue
        if STATE.face_stitch_map[face_id].edge_count != 4:
            continue  # increase/decrease faces (5-sided) keep their type

        parity = (row + col) % 2 if pattern_type == "checker" else col % 2
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
        except:
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