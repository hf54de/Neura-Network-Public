import unittest
from copy import deepcopy
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage,QPainter,QFont,QFontDatabase
from _test_adam import APP,IntegrationTests
from editorscene import EditorScene
from neurontype import NeuronType
from settingsdialog import SettingsDialog
from projectio import ProjectIO
from settings import Settings
from _test_review_fixes import language

class BundledTests(unittest.TestCase):
    def test_scene_modes_geometry_and_model(self):
        scene=EditorScene(language('de'))
        layers=[]
        for x,count,kind in [(0,1,NeuronType.INPUT),(380,3,NeuronType.HIDDEN),(760,2,NeuronType.HIDDEN),(1140,1,NeuronType.OUTPUT)]:
            layer=[]
            for j in range(count):
                n=scene.add_neuron(sum(map(len,layers))+len(layer)+1,x,j*220+(3-count)*110,'N'+str(sum(map(len,layers))+len(layer)+1),False)
                n.neuron_type=kind;layer.append(n)
            layers.append(layer)
        for left,right in zip(layers,layers[1:]):
            for source in left:
                for target in right:scene.add_connection(len(scene.network.get_connections())+1,source,target,.1,False)
        weights=[c.weight for c in scene.network.get_connections()]
        scene.set_connection_display_mode(True,True)
        self.assertTrue(all(not c.isVisible() and not c.weight_label_visible for c in scene.network.get_connections()))
        scene.bundled_connections.rebuild()
        self.assertEqual(scene.bundled_connections.group_count,3)
        before=scene.bundled_connections.path.boundingRect()
        layers[1][0].setPos(400,-100)
        self.assertTrue(scene.bundled_connections.dirty)
        scene.bundled_connections.rebuild()
        self.assertNotEqual(scene.bundled_connections.path.boundingRect(),before)
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf');APP.setFont(QFont('Segoe UI',9))
        image=QImage(1200,800,QImage.Format.Format_ARGB32);image.fill(0xffffffff)
        painter=QPainter(image);scene.render(painter,QRectF(0,0,1200,800),scene.itemsBoundingRect().adjusted(-45,-30,45,30));painter.end()
        image.save('diagnostics/bundled_connections_checked.png')
        scene.set_connection_display_mode(False)
        self.assertFalse(scene.connections_visible)
        scene.set_connection_display_mode(True)
        self.assertTrue(all(c.isVisible() for c in scene.network.get_connections()))
        self.assertEqual(weights,[c.weight for c in scene.network.get_connections()])
        scene.clear_project();scene.deleteLater()

    def test_large_network_draws_three_cached_bundles(self):
        scene=EditorScene(language('de'));scene.set_connection_display_mode(True,True)
        layers=[];nid=1;cid=1
        for level,size in enumerate((13,50,50,1)):
            layer=[]
            for index in range(size):
                n=scene.add_neuron(nid,level*380,index*180,'N'+str(nid),False)
                layer.append(n);nid+=1
            layers.append(layer)
        for left,right in zip(layers,layers[1:]):
            for source in left:
                for target in right:
                    scene.add_connection(cid,source,target,.01,False);cid+=1
        scene.bundled_connections.rebuild()
        self.assertEqual(len(scene.network.get_connections()),3200)
        self.assertEqual(scene.bundled_connections.group_count,3)
        self.assertLess(scene.bundled_connections.path.elementCount(),500)
        self.assertFalse(scene.bundled_connections.dirty)
        self.assertTrue(all(not c.isVisible() for c in scene.network.get_connections()))
        scene.clear_project();scene.deleteLater()

    def test_settings_legacy_and_roundtrip(self):
        for visible in (True,False):
            settings=ProjectIO.normalize_display_settings({'show_connections':visible})
            self.assertFalse(settings['bundle_connections'])
            self.assertEqual(settings['show_connections'],visible)
        settings=ProjectIO.default_display_settings()
        d=SettingsDialog(settings,settings,Settings.default_ui_settings(),Settings.default_ui_settings(),language('de'))
        try:
            for mode in ('all','hidden','bundled'):
                d.connection_mode.setCurrentIndex(d.connection_mode.findData(mode))
                result=d.project_settings()
                self.assertEqual(result['show_connections'],mode!='hidden')
                self.assertEqual(result['bundle_connections'],mode=='bundled')
                ProjectIO._validate_display_settings_data(result)
        finally:d.deleteLater()

class BundledPersistenceTests(unittest.TestCase):
    setUp=IntegrationTests.setUp
    tearDown=IntegrationTests.tearDown
    def test_project_preserves_mode_and_network(self):
        before=self.w.capture_training_network_state()
        settings=deepcopy(self.w.display_settings);settings['bundle_connections']=True
        self.w.apply_display_settings(settings)
        self.assertTrue(self.w.write_project_file(str(self.file)))
        self.assertTrue(self.w.open_project(str(self.file)))
        self.assertTrue(self.w.scene.bundle_connections)
        self.assertEqual(self.w.capture_training_network_state(),before)

if __name__=='__main__':unittest.main()
