import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from PySide6.QtWidgets import QMessageBox,QAbstractItemView
from PySide6.QtGui import QFontDatabase,QFont
from _test_adam import APP,IntegrationTests as Fixture
from trainingprotocol import TrainingProtocol
from protocoltable import ProtocolTableDialog
from protocolparameters import import_parameters

class TableProtocolTests(unittest.TestCase):
    setUp=Fixture.setUp
    tearDown=Fixture.tearDown
    make_dialog=Fixture.make_dialog

    def run_block(self,run):
        return next(b for b in self.w.training_protocol.blocks if b['run_id']==run)

    def test_run_resume_result_load_and_deleted_history(self):
        d=self.make_dialog();d.execute_training(2,False,shuffle_seed=42)
        run=d.current_run_id;block=self.run_block(run)
        self.assertIsNotNone(block['parameters']);self.assertEqual(block['result']['epochs'],2)
        d.execute_training(2,False,continue_existing=True)
        self.assertEqual(d.current_run_id,run)
        block=self.run_block(run)
        self.assertEqual(block['result']['epochs'],4)
        self.assertEqual([e['kind'] for e in block['events']],[])
        self.w.protocol_run_loaded(run)
        self.assertEqual(block['events'][-1]['kind'],'loaded')
        self.w.protocol_deleted_runs(self.w.training_history,[])
        self.assertTrue(block['deleted'])
        journal=TrainingProtocol(self.w.language,self.w.training_protocol.path)
        self.assertEqual(journal.blocks,self.w.training_protocol.blocks)
        self.assertTrue(journal.path.name.endswith('.json'))

    def test_readonly_header_only_delete_cancel_and_confirm(self):
        d=self.make_dialog();d.execute_training(1,False,shuffle_seed=42)
        journal=self.w.training_protocol;block=self.run_block(d.current_run_id)
        history=deepcopy(self.w.training_history)
        view=ProtocolTableDialog(journal,self.w.language,self.w,d)
        try:
            self.assertEqual(view.tree.editTriggers(),QAbstractItemView.EditTrigger.NoEditTriggers)
            header=next(view.tree.topLevelItem(i) for i in range(view.tree.topLevelItemCount())
                        if view.tree.topLevelItem(i).data(0,256)==block['id'])
            self.assertIs(view.block_for_header(header),block)
            self.assertIsNone(view.block_for_header(header.child(0)))
            before=deepcopy(journal.blocks)
            with patch.object(QMessageBox,'exec',return_value=QMessageBox.StandardButton.Cancel):view.delete_block(block)
            self.assertEqual(journal.blocks,before)
            with patch.object(QMessageBox,'exec',return_value=QMessageBox.StandardButton.Yes):view.delete_block(block)
            self.assertFalse(any(b['id']==block['id'] for b in journal.blocks))
            self.assertEqual(self.w.training_history,history)
            reloaded=TrainingProtocol(self.w.language,journal.path)
            self.assertEqual(reloaded.document,None)
            self.assertEqual(reloaded.blocks,journal.blocks)
            self.assertGreaterEqual(reloaded.document['last_run_id'],d.current_run_id)
        finally:view.deleteLater()

    def test_native_parameter_import_and_scope(self):
        d=self.make_dialog();d.execute_training(1,False,shuffle_seed=42)
        params=deepcopy(self.run_block(d.current_run_id)['parameters'])
        params['learning_rate']=.002
        state=deepcopy(self.w.capture_training_network_state())
        with patch.object(QMessageBox,'exec',return_value=QMessageBox.StandardButton.Ok):
            self.assertTrue(import_parameters(d,'',d,values=params))
        self.assertEqual(d.learning_rate.value(),.002)
        self.assertEqual(self.w.capture_training_network_state(),state)
        views=[]
        def inspect(view):views.append(view.training_dialog);return 0
        with patch.object(ProtocolTableDialog,'exec',inspect):
            self.w.open_training_protocol();d.open_training_protocol()
        self.assertEqual(views,[None,d])

    def test_context_menu_header_scope_and_running_lock(self):
        from PySide6.QtWidgets import QMenu
        d=self.make_dialog();d.execute_training(1,False,shuffle_seed=42)
        journal=self.w.training_protocol
        for training in (None,d):
            view=ProtocolTableDialog(journal,self.w.language,self.w,training)
            try:
                view.show();APP.processEvents()
                header=next(view.tree.topLevelItem(i) for i in range(view.tree.topLevelItemCount())
                            if view.tree.topLevelItem(i).data(0,256)==self.run_block(d.current_run_id)['id'])
                view.tree.scrollToItem(header);APP.processEvents()
                def inspect(menu,pos):
                    names=[a.text() for a in menu.actions() if not a.isSeparator()]
                    self.assertEqual(len(names),2 if training else 1)
                    if training:self.assertEqual(menu.actions()[0].isEnabled(),not d.is_training)
                    return None
                class Menu(QMenu):
                    def exec(menu,pos):return inspect(menu,pos)
                for running in (False,True):
                    d.is_training=running
                    with patch('protocoltable.QMenu',Menu):
                        view.context_menu(view.tree.visualItemRect(header).center())
                with patch('protocoltable.QMenu') as menu:
                    view.context_menu(view.tree.visualItemRect(header.child(0)).center())
                    menu.assert_not_called()
            finally:
                d.is_training=False;view.hide();view.deleteLater()

    def test_old_txt_discarded_only_on_open_and_save_as(self):
        old=self.root/'trainingsprotokoll.txt';old.write_text('OLD RUN 999',encoding='utf-8')
        self.w.initialize_training_protocol()
        self.assertTrue(old.exists())
        self.assertEqual(self.w.training_protocol.blocks,[])
        with patch.object(ProtocolTableDialog,'exec',return_value=0):self.w.open_training_protocol()
        self.assertFalse(old.exists())
        self.assertTrue((self.root/'trainingsprotokoll.json').exists())
        self.assertEqual(self.w.training_protocol.blocks,[])
        self.w.training_protocol.run_event(7,'loaded','Run loaded')
        folder=self.root/'Copy';folder.mkdir()
        self.w.training_protocol.flush(folder/'trainingsprotokoll.json')
        self.assertEqual(TrainingProtocol(self.w.language,folder/'trainingsprotokoll.json').blocks,
                         self.w.training_protocol.blocks)

    def test_rename_saves_pending_protocol_entries_in_new_folder(self):
        from PySide6.QtWidgets import QInputDialog

        old_dir = self.root / "Alter Name"
        new_dir = self.root / "Neuer-Name"
        old_dir.mkdir()
        self.assertEqual(old_dir.resolve().parent, self.root.resolve())
        self.assertEqual(new_dir.resolve().parent, self.root.resolve())
        project = old_dir / "Alter Name.nnproj"
        old_data = old_dir / "trainingsdaten.nndata"
        old_data.write_bytes(self.data_path.read_bytes())
        self.w.current_project_path = str(project)
        self.w.initialize_training_protocol()
        manager = self.w.training_data_manager
        manager.set_document(manager.document, file_path=str(old_data))
        self.assertTrue(self.w.write_project_file(str(project)))

        journal = self.w.training_protocol
        journal.add("Gespeichert", ["Eintrag vor dem Umbenennen"])
        journal.add("Vorgemerkt", ["Eintrag im Arbeitsspeicher"], flush=False)
        expected = deepcopy(journal.blocks)
        self.assertTrue(journal.dirty)
        self.assertTrue(journal.path.exists())
        with (
            patch.object(QInputDialog, "getText", return_value=("Neuer-Name", True)),
            patch.object(QMessageBox, "warning") as warning,
            patch.object(QMessageBox, "critical") as critical,
        ):
            self.assertTrue(self.w.rename_current_project())
            warning.assert_not_called()
            critical.assert_not_called()

        self.assertFalse(old_dir.exists())
        self.assertTrue((new_dir / "Neuer-Name.nnproj").is_file())
        self.assertEqual(manager.file_path, str(new_dir / old_data.name))
        self.assertIs(self.w.training_protocol, journal)
        self.assertFalse(journal.dirty)
        self.assertEqual(journal.path, new_dir / "trainingsprotokoll.json")
        saved_blocks = TrainingProtocol(self.w.language, journal.path).blocks
        self.assertEqual(saved_blocks[:len(expected)], expected)
        self.assertEqual(saved_blocks, journal.blocks)

    def test_failed_write_keeps_events_and_failed_delete_keeps_block(self):
        j=self.w.training_protocol
        with patch('trainingprotocol.write_text_atomic',side_effect=PermissionError('test')):
            with self.assertRaises(PermissionError):j.run_event(1,'started','Run 1',parameters={'solver':'adam'})
        self.assertTrue(j.dirty);self.assertEqual(len(j.blocks),1)
        j.flush();before=deepcopy(j.blocks)
        with patch('trainingprotocol.write_text_atomic',side_effect=PermissionError('test')):
            with self.assertRaises(PermissionError):j.delete_block(j.blocks[0]['id'])
        self.assertEqual(j.blocks,before)
        self.assertEqual(TrainingProtocol(self.w.language,j.path).blocks,before)

    def test_parameter_changes_do_not_create_isolated_blocks(self):
        d=self.make_dialog()
        d.learning_rate.setValue(.02)
        d.initialize_network.setChecked(True)
        self.w.training_settings=d.get_training_settings()
        self.w.protocol_checkpoint()
        self.assertEqual(self.w.training_protocol.blocks,[])
        d.execute_training(1,False,shuffle_seed=42)
        block=self.run_block(d.current_run_id)
        self.assertEqual(block['parameters']['learning_rate'],.02)
        self.assertTrue(block['parameters']['initialize_network'])
        self.assertEqual(len(self.w.training_protocol.blocks),1)

    def test_existing_unambiguous_parameter_note_moves_into_run(self):
        journal=self.w.training_protocol
        journal.add('Trainingsparameter ge\u00e4ndert',['Lernrate: 0,01 -> 0,02'])
        journal.run_event(7,'started','Lauf 7',parameters={'learning_rate':.02})
        note,run=journal.blocks
        run['created']=note['created']
        journal.dirty=True;journal.flush()
        loaded=TrainingProtocol(self.w.language,journal.path)
        self.assertEqual(len(loaded.blocks),1)
        self.assertEqual(loaded.blocks[0]['run_id'],7)
        self.assertEqual(loaded.blocks[0]['events'],[])
        loaded.flush()
        self.assertEqual(len(TrainingProtocol(self.w.language,journal.path).blocks[0]['events']),0)

    def test_target_changes_keep_curve_and_only_new_curves_create_blocks(self):
        d=self.make_dialog('sgd')
        d.select_training_target('epochs');d.epoch_count.setValue(1)
        d.execute_training(1,False,shuffle_seed=42)
        run=d.current_run_id
        d.maximum_epochs.setValue(2000)
        d.epoch_count.setValue(2)
        d.continue_selected_training()
        self.assertEqual(d.current_run_id,run)
        block=self.run_block(run)
        self.assertEqual(block['result']['epochs'],3)
        self.assertEqual([e['kind'] for e in block['events']],['target'])
        self.assertEqual(len([b for b in self.w.training_protocol.blocks if b['run_id'] is not None]),1)
        d.continue_selected_training()
        self.assertEqual([e['kind'] for e in block['events']],['target'])
        self.assertEqual(block['result']['epochs'],5)
        with patch.object(d,'prepare_continuation_parameters',return_value='changed'):
            d.learning_rate.setValue(.02)
            d.continue_selected_training()
        self.assertNotEqual(d.current_run_id,run)
        linked=self.run_block(d.current_run_id)
        self.assertEqual(linked['events'],[])
        self.assertEqual(linked['parameters']['learning_rate'],.02)
        parent=d.current_run_parent_id
        self.assertEqual(parent,run)
        previous=d.current_run_id
        d.repeat_with_same_initialization()
        self.assertNotEqual(d.current_run_id,previous)
        previous=d.current_run_id
        d.start_selected_training()
        self.assertNotEqual(d.current_run_id,previous)
        self.assertEqual(len([b for b in self.w.training_protocol.blocks if b['run_id'] is not None]),4)

    def test_manual_reconstruction_button_cancel_and_delete(self):
        d=self.make_dialog();d.execute_training(1,False,shuffle_seed=42)
        journal=self.w.training_protocol
        view=ProtocolTableDialog(journal,self.w.language,self.w,d)
        try:
            self.assertFalse(view.rebuild_button.isEnabled())
            block=self.run_block(d.current_run_id)
            journal.delete_block(block['id']);view.populate()
            self.assertTrue(view.rebuild_button.isEnabled())
            with patch.object(QMessageBox,'exec',return_value=QMessageBox.StandardButton.Cancel):view.rebuild_missing()
            self.assertEqual(journal.blocks,[])
            with patch.object(QMessageBox,'exec',return_value=QMessageBox.StandardButton.Yes):view.rebuild_missing()
            self.assertFalse(view.rebuild_button.isEnabled())
            rebuilt=journal.blocks[0]
            self.assertTrue(rebuilt['reconstructed'])
            self.assertEqual(rebuilt['created'],self.w.training_history[0]['timestamp'])
            self.assertEqual(rebuilt['result']['mse'],self.w.training_history[0]['end_error'])
            self.assertNotIn('maximum_epochs',rebuilt['parameters'])
            self.assertEqual(rebuilt['events'],[])
            d.maximum_epochs.setValue(9031)
            with patch.object(QMessageBox,'exec',return_value=QMessageBox.StandardButton.Ok):
                self.assertTrue(import_parameters(d,'',d,values=rebuilt['parameters'],partial=True))
            self.assertEqual(d.maximum_epochs.value(),9031)
            journal.delete_block(rebuilt['id'])
            loaded=TrainingProtocol(self.w.language,journal.path)
            reopened=ProtocolTableDialog(loaded,self.w.language,self.w,d)
            self.assertEqual(loaded.blocks,[])
            self.assertTrue(reopened.rebuild_button.isEnabled())
            reopened.deleteLater()
        finally:view.deleteLater()

    def test_reconstruction_preserves_existing_and_rolls_back_failed_write(self):
        d=self.make_dialog();d.execute_training(1,False,shuffle_seed=42)
        d.execute_training(1,False,shuffle_seed=43)
        journal=self.w.training_protocol
        journal.delete_block(self.run_block(d.current_run_id)['id'])
        before=deepcopy(journal.blocks);history=deepcopy(self.w.training_history)
        with patch('trainingprotocol.write_text_atomic',side_effect=PermissionError('test')):
            with self.assertRaises(PermissionError):journal.reconstruct_runs(history)
        self.assertEqual(journal.blocks,before)
        self.assertEqual(journal.reconstruct_runs(history),1)
        self.assertEqual(journal.blocks[0],before[0])
        self.assertEqual(journal.reconstruct_runs(history),0)
        self.assertEqual(self.w.training_history,history)
        empty=ProtocolTableDialog(journal,self.w.language,history=[])
        self.assertFalse(empty.rebuild_button.isEnabled());empty.deleteLater()

    def test_compact_render_and_corrupt_json_preserved(self):
        d=self.make_dialog();d.execute_training(1,False,shuffle_seed=42)
        self.w.protocol_run_loaded(d.current_run_id)
        d.execute_training(1,False,shuffle_seed=43)
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf');APP.setFont(QFont('Segoe UI',9))
        view=ProtocolTableDialog(self.w.training_protocol,self.w.language,self.w,d)
        try:
            view.show();APP.processEvents();self.assertLessEqual(view.width(),590)
            view.grab().save('diagnostics/protocol_table_checked.png')
        finally:view.hide();view.deleteLater()
        path=self.root/'invalid.json';path.write_text('{bad',encoding='utf-8')
        j=TrainingProtocol(self.w.language,path)
        with self.assertRaises(ValueError):j.flush()
        self.assertEqual(path.read_text(encoding='utf-8'),'{bad')

if __name__=='__main__':unittest.main()
