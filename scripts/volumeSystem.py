'''
"This project is licensed under the MIT License. 
This means you are free to use, modify, distribute, 
and sublicense the code with minimal restrictions. 
The software is provided 'as is,' without warranty of any kind, 
express or implied, including but not limited to warranties of merchantability, 
fitness for a particular purpose, and non-infringement. 
For more details, please refer to the full license text included in this repository."



DESCRIPTION:
    Maya dockable window
USAGE:
    from dockableWidget import DockableWidgetUIScript
    from volumeSystem import VolumeSystemUI

    # Create
    VolumeSystemUI = DockableWidgetUIScript(VolumeSystemUI)

    # Delete
    DockableWidgetUIScript(VolumeSystemUI, delete=True)

    # Query
    import maya.cmds as cmds

    uiExists = cmds.workspaceControl(VolumeSystemUI.workspace_ctrl_name, query=True, exists=True)
    print('UI Exists: %s') % uiExists

    # If user closes the workspaceControl it is not deleted, but hidden
    from dockableWidget import findControl

    ctrl = VolumeSystemUI.workspace_ctrl_name

    # Show/Hide workspaceControlv
    cmds.workspaceControl(ctrl, edit=True, restore=True)
    cmds.workspaceControl(ctrl, edit=True, visible=False)
    cmds.workspaceControl(ctrl, edit=True, visible=True)
'''

####TODO##
# showCurves()
# filterType for 'L', 'R', 'M'
# undoChunk()
# buildGuidesUI: use filterGuideList
# filter by selected - selected guides option is locking up maya (filterGuideList: selectionChangedEvent)
# vpStrSelect
# VolumeSystemUI_guideDialog: - use callbacks for button enabling


import sys
version = sys.version
version_info = sys.version_info
pythonVersion = version_info.major
print('pythonVersion: %s' % pythonVersion)

from functools import partial
from collections import OrderedDict
import json
import re, os, time

import maya.cmds as cmds
import maya.OpenMaya as om
import maya.api.OpenMaya as om2
from maya.api.OpenMaya import MMatrix
from maya.api import OpenMayaAnim

from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *

from lib_python_velan.mayaQT.scripts.dockableWidget import DockableWidget
from lib_python_velan.mayaQT.scripts.filtersWidget import SearchFiltersFrame
from lib_python_velan.mayaQT.scripts.collapsibleWidget import CollapsibleListWidget
from lib_python_velan.mayaQT.scripts import styles as styles


if not cmds.pluginInfo('quatNodes', q=True, loaded=True):
    cmds.loadPlugin('quatNodes')

class VolumeSystemUI(DockableWidget):
    # Unique name
    ctrl_obj_name = 'VolumeSystemUIWidget'

    # All workspace controls are named this way by Maya
    workspace_ctrl_name = ctrl_obj_name + 'WorkspaceControl'

    # Tile for your workspace control
    window_title = 'Volume System UI'

    def __init__(self, parent=None, **kwargs):
        if self.registry.getInstance(VolumeSystemUI) is not None:
            print('\nREGISTRY WARNING:')
            print('Cannot create multiple UI instances for any single type.\n'
                  'Therefore the old instance will be replaced in the registry.\n')
        super(VolumeSystemUI, self).__init__(parent=parent)

        # setting the minimum size
        width = 400
        height = 333
        self.setMinimumSize(width, height)

        self.guides = None

        self.buildGuideDict()

        self.guideSearchFiltersFrame = {}

        self.guideTypeFilterCheckBox = {}

        self.guideCollapsibleListWidget = {}
        self.guideCollapsibleListWidgetMenu = {}

        # legacy start
        self.sliderParDict    = None
        self.stretchParDict   = None
        self.gdeBackupDict    = OrderedDict()
        self.selSystemGlob    = None
        self.selSystemGlobSld = None
        self.selSystemGlobStr = None
        self.selGdeGlobSld    = None
        self.selGdeGlobStr    = None
        self.enableCommitSld  = False
        self.enableCommitStr  = False
        # legacy end

        self.buildUI()
        self.initCallbacks()


    # UI
    def buildGuideDict(self):
        '''
        '''
        # start = time.perf_counter()
        transforms = cmds.ls('Hbfr_*GuideRoot', type='transform')
        self.guides = {}
        self.guides['all'] = []
        self.guides['stretch'] = []
        self.guides['slider'] = []
        # filterType for 'L', 'R', 'M'
        #self.guides['L'] = []
        #self.guides['R'] = []
        #self.guides['M'] = []
        for transform in transforms:
            isGuide = cmds.attributeQuery('guideType', node=transform, exists=True)
            if isGuide:
                guideType = cmds.getAttr(transform + '.guideType')
                if guideType == 'slider':
                    self.guides['all'].append(transform)
                    self.guides['slider'].append(transform)
                if guideType == 'stretch':
                    self.guides['all'].append(transform)
                    self.guides['stretch'].append(transform)

        sorted(self.guides['all'])
        sorted(self.guides['stretch'])
        sorted(self.guides['slider'])

        # end = time.perf_counter()
        #print('self.buildGuideDict()')
        #print(end-start)

        return self.guides

    def buildUI(self):
        '''
        '''
        # Build Main Layout
        self.buildMainLayout()

        # Build Guide List
        self.buildGuidesList()

    def buildMainLayout(self):
        '''
        '''
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(10,10,10,10)

        return self.mainLayout

    def buildGuidesList(self):
        '''
        '''
        self.guidesListLayout = QVBoxLayout()
        self.mainLayout.addLayout(self.guidesListLayout)

        guides = self.guides['all']
        guideTypes = list(self.guides.keys())
        if 'all' in guideTypes:
            guideTypes.remove('all')
        guideTypes = sorted(guideTypes)

        self.guidesListLayout.addWidget(self.buildGuideFilters(guides))
        self.guidesListLayout.addWidget(self.buildGuideTypeFilters(guides, guideTypes))
        self.guidesListLayout.addWidget(self.buildGuideCollapsibleListWidget(guides))

        self.buildGuideListContextMenu(guides)

    def buildGuideListContextMenu(self, guides):
        '''
        '''
        self.guideCollapsibleListWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.guideCollapsibleListWidgetMenu = QMenu()
        self.guideCollapsibleListWidgetMenu.setTearOffEnabled(True)

        self.createGuideCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Create Guide', lambda:self.guideCollapsibleListWidgetMenuCallBack(dialogMode='create'))

        self.guideCollapsibleListWidgetMenu.addSeparator()

        self.expandAllCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Expand All', lambda:self.guideCollapsibleListWidgetExpandCollapseCallBack(setCollapsed=False))
        self.collapseAllCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Collapse All', lambda:self.guideCollapsibleListWidgetExpandCollapseCallBack(setCollapsed=True))

        self.expandAllCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Expand Selected', lambda:self.guideCollapsibleListWidgetExpandCollapseSelectedCallBack(setCollapsed=False))
        self.collapseAllCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Collapse Selected', lambda:self.guideCollapsibleListWidgetExpandCollapseSelectedCallBack(setCollapsed=True))

        self.guideCollapsibleListWidgetMenu.addSeparator()

        self.toggleGuideVisCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Toggle Guide Vis', lambda:self.showGuides())
        self.toggleSystemeVisCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Toggle System Vis', lambda:self.showSystems())

        self.guideCollapsibleListWidgetMenu.addSeparator()

        self.toggleSystemeVisCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Toggle System Vis', lambda:self.showSystems())

        self.guideCollapsibleListWidgetMenu.addSeparator()

        self.mirrorGuidesCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Mirror Guide(s)', lambda:self.mirrorGuideMultiple())

        self.guideCollapsibleListWidgetMenu.addSeparator()

        self.buildFromGuidesCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Build from Guide(s)', lambda:self.buildFromGuide())

        self.guideCollapsibleListWidgetMenu.addSeparator()

        self.deleteSelectedGuidesCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Delete Selected Guide(s)', lambda:self.deleteMultiple())

        self.guideCollapsibleListWidgetMenu.addSeparator()

        self.selectAllGuidesCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Select All Guides', lambda:self.selectAllGuideRoot())

        self.guideCollapsibleListWidgetMenu.addSeparator()

        self.alignSelectedGuidesToStartCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Align Selected Guide Hbfr(s) to Start', lambda:self.alignSelctGuideRoot())
        self.alignAllGuidesToStartCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Align All Guide Hbfr(s) to Start', lambda:self.alignAllGuideRoot())
        self.alignAllGuidesToWorldCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Align All Guide Hbfr(s) to World', lambda:self.alignGuideWorld())

        self.guideCollapsibleListWidgetMenu.addSeparator()

        self.fixTrackersCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Fix Tracker(s)', lambda:self.fixConstrainSldTracker())

        self.guideCollapsibleListWidgetMenu.addSeparator()

        # globalScale

        self.saveSelectedGuidesCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Save Guides', lambda:self.backupGuideDecide())
        self.loadGuidesCollapsibleListWidgetMenuItem = self.guideCollapsibleListWidgetMenu.addAction('Load Guides', lambda:self.restoreGuides())

        self.guideCollapsibleListWidget.customContextMenuRequested.connect(partial(self.guideCollapsibleListWidgetContextMenuCallBack))

    def buildGuideFilters(self, guides):
        '''
        '''
        self.guideSearchFiltersFrame = SearchFiltersFrame(self,
                                                                inputList=guides,
                                                                wildcardRequired=False)
        self.guideSearchFiltersFrame.filterResultChanged.connect(partial(self.filterGuideList, guides))

        return self.guideSearchFiltersFrame

    def buildGuideTypeFilters(self, guides, guideTypes):
        '''
        '''
        self.filterTypesFrame = QFrame(self)
        self.filterTypesFrame.setLayout(QVBoxLayout())
        self.filterTypesFrame.setContentsMargins(0, 0, 0, 0)

        self.guideTypesHBoxLayout = QHBoxLayout()
        self.guideTypesHBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.filterTypesFrame.layout().addLayout(self.guideTypesHBoxLayout)

        self.guideTypesHBoxLayout.addWidget(QLabel('Guide Types'))
        for guideType in guideTypes:
            self.guideTypeFilterCheckBox[guideType] = QCheckBox(guideType)
            self.guideTypeFilterCheckBox[guideType].setChecked(True)
            self.guideTypesHBoxLayout.addWidget(self.guideTypeFilterCheckBox[guideType])
            self.guideTypeFilterCheckBox[guideType].clicked.connect(lambda: self.filterGuideList(guides, self.guideSearchFiltersFrame.filterResults))
        self.guideTypesHBoxLayout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.guideTypeFilterCheckBox['expand'] = QCheckBox('Expand / Collapse')
        self.guideTypeFilterCheckBox['expand'].setChecked(False)
        self.guideTypesHBoxLayout.addWidget(self.guideTypeFilterCheckBox['expand'])
        self.guideTypeFilterCheckBox['expand'].clicked.connect(lambda: self.filterGuideList(guides, self.guideSearchFiltersFrame.filterResults))

        self.guideTypesHBoxLayout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

        return self.filterTypesFrame

    def filterGuideList(self, guides, filterResults):
        '''
        DESCRIPTION:
            Filter display result by given list
        '''
        # start = time.perf_counter()

        if not filterResults:
            filterResults = guides

        guideCollapsibleListWidgetItems = self.guideCollapsibleListWidget.getItems()
        for i in range(len(guideCollapsibleListWidgetItems)):
            curItem = self.guideCollapsibleListWidget.item(i)
            curItemWidget = self.guideCollapsibleListWidget.itemWidget(curItem)
            curItemTitle = self.guideCollapsibleListWidget.itemWidget(curItem).title()
            curItemGuideType = cmds.getAttr(curItemTitle + '.guideType')
            setHidden = True
            if curItemTitle in filterResults and self.guideTypeFilterCheckBox[curItemGuideType].isChecked():
                setHidden = False
                curItem.setHidden(setHidden)
                collapsedState = self.guideTypeFilterCheckBox['expand'].isChecked()
                curItemWidget.setCollapsed(not collapsedState)
            else:
                curItem.setHidden(setHidden)

        # time.perf_counter()
        #print('self.filterGuideList(guides, self.guideSearchFiltersFrame.filterResults)')
        #print(end-start)

    def buildGuideCollapsibleListWidget(self, guides):
        '''
        SelectionMode = 0 => NoSelection
        SelectionMode = 1 => SingleSelection
        SelectionMode = 2 => MultiSelection
        SelectionMode = 3 => ExtendedSelection
        SelectionMode = 4 => ContiguousSelection
        '''
        self.guideCollapsibleListWidget = CollapsibleListWidget()
        self.guideCollapsibleListWidget.setSelectionMode(self.guideCollapsibleListWidget.ExtendedSelection)
        self.guideCollapsibleListWidget.setFocusPolicy(Qt.NoFocus)
        self.populateGuideCollapsableListWidget(guides)
        self.guideCollapsibleListWidget.itemSelectionChanged.connect(self.callback_selectedData)

        return self.guideCollapsibleListWidget

    def populateGuideCollapsableListWidget(self, guides):
        '''
        '''
        # start = time.perf_counter()

        for guide in guides:
            setTextColor = None
            if guide in self.guides['stretch']:
                setTextColor = QColor(0.0, 255.0, 255.0)
            elif guide in self.guides['slider']:
                setTextColor = QColor(70.0, 255.0, 0.0)
            else:
                setTextColor = QColor(225.0, 115.0, 100.0)
            self.guideCollapsibleListWidget.makeItem(self.buildGuideFrame(guide), title=str(guide), setTextColor=setTextColor, showExpandCollapseMenu=False, showDeleteMenu=False, collapsed=True)

        # end = time.perf_counter()
        #print('self.populateGuideCollapsableListWidget(guides)')
        #print(end-start)

    def buildGuideFrame(self, guide):
        '''
        '''
        # buildGuideFrame: use callbacks for button enabling
        frame = QFrame(self)
        frame.setLayout(QVBoxLayout())
        frame.setObjectName('frame')
        frame.setStyleSheet('QFrame#frame{background-color:rgb(50,50,50)}')

        guideType = cmds.getAttr(guide + '.guideType')
        if guideType == 'slider':
            sliderHBoxLayout = QHBoxLayout()
            frame.layout().addLayout(sliderHBoxLayout)

            sliderHBoxLayout.addWidget(QLabel('Name'))

            guideName = cmds.getAttr(guide + '.guideName')
            guideNameLineEdit = QLineEdit(guideName)
            sliderHBoxLayout.addWidget(guideNameLineEdit)
            guideNameLineEdit.editingFinished.connect(lambda:self.renameGuide(guide, guideNameLineEdit))

            sliderHBoxLayout.addItem(QSpacerItem(10, 0, QSizePolicy.Minimum, QSizePolicy.Minimum))

            parentPushButton = QPushButton('Parent')
            sliderHBoxLayout.addWidget(parentPushButton)

            parent = cmds.getAttr('%s.guideParent' % (guide))
            parentLineEdit = QLineEdit(parent)
            parentLineEdit.setReadOnly(True)
            parentPushButton.clicked.connect(lambda:self.constrainSldParent(guide, parentLineEdit))

            sliderHBoxLayout.addWidget(parentLineEdit)
            deleteParentButton = QPushButton('X')
            sliderHBoxLayout.addWidget(deleteParentButton)
            deleteParentButton.clicked.connect(lambda:self.delParCon(guide, parentLineEdit))

            sliderHBoxLayout.addItem(QSpacerItem(10, 0, QSizePolicy.Minimum, QSizePolicy.Minimum))

            trackerPushButton = QPushButton('Tracker')
            sliderHBoxLayout.addWidget(trackerPushButton)

            tracker = cmds.getAttr('%s.guideTracker' % (guide))
            trackerLineEdit = QLineEdit(tracker)
            trackerLineEdit.setReadOnly(True)
            sliderHBoxLayout.addWidget(trackerLineEdit)

            deleteTrackerButton = QPushButton('X')
            sliderHBoxLayout.addWidget(deleteTrackerButton)
            deleteTrackerButton.clicked.connect(lambda:self.delTrkCon(guide, trackerLineEdit))

            sliderSettingsHBoxLayout = QHBoxLayout()
            frame.layout().addLayout(sliderSettingsHBoxLayout)

            xyz = cmds.getAttr('%s.XYZ' % (guide))
            rotAxisQLabel = QLabel('Axis')
            rotAxisQLabel.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            sliderSettingsHBoxLayout.addWidget(rotAxisQLabel)
            rotAxisComboBox = QComboBox()
            rotAxisComboBox.addItem('X')
            rotAxisComboBox.addItem('Y')
            rotAxisComboBox.addItem('Z')
            rotAxisComboBox.setCurrentIndex(xyz)
            sliderSettingsHBoxLayout.addWidget(rotAxisComboBox)
            trackerPushButton.clicked.connect(lambda:self.constrainSldTracker(guide, trackerLineEdit, rotAxisComboBox))

            trackerMinRot = cmds.getAttr('%s.trackerMinRot' % (guide))
            startValQLabel = QLabel('Start')
            startValQLabel.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            sliderSettingsHBoxLayout.addWidget(startValQLabel)
            startValDoubleSpinBox = QDoubleSpinBox()
            startValDoubleSpinBox.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            startValDoubleSpinBox.setDecimals(2)
            startValDoubleSpinBox.setSingleStep(1)
            startValDoubleSpinBox.setMinimum(-360.0)
            startValDoubleSpinBox.setMaximum(360.0)
            startValDoubleSpinBox.setValue(trackerMinRot)
            sliderSettingsHBoxLayout.addWidget(startValDoubleSpinBox)

            trackerMaxRot = cmds.getAttr('%s.trackerMaxRot' % (guide))
            endValQLabel = QLabel('End')
            endValQLabel.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            sliderSettingsHBoxLayout.addWidget(endValQLabel)
            endValDoubleSpinBox = QDoubleSpinBox()
            endValDoubleSpinBox.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            endValDoubleSpinBox.setDecimals(2)
            endValDoubleSpinBox.setSingleStep(1)
            endValDoubleSpinBox.setMinimum(-360.0)
            endValDoubleSpinBox.setMaximum(360.0)
            endValDoubleSpinBox.setValue(trackerMaxRot)
            sliderSettingsHBoxLayout.addWidget(endValDoubleSpinBox)

            sliderSettingsHBoxLayout.addItem(QSpacerItem(10, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

            currentValRef = cmds.getAttr('%s.currentValRef' % (guide))
            currentValQLabel = QLabel('Cur')
            currentValQLabel.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            sliderSettingsHBoxLayout.addWidget(currentValQLabel)

            currentValDoubleSpineBox = QDoubleSpinBox()
            currentValDoubleSpineBox.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            currentValDoubleSpineBox.setDecimals
            currentValDoubleSpineBox.setSingleStep(1)
            currentValDoubleSpineBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
            currentValDoubleSpineBox.setMinimum(-180)
            currentValDoubleSpineBox.setValue(currentValRef)
            sliderSettingsHBoxLayout.addWidget(currentValDoubleSpineBox)

            currentValPushButton = QPushButton('<<')
            sliderSettingsHBoxLayout.addWidget(currentValPushButton)
            currentValPushButton.clicked.connect(lambda:self.angleRefresh(guide, currentValDoubleSpineBox))

            sliderSettingsHBoxLayout.addItem(QSpacerItem(10, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

            reverseCheckBoxState = cmds.getAttr('%s.trackerRev' % (guide))
            reverseCheckBox = QCheckBox('+ / -')
            reverseCheckBox.setChecked(reverseCheckBoxState)
            sliderSettingsHBoxLayout.addWidget(reverseCheckBox)

            jntCheckBoxState = cmds.getAttr('%s.sliderJoint' % (guide))
            jntCheckBox = QCheckBox('jnt')
            jntCheckBox.setChecked(jntCheckBoxState)
            sliderSettingsHBoxLayout.addWidget(jntCheckBox)

            doritoCheckBoxState = cmds.getAttr('%s.sliderDorito' % (guide))
            doritoCheckBox = QCheckBox('dor')
            doritoCheckBox.setChecked(doritoCheckBoxState)
            sliderSettingsHBoxLayout.addWidget(doritoCheckBox)

            rotAxisComboBox.activated[int].connect(lambda:self.commitGdeSld(guide, rotAxisComboBox, startValDoubleSpinBox, endValDoubleSpinBox, reverseCheckBox, jntCheckBox, doritoCheckBox))
            startValDoubleSpinBox.valueChanged.connect(lambda:self.commitGdeSld(guide, rotAxisComboBox, startValDoubleSpinBox, endValDoubleSpinBox, reverseCheckBox, jntCheckBox, doritoCheckBox))
            endValDoubleSpinBox.valueChanged.connect(lambda:self.commitGdeSld(guide, rotAxisComboBox, startValDoubleSpinBox, endValDoubleSpinBox, reverseCheckBox, jntCheckBox, doritoCheckBox))
            reverseCheckBox.clicked[bool].connect(lambda:self.commitGdeSld(guide, rotAxisComboBox, startValDoubleSpinBox, endValDoubleSpinBox, reverseCheckBox, jntCheckBox, doritoCheckBox))
            jntCheckBox.clicked[bool].connect(lambda:self.commitGdeSld(guide, rotAxisComboBox, startValDoubleSpinBox, endValDoubleSpinBox, reverseCheckBox, jntCheckBox, doritoCheckBox))
            doritoCheckBox.clicked[bool].connect(lambda:self.commitGdeSld(guide, rotAxisComboBox, startValDoubleSpinBox, endValDoubleSpinBox, reverseCheckBox, jntCheckBox, doritoCheckBox))

        if guideType == 'stretch':
            stretchHBoxLayout = QHBoxLayout()
            frame.layout().addLayout(stretchHBoxLayout)

            stretchHBoxLayout.addWidget(QLabel('Name'))

            guideName = cmds.getAttr(guide + '.guideName')
            guideNameLineEdit = QLineEdit(guideName)
            stretchHBoxLayout.addWidget(guideNameLineEdit)
            guideNameLineEdit.editingFinished.connect(lambda:self.renameGuide(guide, guideNameLineEdit))

            stretchHBoxLayout.addItem(QSpacerItem(10, 0, QSizePolicy.Minimum, QSizePolicy.Minimum))

            startParentPushButton = QPushButton('Start Parent')
            stretchHBoxLayout.addWidget(startParentPushButton)

            startParent = cmds.getAttr('%s.startParent' % (guide))
            startParentLineEdit = QLineEdit(startParent)
            startParentLineEdit.setReadOnly(True)
            startParentPushButton.clicked.connect(lambda:self.constrainStrStart(guide, startParentLineEdit))

            stretchHBoxLayout.addWidget(startParentLineEdit)
            deleteStartParentButton = QPushButton('X')
            stretchHBoxLayout.addWidget(deleteStartParentButton)
            deleteStartParentButton.clicked.connect(lambda:self.delStartCon(guide, startParentLineEdit))

            stretchHBoxLayout.addItem(QSpacerItem(10, 0, QSizePolicy.Minimum, QSizePolicy.Minimum))

            endParentPushButton = QPushButton('End Parent')
            stretchHBoxLayout.addWidget(endParentPushButton)

            endParent = cmds.getAttr('%s.endParent' % (guide))
            endParentLineEdit = QLineEdit(endParent)
            endParentLineEdit.setReadOnly(True)
            endParentPushButton.clicked.connect(lambda:self.constrainStrEnd(guide, endParentLineEdit))
            stretchHBoxLayout.addWidget(endParentLineEdit)

            deleteEndParentButton = QPushButton('X')
            stretchHBoxLayout.addWidget(deleteEndParentButton)
            deleteEndParentButton.clicked.connect(lambda:self.delEndCon(guide, endParentLineEdit))

            stretchSettingsHBoxLayout = QHBoxLayout()
            frame.layout().addLayout(stretchSettingsHBoxLayout)

            twistState = cmds.getAttr('%s.twist' % (guide))
            twistCheckBox = QCheckBox('Twist')
            twistCheckBox.setChecked(twistState)
            stretchSettingsHBoxLayout.addWidget(twistCheckBox)

            stretchSettingsHBoxLayout.addItem(QSpacerItem(10, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

            strDefPosHBoxLayout = QHBoxLayout()
            stretchSettingsHBoxLayout.addLayout(strDefPosHBoxLayout)

            strDefPos = cmds.getAttr('%s.strDefPos' % (guide))
            strDefPosQLabel = QLabel('Str Def Pos')
            strDefPosQLabel.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            strDefPosHBoxLayout.addWidget(strDefPosQLabel)
            strDefPosDoubleSpinBox = QDoubleSpinBox()
            strDefPosDoubleSpinBox.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            strDefPosDoubleSpinBox.setDecimals(1)
            strDefPosDoubleSpinBox.setSingleStep(0.1)
            strDefPosDoubleSpinBox.setMaximum(1.0)
            strDefPosDoubleSpinBox.setValue(strDefPos)
            strDefPosHBoxLayout.addWidget(strDefPosDoubleSpinBox)

            stretchSettingsHBoxLayout.addItem(QSpacerItem(10, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

            enableSnsHBoxLayout = QHBoxLayout()
            stretchSettingsHBoxLayout.addLayout(enableSnsHBoxLayout)

            enableSnsState = cmds.getAttr('%s.enableSns' % (guide))
            enableSnsCheckBox = QCheckBox('Enable SNS')
            enableSnsCheckBox.setChecked(enableSnsState)
            enableSnsHBoxLayout.addWidget(enableSnsCheckBox)

            multiplierHBoxLayout = QHBoxLayout()
            enableSnsHBoxLayout.addLayout(multiplierHBoxLayout)

            snsMultiplier = cmds.getAttr('%s.snsMultiplier' % (guide))
            multiplierQLabel = QLabel('Multiplier')
            multiplierQLabel.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            multiplierHBoxLayout.addWidget(multiplierQLabel)
            multiplierDoubleSpinBox = QDoubleSpinBox()
            multiplierDoubleSpinBox.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            multiplierDoubleSpinBox.setDecimals(2)
            multiplierDoubleSpinBox.setSingleStep(1)
            multiplierDoubleSpinBox.setMinimum(0.01)
            multiplierDoubleSpinBox.setMaximum(50.00)
            multiplierDoubleSpinBox.setValue(snsMultiplier)
            multiplierHBoxLayout.addWidget(multiplierDoubleSpinBox)

            stretchSettingsHBoxLayout.addItem(QSpacerItem(10, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

            miscHBoxLayout = QHBoxLayout()
            stretchSettingsHBoxLayout.addLayout(miscHBoxLayout)

            jntCheckBoxState = cmds.getAttr('%s.stretchJoint' % (guide))
            jntCheckBox = QCheckBox('jnt')
            jntCheckBox.setChecked(jntCheckBoxState)
            miscHBoxLayout.addWidget(jntCheckBox)

            doritoCheckBoxState = cmds.getAttr('%s.stretchDorito' % (guide))
            doritoCheckBox = QCheckBox('dor')
            doritoCheckBox.setChecked(doritoCheckBoxState)
            miscHBoxLayout.addWidget(doritoCheckBox)

            twistCheckBox.clicked[bool].connect(lambda:self.commitGdeStr(guide, twistCheckBox, strDefPosDoubleSpinBox, enableSnsCheckBox, multiplierDoubleSpinBox, jntCheckBox, doritoCheckBox))
            strDefPosDoubleSpinBox.valueChanged.connect(lambda:self.commitGdeStr(guide, twistCheckBox, strDefPosDoubleSpinBox, enableSnsCheckBox, multiplierDoubleSpinBox, jntCheckBox, doritoCheckBox))
            enableSnsCheckBox.clicked[bool].connect(lambda:self.commitGdeStr(guide, twistCheckBox, strDefPosDoubleSpinBox, enableSnsCheckBox, multiplierDoubleSpinBox, jntCheckBox, doritoCheckBox))
            multiplierDoubleSpinBox.valueChanged.connect(lambda:self.commitGdeStr(guide, twistCheckBox, strDefPosDoubleSpinBox, enableSnsCheckBox, multiplierDoubleSpinBox, jntCheckBox, doritoCheckBox))
            jntCheckBox.clicked[bool].connect(lambda:self.commitGdeStr(guide, twistCheckBox, strDefPosDoubleSpinBox, enableSnsCheckBox, multiplierDoubleSpinBox, jntCheckBox, doritoCheckBox))
            doritoCheckBox.clicked[bool].connect(lambda:self.commitGdeStr(guide, twistCheckBox, strDefPosDoubleSpinBox, enableSnsCheckBox, multiplierDoubleSpinBox, jntCheckBox, doritoCheckBox))

        return frame

    def callback_selectedData(self):
        '''
        '''
        selectedItems = []

        items = self.guideCollapsibleListWidget.selectedItems()
        if items:
            for item in items:
                curItemTitle = self.guideCollapsibleListWidget.itemWidget(item).title()
                selectedItems.append(curItemTitle)

        cmds.select(selectedItems)

    def guideCollapsibleListWidgetMenuCallBack(self, dialogMode):
        '''
        '''
        try:
            self.guideDialog.close()
        except:
            pass
        self.guideDialog = VolumeSystemUI_guideDialog(self, dialogMode)
        self.guideDialog.show()

    def guideCollapsibleListWidgetExpandCollapseCallBack(self, setCollapsed):
        '''
        DESCRIPTION:
            Callback for expanding all guides
        '''
        guideCollapsibleListWidgetItems = self.guideCollapsibleListWidget.getItems()
        for i in range(len(guideCollapsibleListWidgetItems)):
            curItem = self.guideCollapsibleListWidget.item(i)
            curItemWidget = self.guideCollapsibleListWidget.itemWidget(curItem)
            curItemWidget.setCollapsed(setCollapsed)

    def guideCollapsibleListWidgetExpandCollapseSelectedCallBack(self, setCollapsed):
        '''
        DESCRIPTION:
            Callback for expanding all guides
        '''
        guideCollapsibleListWidgetItems = self.guideCollapsibleListWidget.selectedItems()
        items = self.guideCollapsibleListWidget.selectedItems()
        if items:
            for item in items:
                curItemWidget = self.guideCollapsibleListWidget.itemWidget(item)
                curItemWidget.setCollapsed(setCollapsed)

    def guideCollapsibleListWidgetContextMenuCallBack(self, point):
        '''
        DESCRIPTION:
            Right click pop up callback method for creating and editing guides
        '''
        self.guideCollapsibleListWidgetMenu.exec_(self.guideCollapsibleListWidget.mapToGlobal(point))

    def refreshUI(self):
        '''
        DESCRIPTION:
            Refreshes the UI with all of the data in the current scene.
        '''
        items = self.guideCollapsibleListWidget.getItems()
        if items:
            try:
                self.guideCollapsibleListWidget.onClearAllRequested()
            except:
                pass

        self.buildGuideDict()
        guides = self.guides['all']
        self.populateGuideCollapsableListWidget(guides)
        self.guideSearchFiltersFrame.updateInputList(guides)
        self.filterGuideList(guides, self.guideSearchFiltersFrame.filterResults)

    def initCallbacks(self):
        '''
        '''
        self.afterOpenCallback = om.MSceneMessage.addCallback(om.MSceneMessage.kAfterOpen,self.refreshCallback)
        self.afterNewCallback = om.MSceneMessage.addCallback(om.MSceneMessage.kAfterNew,self.refreshCallback)
        self.afterImportCallback = om.MSceneMessage.addCallback(om.MSceneMessage.kAfterImport,self.refreshCallback)

    def refreshCallback(self, *args):
        '''
        '''
        self.refreshUI()


    # legacy start


    # Create Guides / Systems
    def createSliderGuide(self, guideName, globScl):
        # SldGuideOrig
        sldGdeOrig = cmds.createNode('transform', n='Orig_'+guideName+'_SldGuideRoot')
        for axis in ['tx','ty','tz','rx','ry','rz','sx','sy','sz']:
            cmds.setAttr(sldGdeOrig+'.'+axis, l=True)

        # SldGuideRoot
        sldGdeRoot = cmds.createNode('transform', n='Hbfr_'+guideName+'_SldGuideRoot', p=sldGdeOrig)
        cmds.addAttr(ci=True, dt='string', sn='guideType')
        cmds.addAttr(ci=True, dt='string', sn='guideName')
        cmds.addAttr(ci=True, dt='string', sn='guideParent')
        cmds.addAttr(ci=True, dt='string', sn='guideTracker')
        cmds.addAttr(ci=True, at='float',  sn='globalScale')
        cmds.addAttr(ci=True, at='float',  sn='trackerMinRot', min=-360, max=360)
        cmds.addAttr(ci=True, at='float',  sn='trackerMaxRot', min=-360, max=360)
        cmds.addAttr(ci=True, at='float',  sn='currentValRef')
        cmds.addAttr(ci=True, at='long',   sn='XYZ', min=0, max=2)
        cmds.addAttr(ci=True, at='bool',   sn='trackerRev', min=0, max=1)
        cmds.addAttr(ci=True, at='bool',   sn='sliderJoint', min=0, max=1)
        cmds.addAttr(ci=True, at='bool',   sn='sliderDorito', min=0, max=1)
        cmds.setAttr('.XYZ', 1)
        cmds.setAttr('.trackerMaxRot', -30.0)
        cmds.setAttr('.guideType', 'slider', type='string', l=True)
        cmds.setAttr('.guideName', guideName, type='string', l=True)
        cmds.setAttr('.globalScale', globScl)
        cmds.setAttr('.trackerRev', False)
        cmds.setAttr('.sliderJoint', True)
        cmds.setAttr('.sliderDorito', False)

        # SldGuideStart
        sldGdeStart = cmds.curve(p=[(0.65043, 0, 0), (0.600919, 0, -0.248908), (0.248908, 0, -0.600919), (0, 0, -0.65043), (-0.248908, 0, -0.600919), (-0.459923, 0, -0.459923), (-0.600919, 0, -0.248908), (-0.65043, 0, 0), (-0.600919, 0, 0.248908), (-0.459923, 0, 0.459923), (-0.248908, 0, 0.600919), (0, 0, 0.65043), (0.248908, 0, 0.600919), (0.459923, 0, 0.459923), (0.600919, 0, 0.248908), (0.65043, 0, 0), (0.600919, 0.248908, 0), (0.459923, 0.459923, 0), (0.248908, 0.600919, 0), (0, 0.65043, 0), (-0.248908, 0.600919, 0), (-0.459923, 0.459923, 0), (-0.600919, 0.248908, 0), (-0.65043, 0, 0), (-0.600919, -0.248908, 0), (-0.459923, -0.459923, 0), (-0.248908, -0.600919, 0), (0, -0.65043, 0), (0, -0.600919, -0.248908), (0, -0.459923, -0.459923), (0, -0.248908, -0.600919), (0, 0, -0.65043), (0, 0.248908, -0.600919), (0, 0.459923, -0.459923), (0, 0.600919, -0.248908), (0, 0.65043, 0), (0, 0.600919, 0.248908), (0, 0.459923, 0.459923), (0, 0.248908, 0.600919), (0, 0, 0.65043), (0, -0.248908, 0.600919), (0, -0.459923, 0.459923), (0, -0.600919, 0.248908), (0, -0.65043, 0), (0.248908, -0.600919, 0), (0.459923, -0.459923, 0), (0.600919, -0.248908, 0), (0.65043, 0, 0), (0.600919, 0.248908, 0), (0.459923, 0.459923, 0), (0.248908, 0.600919, 0), (0, 0.65043, 0)], k=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51], d=1)
        cmds.addAttr(ci=True, dt='string', sn='guideType')
        cmds.addAttr(ci=True, dt='string', sn='guideName')
        cmds.setAttr('.guideType', 'slider', type='string', l=True)
        cmds.setAttr('.guideName', guideName, type='string', l=True)
        for axis in ['X','Y','Z']:
            cmds.setAttr(sldGdeStart+'.scale'+axis, globScl)
        cmds.makeIdentity(sldGdeStart, apply=1, s=1)# Freeze scale
        cmds.parent(sldGdeStart, sldGdeRoot)
        cmds.color(sldGdeStart, rgb=(0.273, 1.0, 0.0))

        # SldGuideEnd
        sldGdeEnd = cmds.curve(p=[(-2, 0, 0), (0, 0, 0), (0, 0, 2), (0, 0, 0), (2, 0, 0), (0, 0, 0), (0, 0, -2), (0, 0, 0), (0, 2, 0), (0, 0, 0), (0, -2, 0), (0, 0, 0), (0.650566, 0, 0), (0.601045, 0, -0.248961), (0.46002, 0, -0.46002), (0.248961, 0, -0.601045), (0, 0, -0.650566), (-0.248961, 0, -0.601045), (-0.46002, 0, -0.46002), (-0.601045, 0, -0.248961), (-0.650566, 0, 0), (-0.601045, 0, 0.248961), (-0.46002, 0, 0.46002), (-0.248961, 0, 0.601045), (0, 0, 0.650566), (0.248961, 0, 0.601045), (0.46002, 0, 0.46002), (0.601045, 0, 0.248961), (0.650566, 0, 0), (0.601045, 0.248961, 0), (0.46002, 0.46002, 0), (0.248961, 0.601045, 0), (0, 0.650566, 0), (-0.248961, 0.601045, 0), (-0.46002, 0.46002, 0), (-0.601045, 0.248961, 0), (-0.650566, 0, 0), (-0.601045, -0.248961, 0), (-0.46002, -0.46002, 0), (-0.248961, -0.601045, 0), (0, -0.650566, 0), (0, -0.601045, -0.248961), (0, -0.46002, -0.46002), (0, -0.248961, -0.601045), (0, 0, -0.650566), (0, 0.248961, -0.601045), (0, 0.46002, -0.46002), (0, 0.601045, -0.248961), (0, 0.650566, 0), (0, 0.601045, 0.248961), (0, 0.46002, 0.46002), (0, 0.248961, 0.601045), (0, 0, 0.650566), (0, -0.248961, 0.601045), (0, -0.46002, 0.46002), (0, -0.601045, 0.248961), (0, -0.650566, 0), (0.248961, -0.601045, 0), (0.46002, -0.46002, 0), (0.601045, -0.248961, 0), (0.650566, 0, 0), (0.601045, 0.248961, 0), (0.46002, 0.46002, 0), (0.248961, 0.601045, 0), (0, 0.650566, 0)], k=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64], d=1)
        cmds.addAttr(ci=True, dt='string', sn='guideType')
        cmds.addAttr(ci=True, dt='string', sn='guideName')
        cmds.setAttr('.guideType', 'slider', type='string', l=True)
        cmds.setAttr('.guideName', guideName, type='string', l=True)
        for axis in ['X','Y','Z']:
            cmds.setAttr(sldGdeEnd+'.scale'+axis, (globScl*0.5))
        cmds.makeIdentity(sldGdeEnd, apply=1, s=1)# Freeze scale
        cmds.move((4*globScl), sldGdeEnd, z=True)
        cmds.parent(sldGdeEnd, sldGdeStart)
        cmds.color(sldGdeEnd, rgb=(0.273, 1.0, 0.0))

        # SldGuidePath
        sldGdePth = cmds.curve(p=[(0, 0, 1), (0, 0, 0)], k=[0, 1], d=1)
        cmds.addAttr(ci=True, dt='string', sn='guideType')
        cmds.addAttr(ci=True, dt='string', sn='guideName')
        cmds.setAttr('.guideType', 'slider', type='string', l=True)
        cmds.setAttr('.guideName', guideName, type='string', l=True)
        for axis in ['tx','ty','tz','rx','ry','rz','sx','sy','sz']:
            cmds.setAttr(sldGdePth+'.'+axis, l=True)
        cmds.color(sldGdePth, rgb=(0.273, 1.0, 0.0))
        cmds.parent(sldGdePth, sldGdeOrig)
        sldGdeEndDecomp = cmds.createNode('decomposeMatrix', n=sldGdeEnd+'_decompMat')
        sldGdeStartDecomp = cmds.createNode('decomposeMatrix', n=sldGdeStart+'_decompMat')
        cmds.connectAttr(sldGdeEnd+'.worldMatrix[0]', sldGdeEndDecomp+'.inputMatrix')
        cmds.connectAttr(sldGdeStart+'.worldMatrix[0]', sldGdeStartDecomp+'.inputMatrix')
        cmds.connectAttr(sldGdeStartDecomp+'.outputTranslate', sldGdePth+'.controlPoints[0]')
        cmds.connectAttr(sldGdeEndDecomp+'.outputTranslate', sldGdePth+'.controlPoints[1]')

        # Extract twist WIP
        # transforms
        angRoot = cmds.createNode('transform', n='angBet_'+guideName+'_gdeRoot', ss=True)
        refPosA = cmds.createNode('transform', n='trkRot_'+guideName+'_gdeA', p=angRoot, ss=True)

        twistPort = self.extractTwist(angRoot, refPosA, 'y', name='twist_'+guideName+'_gdeExtract')

        # Connect current value ref
        angConv = cmds.createNode('unitConversion', n='eulerConv_'+guideName+'_gdeRotConv', ss=True)
        cmds.connectAttr(twistPort, angConv+'.input')
        cmds.setAttr(angConv+'.conversionFactor', 57.2957795131)
        cmds.connectAttr(angConv+'.output', sldGdeRoot+'.currentValRef')

        # Rename nodes
        cmds.rename(sldGdePth, 'Rig_'+guideName+'_SldGuidePath')# Shape node not named correctly when specifying name at creation
        gdeStart = cmds.rename(sldGdeStart, 'Ctl_'+guideName+'_SldGuideStart')
        gdeEnd = cmds.rename(sldGdeEnd, 'Ctl_'+guideName+'_SldGuideEnd')

        cmds.parent(angRoot, sldGdeOrig)

        return sldGdeRoot, gdeStart, gdeEnd

    def createStretchGuide(self, guideName, globScl):
        ### StrGuideOrig
        strGdeOrig = cmds.createNode('transform', n='Orig_'+guideName+'_StrGuideRoot')
        for axis in ['tx','ty','tz','rx','ry','rz','sx','sy','sz']:
            cmds.setAttr(strGdeOrig+'.'+axis, l=True)
        cmds.setAttr('.outlinerColor', 0.0, 1.0, 1.0)

        ### StrGuideRoot
        strGdeRoot = cmds.createNode('transform', n='Hbfr_'+guideName+'_StrGuideRoot')
        cmds.color(strGdeRoot, rgb=(0.0, 1.0, 1.0))
        cmds.parent(strGdeRoot, strGdeOrig)
        cmds.addAttr(ci=True, dt='string', sn='guideType')
        cmds.addAttr(ci=True, dt='string', sn='guideName')
        cmds.addAttr(ci=True, dt='string', sn='startParent')
        cmds.addAttr(ci=True, dt='string', sn='endParent')
        cmds.addAttr(ci=True, at='float',  sn='globalScale')
        cmds.addAttr(ci=True, at='bool',   sn='enableSns', min=0, max=1)
        cmds.addAttr(ci=True, at='double', sn='snsMultiplier')
        cmds.addAttr(ci=True, at='bool',   sn='twist', min=0, max=1)
        cmds.addAttr(ci=True, at='bool',   sn='stretchJoint', min=0, max=1)
        cmds.addAttr(ci=True, at='bool',   sn='stretchDorito', min=0, max=1)
        cmds.addAttr(ci=True, at='float',  sn='strDefPos', min=0, max=1)
        cmds.setAttr('.guideType', 'stretch', type='string', l=True)
        cmds.setAttr('.guideName', guideName, type='string', l=True)
        cmds.setAttr('.globalScale', globScl)
        cmds.setAttr('.snsMultiplier', 1.0, k=True)
        cmds.setAttr('.twist', False)
        cmds.setAttr('.stretchJoint', True)
        cmds.setAttr('.stretchDorito', False)
        cmds.setAttr('.strDefPos', 0.5)

        ### StrGuideStart
        strGdeStart = cmds.curve(p=[(0, 0, 0.81), (0.309973, 0, 0.748343), (0.572757, 0, 0.572757), (0.748343, 0, 0.309973), (0.81, 0, 0), (0.748343, 0, -0.309973), (0.572757, 0, -0.572757), (0.309973, 0, -0.748343), (0, 0, -0.81), (-0.309973, 0, -0.748343), (-0.572757, 0, -0.572757), (-0.748343, 0, -0.309973), (-0.81, 0, 0), (-0.748343, 0, 0.309973), (-0.572757, 0, 0.572757), (-0.309973, 0, 0.748343), (0, 0, 0.81), (0, 0.309973, 0.748343), (0, 0.572757, 0.572757), (0, 0.748343, 0.309973), (0, 0.81, 0), (0.309973, 0.748343, 0), (0.572757, 0.572757, 0), (0.748343, 0.309973, 0), (0.81, 0, 0), (0.748343, -0.309973, 0), (0.572757, -0.572757, 0), (0.309973, -0.748343, 0), (0, -0.81, 0), (-0.309973, -0.748343, 0), (-0.572757, -0.572757, 0), (-0.748343, -0.309973, 0), (-0.81, 0, 0), (-0.748343, 0.309973, 0), (-0.572757, 0.572757, 0), (-0.309973, 0.748343, 0), (0, 0.81, 0), (0, 0.748343, -0.309973), (0, 0.572757, -0.572757), (0, 0.309973, -0.748343), (0, 0, -0.81), (0, -0.309973, -0.748343), (0, -0.572757, -0.572757), (0, -0.748343, -0.309973), (0, -0.81, 0), (0, -0.748343, 0.309973), (0, -0.572757, 0.572757), (0, -0.309973, 0.748343), (0, 0, 0.81)], k=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48], d=1)
        cmds.addAttr(ci=True, dt='string', sn='guideType')
        cmds.addAttr(ci=True, dt='string', sn='guideName')
        cmds.setAttr('.guideType', 'stretch', type='string', l=True)
        cmds.setAttr('.guideName', guideName, type='string', l=True)
        for axis in ['X','Y','Z']:
            cmds.setAttr(strGdeStart+'.scale'+axis, globScl)
        cmds.makeIdentity(strGdeStart, apply=1, s=1)# Freeze scale
        cmds.parent(strGdeStart, strGdeRoot)
        cmds.color(strGdeStart, rgb=(0.0, 1.0, 1.0))

        ### StrGuideEnd
        strGdeEnd = cmds.curve(p=[(0, 0, 0.696254), (0.266445, 0, 0.643255), (0.492326, 0, 0.492326), (0.643255, 0, 0.266445), (0.696254, 0, 0), (0.643255, 0, -0.266445), (0.492326, 0, -0.492326), (0.266445, 0, -0.643255), (0, 0, -0.696254), (-0.266445, 0, -0.643255), (-0.492326, 0, -0.492326), (-0.643255, 0, -0.266445), (-0.696254, 0, 0), (-0.643255, 0, 0.266445), (-0.492326, 0, 0.492326), (-0.266445, 0, 0.643255), (0, 0, 0.696254), (0, 0.266445, 0.643255), (0, 0.492326, 0.492326), (0, 0.643255, 0.266445), (0, 0.696254, 0), (0.266445, 0.643255, 0), (0.492326, 0.492326, 0), (0.643255, 0.266445, 0), (0.696254, 0, 0), (0.643255, -0.266445, 0), (0.492326, -0.492326, 0), (0.266445, -0.643255, 0), (0, -0.696254, 0), (-0.266445, -0.643255, 0), (-0.492326, -0.492326, 0), (-0.643255, -0.266445, 0), (-0.696254, 0, 0), (-0.643255, 0.266445, 0), (-0.492326, 0.492326, 0), (-0.266445, 0.643255, 0), (0, 0.696254, 0), (0, 0.643255, -0.266445), (0, 0.492326, -0.492326), (0, 0.266445, -0.643255), (0, 0, -0.696254), (0, -0.266445, -0.643255), (0, -0.492326, -0.492326), (0, -0.643255, -0.266445), (0, -0.696254, 0), (0, -0.643255, 0.266445), (0, -0.492326, 0.492326), (0, -0.266445, 0.643255), (0, 0, 0.696254), (0, 0, 2), (0, 0, -2), (0, 0, 0), (0, 2, 0), (0, -2, 0), (0, 0, 0), (-2, 0, 0), (2, 0, 0)], k=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56], d=1)
        cmds.addAttr(ci=True, dt='string', sn='guideType')
        cmds.addAttr(ci=True, dt='string', sn='guideName')
        cmds.setAttr('.guideType', 'stretch', type='string', l=True)
        cmds.setAttr('.guideName', guideName, type='string', l=True)
        for axis in ['X','Y','Z']:
            cmds.setAttr(strGdeEnd+'.scale'+axis, (globScl*0.5))
        cmds.makeIdentity(strGdeEnd, apply=1, s=1)# Freeze scale
        cmds.parent(strGdeEnd, strGdeRoot)
        cmds.color(strGdeEnd, rgb=(0.0, 1.0, 1.0))

        ### Move Neg
        cmds.move((4*globScl), strGdeEnd, z=True)

        ### StrGuidePath
        strGdePth = cmds.curve(p=[(0, 0, 1), (0, 0, 0)], k=[0, 1], d=1)
        cmds.addAttr(ci=True, dt='string', sn='guideType')
        cmds.addAttr(ci=True, dt='string', sn='guideName')
        cmds.setAttr('.guideType', 'stretch', type='string', l=True)
        cmds.setAttr('.guideName', guideName, type='string', l=True)
        for axis in ['tx','ty','tz','rx','ry','rz','sx','sy','sz']:
            cmds.setAttr(strGdePth+'.'+axis, l=True)
        cmds.color(strGdePth, rgb=(0.0, 1.0, 1.0))
        cmds.parent(strGdePth, strGdeRoot)
        cmds.connectAttr(strGdeStart+'.translate', strGdePth+'.controlPoints[0]')
        cmds.connectAttr(strGdeEnd+'.translate', strGdePth+'.controlPoints[1]')

        ## Rename nodes
        cmds.rename(strGdePth, 'Rig_'+guideName+'_StrGuidePath')
        gdeEnd = cmds.rename(strGdeEnd, 'Ctl_'+guideName+'_StrGuideEnd')
        gdeStart = cmds.rename(strGdeStart, 'Ctl_'+guideName+'_StrGuideStart')

        return strGdeRoot, gdeStart, gdeEnd

    def buildFromGuide(self, globScl=1.0, visCrv=None, guideList=None):
        '''
        Builds either selected guides or list of guides

        globScl    = (float) Size of def's and ctrls
        visCrv     = (bol) Create curve for viewport
        guideList  = ([]) Supplied list of guides to build (mGear post script)
        '''
        '''
        sliderGuidesDict = None
        stretchGuidesDict = None
        sliderParDict = None
        stretchParDict = None
        '''

        if visCrv == None:
            # visCrv = self.ui.visCrv_chk.isChecked()
            visCrv = False

        if guideList == None:
            guideList = []
            for sel in cmds.ls(sl=1):
                hbfr = []
                if cmds.attributeQuery('guideType', node=sel, ex=True):
                    hbfr = self.getGuideRoot(guide=sel, select=False)
                    if hbfr != []:
                        if not hbfr[0] in guideList:
                            guideList.append(hbfr[0])

        if guideList != []:
            sliderGuidesDict = {}
            stretchGuidesDict = {}

            for hbfr in guideList:
                guideName = cmds.getAttr(hbfr+'.guideName')
                guideType = cmds.getAttr(hbfr+'.guideType')

                if guideType == 'slider':
                    if self.sliderBuildCheck(hbfr) == True:
                        sliderGuidesDict.update({hbfr : guideName})
                if guideType == 'stretch':
                    if self.stretchBuildCheck(hbfr) == True:
                        stretchGuidesDict.update({hbfr : guideName})

            if cmds.objExists('volumeSystems') == False:
                cmds.createNode('transform', n='volumeSystems')

            self.sliderParDict  = {}
            self.stretchParDict = {}

            # for hbfr, guideName in sliderGuidesDict.iteritems():
            for hbfr, guideName in sliderGuidesDict.items():
                # globScl = cmds.getAttr(hbfr+'.globalScale')
                self.buildSlider(hbfr, guideName, globScl, visCrv)
            # for hbfr, guideName in stretchGuidesDict.iteritems():
            for hbfr, guideName in stretchGuidesDict.items():
                # globScl = cmds.getAttr(hbfr+'.globalScale')
                self.buildStretch(hbfr, guideName, globScl, visCrv)

        # Post parenting of systems
        # for k,v in self.sliderParDict.iteritems():
        for k,v in self.sliderParDict.items():
            # sldName  = ['slider', sldPar]
            if v[0] == 'slider':
                if cmds.objExists(k+'_sliderStartPos') and cmds.objExists(v[1]):
                    self.parentConstraint(v[1], k+'_sliderStartPos', mo=True)
                    self.parentConstraint(v[1], k+'_sliderEndPos', mo=True)
        # for k,v in self.stretchParDict.iteritems():
        for k,v in self.stretchParDict.items():
            # strName = ['stretch', startPar, endPar]
            if v[0] == 'stretch':
                if cmds.objExists(k+'_stretchStartPos') and cmds.objExists(v[1]):
                    self.parentConstraint(v[1], k+'_stretchStartPos', mo=True)
                if cmds.objExists(k+'_stretchStartPos') and cmds.objExists(v[2]):
                    self.parentConstraint(v[2], k+'_stretchEndPos', mo=True)

        self.globalScaleConn()
        self.hideGuides()
        print('***** Done *****')

    def sliderBuildCheck(self, hbfr):
        '''
        Check that slider guide has parent and tracker before building
        '''
        if cmds.getAttr(hbfr+'.guideParent') == None or cmds.getAttr(hbfr+'.guideTracker') == None:
            print('_'*80)
            print(hbfr, 'Slider not setup properly, check guide settings. Skipping guide')
            print('_'*80)
            return False
        if not cmds.objExists(cmds.getAttr(hbfr+'.guideParent')) or not cmds.objExists(cmds.getAttr(hbfr+'.guideTracker')):
            print('_'*80)
            print(hbfr, 'Slider parent or tracker object does not exists. Skipping guide')
            print('_'*80)
            return False
        else:
            return True

    def stretchBuildCheck(self, hbfr):
        '''
        Check that stretch has start parent and end parent before building
        '''
        if cmds.getAttr(hbfr+'.startParent') == None or cmds.getAttr(hbfr+'.endParent') == None:
            print('_'*80)
            print(hbfr, 'Stretch not setup properly, check guide settings. Skipping guide')
            print('_'*80)
            return False
        if not cmds.objExists(cmds.getAttr(hbfr+'.startParent')) or not cmds.objExists(cmds.getAttr(hbfr+'.endParent')):
            print('_'*80)
            print(hbfr, 'Stretch start parent, or end parent object does not exists. Skipping guide')
            print('_'*80)
            return False
        else:
            return True

    def buildSlider(self, guide, sldName, globScl=None, visCrv=0):
        # is def a joint? Is it in a skincluster?
        newDef, sknMsh, jntSkn = self.newDefCheck('slider', sldName)

        ## List slider children for start and end pos
        sliderGdeRef = cmds.ls(guide)+cmds.listRelatives(guide, allDescendents=True, type='transform')
        startPos     = self.getTransform(sliderGdeRef[2]) # is type transform matrix
        endPos       = self.getTransform(sliderGdeRef[1]) # is type transform matrix

        ## Get slider settings
        axisDict   = { 0:'X', 1:'Y', 2:'Z' }
        upAxis     = axisDict[cmds.getAttr(guide+'.XYZ')]
        sldPar     = cmds.getAttr(guide+'.guideParent')
        sldTrk     = cmds.getAttr(guide+'.guideTracker')
        startAngle = cmds.getAttr(guide+'.trackerMinRot')
        endAngle   = cmds.getAttr(guide+'.trackerMaxRot')
        sldJnt     = cmds.getAttr(guide+'.sliderJoint')
        sldDor     = cmds.getAttr(guide+'.sliderDorito')

        if globScl == None:
            globScl = cmds.getAttr(guide+'.globalScale')

        # Check to see if slider is going to follow another system,
        # and get system def name from guide name.
        if 'SldGuide' in sldPar:
            sldPar = self.getDefFromGuide(slider=sldPar)
        if 'StrGuide' in sldPar:
            sldPar = self.getDefFromGuide(stretch=sldPar)

        # Create Slider System
        print(sldName, 'slider', '*'*(80-len(sldName)))
        self.createSliderSystem(sldName, startPos, endPos, sldPar, sldTrk, startAngle,
                                 endAngle, upAxis, globScl, visCrv, newDef, sldJnt)

        # Post parenting dict
        self.sliderParDict[sldName] = ['slider', sldPar]

        # Reset bindpose for skinCluster
        if jntSkn != []:
            self.setBindPose(mesh=None, setAngle=0, sknCls=jntSkn)

    def buildStretch(self, guide, strName, globScl=None, visCrv=0):
        # is def a joint? Is it in a skincluster?
        newDef, sknMsh, jntSkn = self.newDefCheck('stretch', strName)

        # List stretch guide for reference
        stretchGdeRef = cmds.ls(guide)+cmds.listRelatives(guide, children=True, type='transform')
        startPos = self.getTransform(stretchGdeRef[1]) # is type transform matrix
        endPos   = self.getTransform(stretchGdeRef[2]) # is type transform matrix

        twist    = cmds.getAttr(guide+'.twist')
        sns      = cmds.getAttr(guide+'.enableSns')
        snsAmt   = cmds.getAttr(guide+'.snsMultiplier')
        startPar = cmds.getAttr(guide+'.startParent')
        endPar   = cmds.getAttr(guide+'.endParent')
        strJnt   = cmds.getAttr(guide+'.stretchJoint')
        strDor   = cmds.getAttr(guide+'.stretchDorito')
        strPos   = cmds.getAttr(guide+'.strDefPos')

        if globScl == None:
            globScl = cmds.getAttr(guide+'.globalScale')

        # Check to see if stretch is going to follow another system,
        # and get system def name from guide name.
        if 'SldGuide' in startPar:
            startPar = self.getDefFromGuide(slider=startPar)
        if 'SldGuide' in endPar:
            endPar   = self.getDefFromGuide(slider=endPar)
        if 'StrGuide' in startPar:
            startPar = self.getDefFromGuide(stretch=startPar)
        if 'StrGuide' in endPar:
            endPar   = self.getDefFromGuide(stretch=endPar)

        ## Create Stretch System
        print(strName, 'stretch', '*'*(79-len(strName)))
        self.createStretchSystem(twist, strName, startPos, endPos, startPar, endPar, sns, snsAmt,
                                  globScl, visCrv, newDef, strJnt, strPos)
        # Post parenting dict
        self.stretchParDict[strName] = ['stretch', startPar, endPar]

        # Reset bindpose for skinCluster
        if jntSkn != []:
            self.setBindPose(mesh=None, setAngle=0, sknCls=jntSkn)

    def createSliderSystem(self, sldName, startPos, endPos, sldPar, sldTrk, startAngle, endAngle, upAxis, globScl, visCrv, newDef, sldJnt):
        '''
        sldName    = (str):
        startPos   = (transform matrix):
        endPos     = (transform matrix):
        sldPar     = (str):
        sldRef     = (str):
        sldTrk     = (str):
        startAngle = (float):
        endAngle   = (float):
        upAxis     = (str)
        visCrv     = (str) Creates curve in viewport
        '''

        # Delete existing nodes
        delDict = {sldName+'_StartPos_DecompMat':'decomposeMatrix',
                   sldName+'_EndPos_DecompMat':'decomposeMatrix',
                   sldName+'_MatrixSub':'plusMinusAverage',
                   sldName+'_MatrixMod':'multiplyDivide',
                   sldName+'_snsSysGlobalScale':'multiplyDivide',
                   sldName+'_RotRemap':'remapValue',
                   'eulerConv_'+sldName+'_RotConv':'unitConversion',
                   sldName+'_sldDeftwist':'pairBlend'}
        # for k,v in delDict.iteritems():
        for k,v in delDict.items():
            if cmds.objExists(k):
                if cmds.objectType(k, isType=v):
                    cmds.delete(k)

        # Create slider components
        sldRoot = cmds.createNode('transform', n='Orig_'+sldName+'_SldRoot')

        sldStartLoc = cmds.createNode('transform', n=sldName+'_sliderStartPos')
        self.setTransformFromMatrix(startPos, sldStartLoc)

        sldEndLoc = cmds.createNode('transform', n=sldName+'_sliderEndPos')
        self.setTransformFromMatrix(endPos, sldEndLoc)

        if newDef == 1:
            if not cmds.objExists('Def_'+sldName+'_SldMain'):
                if sldJnt == 0: # Create transform instead
                    sldDef = cmds.createNode('transform', n='Def_'+sldName+'_SldMain')
                else:
                    sldDef = cmds.createNode('joint', n='Def_'+sldName+'_SldMain')
                    cmds.color( sldDef, rgb=(0.0, 0.647, 0.0))
                    cmds.setAttr(sldDef+'.radius', globScl)
            else:
                sldDef = 'Def_'+sldName+'_SldMain'
                cmds.setAttr(sldDef+'.radius', globScl)
        else:
            sldDef = 'Def_'+sldName+'_SldMain'
            cmds.setAttr(sldDef+'.radius', globScl)

        # Create slider nodes
        startPosDecompose = cmds.createNode('decomposeMatrix', n=sldName+'_StartPos_DecompMat', ss=True)
        endPosDecompose = cmds.createNode('decomposeMatrix', n=sldName+'_EndPos_DecompMat', ss=True)
        sldVectorSub = cmds.createNode('plusMinusAverage', n=sldName+'_MatrixSub', ss=True)
        cmds.setAttr(sldVectorSub+'.operation', 2) # Subtract
        sldVectorSum = cmds.createNode('plusMinusAverage', n=sldName+'_MatrixCombine', ss=True)
        sldVectorMod = cmds.createNode('multiplyDivide', n=sldName+'_MatrixMod', ss=True)
        # Connect nodes
        cmds.connectAttr(startPosDecompose+'.outputTranslate', sldVectorSub+'.input3D[1]')
        cmds.connectAttr(endPosDecompose+'.outputTranslate', sldVectorSub+'.input3D[0]')
        cmds.connectAttr(sldVectorSub+'.output3D', sldVectorMod+'.input1')
        cmds.connectAttr(startPosDecompose+'.outputTranslate', sldVectorSum+'.input3D[0]')
        cmds.connectAttr(sldVectorMod+'.output', sldVectorSum+'.input3D[1]')
        # Global scale
        snsGlobScl = cmds.createNode('multiplyDivide',  n=sldName+'_snsSysGlobalScale', ss=True)
        cmds.addAttr(snsGlobScl, ci=True, at='float', sn='snsSysGlobalScale')
        cmds.setAttr(snsGlobScl+'.snsSysGlobalScale', 1.0)
        cmds.connectAttr(snsGlobScl+'.snsSysGlobalScale', sldDef+'.sx')
        cmds.connectAttr(snsGlobScl+'.snsSysGlobalScale', sldDef+'.sy')
        cmds.connectAttr(snsGlobScl+'.snsSysGlobalScale', sldDef+'.sz')
        # Connect objects to nodes
        cmds.connectAttr(sldStartLoc+'.worldMatrix', startPosDecompose+'.inputMatrix')
        cmds.connectAttr(sldEndLoc+'.worldMatrix', endPosDecompose+'.inputMatrix')
        cmds.connectAttr(sldVectorSum+'.output3D', sldDef+'.translate')

        if visCrv:
            sldPath = cmds.curve( p=[(0,0,0), (0,0,1)], d=1, n=sldName+'_sliderPath')
            cmds.color( sldPath, rgb=(0.0, 0.647, 0.0))
            cmds.connectAttr(sldStartLoc+'.translate', sldPath+'.controlPoints[0]')
            cmds.connectAttr(sldEndLoc+'.translate', sldPath+'.controlPoints[1]')
            cmds.select(None)
            cmds.parent(sldPath, sldRoot)

        cmds.parent(sldStartLoc, sldEndLoc, sldDef, sldRoot)

        # Extract twist from tracker
        # transforms
        angRoot = cmds.createNode('transform', n='angBet_'+sldName+'_Root', ss=True)
        refPosA = cmds.createNode('transform', n='trkRot_'+sldName+'_A', p=angRoot, ss=True)
        twistPort = self.extractTwist(angRoot, refPosA, upAxis.lower(), name='twist_'+sldName+'_extract')

        # Move twist setup to match tracker
        trkPos = cmds.xform(sldTrk, q=1, ws=1, matrix=1)
        cmds.xform(angRoot, m=trkPos)

        # Constrain twist setup
        trkPar = cmds.listRelatives(sldTrk, p=1, type='transform')[0]
        self.parentConstraint(trkPar, angRoot, mo=True)
        self.parentConstraint(sldTrk, refPosA, t=[], s=[], r=[upAxis.lower()], mo=True)

        # Modulate Def pos
        rotRemap = cmds.createNode('remapValue', n=sldName+'_RotRemap', ss=True)
        cmds.setAttr(rotRemap+'.inputMin', startAngle)
        cmds.setAttr(rotRemap+'.inputMax', endAngle)
        for x in ['X', 'Y', 'Z']:
            cmds.connectAttr(rotRemap+'.outValue', sldVectorMod+'.input2'+x)

        # Connect current rot value
        angConv = cmds.createNode('unitConversion', n='eulerConv_'+sldName+'_RotConv', ss=True)
        cmds.connectAttr(twistPort, angConv+'.input')
        cmds.setAttr(angConv+'.conversionFactor', 57.2957795131)
        cmds.connectAttr(angConv+'.output', rotRemap+'.inputValue')
        # END EXTRACT twist

        # Blend rotation between sldStartLoc and sldEndLoc
        # To do:  Parent sldEndLoc to tracker for future twist option, and adjust twist value below
        sldDefTwst = cmds.createNode('pairBlend', n=sldName+'_sldDeftwist')
        cmds.connectAttr(sldStartLoc+'.rotate', sldDefTwst+'.inRotate1')
        cmds.connectAttr(sldEndLoc+'.rotate', sldDefTwst+'.inRotate2')
        cmds.connectAttr(sldDefTwst+'.outRotate', sldDef+'.rotate')
        cmds.setAttr(sldDefTwst+'.weight', 0.0) # twist value, higher value will follow sldEndLoc

        cmds.parent(angRoot, sldRoot)
        cmds.parent(sldRoot, 'volumeSystems')

    def createStretchSystem(self, twist, strName, startPos, endPos, startPar, endPar, sns,
        snsAmt, globScl, visCrv, newDef, strJnt, strPos):
        '''
        strName (str):
        startPos (transform matrix):
        endPos (transform matrix):
        startPar (str):
        endPar (str):
        sns (int):
        snsAmt (float):
        '''

        # Delete existing nodes
        delDict = {strName+'_stretchMotionPath':'motionPath',
                   strName+'_stretchCrvInfo':'pointOnCurveInfo',
                   strName+'_snsTwistBlend':'blendMatrix',
                   strName+'_distBetween':'distanceBetween',
                   strName+'_snsSysGlobalScale':'multiplyDivide',
                   strName+'_decimalPlaceMult':'multiplyDivide',
                   strName+'_decimalPlaceDivide':'multiplyDivide',
                   strName+'_distTimesTwo':'multiplyDivide',
                   strName+'_snsStretchXY':'remapValue',
                   strName+'_snsStretchZ':'remapValue',
                   strName+'_snsSquashXY':'remapValue',
                   strName+'_snsSquashZ':'remapValue',
                   strName+'_snsCond':'condition',
                   strName+'_snsClamp':'clamp',
                   strName+'_snsMultPowerXY':'multiplyDivide',
                   strName+'_snsMultPowerZ':'multiplyDivide',
                   strName+'_snsRigScaleModXY':'multiplyDivide',
                   strName+'_snsRigScaleModZ':'multiplyDivide',
                   strName+'_snsSysGlobalScale':'multiplyDivide'}
        # for k,v in delDict.iteritems():
        for k,v in delDict.items():
            if cmds.objExists(k):
                if cmds.objectType(k, isType=v):
                    cmds.delete(k)
        if cmds.objExists(strName+'_stretchStartPos'):
            rigUtils.delParentConstraint(strName+'_stretchStartPos')
        if cmds.objExists(strName+'_stretchEndPos'):
            rigUtils.delParentConstraint(strName+'_stretchEndPos')


        strRoot = cmds.createNode('transform', n='Orig_'+strName+'_StrRoot', ss=True)
        strEndLoc = cmds.createNode('transform', n=strName+'_stretchEndPos', p=strRoot, ss=True)
        self.setTransformFromMatrix(endPos, strEndLoc)
        strStartLoc = cmds.createNode('transform', n=strName+'_stretchStartPos', p=strRoot, ss=True)
        self.setTransformFromMatrix(startPos, strStartLoc)
        strStAim = cmds.aimConstraint(strEndLoc, strStartLoc, wut="none", aim=(0, 0, 1), u=(0, 1, 0), w=1, o=(0, 0, 0)) # aim start to end
        cmds.delete(strStAim)
        strCrvPath = cmds.curve(p=[(0, 0, 0), (0, 0, -1)], k=[0, 1], d=1, n=strName+'_stretchPath')
        cmds.color(strCrvPath, rgb=(0.0, 0.5, 1.0))
        cmds.parent(strCrvPath, strRoot)
        strDefPar = cmds.createNode('transform', n=strName+'_stretchDefBfr', p=strRoot, ss=True)

        if newDef == 1:
            if not cmds.objExists('Def_'+strName+'_StrMain'):
                if strJnt == 0: # Create transform instead
                    strDef = cmds.createNode('transform', n='Def_'+strName+'_StrMain')
                    self.setTransformFromMatrix(startPos, strDefPar)
                else:
                    strDef = cmds.createNode('joint', n='Def_'+strName+'_StrMain')
                    cmds.setAttr(strDef+'.radius', globScl)
                    cmds.color(strDef, rgb=(0.0, 0.5, 1.0))
                    self.setTransformFromMatrix(startPos, strDefPar)
            else:
                strDef = 'Def_'+strName+'_StrMain'
                cmds.setAttr(strDef+'.radius', globScl)
        else:
            strDef = 'Def_'+strName+'_StrMain'
            cmds.setAttr(strDef+'.radius', globScl)


        strMotPth = cmds.createNode('motionPath', n=strName+'_stretchMotionPath', ss=1)
        strPntOnCrv = cmds.createNode('pointOnCurveInfo', n=strName+'_stretchCrvInfo', ss=1)

        defPos = cmds.xform(strDefPar, q=1, m=1)
        cmds.xform(strDef, m=defPos)
        cmds.parent(strDef, strDefPar)

        if not visCrv:
            cmds.setAttr(strCrvPath+'.v', 0)
            cmds.setAttr(strCrvPath+'.v', l=True, k=False, channelBox=False)

        # Constrain curve end points
        cmds.connectAttr(strStartLoc+'.translate', strCrvPath+'.controlPoints[0]')
        cmds.connectAttr(strEndLoc+'.translate', strCrvPath+'.controlPoints[1]')

        # point on curve settings
        cmds.connectAttr(strCrvPath+'.worldSpace[0]', strPntOnCrv+'.inputCurve')
        cmds.setAttr(strPntOnCrv+'.turnOnPercentage', 1)
        cmds.setAttr(strPntOnCrv+'.parameter', strPos)

        # Motion path settings
        cmds.setAttr(strMotPth+'.follow', 1)
        cmds.setAttr(strMotPth+'.worldUpType', 2) # Object Rotation Up
        cmds.setAttr(strMotPth+'.worldUpVectorX', 0)
        cmds.setAttr(strMotPth+'.worldUpVectorY', 1)
        cmds.setAttr(strMotPth+'.worldUpVectorZ', 0)
        cmds.setAttr(strMotPth+'.frontAxis', 2)# Front Axis Z
        cmds.setAttr(strMotPth+'.upAxis', 1)# Up Axis Y
        cmds.connectAttr(strCrvPath+'.worldSpace[0]', strMotPth+'.geometryPath')
        # Twist
        snsTwist = cmds.createNode('blendMatrix', n=strName+'_snsTwistBlend', ss=True)
        cmds.connectAttr(strStartLoc+'.worldMatrix[0]', snsTwist+'.inputMatrix')
        cmds.connectAttr(strEndLoc+'.worldMatrix[0]', snsTwist+'.target[0].targetMatrix')
        cmds.setAttr(snsTwist+'.envelope', twist)
        cmds.connectAttr(snsTwist+'.outputMatrix', strMotPth+'.worldUpMatrix')

        if sns == True:
            snsDistBet = cmds.createNode('distanceBetween', n=strName+'_distBetween', ss=True)
            snsDistScl = cmds.createNode('multiplyDivide',  n=strName+'_snsSysGlobalScale', ss=True)
            snsDistMul = cmds.createNode('multiplyDivide',  n=strName+'_decimalPlaceMult', ss=True)
            snsDistDiv = cmds.createNode('multiplyDivide',  n=strName+'_decimalPlaceDivide', ss=True)
            snsTimeTwo = cmds.createNode('multiplyDivide',  n=strName+'_distTimesTwo', ss=True)
            snsStrXY   = cmds.createNode('remapValue', n=strName+'_snsStretchXY', ss=True)
            snsStrZ    = cmds.createNode('remapValue', n=strName+'_snsStretchZ', ss=True)
            snsSquXY   = cmds.createNode('remapValue', n=strName+'_snsSquashXY', ss=True)
            snsSquZ    = cmds.createNode('remapValue', n=strName+'_snsSquashZ', ss=True)
            snsSysCond = cmds.createNode('condition',  n=strName+'_snsCond', ss=True)
            snsSysClmp = cmds.createNode('clamp',      n=strName+'_snsClamp')
            snsPowXY   = cmds.createNode('multiplyDivide',  n=strName+'_snsMultPowerXY', ss=True)
            snsPowZ    = cmds.createNode('multiplyDivide',  n=strName+'_snsMultPowerZ', ss=True)
            snsGlobXY  = cmds.createNode('multiplyDivide',  n=strName+'_snsRigScaleModXY', ss=True)
            snsGlobZ   = cmds.createNode('multiplyDivide',  n=strName+'_snsRigScaleModZ', ss=True)

            cmds.addAttr(snsDistScl, ci=True, at='float', sn='snsSysGlobalScale')
            cmds.addAttr(snsSysClmp, ci=True, at='float', sn='snsSysMultiplier')
            cmds.addAttr(snsDistMul, ci=True, at='short', sn='snsDistFloatToInt')
            cmds.addAttr(snsDistMul, ci=True, at='short', sn='distDecimalClamp')

            # clamp dist between to 100th decimal place
            cmds.connectAttr(strStartLoc+'.translate', snsDistBet+'.point1')
            cmds.connectAttr(strEndLoc+'.translate',   snsDistBet+'.point2')
            cmds.setAttr(snsDistMul+'.distDecimalClamp', 100)# decimal place
            cmds.connectAttr(snsDistMul+'.distDecimalClamp', snsDistMul+'.input2X')
            cmds.connectAttr(snsDistMul+'.distDecimalClamp', snsDistDiv+'.input2X')
            cmds.connectAttr(snsDistMul+'.outputX', snsDistMul+'.snsDistFloatToInt')
            cmds.connectAttr(snsDistMul+'.snsDistFloatToInt', snsDistDiv+'.input1X')

            cmds.setAttr(snsSysCond+'.operation', 4)
            cmds.setAttr(snsDistScl+'.operation', 2)#divide
            cmds.setAttr(snsDistMul+'.operation', 1)#multiply
            cmds.setAttr(snsDistDiv+'.operation', 2)
            cmds.setAttr(snsTimeTwo+'.operation', 1)
            cmds.setAttr(snsPowXY+'.operation', 3)#power
            cmds.setAttr(snsPowZ+'.operation', 3)
            cmds.setAttr(snsGlobXY+'.operation', 1)
            cmds.setAttr(snsGlobZ+'.operation', 1)
            cmds.setAttr(snsDistScl+'.snsSysGlobalScale', 1.0)
            cmds.setAttr(snsSysClmp+'.maxR', 10000)#max stretch
            cmds.setAttr(snsSysClmp+'.maxG', 10000)#max stretch
            cmds.setAttr(snsSysClmp+'.snsSysMultiplier', snsAmt)

            cmds.setAttr(snsTimeTwo+'.input1X', cmds.getAttr(snsDistBet+'.distance'))
            cmds.setAttr(snsTimeTwo+'.input2X', 2.0)

            cmds.connectAttr(snsDistBet+'.distance', snsDistScl+'.input1X')
            cmds.connectAttr(snsDistScl+'.snsSysGlobalScale', snsDistScl+'.input2X')
            cmds.connectAttr(snsDistScl+'.outputX', snsDistMul+'.input1X')
            cmds.connectAttr(snsDistDiv+'.outputX', snsStrXY+'.inputValue')
            cmds.connectAttr(snsDistDiv+'.outputX', snsStrZ+'.inputValue')
            cmds.connectAttr(snsDistDiv+'.outputX', snsSquXY+'.inputValue')
            cmds.connectAttr(snsDistDiv+'.outputX', snsSquZ+'.inputValue')
            cmds.connectAttr(snsTimeTwo+'.outputX', snsStrXY+'.inputMax')
            cmds.connectAttr(snsTimeTwo+'.outputX', snsStrZ+'.inputMax')
            cmds.connectAttr(snsStrXY+'.outValue', snsSysCond+'.colorIfFalseR')
            cmds.connectAttr(snsStrZ+'.outValue', snsSysCond+'.colorIfFalseG')
            cmds.connectAttr(snsSquXY+'.outValue', snsSysCond+'.colorIfTrueR')
            cmds.connectAttr(snsSquZ+'.outValue', snsSysCond+'.colorIfTrueG')
            cmds.connectAttr(snsDistDiv+'.outputX', snsSysCond+'.firstTerm')
            cmds.setAttr(snsSysCond+'.secondTerm', cmds.getAttr(snsDistDiv+'.outputX'))
            cmds.connectAttr(snsSysCond+'.outColorR', snsSysClmp+'.inputR')
            cmds.connectAttr(snsSysCond+'.outColorG', snsSysClmp+'.inputG')
            cmds.connectAttr(snsSysClmp+'.outputR', snsPowXY+'.input1X')
            cmds.connectAttr(snsSysClmp+'.outputG', snsPowZ+'.input1X')
            cmds.connectAttr(snsSysClmp+'.snsSysMultiplier', snsPowXY+'.input2X')
            cmds.connectAttr(snsSysClmp+'.snsSysMultiplier', snsPowZ+'.input2X')
            cmds.connectAttr(snsPowXY+'.outputX', snsGlobXY+'.input1X')
            cmds.connectAttr(snsPowZ+'.outputX', snsGlobZ+'.input1X')
            cmds.connectAttr(snsDistScl+'.snsSysGlobalScale', snsGlobXY+'.input2X')
            cmds.connectAttr(snsDistScl+'.snsSysGlobalScale', snsGlobZ+'.input2X')
            cmds.connectAttr(snsGlobXY+'.outputX', strDef+'.sx')
            cmds.connectAttr(snsGlobXY+'.outputX', strDef+'.sy')
            cmds.connectAttr(snsGlobZ+'.outputX', strDef+'.sz')

            cmds.setAttr(snsStrXY+'.inputMin', cmds.getAttr(snsDistDiv+'.outputX'))
            cmds.setAttr(snsStrXY+'.outputMin', 1.0)
            cmds.setAttr(snsStrXY+'.outputMax', 0.0)
            cmds.setAttr(snsStrZ+'.inputMin', cmds.getAttr(snsDistDiv+'.outputX'))
            cmds.setAttr(snsStrZ+'.outputMin', 1.0)
            cmds.setAttr(snsStrZ+'.outputMax', 2.25)
            cmds.setAttr(snsSquXY+'.inputMax', cmds.getAttr(snsDistDiv+'.outputX'))
            cmds.setAttr(snsSquXY+'.outputMin', 2.25)
            cmds.setAttr(snsSquZ+'.inputMax', cmds.getAttr(snsDistDiv+'.outputX'))
        else:
            snsGlobScl = cmds.createNode('multiplyDivide',  n=strName+'_snsSysGlobalScale', ss=True)
            cmds.addAttr(snsGlobScl, ci=True, at='float', sn='snsSysGlobalScale')
            cmds.setAttr(snsGlobScl+'.snsSysGlobalScale', 1.0)
            cmds.connectAttr(snsGlobScl+'.snsSysGlobalScale', strDef+'.sx')
            cmds.connectAttr(snsGlobScl+'.snsSysGlobalScale', strDef+'.sy')
            cmds.connectAttr(snsGlobScl+'.snsSysGlobalScale', strDef+'.sz')

        # Joint connections
        cmds.connectAttr(strPntOnCrv+'.position', strDefPar+'.translate')
        cmds.connectAttr(strMotPth+'.rotate', strDefPar+'.rotate')

        cmds.parent(strRoot, 'volumeSystems')


    # Slider Settings
    def constrainSldParent(self, guide, parentLineEdit):
        '''
        '''
        if len(cmds.ls(sl=True)) != 1:
            raise IndexError('Select one object')

        sldPar = cmds.ls(sl=True)[0]
        cmds.setAttr(guide+'.guideParent', sldPar, type='string')
        parentLineEdit.setText(sldPar)

    def constrainSldTracker(self, guide=None, trackerLineEdit=None, rotAxisComboBox=None, sldTrk=None, mirror=False):
        if guide == None:
            cmds.warning('Load a guide in the ui before assigning its Tracker')
            return

        if not sldTrk:
            if len(cmds.ls(sl=True)) != 1:
                raise IndexError('Select only one object')
            sldTrk = cmds.ls(sl=True)[0]

        guideName = cmds.getAttr(guide+'.guideName')

        cmds.setAttr(guide+'.guideTracker', sldTrk, type='string')
        if mirror == False: # Do not populate UI when mirroring sliders
            if trackerLineEdit is not None:
                trackerLineEdit.setText(sldTrk)

        # Delete parent constraint if it exists
        if cmds.objExists('angBet_'+guideName+'_gdeRoot'):
            # Check for existing parent constraint
            for nde in ['angBet_'+guideName+'_gdeRoot', 'trkRot_'+guideName+'_gdeA']:
                try:
                    node = cmds.listConnections(nde+'.parentInverseMatrix')
                    if node:
                        if cmds.nodeType(node) == 'multMatrix':
                            cmds.delete(node)
                except TypeError:
                    pass

            trkPos = cmds.xform(sldTrk, q=1, ws=1, matrix=1)
            cmds.xform('angBet_'+guideName+'_gdeRoot', m=trkPos)

            for axis in ['tx','ty','tz','rx','ry','rz']:
                cmds.setAttr('trkRot_'+guideName+'_gdeA'+'.'+axis, 0)

            axisDict = { 0:'x', 1:'y', 2:'z' }
            axis = cmds.getAttr(guide+'.XYZ')
            if rotAxisComboBox is not None:
                axis = axisDict[rotAxisComboBox.currentIndex()]
            else:
                axis = axisDict[axis]

            # get tracker parent
            try:
                trkPar = cmds.listRelatives(sldTrk, p=1, shapes=False)[0]
            except TypeError:
                raise TypeError('This tracker object does not have a parent. Must have a parent')

            self.parentConstraint(trkPar, 'angBet_'+guideName+'_gdeRoot', mo=True)
            self.parentConstraint(sldTrk, 'trkRot_'+guideName+'_gdeA', t=[], s=[], r=[axis], mo=True)

            # Fix twist extractor
            if not cmds.isConnected('twist_'+guideName+'_gdeExtract_twistExtractor_q2e.outputRotate'+axis.upper(),
                             'eulerConv_'+guideName+'_gdeRotConv.input'):
                cmds.connectAttr('twist_'+guideName+'_gdeExtract_twistExtractor_q2e.outputRotate'+axis.upper(),
                                 'eulerConv_'+guideName+'_gdeRotConv.input', f=True)

    def delParCon(self, guide, parentLineEdit):
        '''
        '''
        cmds.setAttr(guide+'.guideParent', '', type='string')
        parentLineEdit.setText('')

    def delTrkCon(self, guide, trackerLineEdit):
        '''
        '''
        cmds.setAttr(guide+'.guideTracker', '', type='string')
        trackerLineEdit.setText('')

    def commitGdeSld(self, guide, rotAxisComboBox, startValDoubleSpinBox, endValDoubleSpinBox, reverseCheckBox, jntCheckBox, doritoCheckBox):
        '''
        '''
        if guide:
            print('Committing changes to slider guide')
            # set Axis attr from UI
            cmds.setAttr(guide+'.XYZ', rotAxisComboBox.currentIndex())
            # set Axis Min from UI
            cmds.setAttr(guide+'.trackerMinRot', startValDoubleSpinBox.value())
            # set Axis Max from UI
            cmds.setAttr(guide+'.trackerMaxRot', endValDoubleSpinBox.value())
            # set tracker reverse
            cmds.setAttr(guide+'.trackerRev', reverseCheckBox.isChecked())
            # set joint option
            cmds.setAttr(guide+'.sliderJoint', jntCheckBox.isChecked())
            # set joint dorito option
            cmds.setAttr(guide+'.sliderDorito', doritoCheckBox.isChecked())

            # Axis value change
            guideName = cmds.getAttr(guide+'.guideName')
            axisDict = { 0:'X', 1:'Y', 2:'Z' }
            axis = axisDict[rotAxisComboBox.currentIndex()]
            if not cmds.isConnected('twist_'+guideName+'_gdeExtract_twistExtractor_q2e.outputRotate'+axis,
                                 'eulerConv_'+guideName+'_gdeRotConv.input'):
                cmds.connectAttr('twist_'+guideName+'_gdeExtract_twistExtractor_q2e.outputRotate'+axis,
                                 'eulerConv_'+guideName+'_gdeRotConv.input', f=True)

                # re constrain gdeA to new axis
                if cmds.objExists('trkRot_'+guideName+'_gdeA.parentInverseMatrix'):
                    if cmds.listConnections('trkRot_'+guideName+'_gdeA.parentInverseMatrix') != None:
                        node = cmds.listConnections('trkRot_'+guideName+'_gdeA.parentInverseMatrix')[0]
                        node = cmds.listConnections('trkRot_'+guideName+'_gdeA.parentInverseMatrix')[0]
                        if cmds.nodeType(node) == 'multMatrix':
                            decomp = cmds.listConnections(node+'.matrixSum')[0] # DecomposeMatrix node
                            rotAxi = cmds.listConnections(decomp, p=True, c=True, t='transform') # Connection from decomp to gdeA
                            cmds.disconnectAttr(rotAxi[0], rotAxi[1]) # Disconnect output axis, trkRot input axis
                            cmds.setAttr(rotAxi[1], 0) # Zero out previously contrained axis of gdeA
                            cmds.connectAttr(decomp+'.outputRotate'+axis, 'trkRot_'+guideName+'_gdeA.rotate'+axis) # New connection
                        else:
                            cmds.warning('Failed to fix parent constraint for tracker axis change')

    def fixConstrainSldTracker(self, hbfrLst=None):
        '''
        Fix slider tracker constraints
        '''
        if hbfrLst == None:
            if cmds.ls(sl=1):
                hbfrLst=cmds.ls(sl=1)

        if hbfrLst != None:
            for hbfr in hbfrLst:
                if cmds.attributeQuery('guideTracker', node=hbfr, ex=True):
                    sldTrk = cmds.getAttr(hbfr+'.guideTracker')
                    if sldTrk:
                        self.constrainSldTracker(guide=hbfr, sldTrk=sldTrk)


    # Stretch Settings
    def constrainStrStart(self, guide, startParentLineEdit):
        '''
        '''
        if len(cmds.ls(sl=True)) == 1:
            cmds.setAttr(guide+'.startParent', cmds.ls(sl=True)[0], type='string')
            startParentLineEdit.setText(cmds.ls(sl=True)[0])
        else:
            cmds.warning('Select only one object')

    def constrainStrEnd(self, guide, endParentLineEdit):
        '''
        '''
        if len(cmds.ls(sl=True)) == 1:
            cmds.setAttr(guide+'.endParent', cmds.ls(sl=True)[0], type='string')
            endParentLineEdit.setText(cmds.ls(sl=True)[0])
        else:
            cmds.warning('Select only one object')

    def delStartCon(self, guide, startParentLineEdit):
        cmds.setAttr(guide+'.startParent', '', type='string')
        startParentLineEdit.setText('')

    def delEndCon(self, guide, endParentLineEdit):
        '''
        '''
        cmds.setAttr(guide+'.endParent', '', type='string')
        endParentLineEdit.setText('')

    def commitGdeStr(self, guide, twistCheckBox, strDefPosDoubleSpinBox, enableSnsCheckBox, multiplierDoubleSpinBox, jntCheckBox, doritoCheckBox):
        '''
        '''
        if guide:
            print('Committing changes to stretch guide')
            # set twist options
            cmds.setAttr(guide+'.twist', twistCheckBox.isChecked())
            # set deformer position option
            cmds.setAttr(guide+'.strDefPos', strDefPosDoubleSpinBox.value())
            # set sns option
            cmds.setAttr(guide+'.enableSns', enableSnsCheckBox.isChecked())
            # set sns multiplier option
            cmds.setAttr(guide+'.snsMultiplier', multiplierDoubleSpinBox.value())
            # set joint option
            cmds.setAttr(guide+'.stretchJoint', jntCheckBox.isChecked())
            # set joint dorito option
            cmds.setAttr(guide+'.stretchDorito', doritoCheckBox.isChecked())


    # Show / Hide
    def showCurves(self):
        pass
        '''self.hideGuides()
        countListTrue = []
        countListFalse = []
        showSystemList = cmds.ls("Orig*SldRoot", "Orig*StrRoot")
        # determine if guides are visible or not
        for x in showSystemList:
            if cmds.getAttr(x+'.visibility') == True:
                countListTrue.append(x)
            else:
                countListFalse.append(x)
        # show or hide based on current visibliity
        if len(countListTrue) > len(countListFalse):
            [cmds.setAttr(x+".visibility", False) for x in showSystemList]
        else:
            [cmds.setAttr(x+".visibility", True) for x in showSystemList]'''

    def showGuides(self):
        self.hideSystems()
        countListTrue = []
        countListFalse = []
        showGuideList = cmds.ls("Hbfr*GuideRoot", "Rig*GuidePath")
        # determine if guides are visible or not
        for x in showGuideList:
            if cmds.getAttr(x+'.visibility') == True:
                countListTrue.append(x)
            else:
                countListFalse.append(x)
        # show or hide based on current visibliity
        if len(countListTrue) > len(countListFalse):
            [cmds.setAttr(x+".visibility", False) for x in showGuideList]
        else:
            [cmds.setAttr(x+".visibility", True) for x in showGuideList]

    def showSystems(self):
        self.hideGuides()
        countListTrue = []
        countListFalse = []
        showSystemList = cmds.ls("Orig*SldRoot", "Orig*StrRoot")
        # determine if guides are visible or not
        for x in showSystemList:
            if cmds.getAttr(x+'.visibility') == True:
                countListTrue.append(x)
            else:
                countListFalse.append(x)
        # show or hide based on current visibliity
        if len(countListTrue) > len(countListFalse):
            [cmds.setAttr(x+".visibility", False) for x in showSystemList]
        else:
            [cmds.setAttr(x+".visibility", True) for x in showSystemList]

    def hideGuides(self):
        hideGuideList = cmds.ls("Hbfr*GuideRoot", "Rig*GuidePath")
        for x in hideGuideList:
            cmds.setAttr(x+".visibility", 0)

    def hideSystems(self):
        hideSystemList = cmds.ls("Orig*SldRoot", "Orig*StrRoot")
        for x in hideSystemList:
            cmds.setAttr( x+".visibility", 0)


    # Mirror Guides
    def mirrorGuideMultiple(self):
        sldGde = []
        strGde = []

        for guide in cmds.ls(sl=True):
            if cmds.attributeQuery('guideType', node=guide, ex=True):
                if cmds.getAttr(guide+'.guideType') == 'slider':
                    guideName = cmds.getAttr(guide+'.guideName')
                    if not guideName in sldGde:
                        sldGde.append(guideName)
                if cmds.getAttr(guide+'.guideType') == 'stretch':
                    guideName = cmds.getAttr(guide+'.guideName')
                    if not guideName in strGde:
                        strGde.append(guideName)

        if sldGde != []:
            for gdeNme in sldGde:
                if gdeNme[0] != 'M':
                    self.duplicateSymSld(gdeNme)
        if strGde != []:
            for gdeNme in strGde:
                if gdeNme[0] != 'M':
                    self.duplicateSymStr(gdeNme)

        self.refreshUI()

    def duplicateSymSld(self, guideName):
        # Name guide
        guide = 'Hbfr_'+guideName+'_SldGuideRoot'
        guideName = self.convertRLName(guideName)

        # Delete if mirror guide exists
        if cmds.objExists('Hbfr_'+guideName+'_SldGuideRoot'):
            cmds.delete(cmds.listRelatives('Hbfr_'+guideName+'_SldGuideRoot', p=True), hierarchy=True)

        # Mirror the guide
        sldGdeChild = cmds.listRelatives((cmds.listRelatives(guide, p=True)[0]), ad=True, type='transform')
        t           = self.getTransform(sldGdeChild[1])
        startPos    = self.getSymmetricalTransformOM(t, axis="yz")
        t           = self.getTransform(sldGdeChild[0])
        endPos      = self.getSymmetricalTransformOM(t, axis="yz")
        globScl     = cmds.getAttr(guide+'.globalScale')
        trkRev      = cmds.getAttr(guide+'.trackerRev')

        # mirrGde return = sldGdeRoot, gdeStart, gdeEnd
        mirrGde = self.createSliderGuide(guideName, globScl)

        self.setTransformFromMatrix(startPos, mirrGde[1])
        self.setTransformFromMatrix(endPos, mirrGde[2])

        # Mirror constraints settings
        if cmds.getAttr(guide+'.guideParent') != None:
            guidePar = self.convertRLName(cmds.getAttr(guide+'.guideParent'))
            cmds.setAttr(mirrGde[0]+'.guideParent', guidePar, type='string')

        if cmds.getAttr(guide+'.guideTracker') != None:
            guideTrk = self.convertRLName(cmds.getAttr(guide+'.guideTracker'))
            cmds.setAttr(mirrGde[0]+'.guideTracker', guideTrk, type='string')
            if cmds.objExists(guideTrk):
                # guide = mirrGde[0] # To avoid warning from constrainSldTracker
                self.constrainSldTracker(guide=mirrGde[0], sldTrk=guideTrk, mirror=True)

            # Set tracker axis
            axisDict = { 0:'X', 1:'Y', 2:'Z' }
            axis = axisDict[cmds.getAttr(guide+'.XYZ')]
            if not cmds.isConnected('twist_'+guideName+'_gdeExtract_twistExtractor_q2e.outputRotate'+axis,
                                    'eulerConv_'+guideName+'_gdeRotConv.input'):
                cmds.connectAttr('twist_'+guideName+'_gdeExtract_twistExtractor_q2e.outputRotate'+axis,
                                 'eulerConv_'+guideName+'_gdeRotConv.input', f=True)

        # Mirror tracker values
        cmds.setAttr(mirrGde[0]+'.XYZ', cmds.getAttr(guide+'.XYZ'))
        cmds.setAttr(mirrGde[0]+'.trackerRev', cmds.getAttr(guide+'.trackerRev'))

        if trkRev == 1: # Negative tracker values
            cmds.setAttr(mirrGde[0]+'.trackerMinRot', cmds.getAttr(guide+'.trackerMinRot')/-1)
            cmds.setAttr(mirrGde[0]+'.trackerMaxRot', cmds.getAttr(guide+'.trackerMaxRot')/-1)
        else:
            cmds.setAttr(mirrGde[0]+'.trackerMinRot', cmds.getAttr(guide+'.trackerMinRot'))
            cmds.setAttr(mirrGde[0]+'.trackerMaxRot', cmds.getAttr(guide+'.trackerMaxRot'))

        cmds.setAttr(mirrGde[0]+'.sliderJoint', cmds.getAttr(guide+'.sliderJoint'))
        cmds.setAttr(mirrGde[0]+'.sliderDorito', cmds.getAttr(guide+'.sliderDorito'))

        cmds.parent('Orig_'+guideName+'_SldGuideRoot', 'volumeGuides')

    def duplicateSymStr(self, guideName):
        guide = 'Hbfr_'+guideName+'_StrGuideRoot'
        guideName = self.convertRLName(guideName)

        # Delete if mirror guide exists
        if cmds.objExists('Hbfr_'+guideName+'_StrGuideRoot'):
            cmds.delete(cmds.listRelatives('Hbfr_'+guideName+'_StrGuideRoot', p=True), hierarchy=True)

        # Mirror the guide
        strGdeChild = cmds.listRelatives((cmds.listRelatives(guide, p=True)[0]), ad=True, type='transform')
        strGdeRoot = strGdeChild[3]
        strGdeStart = strGdeChild[0]
        strGdeEnd = strGdeChild[1]

        t           = self.getTransform(strGdeStart)
        startPos    = self.getSymmetricalTransformOM(t, axis="yz")
        t           = self.getTransform(strGdeEnd)
        endPos      = self.getSymmetricalTransformOM(t, axis="yz")
        globScl = cmds.getAttr(guide+'.globalScale')
        mirrGde = self.createStretchGuide(guideName, globScl)

        self.setTransformFromMatrix(startPos, mirrGde[1])
        self.setTransformFromMatrix(endPos, mirrGde[2])

        cmds.setAttr(mirrGde[0]+'.snsMultiplier', cmds.getAttr(strGdeRoot+'.snsMultiplier'))
        cmds.setAttr(mirrGde[0]+'.enableSns', cmds.getAttr(strGdeRoot+'.enableSns'))
        cmds.setAttr(mirrGde[0]+'.twist', cmds.getAttr(strGdeRoot+'.twist'))
        cmds.setAttr(mirrGde[0]+'.stretchJoint', cmds.getAttr(strGdeRoot+'.stretchJoint'))
        cmds.setAttr(mirrGde[0]+'.stretchDorito', cmds.getAttr(strGdeRoot+'.stretchDorito'))
        cmds.setAttr(mirrGde[0]+'.strDefPos', cmds.getAttr(strGdeRoot+'.strDefPos'))
        if cmds.getAttr(strGdeRoot+'.startParent') != None:
            startPar = self.convertRLName(cmds.getAttr(strGdeRoot+'.startParent'))
            cmds.setAttr(mirrGde[0]+'.startParent', startPar, type='string')

        if cmds.getAttr(strGdeRoot+'.endParent') != None:
            endPar = self.convertRLName(cmds.getAttr(strGdeRoot+'.endParent'))
            cmds.setAttr(mirrGde[0]+'.endParent', endPar, type='string')

        # Parent
        cmds.parent('Orig_'+guideName+'_StrGuideRoot', 'volumeGuides')


    # Guide Selection
    def getGuideRoot(self, guide=False, select=True):
        '''
        Returns guide root from guide objects

        guide = (str) Individual guide object
        select = (bol) Select guide root(s)
        '''

        if guide != False:
            guides = [guide]
        else:
            guides = cmds.ls(sl=True)

        hbfrLst = []
        for item in guides:
            if cmds.attributeQuery('guideType', node=item, ex=True):
                guideType = cmds.getAttr(item+'.guideType')
                guideName = cmds.getAttr(item+'.guideName')

                if guideType == ('slider'):
                    sldHbfr = 'Hbfr_'+guideName+'_SldGuideRoot'
                    if not sldHbfr in hbfrLst:
                        hbfrLst.append(sldHbfr)

                if guideType == ('stretch'):
                    strHbfr = 'Hbfr_'+guideName+'_StrGuideRoot'
                    if not strHbfr in hbfrLst:
                        hbfrLst.append(strHbfr)

        if select == True:
            cmds.select(hbfrLst, r=True)

        return hbfrLst

    def selectAllGuideRoot(self):
        # Select all guide HBFR's
        slider = cmds.ls('Hbfr_*_SldGuideRoot')
        stretch = cmds.ls('Hbfr_*_StrGuideRoot')
        cmds.select(slider, stretch)
        self.guideCollapsibleListWidget.selectAll()

    def selectGuide(self):
        '''
        '''
        curItem = self.guideCollapsibleListWidget.currentItem()
        if curItem:
            curItemTitle = self.guideCollapsibleListWidget.itemWidget(curItem).title()
            cmds.select(curItemTitle)


    # Align Guides
    def alignSelctGuideRoot(self):
        hbfrLst = []
        selList = []
        for sel in cmds.ls(sl=1):
            hbfr = self.getGuideRoot(guide=sel, select=False)[0]
            if hbfr not in hbfrLst:
                hbfrLst.append(hbfr)
        if hbfrLst != []:
            for h in hbfrLst:
                if cmds.getAttr(h+'.guideType') == 'slider':
                    guideName = cmds.getAttr(h+'.guideName')
                    sldGdeStart = 'Ctl_'+guideName+'_SldGuideStart'
                    sldGdeStartPos = cmds.xform(sldGdeStart, q=True, ws=True, m=True)
                    cmds.xform(h, ws=True, m=sldGdeStartPos)
                    cmds.xform(sldGdeStart, ws=True, m=sldGdeStartPos)
                    selList.append(h)

                if cmds.getAttr(h+'.guideType') == 'stretch':
                    guideName = cmds.getAttr(h+'.guideName')
                    strGdeStart = 'Ctl_'+guideName+'_StrGuideStart'
                    strGdeEnd   = 'Ctl_'+guideName+'_StrGuideEnd'
                    strGdeStartPos = cmds.xform(strGdeStart, q=True, ws=True, m=True)
                    strGdeEndPos   = cmds.xform(strGdeEnd, q=True, ws=True, m=True)
                    cmds.xform(h, ws=True, m=strGdeStartPos)
                    cmds.xform(strGdeStart, ws=True, m=strGdeStartPos)
                    cmds.xform(strGdeEnd, ws=True, m=strGdeEndPos)
                    selList.append(h)

        if selList != []:
            cmds.select(selList, r=True)

    def alignAllGuideRoot(self):
        '''
        Align all guide HBFR's to guide 'start' obj.
        '''
        selList = []
        slider, stretch = cmds.ls('Hbfr_*_SldGuideRoot'), cmds.ls('Hbfr_*_StrGuideRoot')
        for item in [slider, stretch]:
            for i in item:
                nmeSplit = i.split('_')
                side, name, type = nmeSplit[1], nmeSplit[2], nmeSplit[3]

                if type.startswith('Sld'):
                    sldGdeStart = 'Ctl_'+side+'_'+name+'_SldGuideStart'
                    sldHbfr     = 'Hbfr_'+side+'_'+name+'_SldGuideRoot'
                    sldGdeStartPos = cmds.xform(sldGdeStart, q=True, ws=True, m=True)
                    cmds.xform(sldHbfr, ws=True, m=sldGdeStartPos)
                    cmds.xform(sldGdeStart, ws=True, m=sldGdeStartPos)
                    selList.append(sldHbfr)

                if type.startswith('Str'):
                    strGdeStart = 'Ctl_'+side+'_'+name+'_StrGuideStart'
                    strGdeEnd   = 'Ctl_'+side+'_'+name+'_StrGuideEnd'
                    strHbfr     = 'Hbfr_'+side+'_'+name+'_StrGuideRoot'
                    strGdeStartPos = cmds.xform(strGdeStart, q=True, ws=True, m=True)
                    strGdeEndPos   = cmds.xform(strGdeEnd, q=True, ws=True, m=True)
                    cmds.xform(strHbfr, ws=True, m=strGdeStartPos)
                    cmds.xform(strGdeStart, ws=True, m=strGdeStartPos)
                    cmds.xform(strGdeEnd, ws=True, m=strGdeEndPos)
                    selList.append(strHbfr)

        if selList != []:
            cmds.select(selList, r=True)

    def alignGuideWorld(self):
        wldPos = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        # Align all guide HBFR's to center of world.
        # Used to scale all guides at once.
        selList = []
        slider, stretch = cmds.ls('Hbfr_*_SldGuideRoot'), cmds.ls('Hbfr_*_StrGuideRoot')
        for item in [slider, stretch]:
            for i in item:
                nmeSplit = i.split('_')
                side, name, type = nmeSplit[1], nmeSplit[2], nmeSplit[3]

                if type.startswith('Sld'):
                    sldGdeStart = 'Ctl_'+side+'_'+name+'_SldGuideStart'
                    sldHbfr     = 'Hbfr_'+side+'_'+name+'_SldGuideRoot'
                    sldGdeStartPos = cmds.xform(sldGdeStart, q=True, ws=True, m=True)
                    cmds.xform(sldHbfr, ws=True, m=wldPos)
                    cmds.xform(sldGdeStart, ws=True, m=sldGdeStartPos)
                    selList.append(sldHbfr)

                if type.startswith('Str'):
                    strGdeStart = 'Ctl_'+side+'_'+name+'_StrGuideStart'
                    strGdeEnd   = 'Ctl_'+side+'_'+name+'_StrGuideEnd'
                    strHbfr     = 'Hbfr_'+side+'_'+name+'_StrGuideRoot'

                    strGdeStartPos = cmds.xform(strGdeStart, q=True, ws=True, m=True)
                    strGdeEndPos   = cmds.xform(strGdeEnd, q=True, ws=True, m=True)

                    cmds.xform(strHbfr, ws=True, m=wldPos)
                    cmds.xform(strGdeStart, ws=True, m=strGdeStartPos)
                    cmds.xform(strGdeEnd, ws=True, m=strGdeEndPos)
                    selList.append(strHbfr)

        if selList != []:
            cmds.select(selList, r=True)


    # Load / Save Gides
    def backupGuideDecide(self):
        # New guide backup
        self.gdeBackupDict = OrderedDict()
        slider = cmds.ls('Hbfr_*_SldGuideRoot')
        stretch = cmds.ls('Hbfr_*_StrGuideRoot')
        cmds.select(slider, stretch)
        guideList = cmds.ls(sl=True)
        sliderList = []
        stretchList = []
        if not guideList:
            raise IndexError('No Guides slected for backup')

        for guide in guideList:
            if cmds.getAttr(guide+'.guideType') == 'slider':
                sliderList.append(guide)
            else:
                stretchList.append(guide)

        for guide in sliderList:
            self.backupGuideSlider(guide)
        for guide in stretchList:
            self.backupGuideStretch(guide)

        dirName = os.path.dirname(__file__)
        startingDirectory = os.path.join(dirName, '../elements/template/biped')
        fileType = '*.json'
        savePath = cmds.fileDialog2(startingDirectory=startingDirectory, fm=0, okc="Save", fileFilter=fileType)

        with open(savePath[0], 'w') as f:
            data = self.gdeBackupDict
            json.dump(data, f)
            print('Seccessfully backed up guide dictionary to', savePath)

    def backupGuideSlider(self, guide):
        guideChildren = cmds.listRelatives(guide, ad=True, type='transform')
        guideStart = guideChildren[1]
        guideEnd = guideChildren[0]
        guideStartMatrix = list(self.getTransform(guideStart))
        guideEndMatrix = list(self.getTransform(guideEnd))
        # guideStartMatrix = [item for items in self.getTransform(guideStart) for item in items] #Flattens matrix to an array
        # guideEndMatrix = [item for items in self.getTransform(guideEnd) for item in items] #Flattens matrix to an array

        gdeAttrDict = OrderedDict() # Get guide attrs
        gdeAttrDict[guide+'.guideType'] = [cmds.getAttr(guide+'.guideType') , cmds.getAttr(guide+'.guideName', type=True)]
        gdeAttrDict[guide+'.guideName'] = [cmds.getAttr(guide+'.guideName') , cmds.getAttr(guide+'.guideName', type=True)]
        gdeAttrDict[guide+'.globalScale'] = [cmds.getAttr(guide+'.globalScale') , cmds.getAttr(guide+'.globalScale', type=True)]
        gdeAttrDict[guide+'.guideParent'] = [cmds.getAttr(guide+'.guideParent') , cmds.getAttr(guide+'.guideParent', type=True)]
        gdeAttrDict[guide+'.guideTracker'] = [cmds.getAttr(guide+'.guideTracker') , cmds.getAttr(guide+'.guideTracker', type=True)]
        gdeAttrDict[guide+'.trackerMinRot'] = [cmds.getAttr(guide+'.trackerMinRot') , cmds.getAttr(guide+'.trackerMinRot', type=True)]
        gdeAttrDict[guide+'.trackerMaxRot'] = [cmds.getAttr(guide+'.trackerMaxRot') , cmds.getAttr(guide+'.trackerMaxRot', type=True)]
        gdeAttrDict[guide+'.XYZ'] = [cmds.getAttr(guide+'.XYZ') , cmds.getAttr(guide+'.XYZ', type=True)]
        gdeAttrDict[guide+'.trackerRev'] = [cmds.getAttr(guide+'.trackerRev') , cmds.getAttr(guide+'.trackerRev', type=True)]
        gdeAttrDict[guide+'.sliderJoint'] = [cmds.getAttr(guide+'.sliderJoint') , cmds.getAttr(guide+'.sliderJoint', type=True)]
        gdeAttrDict[guide+'.sliderDorito'] = [cmds.getAttr(guide+'.sliderDorito') , cmds.getAttr(guide+'.sliderDorito', type=True)]

        # Matrix need to be added last for restoreGuides()
        gdeAttrDict[guideStart] = guideStartMatrix
        gdeAttrDict[guideEnd] = guideEndMatrix

        self.gdeBackupDict[cmds.getAttr(guide+'.guideName')+'_'+cmds.getAttr(guide+'.guideType')] = gdeAttrDict # Add attrs dict to backup dict

    def backupGuideStretch(self, guide):
        guideChildren = cmds.listRelatives(guide, ad=True, type='transform')

        for child in guideChildren:
            if child.endswith('Start'):
                guideStart = child
            if child.endswith('End'):
                guideEnd = child

        guideStartMatrix = list(self.getTransform(guideStart))
        guideEndMatrix = list(self.getTransform(guideEnd))
        # guideStartMatrix = [item for items in self.getTransform(guideStart) for item in items] #Flattens matrix to an array
        # guideEndMatrix = [item for items in self.getTransform(guideEnd) for item in items] #Flattens matrix to an array

        gdeAttrDict = OrderedDict() # Get guide attrs
        gdeAttrDict[guide+'.guideType'] = [cmds.getAttr(guide+'.guideType') , cmds.getAttr(guide+'.guideName', type=True)]
        gdeAttrDict[guide+'.guideName'] = [cmds.getAttr(guide+'.guideName') , cmds.getAttr(guide+'.guideName', type=True)]
        gdeAttrDict[guide+'.globalScale'] = [cmds.getAttr(guide+'.globalScale') , cmds.getAttr(guide+'.globalScale', type=True)]
        gdeAttrDict[guide+'.startParent'] = [cmds.getAttr(guide+'.startParent') , cmds.getAttr(guide+'.startParent', type=True)]
        gdeAttrDict[guide+'.endParent'] = [cmds.getAttr(guide+'.endParent') , cmds.getAttr(guide+'.endParent', type=True)]
        gdeAttrDict[guide+'.snsMultiplier'] = [cmds.getAttr(guide+'.snsMultiplier') , cmds.getAttr(guide+'.snsMultiplier', type=True)]
        gdeAttrDict[guide+'.enableSns'] = [cmds.getAttr(guide+'.enableSns') , cmds.getAttr(guide+'.enableSns', type=True)]
        gdeAttrDict[guide+'.twist'] = [cmds.getAttr(guide+'.twist') , cmds.getAttr(guide+'.twist', type=True)]
        gdeAttrDict[guide+'.strDefPos'] = [cmds.getAttr(guide+'.strDefPos') , cmds.getAttr(guide+'.strDefPos', type=True)]
        gdeAttrDict[guide+'.stretchDorito'] = [cmds.getAttr(guide+'.stretchDorito') , cmds.getAttr(guide+'.stretchDorito', type=True)]

        # Matrix need to be added last for restoreGuides()
        gdeAttrDict[guideStart] = guideStartMatrix
        gdeAttrDict[guideEnd] = guideEndMatrix

        self.gdeBackupDict[cmds.getAttr(guide+'.guideName')+'_'+cmds.getAttr(guide+'.guideType')] = gdeAttrDict # Add attrs dict to backup dict

    def restoreGuides(self, fromFile=None):
        ''' #gdeBackupDict example:

        OrderedDict([('L_TestSys_slider',
        OrderedDict(
            [
            ('Hbfr_L_TestSys_SldGuideRoot.guideType', ['slider', 'string']),
            ('Hbfr_L_TestSys_SldGuideRoot.guideName', ['L_TestSys', 'string']),
            ('Hbfr_L_TestSys_SldGuideRoot.globalScale', [1.0, 'float']),
            ('Hbfr_L_TestSys_SldGuideRoot.guideParent', ['joint1', 'string']),
            ('Hbfr_L_TestSys_SldGuideRoot.guideTracker', ['joint2', 'string']),
            ('Hbfr_L_TestSys_SldGuideRoot.trackerMinRot', [0.0, 'float']),
            ('Hbfr_L_TestSys_SldGuideRoot.trackerMaxRot', [30.0, 'float']),
            ('Hbfr_L_TestSys_SldGuideRoot.XYZ', [0, 'long']),
            ('Hbfr_L_TestSys_SldGuideRoot.trackerRev', [False, 'bool']),
            ('Hbfr_L_TestSys_SldGuideRoot.sliderJoint', [True, 'bool']),
            ('Ctl_L_TestSys_SldGuideStart', [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]),
            ('Ctl_L_TestSys_SldGuideEnd', [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 4.0, 1.0])
            ]
            )
        )])
        '''

        # Load fromFile arg
        gdeBackupDict = OrderedDict()
        if fromFile:# From postbuild script
            gdeBackupDict = json.load(open(fromFile), object_pairs_hook=OrderedDict)
        else:# From UI
            dirName = os.path.dirname(__file__)
            startingDirectory = os.path.join(dirName, '../elements/template/biped')
            fileType = '*.json'
            loadPath = cmds.fileDialog2(startingDirectory=startingDirectory, fm = 1, okc = "Load", fileFilter = fileType)
            gdeBackupDict = json.load(open(loadPath[0]), object_pairs_hook=OrderedDict)


        # Load guides
        if not cmds.objExists('volumeGuides'):
            cmds.createNode('transform', n='volumeGuides')

        for key,value in gdeBackupDict.items():
            guideType = key.split('_')[-1] #key = 'L_TestSys_slider'
            guideName = key[:-(len(guideType)+1)]
            items = list(value.items())

            if guideType == 'slider':
                #___________________________________
                for item in items:# Create new guide
                    if '.globalScale' in list(item)[0]:#get correct tuple (attr, [attrVal, attrTyp])
                        globalScl = item[1][0] # [attrVal, attrTyp]
                        newGde = self.createSliderGuide(guideName, globalScl)
                #___________________________________
                hbfr = items[0][0].split('.')[0]
                for item in items:# Set guide tracker constraint
                    if '.guideTracker' in list(item)[0]:#get correct tuple (attr, [attrVal, attrTyp])
                        tracker = item[1][0] # [attrVal, attrTyp]
                        if tracker != None:
                            if cmds.objExists(tracker):
                                self.selGdeGlobSld = hbfr
                                self.constrainSldTracker(guide=newGde[0], sldTrk=tracker)
                #___________________________________
                for item in items:# Set tracker axis
                    if '.XYZ' in list(item)[0]:#get correct tuple (attr, [attrVal, attrTyp])
                        axis = item[1][0] # [attrVal, attrTyp]
                        axisDict = {0:'X', 1:'Y', 2:'Z'}
                        try:
                            cmds.connectAttr('twist_'+guideName+'_gdeExtract_twistExtractor_q2e.outputRotate'+axis,
                                             'eulerConv_'+guideName+'_gdeRotConv.input', f=True)
                        except:
                            pass
                #___________________________________
                for item in items[:-2]:# Skip guide position attrs
                    attr    = item[0]
                    attrVal = item[1][0]
                    attrTyp = item[1][1]
                    if attrVal != None:
                        if attrTyp == 'string':# Can only set Type, if type == string
                            cmds.setAttr(attr, l=False)
                            cmds.setAttr(attr, attrVal, type='string')
                        else:
                            cmds.setAttr(attr, l=False)
                            cmds.setAttr(attr, attrVal)
                #___________________________________
                for item in items[-2:]:# Guide position attrs
                    ctl     = item[0]
                    attrVal = item[1]
                    if attrVal != None:
                        self.setTransformFromMatrix(attrVal, ctl) # Slider start position
                #___________________________________
                orig = hbfr.replace('Hbfr_', 'Orig_')
                cmds.parent(orig, 'volumeGuides')


            if guideType == 'stretch':
                #___________________________________
                for item in items:# Create new guide
                    if '.globalScale' in list(item)[0]:#get correct tuple (attr, [attrVal, attrTyp])
                        globalScl = item[1][0] # [attrVal, attrTyp]
                        newGde = self.createStretchGuide(guideName, globalScl) # guideName , globScl
                #___________________________________
                for item in items[:-2]:# Skip guide position attrs
                    attr    = item[0]
                    attrVal = item[1][0]
                    attrTyp = item[1][1]
                    if attrVal != None:
                        if attrTyp == 'string':# Can only set Type, if type == string
                            cmds.setAttr(attr, l=False)
                            cmds.setAttr(attr, attrVal, type='string')
                        else:
                            cmds.setAttr(attr, l=False)
                            cmds.setAttr(attr, attrVal)
                #___________________________________
                for item in items[-2:]:# Guide position attrs
                    ctl     = item[0]
                    attrVal = item[1]
                    if attrVal != None:
                        self.setTransformFromMatrix(attrVal, ctl) # Slider start position
                #___________________________________
                hbfr = items[0][0].split('.')[0]
                orig = hbfr.replace('Hbfr_', 'Orig_')
                cmds.parent(orig, 'volumeGuides')

        cmds.select(None)
        self.refreshUI()



    def newDefCheck(self, guideType, guideName):
        '''
        Checks to see if guide uses a joint or transform for Def.
        Checks to see if joint is in a skincluster.
        If False, returns newDef == 1
        If True, returns newDef == 0
        if True, returns list of objects that have joint as part of its skincluster.
        '''

        if guideType == 'slider':
            root = '_SldRoot'
            suff = '_SldMain'
        if guideType == 'stretch':
            root = '_StrRoot'
            suff = '_StrMain'

        origObj = 'Orig_'+guideName+root
        sknMsh = [] # Compiled list of skinned objects
        newDef  = 1

        jntSkn = [] # Stores skinclusters that contain system joint
        if cmds.objExists(origObj):
            sysDef = [i for i in cmds.listRelatives(origObj, ad=True) if i.endswith(suff)][0]
            if cmds.nodeType(sysDef) == 'joint': # Check if joint or transform
                if cmds.listConnections(sysDef+'.wm[0]') != None: # Check if joint is used in a skinCluster
                    for con in cmds.listConnections(sysDef+'.wm[0]'):
                        if cmds.objectType(con) == 'skinCluster':
                            jntSkn.append(con)
                            newDef = 0
                        else:
                            newDef = 1
                else:
                    newDef = 1
            else:
                newDef = 1
        else:
            newDef = 1

        # Get skinned meshes or surfaces from stored skinclusters in jntSkn
        if jntSkn != []:
            for sknCls in jntSkn:
                sknObj = [] # Stores objects connected to stored skinclusters
                for nde in cmds.listHistory(sknCls+'.outputGeometry', future=True):
                    if cmds.nodeType(nde) == 'mesh' or cmds.nodeType(nde) == 'nurbsSurface':
                        sknObj.append(nde)
                if sknObj != []:
                    [sknMsh.append(nde) for nde in sknObj]


        if newDef == 0:
            cmds.parent(sysDef, w=1)
            # Disconnect connections
            if cmds.listConnections(sysDef+'.translate', d=0, s=1, p=1)!= None:
                inTra = cmds.listConnections(sysDef+'.translate', d=0, s=1, p=1)[0]
                if inTra:
                    cmds.delete(inTra.split('.')[0])

            if cmds.listConnections(sysDef+'.rotate', d=0, s=1, p=1) != None:
                inRot = cmds.listConnections(sysDef+'.rotate', d=0, s=1, p=1)[0]
                if inRot:
                    cmds.delete(inRot.split('.')[0])

            if cmds.listConnections(sysDef+'.sx', d=0, s=1, p=1) != None:
                inScl = cmds.listConnections(sysDef+'.sx', d=0, s=1, p=1)[0]
                if inScl:
                    cmds.delete(inScl.split('.')[0])

            if cmds.listConnections(sysDef+'.sz', d=0, s=1, p=1) != None:
                inScl = cmds.listConnections(sysDef+'.sz', d=0, s=1, p=1)[0]
                if inScl:
                    cmds.delete(inScl.split('.')[0])

            cmds.delete(origObj)
        else:
            if cmds.objExists(origObj):
                cmds.delete(origObj)

        return newDef, sknMsh, jntSkn

    def getDefFromGuide(self, slider=None, stretch=None):
        '''
        Get name of joint, from guide name,
        that will be used when parenting systems
        '''
        if slider != None:
            sliderNameSplit = slider.split("_")
            sliderMidName   = '{Side}_{System}'.format(Side=sliderNameSplit[1], System=sliderNameSplit[2])
            sldPar = 'Def_'+sliderMidName+'_SldMain'
            return sldPar

        if stretch != None:
            stretchNameSplit = stretch.split("_")
            stretchMidName   = '{Side}_{System}'.format(Side=stretchNameSplit[1], System=stretchNameSplit[2])
            strPar = 'Def_'+stretchMidName+'_StrMain'
            return strPar

    def globalScaleConn(self, globalObj=None):
        # globalObj = self.ui.lne_globalScaleObj.text()
        # if globalObj == '':
        #     globalObj = 'global_C0_ctl'

        if globalObj == None:
            globalObj = 'global_C0_ctl'

        if cmds.objExists(globalObj):
            sclNde = cmds.ls('*_snsSysGlobalScale*', type='multiplyDivide')
            if sclNde != []:
                if cmds.attributeQuery('globalScale', node=globalObj, ex=True):
                    for nde in sclNde:
                        if cmds.listConnections(nde+'.snsSysGlobalScale', p=True, d=False): # see if there is a connection
                            if cmds.listConnections(nde+'.snsSysGlobalScale', p=True, d=False)[0] != globalObj+'.globalScale': # is connection NOT globalScale?
                                cmds.connectAttr(globalObj+'.globalScale', nde+'.snsSysGlobalScale', f=True)
                        else:
                            cmds.connectAttr(globalObj+'.globalScale', nde+'.snsSysGlobalScale', f=True)
                else:
                    for nde in sclNde:
                        if cmds.listConnections(nde+'.snsSysGlobalScale', p=True, d=False): # see if there is a connection
                            if cmds.listConnections(nde+'.snsSysGlobalScale', p=True, d=False)[0] != globalObj+'.sx': # is connection NOT .sx?
                                cmds.connectAttr(globalObj+'.sx', nde+'.snsSysGlobalScale', f=True)
                        else:
                            cmds.connectAttr(globalObj+'.sx', nde+'.snsSysGlobalScale', f=True)
            print('***** Volume Sys Global Scale - Done *****')
        else:
            print('Global scale obj not found in the scene')

    def angleRefresh(self, guide, currentValDoubleSpineBox):
        if guide == None:
            print('No slider guide loaded')
        else:
            print(cmds.getAttr(guide+'.currentValRef'))
            print(float("{:.2f}".format(cmds.getAttr(guide+'.currentValRef'))))
            currentValDoubleSpineBox.setValue(float("{:.2f}".format(cmds.getAttr(guide+'.currentValRef'))))
            # currentValDoubleSpineBox.setValue(cmds.getAttr(guide+'.currentValRef'))
            # currentValLineEdit.setValue(cmds.getAttr(guide+'.currentValRef')[:6])

    def deleteMultiple(self, hbfr=None):
        '''
        hbfr passed from duplicateSymSld
        '''
        if hbfr:
            cmds.delete(cmds.listRelatives(hbfr, p=True), hierarchy=True)
        else:
            for item in cmds.ls(sl=1):
                if cmds.attributeQuery('guideType', node=item, ex=True):
                    print('found guide')

                    if cmds.getAttr(item+'.guideType') == ('slider'):
                        print('found slider')
                        cmds.delete(cmds.listRelatives('Hbfr_'+cmds.getAttr(item+'.guideName')+'_SldGuideRoot', p=True), hierarchy=True)

                    if cmds.getAttr(item+'.guideType') == ('stretch'):
                        print('found stretch')
                        cmds.delete(cmds.listRelatives('Hbfr_'+cmds.getAttr(item+'.guideName')+'_StrGuideRoot', p=True), hierarchy=True)


    def convertRLName(self, name):
        '''
        Convert a string with underscore

        i.e: "_\L", "_L0\_", "L\_", "_L" to "R". And vice and versa.

        :param string name: string to convert
        :return: Tuple of Integer
        '''
        if name == "L":
            return "R"
        elif name == "R":
            return "L"
        re_str = "_[RL][0-9]+_|^[RL][0-9]+_|_[RL][0-9]+$|_[RL]_|^[RL]_|_[RL]$"
        rePattern = re.compile(re_str)

        reMatch = re.search(rePattern, name)
        if reMatch:
            instance = reMatch.group(0)
            if instance.find("R") != -1:
                rep = instance.replace("R", "L")
            else:
                rep = instance.replace("L", "R")

            name = re.sub(rePattern, rep, name)

        return name

    def extractTwist(self, root, tip, axis, name='', scaleSupport=False):
        # get the worldMatrix for root and tip, without the scale
        rotOrder = {'x':0, 'y':1, 'z':2}
        mOffset = cmds.createNode('multMatrix', ss=1,
            n='_'.join([name, 'twistExtractor', 'mmt']))
        cmds.connectAttr(tip+ '.wm' , mOffset + '.matrixIn[0]')
        cmds.connectAttr(root + '.wim', mOffset + '.matrixIn[1]')
        if scaleSupport:
            inScale  = cmds.createNode('decomposeMatrix', ss=1,
                n='_'.join([name, 'twistInvScale', 'dcm']))

            cmds.connectAttr(root + '.wm', inScale + '.inputMatrix')
            outScale = cmds.createNode('composeMatrix', ss=1,
                n='_'.join([name, 'twistInvScale', 'cpm']))
            cmds.connectAttr(inScale + '.outputScaleX', outScale + '.inputScaleX')
            cmds.connectAttr(inScale + '.outputScaleY', outScale + '.inputScaleY')
            cmds.connectAttr(inScale + '.outputScaleZ', outScale + '.inputScaleZ')
            cmds.connectAttr(outScale + '.outputMatrix', mOffset + '.matrixIn[2]')

        outQuat = cmds.createNode('decomposeMatrix', ss=1,
            n='_'.join([name, 'twistExtractor', 'dcm']))
        cmds.connectAttr(mOffset + '.matrixSum', outQuat + '.inputMatrix')
        output = cmds.createNode('quatToEuler', ss=1,
            n='_'.join([name, 'twistExtractor', 'q2e']))
        cmds.setAttr(output+'.inputRotateOrder', rotOrder[axis])

        conAxis = ['X', 'Y', 'Z']
        [cmds.connectAttr(outQuat + '.outputQuat'+a.upper(), output+'.inputQuat'+a.upper()) for a in conAxis]
        cmds.connectAttr(outQuat + '.outputQuatW', output + '.inputQuatW')
        return output + '.outputRotate'+axis.upper()

    def getTransform(self, node):
        """Return the transformation matrix of the dagNode in worldSpace.

        Arguments:
            node (dagNode): The dagNode to get the translation

        Returns:
            matrix: The transformation matrix
        """
        return cmds.xform(node, q=True, ws=True, m=True)

    def getSymmetricalTransformOM(self, t, axis='yz'):
        '''
        objList = ([]) List of objects to mirror
        axis    = ('') Axis to mirror on, x,y,z
        '''
        axisDict = {}
        axisDict['yz'] = [-1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        axisDict['zx'] = [1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        axisDict['xy'] = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1]

        mat1 = MMatrix(t)
        mat2 = MMatrix(axisDict.get(axis))
        t = (mat1 * mat2)

        return t

    def setTransformFromMatrix(self, matrix, target):
        """sets dagNode transformations in world space.

        Arguments:
            matrix (MMatrix): The source matrix
            target (dagNode): The target dagNode

        Returns:
            None

        """
        cmds.xform(target, ws=True, m=matrix)

    def parentConstraint(self, parent, child, t=['x','y','z'], r=['x','y','z'], s=['x','y','z'], mo=True):
        '''
        Node based parent constraint.

        parent = (str) Name of parent
        child  = (str) Name of child
        t      = []    List of axis to constrain to translate
        r      = []    List of axis to constrain to rotate
        s      = []    List of axis to constrain to scale
        mo     = (bol) Maintain offset option
        '''

        if type(child) != 'list':
            child = [child]

        for c in child:
            multMat = cmds.createNode('multMatrix', n=parent+'_multMatrix_rigUParCon', ss=True)
            decomp  = cmds.createNode('decomposeMatrix', n=parent+'_matrixDecomp_rigUParCon', ss=True)

            if mo == True:
                offset = cmds.createNode('multMatrix', n=parent+'_offset', ss=True)
                cmds.connectAttr(c+'.worldMatrix[0]', offset+'.matrixIn[0]', f=1)
                cmds.connectAttr(parent+'.worldInverseMatrix[0]', offset+'.matrixIn[1]', f=1)
                # Offset
                cmds.setAttr(multMat+'.matrixIn[0]', cmds.getAttr(offset+'.matrixSum'), type='matrix')
                cmds.connectAttr(parent+'.worldMatrix[0]', multMat+'.matrixIn[1]', f=1)
                cmds.connectAttr(c+'.parentInverseMatrix[0]', multMat+'.matrixIn[2]', f=1)
                cmds.connectAttr(multMat+'.matrixSum', decomp+'.inputMatrix', f=1)
                cmds.delete(offset)
            else:
                cmds.connectAttr(parent+'.worldMatrix[0]', multMat+'.matrixIn[0]', f=1)
                cmds.connectAttr(c+'.parentInverseMatrix[0]', multMat+'.matrixIn[1]', f=1)
                cmds.connectAttr(multMat+'.matrixSum', decomp+'.inputMatrix', f=1)

            [cmds.connectAttr(decomp+'.outputTranslate'+axis.upper(), c+'.translate'+axis.upper(), f=1) for axis in t if axis]
            [cmds.connectAttr(decomp+'.outputRotate'+axis.upper(), c+'.rotate'+axis.upper(), f=1) for axis in r if axis]
            [cmds.connectAttr(decomp+'.outputScale'+axis.upper(), c+'.scale'+axis.upper(), f=1) for axis in s if axis]

            return decomp

    def getSkinClusterInfluenceIndex(self, skin_cluster, influence):
        """Get the index of given influence.

        Args:
            skin_cluster (str): skinCluster node
            influence (str): influence object

        Return:
            int: index
        """
        skin_cluster_obj = (
            om2.MSelectionList().add(skin_cluster).getDependNode(0)
        )
        influence_dag = om2.MSelectionList().add(influence).getDagPath(0)
        index = int(
            OpenMayaAnim.MFnSkinCluster(
                skin_cluster_obj
            ).indexForInfluenceObject(influence_dag)
        )

        return index

    def getSkinClusterInfluences(self, skin_cluster, full_path=False):
        """Get skin_cluster influences.

        Args:
            skin_cluster (str): skinCluster node
            full_path (bool): If true returns full path, otherwise partial path of
                influence names.

        Return:
            list(str,): influences
        """
        name = "fullPathName" if full_path else "partialPathName"
        skin_cluster_obj = (
            om2.MSelectionList().add(skin_cluster).getDependNode(0)
        )
        inf_objs = OpenMayaAnim.MFnSkinCluster(
            skin_cluster_obj
        ).influenceObjects()
        influences = [getattr(x, name)() for x in inf_objs]

        return influences

    def setBindPose(self, mesh=None, setAngle=0, sknCls=None):
        '''
        Resets bindpose on all joints connected to skincluster on selected mesh.
        And sets joints prefered angle.

        mesh     = (str) Get skincluster from mesh
        setAngle = (bol) Set joints current oritentation to preferred angle
        sknCls   = ([ ]) list of skinclusters

        '''

        if sknCls == None: #Get skinCls from mesh
            sknCls = getSkinClusters(mesh)
            if not sknCls:
                print('Cannot find skinCluster on obj >> ' + mesh)

        if not isinstance(sknCls, list): #if not a list
            sknCls = [sknCls]

        if len(sknCls) != 0:
            for skn in sknCls:
                sknJts = self.getSkinClusterInfluences(skn)

                # Delete bindPose
                if cmds.listConnections(skn+'.bindPose'):
                    cmds.delete(cmds.listConnections(skn+'.bindPose'))

                # Connect pre bind matrix
                for jnt in sknJts:
                    jntIdx = self.getSkinClusterInfluenceIndex(skn, jnt)
                    if setAngle > 0:
                        cmds.joint(jnt, e=1, spa=1) # Set preferred angle
                    pos = cmds.getAttr(jnt+'.wim')
                    cmds.setAttr(skn+'.bindPreMatrix[{}]'.format(jntIdx), pos, type='matrix')
   # Not in use. on rename, hbfr (line 2350) does not exist
    def renameGuide(self, guide, guideNameLineEdit):
        '''
        '''
        newName = guideNameLineEdit.text()
        if newName == '':
            raise TypeError('Enter a Name')

        hbfr = guide
        nmeSplit = newName.split('_')
        side, name = nmeSplit[0], nmeSplit[1]

        if hbfr.startswith('Hbfr_'):
            if cmds.attributeQuery('guideName', node=hbfr, ex=True):
                hbfrPar = cmds.listRelatives(hbfr, p=True, type='transform')[0]
                gdeNme  = cmds.getAttr(hbfr+'.guideName')

                # Format description
                sysSide = side
                sysDef  = name
                sysDef = sysDef[0].capitalize() + sysDef[1:]
                sysDef  = re.sub('[^A-Za-z0-9]+', '', sysDef) # Remove special characters
                newNme = sysSide+'_'+sysDef

                # Make sure guide does not exist
                if not cmds.objExists('Orig_'+newNme+'_'+hbfrPar.split('_')[3]):
                    renameLst = cmds.listRelatives(hbfr, p=True, type='transform') + cmds.listRelatives(hbfr, ad=True, type='transform') + [hbfr]
                    # set guideName attr
                    chld = cmds.listRelatives(renameLst[0], ad=True, type='transform')
                    for c in chld:
                        if cmds.attributeQuery('guideName', node=c, ex=True):
                            cmds.setAttr(c+'.guideName', l=False)
                            cmds.setAttr(c+'.guideName', newNme, type='string')
                            cmds.setAttr(c+'.guideName', l=True)
                    # rename guide components
                    [cmds.rename(i, i.replace(gdeNme, newNme)) for i in renameLst]

                else:
                    raise NameError('Guide with this name already exists')
            else:
                raise NameError('Current selection is not a guide Hbfr')
        else:
            raise NameError('Current selection is not a guide Hbfr')

    def guide_from_joint():
        '''
        Select a joint created by the volume system
        This function will unhide all elements of the guide that
        created it and select the root to allow for rebuild
        '''
        joint = cmds.ls(sl = True)[0]
        replace_Def = joint.replace("Def_","Hbfr_")
        replace_StrMain = replace_Def.replace("_StrMain","_StrGuideRoot")
        cmds.select(replace_StrMain,hi=True)
        cmds.showHidden()
        cmds.select(replace_StrMain)


    # legacy end



# VolumeSystemUI_guideDialog: - use callbacks for button enabling
class VolumeSystemUI_guideDialog(QWidget):
    '''
    '''
    def __init__(self, mainWidget, dialogMode='create', parent=None):
        # call QWidget's __init__ method
        super(VolumeSystemUI_guideDialog, self).__init__(parent)

        # setting the minimum size
        width = 300
        height = 120
        self.setFixedSize(width, height)

        # set the window title
        self.setWindowTitle('%s Guide' % (dialogMode.capitalize()))

        # store the mainWidget so that it can be updated later
        self.mainWidget = mainWidget

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10,10,10,10)

        self.topHLayout = QHBoxLayout(self)
        self.layout.addLayout(self.topHLayout)

        self.globalScaleLabel = QLabel('Global Scale')
        self.topHLayout.addWidget(self.globalScaleLabel)

        self.globalScaleSpinBox = QDoubleSpinBox(self)
        self.globalScaleSpinBox.setValue(1.0)
        self.topHLayout.addWidget(self.globalScaleSpinBox)

        self.systemsCurveVis = QCheckBox('Systems Curve Vis')
        self.topHLayout.addWidget(self.systemsCurveVis)

        self.topHLayout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.midHLayout = QHBoxLayout(self)
        self.layout.addLayout(self.midHLayout)

        self.sideComboBox = QComboBox(self)
        self.sideComboBox.addItem('')
        self.sideComboBox.addItem('L')
        self.sideComboBox.addItem('R')
        self.sideComboBox.addItem('M')
        self.midHLayout.addWidget(self.sideComboBox)

        self.nameQLineEdit = QLineEdit('')
        self.midHLayout.addWidget(self.nameQLineEdit)

        self.selectSystemTypeComboBox = QComboBox(self)
        self.selectSystemTypeComboBox.addItem('System Type')
        self.selectSystemTypeComboBox.addItem('slider')
        self.selectSystemTypeComboBox.addItem('stretch')
        self.midHLayout.addWidget(self.selectSystemTypeComboBox)

        self.bottomHLayout = QHBoxLayout(self)
        self.layout.addLayout(self.bottomHLayout)

        self.createGuidePushButton = QPushButton('Create Guide')
        self.createGuidePushButton.setStyleSheet(styles.color_button_enabled)
        self.bottomHLayout.addWidget(self.createGuidePushButton)
        self.createGuidePushButton.clicked.connect(self.cmImportGuide)

    # legacy start
    def cmImportGuide(self):
        '''
        '''
        sysSide = self.sideComboBox.currentText()
        sysDef  = self.nameQLineEdit.text()
        sysType = self.selectSystemTypeComboBox.currentIndex()
        globScl = self.globalScaleSpinBox.value()

        if not sysSide:
            raise AttributeError('Select guide SIDE')
        if not sysDef:
           raise AttributeError('Give the guide a DESCRIPTION')
        if not sysType:
            raise AttributeError('Select guide TYPE')

        # Format description
        sysDef = sysDef[0].capitalize() + sysDef[1:]
        sysDef = re.sub('[^A-Za-z0-9]+', '', sysDef) # Remove special characters
        guideName = sysSide+'_'+sysDef

        # If selection: import guide to match selection xform to help place guides rapidly
        qckMatrix = None
        if cmds.ls(sl=True):
            objTyp = cmds.objectType(cmds.ls(sl=True)[0])
            if (objTyp == 'transform') or (objTyp == 'joint'):
                qckMatrix = self.getTransform(cmds.ls(sl=True)[0])

        # Check if guide already exists
        prefixDict = { 1:'_Sld', 2:'_Str' }
        gdePrefix  = prefixDict[sysType]
        if cmds.objExists('Orig_'+guideName+gdePrefix+'GuideRoot'):
            raise AttributeError('SLIDER GUIDE WITH THIS NAME ALREADY EXISTS')

        # Import guide
        if sysType == 1:
            self.mainWidget.createSliderGuide(guideName, globScl)
        if sysType == 2:
            self.mainWidget.createStretchGuide(guideName, globScl)

        if not cmds.objExists('volumeGuides'):
            cmds.createNode('transform', n='volumeGuides')

        cmds.parent('Orig_'+guideName+gdePrefix+'GuideRoot', 'volumeGuides')

        # Move guide to selected obj if something is selected
        if qckMatrix != None:
            target = 'Hbfr_'+guideName+gdePrefix+'GuideRoot'
            self.setTransformFromMatrix(qckMatrix, target)

        cmds.select('Hbfr_'+guideName+gdePrefix+'GuideRoot')

        self.close()
        self.mainWidget.refreshUI()

    def getTransform(self, node):
        """Return the transformation matrix of the dagNode in worldSpace.

        Arguments:
            node (dagNode): The dagNode to get the translation

        Returns:
            matrix: The transformation matrix
        """
        return cmds.xform(node, q=True, ws=True, m=True)

    def setTransformFromMatrix(self, matrix, target):
        """sets dagNode transformations in world space.

        Arguments:
            matrix (MMatrix): The source matrix
            target (dagNode): The target dagNode

        Returns:
            None

        """
        cmds.xform(target, ws=True, m=matrix)
    # legacy end
