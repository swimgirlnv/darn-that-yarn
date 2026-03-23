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
    mesh = get_selected_mesh_transform()
    if mesh:
        STATE.selected_mesh = mesh
        _set_status(f"Ready. Mesh selected: {mesh}")
        close_darn_that_yarn_ui()
        print("show_darn_that_yarn_ui CALLED")

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
        init_stitch_mesh_data_structures()
        init_stitch_face_data_structure()
        draw_course_edges_as_curves()
        refresh_ui_state()
    else:
        show_no_mesh_selected_warning()


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
        command=lambda *_: set_selected_edges_to_course(),
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

    UI["restore_btn"] = cmds.button(
        label="Restore Original Mesh",
        command=lambda *_: _handle_restore_mesh(),
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
    print("REFRESH UI CALLED!")
    info = get_selection_summary()

    edges = info["edges"]
    faces = info["faces"]

    mesh = STATE.selected_mesh
    _set_status(f"Active mesh: {mesh}")

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

    has_edges = len(edges) > 0
    has_faces = len(faces) > 0
    has_active_faces_selected = are_selected_faces_active()
    has_any_stitch_data = len(STATE.course_edges) > 0 or len(STATE.active_faces) > 0

    cmds.button(UI["set_course_btn"], edit=True, enable=has_edges)
    cmds.button(UI["set_stitch_btn"], edit=True, enable=has_faces and has_active_faces_selected)
    cmds.button(UI["flip_row_btn"], edit=True, enable=has_faces and has_active_faces_selected)
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


def _handle_reset():
    reset_stitch_mesh()
    init_stitch_face_data_structure()
    init_stitch_mesh_data_structures()
    draw_course_edges_as_curves()
    refresh_ui_state()