import maya.api.OpenMaya as om
from enum import Enum

class EdgeType(Enum):
    UNASSIGNED = 0
    COURSE = 1
    WALE = 2
    
edge_map = {}  # key: edge index, value: EdgeType
selectedMeshes = cmds.ls(selection=True, long=True)
base_mesh = selectedMeshes[0]

def print_edges_of_selection():
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
        
def set_selected_edges_to_courseORIGINAL():
    sel = om.MGlobal.getActiveSelectionList()

    if sel.length() == 0:
        om.MGlobal.displayError("Select mesh edges.")
        return

    for i in range(sel.length()):
        dagPath, component = sel.getComponent(i)

        if component.isNull():
            continue

        if component.apiType() != om.MFn.kMeshEdgeComponent:
            om.MGlobal.displayWarning("Selection contains non-edge components.")
            continue

        edge_comp = om.MFnSingleIndexedComponent(component)
        edge_ids = edge_comp.getElements()

        for edge_id in edge_ids:
            edge_map[edge_id] = EdgeType.COURSE
            #print(f"Edge {edge_id} set to COURSE")

    om.MGlobal.displayInfo("Selected edges set to COURSE.")

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
        label="Print Edge Map",
        height=40,
        command=lambda x: draw_course_edges_as_curves()
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

            # parent to mesh transform
            cmds.parent(curve, base_mesh)

            created_curves.append(curve)

        edge_iter.next()

    om.MGlobal.displayInfo(f"Created {len(created_curves)} COURSE edge curves.")

#function to set selected edge loop as all course edges and to set perpendicular edges with verts in edge loop as wale

#can you get edge by selection?
#can you get edge by vertice?


print_edges_of_selection()
create_knit_gui()
print(edge_map)