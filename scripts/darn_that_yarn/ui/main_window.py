import maya.cmds as cmds

from darn_that_yarn.core.selection import get_selection_summary, get_selected_mesh_transform
from darn_that_yarn.core.state import STATE
from darn_that_yarn.commands.stitch_commands import (
    set_course_edges,
    set_stitch_type,
    flip_row_direction,
    tessellate_stitch_mesh,
    restore_stitch_mesh,
    generate_knit_mesh,
    reset_stitch_mesh,
    init_stitch_face_data_structure,
    init_stitch_mesh_data_structures,
    draw_course_edges_as_curves,
    set_selected_edges_to_course,
    are_selected_faces_active,
    set_selected_faces_stitch_type,
    apply_pattern_fill,
    StitchType
)

WINDOW_NAME = "DarnThatYarnWindow"
WORKSPACE_NAME = "DarnThatYarnWorkspaceControl"

_SCRIPT_JOB_IDS = []

UI = {}

stitch_name_to_type_map = { "knit": StitchType.KNIT,
                            "purl": StitchType.PURL,
                            "yarn-over": StitchType.YARNOVER,
                            "increase": StitchType.INCREASE,
                            "decrease": StitchType.DECREASE}


def _safe_delete_script_jobs():
    global _SCRIPT_JOB_IDS
    for job_id in _SCRIPT_JOB_IDS:
        if cmds.scriptJob(exists=job_id):
            cmds.scriptJob(kill=job_id, force=True)
    _SCRIPT_JOB_IDS = []


def _on_close(*_):
    _safe_delete_script_jobs()


def close_darn_that_yarn_ui():
    _safe_delete_script_jobs()

    if cmds.workspaceControl(WORKSPACE_NAME, exists=True):
        cmds.deleteUI(WORKSPACE_NAME)


def show_darn_that_yarn_ui():
    close_darn_that_yarn_ui()

    cmds.workspaceControl(
        WORKSPACE_NAME,
        label="Darn that Yarn!",
        retain=False,
        floating=True,
        initialWidth=360,
        initialHeight=660
    )

    content = cmds.columnLayout(adj=True, parent=WORKSPACE_NAME)
    _build_ui(content)
    _register_script_jobs()

    mesh = get_selected_mesh_transform()
    if mesh:
        _activate_mesh(mesh)
    else:
        refresh_ui_state()


def _activate_mesh(mesh):
    STATE.selected_mesh = mesh
    STATE.base_mesh = mesh
    _set_status(f"Active mesh: {mesh}")
    init_stitch_mesh_data_structures()
    init_stitch_face_data_structure()
    draw_course_edges_as_curves()
    refresh_ui_state()


def _build_ui(parent):
    cmds.columnLayout(adj=True, parent=parent)

    UI["title"] = cmds.text(
        label="Darn that Yarn!",
        align="center",
        height=30,
        font="boldLabelFont"
    )

    UI["set_mesh_btn"] = cmds.button(
        label="Set Active Mesh",
        command=lambda *_: _handle_set_mesh(),
        height=32,
        annotation="Select a polygon mesh in the viewport, then click this to begin."
    )

    UI["status"] = cmds.text(
        label="Select a polygon mesh and click Set Active Mesh.",
        align="left",
        height=24,
        wordWrap=True
    )

    cmds.separator(height=10, style="in")

    # Stitch Mesh Generation section
    UI["stitch_frame"] = cmds.frameLayout(
        label="Stitch Mesh Generation",
        collapsable=False,
        marginWidth=8,
        marginHeight=8
    )
    cmds.columnLayout(adj=True)

    UI["selected_edges_label"] = cmds.text(
        label="Selected Edges: None",
        align="left"
    )
    UI["set_course_btn"] = cmds.button(
        label="Set Course Edge Loop",
        command=lambda *_: set_selected_edges_to_course(),
        enable=False,
        height=32,
        annotation="Select edges in the viewport, then click to mark them as course edges (horizontal rows). Perpendicular edges are automatically marked as wale edges."
    )

    cmds.separator(height=8, style="none")

    UI["selected_faces_label"] = cmds.text(
        label="Selected Faces: None",
        align="left"
    )

    UI["stitch_type_menu"] = cmds.optionMenu(label="Stitch Type")
    for stitch_type in ["knit", "purl", "yarn-over", "increase", "decrease"]:
        cmds.menuItem(label=stitch_type)

    UI["set_stitch_btn"] = cmds.button(
        label="Set Stitch Type",
        command=lambda *_: _handle_set_stitch_type(),
        enable=False,
        height=32,
        annotation="Select fully-assigned faces, choose a stitch type from the dropdown, then click to apply. Only available on faces whose edges are all labeled."
    )

    UI["flip_row_btn"] = cmds.button(
        label="Flip Row Direction",
        command=lambda *_: _handle_flip_row_direction(),
        enable=False,
        height=32,
        annotation="Flips the knit direction for all stitches in the selected faces' row."
    )

    cmds.separator(height=8, style="none")

    UI["pattern_menu"] = cmds.optionMenu(
        label="Pattern Fill",
        annotation="Choose a fill pattern to apply across all assigned faces."
    )
    for p in ["checker", "rib"]:
        cmds.menuItem(label=p)

    UI["pattern_fill_btn"] = cmds.button(
        label="Apply Pattern Fill",
        command=lambda *_: _handle_pattern_fill(),
        enable=False,
        height=32,
        annotation="Auto-fills all assigned quad faces with the selected pattern: checker alternates k/p in both directions, rib alternates by column only."
    )

    cmds.separator(height=8, style="none")

    UI["reset_btn"] = cmds.button(
        label="RESET Stitch Mesh",
        command=lambda *_: _handle_reset(),
        height=32,
        annotation="Clears all course/wale edge assignments and stitch data, restoring the mesh to its original unassigned state."
    )

    cmds.setParent("..")
    cmds.setParent("..")

    cmds.separator(height=10, style="in")

    # Knit Mesh Generation section
    UI["knit_frame"] = cmds.frameLayout(
        label="Knit Mesh Generation",
        collapsable=False,
        marginWidth=8,
        marginHeight=8
    )
    cmds.columnLayout(adj=True)

    UI["tessellation_slider"] = cmds.intSliderGrp(
        label="Tessellation Level",
        field=True,
        minValue=1,
        maxValue=20,
        fieldMinValue=1,
        fieldMaxValue=100,
        value=1
    )

    UI["tessellate_btn"] = cmds.button(
        label="Tessellate",
        command=lambda *_: _handle_tessellate(),
        enable=False,
        height=32,
        annotation="Subdivides the stitch mesh by the tessellation level above. Higher values = more stitches. A preview mesh is created; the original is preserved."
    )

    UI["restore_btn"] = cmds.button(
        label="Restore Original Mesh",
        command=lambda *_: _handle_restore_mesh(),
        enable=False,
        height=32,
        annotation="Removes the tessellated preview and restores the original base mesh."
    )

    UI["mesh_relax_cb"] = cmds.checkBox(
        label="Stitch Mesh Relaxation",
        value=True,
        changeCommand=lambda value: _handle_mesh_relax_changed(value),
        annotation="When enabled, applies a relaxation pass to the stitch mesh before generating yarn geometry to even out stitch sizing."
    )
    UI["yarn_relax_cb"] = cmds.checkBox(
        label="Yarn Level Relaxation",
        value=True,
        changeCommand=lambda value: _handle_yarn_relax_changed(value),
        annotation="When enabled, applies a physics-based relaxation to the yarn geometry for a more realistic drape."
    )

    UI["generate_btn"] = cmds.button(
        label="Generate Knit Mesh",
        command=lambda *_: _handle_generate(),
        enable=False,
        height=36,
        annotation="Runs the full pipeline: tessellate, optional mesh relaxation, yarn curve generation, and optional yarn-level relaxation."
    )

    cmds.setParent("..")
    cmds.setParent("..")

    cmds.separator(height=10, style="none")

    UI["help_text"] = cmds.text(
        label=(
            "Workflow: Select one mesh → Set Active Mesh → select edge loops "
            "→ Set Course Edge Loop → Apply Pattern Fill → Tessellate → Generate Knit Mesh."
        ),
        align="left",
        wordWrap=True
    )

    cmds.separator(height=10, style="in")

    UI["cancel_btn"] = cmds.button(
        label="Cancel / Close Panel",
        command=lambda *_: close_darn_that_yarn_ui(),
        height=32,
        annotation="Close the Darn that Yarn panel. Your mesh and stitch data are preserved in the scene."
    )


def _register_script_jobs():
    global _SCRIPT_JOB_IDS
    _SCRIPT_JOB_IDS.append(
        cmds.scriptJob(
            event=["SelectionChanged", refresh_ui_state],
            protected=True
        )
    )
    _SCRIPT_JOB_IDS.append(
        cmds.scriptJob(
            uiDeleted=[WORKSPACE_NAME, _on_close],
            protected=True
        )
    )


def _set_status(message: str):
    if "status" in UI and cmds.text(UI["status"], exists=True):
        cmds.text(UI["status"], edit=True, label=message)


def refresh_ui_state(*_):
    has_mesh = bool(STATE.base_mesh)

    if not has_mesh:
        _set_status("Select a polygon mesh and click Set Active Mesh.")
        cmds.text(UI["selected_edges_label"], edit=True, label="Selected Edges: None")
        cmds.text(UI["selected_faces_label"], edit=True, label="Selected Faces: None")
        for key in ("set_course_btn", "set_stitch_btn", "flip_row_btn",
                    "pattern_fill_btn", "tessellate_btn", "restore_btn", "generate_btn"):
            cmds.button(UI[key], edit=True, enable=False)
        return

    info = get_selection_summary()
    edges = info["edges"]
    faces = info["faces"]

    _set_status(f"Active mesh: {STATE.base_mesh}")

    cmds.text(UI["selected_edges_label"], edit=True, label=f"Selected Edges: {len(edges)}")
    cmds.text(UI["selected_faces_label"], edit=True, label=f"Selected Faces: {len(faces)}")

    has_edges = len(edges) > 0
    has_faces = len(faces) > 0
    has_active_faces_selected = are_selected_faces_active()
    has_any_stitch_data = (
        len(STATE.course_edges) > 0
        or len(STATE.active_faces) > 0
        or any(v.name == "COURSE" for v in STATE.edge_map.values())
    )

    cmds.button(UI["set_course_btn"], edit=True, enable=has_edges)
    cmds.button(UI["set_stitch_btn"], edit=True, enable=has_faces and has_active_faces_selected)
    cmds.button(UI["flip_row_btn"], edit=True, enable=has_faces and has_active_faces_selected)
    cmds.button(UI["pattern_fill_btn"], edit=True, enable=has_any_stitch_data)
    cmds.button(UI["tessellate_btn"], edit=True, enable=has_any_stitch_data)
    cmds.button(UI["restore_btn"], edit=True, enable=STATE.is_tessellated)
    cmds.button(UI["generate_btn"], edit=True, enable=has_any_stitch_data)

def show_no_mesh_selected_warning():
    cmds.confirmDialog(
            title='Warning',
            message='Must have object selected',
            button=['Confirm'],
            defaultButton='Confirm'
        )

def _handle_set_mesh():
    mesh = get_selected_mesh_transform()
    if mesh:
        _activate_mesh(mesh)
    else:
        _set_status("No polygon mesh selected. Select one in the viewport first.")


def _handle_set_course_edges():
    edges = get_selection_summary()["edges"]
    set_course_edges(edges)
    refresh_ui_state()


def _handle_set_stitch_type():
    faces = get_selection_summary()["faces"]
    stitch_name = cmds.optionMenu(UI["stitch_type_menu"], query=True, value=True)
    set_selected_faces_stitch_type(stitch_name_to_type_map[stitch_name])
    refresh_ui_state()


def _handle_flip_row_direction():
    faces = get_selection_summary()["faces"]
    flip_row_direction(faces)
    refresh_ui_state()


def _handle_tessellate():
    level = cmds.intSliderGrp(UI["tessellation_slider"], query=True, value=True)
    tessellate_stitch_mesh(level)
    refresh_ui_state()


def _handle_restore_mesh():
    restore_stitch_mesh()
    refresh_ui_state()


def _handle_mesh_relax_changed(value):
    STATE.mesh_relaxation_enabled = bool(value)


def _handle_yarn_relax_changed(value):
    STATE.yarn_relaxation_enabled = bool(value)


def _handle_generate():
    generate_knit_mesh()


def _handle_pattern_fill():
    pattern = cmds.optionMenu(UI["pattern_menu"], query=True, value=True)
    apply_pattern_fill(pattern)
    refresh_ui_state()


def _handle_reset():
    reset_stitch_mesh()
    init_stitch_face_data_structure()
    init_stitch_mesh_data_structures()
    draw_course_edges_as_curves()
    refresh_ui_state()