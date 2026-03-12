import maya.cmds as cmds

from darn_that_yarn.core.selection import get_selection_summary, get_selected_mesh_transform
from darn_that_yarn.core.state import STATE
from darn_that_yarn.commands.stitch_commands import (
    set_course_edges,
    set_stitch_type,
    flip_row_direction,
    tessellate_stitch_mesh,
    generate_knit_mesh,
    reset_stitch_mesh,
)

WINDOW_NAME = "DarnThatYarnWindow"
WORKSPACE_NAME = "DarnThatYarnWorkspaceControl"

_SCRIPT_JOB_IDS = []

UI = {}


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
        initialHeight=620
    )

    content = cmds.columnLayout(adj=True, parent=WORKSPACE_NAME)
    _build_ui(content)
    _register_script_jobs()
    refresh_ui_state()

    mesh = get_selected_mesh_transform()
    if mesh:
        STATE.selected_mesh = mesh
        _set_status(f"Ready. Mesh selected: {mesh}")
    else:
        _set_status("Select one polygon mesh to begin.")


def _build_ui(parent):
    cmds.columnLayout(adj=True, parent=parent)

    UI["title"] = cmds.text(
        label="Darn that Yarn!",
        align="center",
        height=30,
        font="boldLabelFont"
    )

    UI["status"] = cmds.text(
        label="Select one polygon mesh to begin.",
        align="left",
        height=24
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
        command=lambda *_: _handle_set_course_edges(),
        enable=False,
        height=32
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
        height=32
    )

    UI["flip_row_btn"] = cmds.button(
        label="Flip Row Direction",
        command=lambda *_: _handle_flip_row_direction(),
        enable=False,
        height=32
    )

    UI["reset_btn"] = cmds.button(
        label="RESET Stitch Mesh",
        command=lambda *_: _handle_reset(),
        height=32
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
        height=32
    )

    UI["mesh_relax_cb"] = cmds.checkBox(
        label="Stitch Mesh Relaxation",
        value=True,
        changeCommand=lambda value: _handle_mesh_relax_changed(value)
    )
    UI["yarn_relax_cb"] = cmds.checkBox(
        label="Yarn Level Relaxation",
        value=True,
        changeCommand=lambda value: _handle_yarn_relax_changed(value)
    )

    UI["generate_btn"] = cmds.button(
        label="Generate Knit Mesh",
        command=lambda *_: _handle_generate(),
        enable=False,
        height=36
    )

    cmds.setParent("..")
    cmds.setParent("..")

    cmds.separator(height=10, style="none")

    UI["help_text"] = cmds.text(
        label=(
            "Workflow: Select one mesh → select edge loops → Set Course Edge Loop "
            "→ tessellate → generate knit mesh."
        ),
        align="left",
        wordWrap=True
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
    info = get_selection_summary()

    edges = info["edges"]
    faces = info["faces"]
    mesh = info["mesh"]

    if mesh:
        STATE.selected_mesh = mesh

    cmds.text(
        UI["selected_edges_label"],
        edit=True,
        label=f"Selected Edges: {len(edges)}"
    )
    cmds.text(
        UI["selected_faces_label"],
        edit=True,
        label=f"Selected Faces: {len(faces)}"
    )

    has_mesh = mesh is not None
    has_edges = len(edges) > 0
    has_faces = len(faces) > 0
    has_any_stitch_data = len(STATE.course_edges) > 0 or len(STATE.active_faces) > 0

    cmds.button(UI["set_course_btn"], edit=True, enable=has_mesh and has_edges)
    cmds.button(UI["set_stitch_btn"], edit=True, enable=has_mesh and has_faces)
    cmds.button(UI["flip_row_btn"], edit=True, enable=has_mesh and has_faces)
    cmds.button(UI["tessellate_btn"], edit=True, enable=has_any_stitch_data)
    cmds.button(UI["generate_btn"], edit=True, enable=has_any_stitch_data)

    if not has_mesh:
        _set_status("Select exactly one polygon mesh.")
    else:
        _set_status(f"Active mesh: {mesh}")


def _handle_set_course_edges():
    edges = get_selection_summary()["edges"]
    set_course_edges(edges)
    refresh_ui_state()


def _handle_set_stitch_type():
    faces = get_selection_summary()["faces"]
    stitch_type = cmds.optionMenu(UI["stitch_type_menu"], query=True, value=True)
    set_stitch_type(faces, stitch_type)
    refresh_ui_state()


def _handle_flip_row_direction():
    faces = get_selection_summary()["faces"]
    flip_row_direction(faces)
    refresh_ui_state()


def _handle_tessellate():
    level = cmds.intSliderGrp(UI["tessellation_slider"], query=True, value=True)
    tessellate_stitch_mesh(level)
    refresh_ui_state()


def _handle_mesh_relax_changed(value):
    STATE.mesh_relaxation_enabled = bool(value)


def _handle_yarn_relax_changed(value):
    STATE.yarn_relaxation_enabled = bool(value)


def _handle_generate():
    generate_knit_mesh()


def _handle_reset():
    reset_stitch_mesh()
    refresh_ui_state()