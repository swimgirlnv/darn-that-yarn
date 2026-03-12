import maya.cmds as cmds

from darn_that_yarn.core.state import STATE


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
    Placeholder for Rebecca's tessellation task.
    """
    STATE.tessellation_level = level
    cmds.inViewMessage(
        amg=f"Preview tessellation level set to <hl>{level}</hl>.",
        pos="topCenter",
        fade=True
    )


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