from typing import Any, Dict, List, Optional

import maya.cmds as cmds


def get_selected_mesh_transform() -> Optional[str]:
    selection = cmds.ls(selection=True, long=True) or []
    if not selection:
        return None

    meshes = cmds.ls(selection, dag=True, shapes=True, type="mesh", long=True) or []
    if len(meshes) < 1:
        return None

    parents = cmds.listRelatives(meshes[0], parent=True, fullPath=True) or []
    return parents[0] if parents else None


def get_selected_edges() -> List[str]:
    return cmds.filterExpand(selectionMask=32, expand=True) or []


def get_selected_faces() -> List[str]:
    return cmds.filterExpand(selectionMask=34, expand=True) or []


def get_selection_summary() -> Dict[str, Any]:
    edges = get_selected_edges()
    faces = get_selected_faces()
    mesh = get_selected_mesh_transform()

    return {
        "mesh": mesh,
        "edges": edges,
        "faces": faces,
        "has_edge_selection": len(edges) > 0,
        "has_face_selection": len(faces) > 0,
    }