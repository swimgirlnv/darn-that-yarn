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