import os
import sys

import maya.api.OpenMaya as om
import maya.cmds as cmds

PLUGIN_NAME = "DarnThatYarn"
MENU_NAME = "DarnThatYarnMenu"
MENU_LABEL = "Darn that Yarn!"

# Add the repo's /scripts directory to sys.path so Maya can import our package
_THIS_DIR = os.path.dirname(__file__)
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, ".."))
_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "scripts")

if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from darn_that_yarn.ui.main_window import show_darn_that_yarn_ui, close_darn_that_yarn_ui


def _delete_menu():
    if cmds.menu(MENU_NAME, exists=True):
        cmds.deleteUI(MENU_NAME)


def _create_menu():
    _delete_menu()

    main_window = "MayaWindow"
    cmds.menu(MENU_NAME, label=MENU_LABEL, parent=main_window, tearOff=True)
    cmds.menuItem(
        label="Open Authoring Tool",
        parent=MENU_NAME,
        command=lambda *_: show_darn_that_yarn_ui()
    )
    cmds.menuItem(divider=True)
    cmds.menuItem(
        label="Close Authoring Tool",
        parent=MENU_NAME,
        command=lambda *_: close_darn_that_yarn_ui()
    )


def initializePlugin(plugin_obj):
    plugin = om.MFnPlugin(plugin_obj, "Rebecca Waterson + Rose Kelly", "0.1.0", "Any")
    _create_menu()
    om.MGlobal.displayInfo(f"{PLUGIN_NAME} loaded.")


def uninitializePlugin(plugin_obj):
    plugin = om.MFnPlugin(plugin_obj)
    close_darn_that_yarn_ui()
    _delete_menu()
    om.MGlobal.displayInfo(f"{PLUGIN_NAME} unloaded.")