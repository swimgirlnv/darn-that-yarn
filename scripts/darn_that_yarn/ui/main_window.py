import os

import maya.cmds as cmds
import maya.mel as mel

from darn_that_yarn.core.selection import get_selection_summary, get_selected_mesh_transform
from darn_that_yarn.core.state import STATE
from darn_that_yarn.commands.yarn_material import create_yarn_material_with_texture, clean_yarn_UVs, set_texture_image, assign_material_to_yarn_by_name
from darn_that_yarn.commands.stitch_commands import (
    set_course_edges,
    set_stitch_type,
    flip_row_direction,
    tessellate_stitch_mesh,
    restore_stitch_mesh,
    generate_knit_mesh,
    set_yarn_thickness,
    reset_stitch_mesh,
    validate_stitch_mesh,
    init_stitch_face_data_structure,
    init_stitch_mesh_data_structures,
    draw_course_edges_as_curves,
    set_selected_edges_to_course,
    are_selected_faces_active,
    set_selected_faces_stitch_type,
    apply_pattern_fill,
    get_selected_faces_edge_num,
    flip_selected_faces_stitch_type,
    StitchType
)

WINDOW_NAME = "DarnThatYarnWindow"
WORKSPACE_NAME = "DarnThatYarnWorkspaceControl"

_SCRIPT_JOB_IDS = []

UI = {}
_YARN_ONLY_ACTIVE = False

_UI_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_UI_DIR, "..", "..", ".."))


def _repo_asset_path(filename):
    return os.path.join(_REPO_ROOT, filename).replace("\\", "/")


def _node_exists(node):
    return bool(node and cmds.objExists(node))


def _set_node_visible(node, visible):
    if _node_exists(node):
        try:
            cmds.setAttr(f"{node}.visibility", bool(visible))
        except Exception:
            pass


def _set_yarn_nodes_visible(visible):
    for prefix in (
        "yarn_row_",
        "yarn_tube_row_",
        "yarn_fabric",
        "yarn_tube_fabric",
        "yarn_spiral",
        "yarn_tube_spiral",
    ):
        for node in cmds.ls(prefix + "*", type="transform") or []:
            _set_node_visible(node, visible)


def _iter_authoring_nodes():
    seen = set()
    for node in (
        STATE.selected_mesh,
        STATE.base_mesh,
        STATE.preview_mesh,
        STATE.t_mesh,
        STATE.smoothed_mesh,
        "edge_type_indicator_grp",
        "t_edge_type_indicator_grp",
    ):
        if _node_exists(node) and node not in seen:
            seen.add(node)
            yield node

    for pattern in (
        "*_tess_preview*",
        "*_base_relaxed_preview*",
        "*_smooth_target*",
        "edge_type_indicator_grp*",
        "t_edge_type_indicator_grp*",
    ):
        for node in cmds.ls(pattern, type="transform") or []:
            if node not in seen:
                seen.add(node)
                yield node


def _set_authoring_nodes_visible(visible):
    for node in _iter_authoring_nodes():
        _set_node_visible(node, visible)

stitch_name_to_type_map = { "knit": StitchType.KNIT,
                            "purl": StitchType.PURL,
                            "yarn-over": StitchType.YARNOVER,
                            "increase": StitchType.INCREASE,
                            "decrease": StitchType.DECREASE}

PATTERN_PREVIEWS = {
    "stockinette": (
        "Stockinette",
        "K K K K\nK K K K\nK K K K",
        "All assigned quad faces become knit stitches."
    ),
    "checker": (
        "Seed checker",
        "K P K P\nP K P K\nK P K P",
        "Alternates knit and purl by row and column."
    ),
    "rib": (
        "Rib columns",
        "K P K P\nK P K P\nK P K P",
        "Alternates knit and purl by column."
    ),
    "wide_rib": (
        "Wide rib",
        "K K P P\nK K P P\nK K P P",
        "Two-column knit/purl ribbing."
    ),
    "garter": (
        "Garter rows",
        "K K K K\nP P P P\nK K K K",
        "Alternates knit and purl by row."
    ),
    "basket": (
        "Basket weave",
        "K K P P\nK K P P\nP P K K",
        "Alternates two-by-two knit and purl blocks."
    ),
}

PATTERN_ORDER = ("stockinette", "checker", "rib", "wide_rib", "garter", "basket")
PATTERN_ICONS = {
    "checker": "checkeredYarn.png",
    "rib": "ribbedKnit.png",
}
PATTERN_COLORS = {
    "stockinette": (0.24, 0.34, 0.30),
    "checker": (0.25, 0.35, 0.42),
    "rib": (0.32, 0.29, 0.38),
    "wide_rib": (0.36, 0.31, 0.26),
    "garter": (0.29, 0.33, 0.36),
    "basket": (0.34, 0.30, 0.32),
}


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

    content = cmds.scrollLayout(
        childResizable=True,
        parent=WORKSPACE_NAME,
        verticalScrollBarThickness=16
    )
    _build_ui(content)
    _register_script_jobs()

    mesh = get_selected_mesh_transform()
    # prevent user from selecting curves that display changes to stitches and edges
    mel.eval('selectType -nurbsCurve false;')
    if mesh:
        _activate_mesh(mesh)
    else:
        refresh_ui_state()


def _activate_mesh(mesh):
    previous_mesh = STATE.selected_mesh
    if previous_mesh and previous_mesh != mesh and cmds.objExists(previous_mesh):
        cmds.showHidden(previous_mesh)

    STATE.selected_mesh = mesh
    STATE.base_mesh = mesh
    if cmds.objExists(mesh):
        cmds.showHidden(mesh)
        cmds.select(mesh, replace=True)

    _set_status(f"Active mesh: {mesh}")
    init_stitch_mesh_data_structures()
    init_stitch_face_data_structure()
    draw_course_edges_as_curves()
    refresh_ui_state()


def _build_ui(parent):
    UI["main_column"] = cmds.columnLayout(adj=True, parent=parent)

    UI["title"] = cmds.text(
        label="Darn that Yarn",
        align="center",
        height=28,
        font="boldLabelFont"
    )
    UI["subtitle"] = cmds.text(
        label="Build a stitch mesh, choose a pattern, then generate yarn.",
        align="center",
        height=20,
        wordWrap=True
    )

    UI["status"] = cmds.text(
        label="Select a polygon mesh and click Set Active Mesh.",
        align="left",
        height=34,
        wordWrap=True
    )
    UI["validation_status"] = cmds.text(
        label="Mesh check: select an active mesh.",
        align="left",
        height=34,
        wordWrap=True
    )

    cmds.separator(height=8, style="in")

    UI["mesh_frame"] = cmds.frameLayout(
        label="1. Choose Mesh",
        collapsable=True,
        marginWidth=8,
        marginHeight=8
    )
    cmds.columnLayout(adj=True)
    cmds.text(
        label="Select the garment or cylinder mesh in the viewport.",
        align="left",
        wordWrap=True
    )
    UI["set_mesh_btn"] = cmds.button(
        label="Set Active Mesh",
        command=lambda *_: _handle_set_mesh(),
        height=32,
        annotation="Select a polygon mesh in the viewport, then click this to begin."
    )
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.separator(height=8, style="in")

    # Stitch Mesh Generation section
    UI["stitch_frame"] = cmds.frameLayout(
        label="2. Label Stitch Direction",
        collapsable=True,
        marginWidth=8,
        marginHeight=8
    )
    cmds.columnLayout(adj=True)
    cmds.text(
        label="Select course edge loops. Course edges run around the rows; wale edges are filled in automatically.",
        align="left",
        wordWrap=True
    )

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

    cmds.text(
        label="Optional per-face stitch override",
        align="left",
        font="boldLabelFont"
    )
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
        label="Flip Selected Stitches",
        command=lambda *_: _handle_flip_row_direction(),
        enable=False,
        height=32,
        annotation="Flips the knit direction for all stitches in the selected faces."
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

    UI["pattern_frame"] = cmds.frameLayout(
        label="3. Choose Knit Pattern",
        collapsable=True,
        marginWidth=8,
        marginHeight=8
    )
    cmds.columnLayout(adj=True)
    cmds.text(
        label="Pick a fill pattern for all assigned quad faces. K = knit, P = purl.",
        align="left",
        wordWrap=True
    )
    cmds.rowColumnLayout(
        numberOfColumns=3,
        columnWidth=[(1, 86), (2, 86), (3, 86)],
        columnSpacing=[(1, 6), (2, 6), (3, 6)],
        rowSpacing=[(1, 6), (2, 6)]
    )
    for pattern in PATTERN_ORDER:
        title, _preview, note = PATTERN_PREVIEWS[pattern]
        icon = PATTERN_ICONS.get(pattern)
        button_args = {
            "label": title,
            "style": "iconAndTextVertical" if icon else "textOnly",
            "command": lambda *_args, pattern=pattern: _handle_pattern_fill(pattern),
            "enable": False,
            "height": 72,
            "width": 86,
            "bgc": PATTERN_COLORS.get(pattern, (0.25, 0.35, 0.42)),
            "annotation": note,
        }
        if icon:
            button_args["image1"] = _repo_asset_path(icon)
        UI[f"{pattern}_pattern_btn"] = cmds.iconTextButton(**button_args)
    cmds.setParent("..")
    UI["pattern_preview"] = cmds.text(
        label="Pattern preview: choose a pattern after assigning course/wale edges.",
        align="left",
        height=50,
        wordWrap=True
    )
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.separator(height=10, style="in")

    # Knit Mesh Generation section
    UI["knit_frame"] = cmds.frameLayout(
        label="4. Tessellate And Generate Yarn",
        collapsable=True,
        marginWidth=8,
        marginHeight=8
    )
    cmds.columnLayout(adj=True)
    cmds.text(
        label="Tessellate controls stitch density. Generate creates yarn tubes; thickness can be adjusted afterward.",
        align="left",
        wordWrap=True
    )

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
        value=STATE.mesh_relaxation_enabled,
        changeCommand=lambda value: _handle_mesh_relax_changed(value),
        annotation="When enabled, applies a relaxation pass to the stitch mesh before generating yarn geometry to even out stitch sizing."
    )
    UI["yarn_relax_cb"] = cmds.checkBox(
        label="Yarn Level Relaxation",
        value=True,
        changeCommand=lambda value: _handle_yarn_relax_changed(value),
        annotation="When enabled, applies a physics-based relaxation to the yarn geometry for a more realistic drape."
    )

    UI["yarn_radius_slider"] = cmds.floatSliderGrp(
        label="Yarn Radius",
        field=True,
        precision=3,
        step=0.001,
        minValue=0.005,
        maxValue=0.08,
        fieldMinValue=0.001,
        fieldMaxValue=0.20,
        value=STATE.yarn_radius,
        changeCommand=lambda value: _handle_yarn_radius_changed(value),
        annotation="Controls yarn tube radius. 0.020 is the default visual target; after generation, changing this rebuilds the yarn tube meshes from the hidden curves."
    )

    UI["generate_btn"] = cmds.button(
        label="Generate Knit Mesh",
        command=lambda *_: _handle_generate(),
        enable=False,
        height=36,
        annotation="Runs the full pipeline: tessellate, optional mesh relaxation, yarn curve generation, and optional yarn-level relaxation."
    )

    cmds.separator(height=8, style="none")

    UI["yarn_only_btn"] = cmds.button(
        label="Show Yarn Only",
        command=lambda *_: _handle_yarn_only_toggle(),
        enable=False,
        height=30,
        annotation="Hides the original mesh, tessellation preview, and edge guide curves so only generated yarn remains visible. Click again to restore authoring nodes."
    )

    cmds.setParent("..")
    cmds.setParent("..")

    cmds.separator(height=10, style="none")

    # Yarn Texturing section
    UI["file_frame"] = cmds.frameLayout(
        label="Generate Yarn Material",
        collapsable=True,
        marginWidth=8,
        marginHeight=8
    )
    cmds.columnLayout(adj=True)

    cmds.text(label="Select a texture file to apply to yarn material", align="left")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(240, 100))

    UI["texture_path_field"] = cmds.textField(
        text="",
        editable=False,
        placeholderText="No file selected"
    )

    UI["browse_texture_btn"] = cmds.button(
        label="Browse",
        height=30,
        command=lambda *_: _handle_browse_texture_file()
    )

    cmds.setParent("..")

    UI["apply_yarn_texture_btn"] = cmds.button(
        label="Apply Yarn Material",
        height=30,
        enable=False,
        command=lambda *_: _handle_material_apply()
    )


    cmds.setParent("..")
    cmds.setParent("..")

    cmds.separator(height=10, style="none")

    UI["help_text"] = cmds.text(
        label=(
            "Workflow: 1 Set mesh | 2 Label course edges | 3 Choose knit pattern | 4 Tessellate and generate."
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


def _set_pattern_preview(pattern: str):
    if "pattern_preview" not in UI or not cmds.text(UI["pattern_preview"], exists=True):
        return
    title, preview, note = PATTERN_PREVIEWS.get(pattern, PATTERN_PREVIEWS["checker"])
    cmds.text(
        UI["pattern_preview"],
        edit=True,
        label=f"Selected: {title}\n{preview}\n{note}"
    )


def refresh_ui_state(*_):
    has_mesh = bool(STATE.base_mesh)

    if not has_mesh:
        _set_status("Select a polygon mesh and click Set Active Mesh.")
        cmds.text(UI["validation_status"], edit=True, label="Mesh check: select an active mesh.")
        cmds.text(UI["selected_edges_label"], edit=True, label="Selected Edges: None")
        cmds.text(UI["selected_faces_label"], edit=True, label="Selected Faces: None")
        for pattern in PATTERN_ORDER:
            cmds.iconTextButton(UI[f"{pattern}_pattern_btn"], edit=True, enable=False)
        for key in ("set_course_btn", "set_stitch_btn", "flip_row_btn",
                    "tessellate_btn", "restore_btn", "generate_btn", "apply_yarn_texture_btn",
                    "yarn_only_btn"):
            cmds.button(UI[key], edit=True, enable=False)
        _set_pattern_preview(STATE.selected_pattern)
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
    validation = validate_stitch_mesh()
    has_any_stitch_data = (
        len(STATE.course_edges) > 0
        or len(STATE.active_faces) > 0
        or any(v.name == "COURSE" for v in STATE.edge_map.values())
    )
    yarn_mesh_generated = STATE.yarn_mesh != None

    # only display possible stitch types by edge number in dropdown
    sel_faces_num_edges = get_selected_faces_edge_num()
    items = cmds.optionMenu(UI["stitch_type_menu"], query=True, itemListLong=True) or []
    for item in items:
        cmds.deleteUI(item)
    if sel_faces_num_edges == 5:
        stitch_types = ["increase", "decrease"]
    elif sel_faces_num_edges == 4:
        stitch_types = ["knit", "purl", "yarn-over"]
    else:
        stitch_types = []
    for stitch_type in stitch_types:
        cmds.menuItem(label=stitch_type, parent=UI["stitch_type_menu"])

    cmds.button(UI["set_course_btn"], edit=True, enable=has_edges)
    cmds.button(UI["set_stitch_btn"], edit=True, enable=has_faces and has_active_faces_selected)
    cmds.button(UI["flip_row_btn"], edit=True, enable=has_faces and has_active_faces_selected)
    for pattern in PATTERN_ORDER:
        cmds.iconTextButton(UI[f"{pattern}_pattern_btn"], edit=True, enable=has_any_stitch_data)
    cmds.button(UI["tessellate_btn"], edit=True, enable=has_any_stitch_data)
    cmds.button(UI["restore_btn"], edit=True, enable=STATE.is_tessellated)
    cmds.button(UI["apply_yarn_texture_btn"], edit=True, enable=yarn_mesh_generated)
    cmds.button(UI["generate_btn"], edit=True, enable=validation.can_generate)
    cmds.button(
        UI["yarn_only_btn"],
        edit=True,
        enable=yarn_mesh_generated,
        label="Restore Authoring View" if _YARN_ONLY_ACTIVE else "Show Yarn Only",
    )
    cmds.text(UI["validation_status"], edit=True, label=validation.summary())
    _set_pattern_preview(STATE.selected_pattern)

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
    flip_selected_faces_stitch_type()
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


def _handle_yarn_radius_changed(value):
    set_yarn_thickness(value)


def _handle_generate():
    generate_knit_mesh()
    refresh_ui_state()


def _handle_yarn_only_toggle():
    global _YARN_ONLY_ACTIVE
    if not STATE.yarn_mesh:
        return

    _YARN_ONLY_ACTIVE = not _YARN_ONLY_ACTIVE
    _set_authoring_nodes_visible(not _YARN_ONLY_ACTIVE)
    _set_yarn_nodes_visible(True)
    _set_status("Yarn-only view." if _YARN_ONLY_ACTIVE else f"Active mesh: {STATE.base_mesh}")
    refresh_ui_state()


def _handle_pattern_fill(pattern=None):
    if pattern is None:
        pattern = STATE.selected_pattern
    STATE.selected_pattern = pattern
    _set_pattern_preview(pattern)
    apply_pattern_fill(pattern)
    refresh_ui_state()


def _handle_reset():
    reset_stitch_mesh()
    init_stitch_mesh_data_structures()
    init_stitch_face_data_structure()
    draw_course_edges_as_curves()
    refresh_ui_state()

def _handle_browse_texture_file():
    result = cmds.fileDialog2(
        fileMode=1,  # 1 = single file
        caption="Select Yarn Texture",
        fileFilter="Images (*.png *.jpg *.jpeg *.tif *.tiff *.exr);;All Files (*.*)"
    )

    if not result:
        return

    file_path = result[0]

    if "texture_path_field" in UI and cmds.textField(UI["texture_path_field"], exists=True):
        cmds.textField(UI["texture_path_field"], edit=True, text=file_path)

    STATE.yarn_texture_path = file_path  # optional if you want to store it
    if STATE.yarn_material:
        set_texture_image(STATE.yarn_material, STATE.yarn_texture_path)

def _handle_material_apply():
    if not STATE.yarn_material:
        create_yarn_material_with_texture(STATE.yarn_texture_path)
    if not STATE.yarn_uvs_clean:
        clean_yarn_UVs()
    assign_material_to_yarn_by_name(STATE.yarn_material)
