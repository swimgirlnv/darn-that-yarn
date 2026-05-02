import maya.cmds as cmds
import maya.mel as mel
import re
import os
from darn_that_yarn.core.state import STATE

def get_next_material_name(base_name="yarn_mat_"):
    existing = cmds.ls(base_name + "*") or []

    max_index = 0
    pattern = re.compile(rf"{base_name}(\d+)$")

    for name in existing:
        match = pattern.match(name)
        if match:
            max_index = max(max_index, int(match.group(1)))

    return f"{base_name}{max_index + 1}"


def create_yarn_material_with_texture(image_path):
    selection = STATE.yarn_mesh

    if not selection:
        cmds.warning("No objects selected.")
        return

    if not image_path or not os.path.isfile(image_path):
        cmds.error("Invalid image path provided.")
        return

    shader_name = get_next_material_name("yarn_mat_")

    # Create shader
    shader = cmds.shadingNode("aiStandardSurface", asShader=True, name=shader_name)

    # Set roughness to 1
    cmds.setAttr(shader + ".specularRoughness", 1)

    # Create file texture node
    file_node = cmds.shadingNode("file", asTexture=True, isColorManaged=True, name=shader_name + "_file")
    cmds.setAttr(file_node + ".fileTextureName", image_path, type="string")

    # Create place2dTexture node
    place2d = cmds.shadingNode("place2dTexture", asUtility=True, name=shader_name + "_place2d")

    # Connect place2d to file node
    connections = [
        "coverage", "translateFrame", "rotateFrame", "mirrorU", "mirrorV",
        "stagger", "wrapU", "wrapV", "repeatUV", "offset", "rotateUV",
        "noiseUV", "vertexUvOne", "vertexUvTwo", "vertexUvThree",
        "vertexCameraOne"
    ]

    for attr in connections:
        cmds.connectAttr(f"{place2d}.{attr}", f"{file_node}.{attr}", force=True)

    cmds.connectAttr(place2d + ".outUV", file_node + ".uvCoord")
    cmds.connectAttr(place2d + ".outUvFilterSize", file_node + ".uvFilterSize")

    # Connect file texture to shader base color
    cmds.connectAttr(file_node + ".outColor", shader + ".baseColor", force=True)

    # Create shading group
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=shader_name + "SG")

    # Connect shader to shading group
    cmds.connectAttr(shader + ".outColor", sg + ".surfaceShader", force=True)

    # # Assign to selection
    # cmds.sets(selection, edit=True, forceElement=sg)

    STATE.yarn_material = shader_name

    print(f"Created {shader_name} with texture: {image_path}")



def assign_material_to_yarn_by_name(material_name):
    # Get selection
    selection = STATE.yarn_mesh

    if not selection:
        cmds.warning("No objects selected.")
        return

    # Check material exists
    if not cmds.objExists(material_name):
        cmds.error(f"Material '{material_name}' does not exist.")
        return

    # Find or create shading group
    sg_connections = cmds.listConnections(material_name, type="shadingEngine")

    if sg_connections:
        shading_group = sg_connections[0]
    else:
        shading_group = cmds.sets(
            renderable=True,
            noSurfaceShader=True,
            empty=True,
            name=material_name + "SG"
        )
        cmds.connectAttr(material_name + ".outColor", shading_group + ".surfaceShader", force=True)

    # Assign to selection
    cmds.sets(selection, edit=True, forceElement=shading_group)

    print(f"Assigned material '{material_name}' to {len(selection)} object(s).")

def set_texture_image(node_name, image_path):
    """
    Updates the file texture path.

    Args:
        node_name (str): file node OR material name
        image_path (str): full path to new image
    """

    if not os.path.isfile(image_path):
        cmds.error(f"Invalid image path: {image_path}")
        return

    if not cmds.objExists(node_name):
        cmds.error(f"Node does not exist: {node_name}")
        return

    file_nodes = []

    # Case 1: node is already a file node
    if cmds.nodeType(node_name) == "file":
        file_nodes = [node_name]

    else:
        # Case 2: assume it's a material → find connected file nodes
        history = cmds.listHistory(node_name) or []
        file_nodes = [n for n in history if cmds.nodeType(n) == "file"]

    if not file_nodes:
        cmds.warning(f"No file texture nodes found connected to: {node_name}")
        return

    # Update all connected file nodes
    for file_node in file_nodes:
        cmds.setAttr(file_node + ".fileTextureName", image_path, type="string")
        print(f"Updated {file_node} → {image_path}")

def get_face_count(mesh):
    """
    Returns the number of faces on a polygon mesh.
    :param mesh: transform or shape name (e.g. 'pCube1')
    :return: int face count
    """
    # Ensure we are working with a transform
    shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True) or []
    
    if not shapes:
        cmds.warning(f"{mesh} has no mesh shape.")
        return 0

    # polyEvaluate works on transforms or shapes
    return cmds.polyEvaluate(mesh, face=True)

def total_edges(mesh):
     # Get shape node
    shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True) or []
    for shape in shapes:
        if cmds.nodeType(shape) == "mesh":
            # Get edge count
            edge_count = cmds.polyEvaluate(shape, edge=True)
            return edge_count

def select_edge_loop_by_id(mesh, edge_id):
    
    # Ensure it's a transform with a mesh shape
    shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True)
    if not shapes:
        cmds.warning("Selected object has no shape.")
        return
    
    # Use polySelect to select the edge by ID
    try:
        cmds.select(clear=True)
        cmds.polySelect(mesh, edgeLoop=edge_id)
    except Exception as e:
        cmds.warning("Failed to select edge: {}".format(e))


def clean_yarn_UVs():
    #get total number of edges
    num_edges = total_edges(STATE.yarn_mesh)


    # set normal UV mapping    
    cmds.polyAutoProjection(STATE.yarn_mesh, planes=6, optimize=2, percentageSpace=0.1)

    #select all edges and sew them
    cmds.select(f"{STATE.yarn_mesh}.e[*]", replace=True)
    cmds.polyMapSew() 

    #select long seam
    select_edge_loop_by_id(STATE.yarn_mesh, 14)
    # Edge indices you want to select
    edge_ids = [0, 4, 7, 10, 13, 16, 19, 22, num_edges-17,  num_edges-18, num_edges-20, num_edges-22, num_edges-24, num_edges-26, num_edges-28, num_edges-31]
    # Resolve to the transform node
    obj = STATE.yarn_mesh.split('.')[0]
    # Build edge component strings
    edges_to_select = ["{}.e[{}]".format(obj, i) for i in edge_ids]
    # Select the edges
    cmds.select(edges_to_select, add=True)
    cmds.select("{}.e[{}]".format(obj, num_edges-3), deselect=True)
    cmds.select("{}.e[{}]".format(obj, num_edges-11), deselect=True)
    cmds.polyMapCut() 

    cmds.select(STATE.yarn_mesh)
    faces = cmds.polyListComponentConversion(STATE.yarn_mesh, toFace=True)
    cmds.select(faces)
    face_count= get_face_count(STATE.yarn_mesh)
    mel.eval(f"u3dUnfold -ite 1 -p 0 -bi 1 -tf 1 -ms 1024 -rs 0 {STATE.yarn_mesh}.f[0:{face_count}];")
    # cmds.u3dUnfold(
    #     f"{STATE.yarn_mesh}.f[*]",
    #     ite=1, p=0, bi=1, tf=1, ms=1024, rs=0
    # )
    STATE.yarn_uvs_clean = True