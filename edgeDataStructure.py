import maya.api.OpenMaya as om
from enum import Enum
from dataclasses import dataclass
import maya.mel as mel


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
    StitchType.NOTASSIGNED: om.MColor((0.2, 0.2, 0.2)),  # dark gray
    StitchType.KNIT:        om.MColor((0.0, 1.0, 0.0)),  # green
    StitchType.PURL:        om.MColor((1.0, 0.0, 0.0)),  # red
    StitchType.YARNOVER:    om.MColor((0.0, 0.5, 1.0)),  # light blue
    StitchType.INCREASE:    om.MColor((1.0, 1.0, 0.0)),  # yellow
    StitchType.DECREASE:    om.MColor((1.0, 0.0, 1.0)),  # magenta
}

# face index - > stitch data
face_stitch_map = {}
# edge index - > EdgeType
edge_map = {}

selectedMeshes = cmds.ls(selection=True, long=True)
base_mesh = selectedMeshes[0]

def init_stitch_face_data_structure():
    sel = om.MGlobal.getActiveSelectionList()
    dag, comp = sel.getComponent(0)
    
    mesh_fn = om.MFnMesh(dag)
    it = om.MItMeshPolygon(dag, comp)
    
    while not it.isDone():
        face_id = it.index()
        edge_count = it.polygonVertexCount()
    
        face_stitch_map[face_id] = FaceStitchData(
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
        
        edge_map[edge_index] = EdgeType.UNASSIGNED

        #print(f"Edge {edge_index}: vertices ({v0}, {v1})")

        edge_iter.next()

def assign_knit_to_fully_assigned_faces():
    cmds.select(base_mesh, replace=True)
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
        wale_count = sum(edge_map[e] == EdgeType.WALE for e in edge_ids)

        # Get all edge indices for this face
        edge_ids = face_iter.getEdges()

        # Check if all edges are assigned (not UNASSIGNED) AND 2 Wale Edges
        # all_assigned = all(
        #     edge_map.get(e, EdgeType.UNASSIGNED) != EdgeType.UNASSIGNED
        #     for e in edge_ids
        # )
        all_assigned = is_face_fully_assigned(dagPath, face_id)

        if all_assigned and face_stitch_map[face_id].stitch_type == StitchType.NOTASSIGNED:
            if face_id in face_stitch_map and wale_count == 2:
                if face_stitch_map[face_id].edge_count == 4:
                    face_data = face_stitch_map[face_id]
                    face_data.stitch_type = StitchType.KNIT
                    updated_faces.append(face_id)
                if face_stitch_map[face_id].edge_count == 5:
                    face_data = face_stitch_map[face_id]
                    face_data.stitch_type = StitchType.INCREASE
                    updated_faces.append(face_id)

        # IF ANY FACES NO LONGER HAVE 2 WALE EDGES OR ARE NOT ASSIGNED, SET UNNASSIGNED
        if not all_assigned:
            face_data = face_stitch_map[face_id]
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

        if face_id in face_stitch_map:
            vertex_indices = face_iter.getVertices()

            for v_id in vertex_indices:
                colors.append(stitch_color_map[face_stitch_map[face_id].stitch_type]) 
                face_ids.append(face_id)
                vert_ids.append(v_id)
                
            if face_stitch_map[face_id].stitch_type != StitchType.NOTASSIGNED:
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
        edge_map.get(e, EdgeType.UNASSIGNED) != EdgeType.UNASSIGNED
        for e in edge_ids
    )

    # Count WALE edges
    wale_count = sum(
        edge_map.get(e) == EdgeType.WALE
        for e in edge_ids
    )

    # Final condition
    return all_assigned and wale_count == 2

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
            if (face_id in face_stitch_map) and all_assigned:
                if (stitch_type == StitchType.PURL or stitch_type == StitchType.KNIT or stitch_type == StitchType.YARNOVER) and face_stitch_map[face_id].edge_count != 4:
                    continue

                if (stitch_type == StitchType.INCREASE or stitch_type == StitchType.DECREASE) and face_stitch_map[face_id].edge_count != 5:
                    continue
                face_stitch_map[face_id].stitch_type = stitch_type
                updated_faces.append(face_id)

    if updated_faces:
        om.MGlobal.displayInfo(
            f"Updated {len(updated_faces)} faces to {stitch_type.name}."
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

            edge_map[edge_id] = EdgeType.COURSE

    # Find perpendicular edges (edges sharing vertices but not selected)
    vert_iter = om.MItMeshVertex(dagPath)

    for v in connected_vertices:
        vert_iter.setIndex(v)
        connected_edges = vert_iter.getConnectedEdges()

        for e in connected_edges:
            if e not in selected_edges:
                edge_map[e] = EdgeType.WALE

    draw_course_edges_as_curves()
    om.MGlobal.displayInfo("Selected edges set to COURSE and perpendicular edges set to WALE.")



def print_edge_map():
    for edge, edge_type in edge_map.items():
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

def draw_course_edges_as_curves():
    
    #Delete curves already parented to base mesh
    curves = cmds.listRelatives(base_mesh, allDescendents=True, type="nurbsCurve", fullPath=True) or []
    curve_transforms = cmds.listRelatives(curves, parent=True, fullPath=True) or []
    if curve_transforms:
                cmds.delete(list(set(curve_transforms)))
                
    cmds.select(base_mesh, replace=True)
    
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
    mesh_name = dagPath.partialPathName()

    edge_iter = om.MItMeshEdge(dagPath)

    created_curves = []

    while not edge_iter.isDone():
        edge_id = edge_iter.index()

        if edge_map.get(edge_id) == EdgeType.COURSE:
            v0 = edge_iter.vertexId(0)
            v1 = edge_iter.vertexId(1)

            p0 = mesh_fn.getPoint(v0, om.MSpace.kWorld)
            p1 = mesh_fn.getPoint(v1, om.MSpace.kWorld)

            curve = cmds.curve(
                p=[(p0.x, p0.y, p0.z), (p1.x, p1.y, p1.z)],
                d=1,
                name=f"courseEdge_{edge_id}_crv"
            )

            # color it blue
            shape = cmds.listRelatives(curve, shapes=True)[0]
            cmds.setAttr(shape + ".overrideEnabled", 1)
            cmds.setAttr(shape + ".overrideRGBColors", 1)
            cmds.setAttr(shape + ".overrideColorRGB", 0, 0, 1)
            cmds.setAttr(shape + ".lineWidth", 10)
            cmds.setAttr(curve + ".overrideEnabled", 1)
            cmds.setAttr(curve + ".overrideDisplayType", 1)  # 1 = Template

            # parent to mesh transform
            cmds.parent(curve, base_mesh)

            created_curves.append(curve)
            
        if edge_map.get(edge_id) == EdgeType.WALE:
            v0 = edge_iter.vertexId(0)
            v1 = edge_iter.vertexId(1)

            p0 = mesh_fn.getPoint(v0, om.MSpace.kWorld)
            p1 = mesh_fn.getPoint(v1, om.MSpace.kWorld)

            curve = cmds.curve(
                p=[(p0.x, p0.y, p0.z), (p1.x, p1.y, p1.z)],
                d=1,
                name=f"courseEdge_{edge_id}_crv"
            )

            # color it blue
            shape = cmds.listRelatives(curve, shapes=True)[0]
            cmds.setAttr(shape + ".overrideEnabled", 1)
            cmds.setAttr(shape + ".overrideRGBColors", 1)
            cmds.setAttr(shape + ".overrideColorRGB", 1, 0, 1)
            cmds.setAttr(shape + ".lineWidth", 4)
            cmds.setAttr(curve + ".overrideEnabled", 1)
            cmds.setAttr(curve + ".overrideDisplayType", 1)  # 1 = Template

            # parent to mesh transform
            cmds.parent(curve, base_mesh)

            created_curves.append(curve)
            

        edge_iter.next()

    om.MGlobal.displayInfo(f"Created {len(created_curves)} COURSE edge curves.")
    assign_knit_to_fully_assigned_faces()

#function to set selected edge loop as all course edges and to set perpendicular edges with verts in edge loop as wale

#can you get edge by selection?
#can you get edge by vertice?


init_stitch_mesh_data_structures()
init_stitch_face_data_structure()
create_knit_gui()
mel.eval('selectType -nurbsCurve false;')
print(edge_map)
print(face_stitch_map)