import maya.cmds as cmds
from lib_python_velan.mayaQT.scripts.dockableWidget import DockableWidgetUIScript
from volume_sys_velan.scripts.volumeSystem import VolumeSystemUI

volumeSystemUICtrl = VolumeSystemUI.workspace_ctrl_name
volumeSystemUIExists = cmds.workspaceControl(volumeSystemUICtrl, query=True, exists=True)


DockableWidgetUIScript(VolumeSystemUI, delete=True)
VolumeSystemUI = DockableWidgetUIScript(VolumeSystemUI)
VolumeSystemUI.refreshUI()

# if volumeSystemUIExists:
# 	DockableWidgetUIScript(VolumeSystemUI, delete=True)
# 	VolumeSystemUI = DockableWidgetUIScript(VolumeSystemUI)
# 	VolumeSystemUI.refreshUI()
# else:
# 	VolumeSystemUI = DockableWidgetUIScript(VolumeSystemUI)
# 	VolumeSystemUI.refreshUI()