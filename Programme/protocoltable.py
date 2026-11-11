"""Read-only, compact training journal with separated run blocks."""
from datetime import datetime
from copy import deepcopy
from PySide6.QtCore import Qt,QSize,QRect
from PySide6.QtGui import QColor,QBrush
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QTreeWidget,QTreeWidgetItem,QDialogButtonBox,
                              QAbstractItemView,QHeaderView,QMenu,QMessageBox,QStyledItemDelegate)
from protocolparameters import import_parameters


class WrappedRows(QStyledItemDelegate):
    def sizeHint(self, option, index):
        tree=self.parent()
        text=str(index.data() or '')
        depth=0;ancestor=index.parent()
        while ancestor.isValid():depth+=1;ancestor=ancestor.parent()
        available=tree.viewport().width() if index.data(Qt.ItemDataRole.UserRole+1) else tree.columnWidth(index.column())
        width=max(80,available-(depth+1)*tree.indentation()-12)
        rect=option.fontMetrics.boundingRect(QRect(0,0,width,10000),Qt.TextFlag.TextWordWrap,text)
        return QSize(width,max(option.fontMetrics.height()+8,rect.height()+8))


class ProtocolTableDialog(QDialog):
    def __init__(self,journal,language,parent=None,training_dialog=None,history=None):
        super().__init__(parent)
        self.journal,self.language,self.training_dialog=journal,language,training_dialog
        self.history=deepcopy(list(history if history is not None else getattr(parent,"training_history",[])))
        self.t=language.text
        self.setWindowTitle(self.t('protocol.title'))
        self.setSizeGripEnabled(True)
        layout=QVBoxLayout(self)
        self.tree=QTreeWidget(self)
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels([self.t('protocol.table.entry'),self.t('protocol.table.value')])
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setWordWrap(True)
        self.tree.setUniformRowHeights(False)
        self.tree.setItemDelegate(WrappedRows(self.tree))
        self.tree.header().setSectionResizeMode(0,QHeaderView.ResizeMode.Interactive)
        self.tree.header().setStretchLastSection(True)
        self.tree.setColumnWidth(0,215)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.context_menu)
        layout.addWidget(self.tree,1)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self.t('common.close'))
        self.rebuild_button=buttons.addButton(self.t('protocol.rebuild.action'),QDialogButtonBox.ButtonRole.ActionRole)
        self.rebuild_button.clicked.connect(self.rebuild_missing)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.populate()
        # Detail values wrap instead of forcing a window as wide as the journal.
        self.resize(min(590,self.screen().availableGeometry().width()-40),
                    min(700,self.screen().availableGeometry().height()-80))

    @staticmethod
    def stamp(value):
        try:return datetime.fromisoformat(value).strftime('%d.%m.%Y %H:%M:%S')
        except (TypeError,ValueError):return str(value or '')

    def row(self,parent,label,value=''):
        item=QTreeWidgetItem(parent,[str(label).strip(),str(value).strip()])
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def parameter_rows(self,parameters):
        t=self.t
        rows=[]
        for key in ('solver','weight_initialization','bias_initialization','initialize_network',
                    'learning_rate','momentum','error_limit','maximum_epochs','training_target_mode'):
            if key not in parameters or (key=='momentum' and parameters.get('solver')=='adam'):continue
            value=parameters[key]
            if key=='solver':value=t('adam.solver.'+str(value))
            elif key.endswith('_initialization'):
                value={'auto':t('training.initialization.auto_short'),'xavier':'Xavier/Glorot','he':'He','zero':'0'}.get(value,str(value))
            elif key=='initialize_network':value=t('common.yes' if value else 'common.no')
            elif key=='training_target_mode':value=t('training.view.target_'+str(value),epochs=parameters.get('training_section_epochs'))
            else:value=self.journal.format_value(value)
            rows.append((t('protocol.param.'+key),value))
        return rows

    def populate(self):
        self.tree.clear()
        blocks=self.journal.blocks
        if not blocks:
            self.row(self.tree,self.t('protocol.table.empty'))
        for index,block in enumerate(blocks):
            if index:
                spacer=self.row(self.tree,'')
                spacer.setFlags(Qt.ItemFlag.NoItemFlags)
            header=self.row(self.tree,block['title'],self.stamp(block['created']))
            header.setData(0,Qt.ItemDataRole.UserRole,block['id'])
            if block.get('reconstructed'):header.setText(0,header.text(0)+' · '+self.t('protocol.rebuild.tag'))
            if block.get('deleted'):header.setText(0,header.text(0)+' · '+self.t('protocol.table.deleted'))
            for column in (0,1):
                header.setBackground(column,QBrush(QColor('#dce9f6')))
                header.setForeground(column,QBrush(QColor('#143554')))
                font=header.font(column);font.setBold(True);header.setFont(column,font)
            if block.get('reconstructed'):
                self.row(header,self.t('protocol.rebuild.note'))
            if block.get('rows'):
                section=self.row(header,self.t('protocol.table.network'))
                for label,value in block['rows']:
                    item=self.row(section,label,value)
                    if not str(value).strip() and str(label).startswith(self.t('protocol.parent_run_suffix',run='').strip()):
                        item.setFirstColumnSpanned(True)
                        item.setData(0,Qt.ItemDataRole.UserRole+1,True)
                section.setExpanded(True)
            if block.get('parameters'):
                section=self.row(header,self.t('protocol.parameters'))
                for label,value in self.parameter_rows(block['parameters']):self.row(section,label,value)
                section.setExpanded(True)
            if block.get('result'):
                r=block['result'];section=self.row(header,self.t('protocol.result'),r.get('status',''))
                labels={'epochs':'protocol.result_epochs','elapsed_seconds':'training.result.elapsed',
                        'mse':'MSE','maximum_error':'protocol.result_maximum'}
                for key,label in labels.items():
                    if key in r:self.row(section,self.t(label) if label!='MSE' else label,
                        self.journal.format_value(r[key])+(' s' if key=='elapsed_seconds' else ''))
                if r.get('epochs',0)>0 and 'elapsed_seconds' in r:self.row(section,self.t('protocol.result_epoch_time'),
                    self.journal.format_value(r['elapsed_seconds']*1000/r['epochs'])+' ms')
                section.setExpanded(True)
            if block.get('events'):
                section=self.row(header,self.t('protocol.table.events'),len(block['events']))
                for event in block['events']:
                    e=self.row(section,self.stamp(event['time']),event['title'])
                    for label,value in event.get('rows',[]):self.row(e,label,value)
                section.setExpanded(True)
            header.setExpanded(index==len(blocks)-1)
        self.rebuild_button.setEnabled(bool(self.missing_runs()))

    def missing_runs(self):
        existing={b.get('run_id') for b in self.journal.blocks}
        return [r for r in self.history if type(r.get('run_id')) is int and r['run_id']>0 and r['run_id'] not in existing]

    def rebuild_missing(self):
        runs=self.missing_runs()
        if not runs:return
        question=QMessageBox(self)
        question.setWindowTitle(self.t('protocol.rebuild.action'))
        question.setText(self.t('protocol.rebuild.confirm',count=len(runs)))
        question.setStandardButtons(QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel)
        question.button(QMessageBox.StandardButton.Yes).setText(self.t('protocol.rebuild.apply'))
        question.button(QMessageBox.StandardButton.Cancel).setText(self.t('common.cancel'))
        question.setDefaultButton(QMessageBox.StandardButton.Cancel)
        result=question.exec();question.deleteLater()
        if result!=QMessageBox.StandardButton.Yes:return
        try:
            self.journal.reconstruct_runs(runs)
            self.populate()
        except (OSError,ValueError,TypeError) as error:
            QMessageBox.warning(self,self.t('protocol.title'),str(error))

    def block_for_header(self,item):
        if item is None or item.parent() is not None:return None
        block_id=item.data(0,Qt.ItemDataRole.UserRole)
        return next((b for b in self.journal.blocks if b['id']==block_id),None)

    def context_menu(self,position):
        block=self.block_for_header(self.tree.itemAt(position))
        if block is None:return
        menu=QMenu(self)
        apply=None
        if self.training_dialog is not None:
            apply=menu.addAction(self.t('protocol.import.action'))
            apply.setEnabled(bool(block.get('parameters')) and not self.training_dialog.is_training)
            menu.addSeparator()
        remove=menu.addAction(self.t('protocol.table.delete'))
        action=menu.exec(self.tree.viewport().mapToGlobal(position))
        if apply is not None and action==apply:
            import_parameters(self.training_dialog,'',self,values=block['parameters'],partial=bool(block.get('reconstructed')))
        elif action==remove:self.delete_block(block)
        menu.deleteLater()

    def delete_block(self,block):
        question=QMessageBox(self)
        question.setWindowTitle(self.t('protocol.table.delete'))
        question.setText(self.t('protocol.table.delete_confirm',title=block['title']))
        question.setStandardButtons(QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel)
        question.button(QMessageBox.StandardButton.Yes).setText(self.t('common.delete'))
        question.button(QMessageBox.StandardButton.Cancel).setText(self.t('common.cancel'))
        question.setDefaultButton(QMessageBox.StandardButton.Cancel)
        result=question.exec();question.deleteLater()
        if result!=QMessageBox.StandardButton.Yes:return
        try:
            self.journal.delete_block(block['id'])
            self.populate()
        except (OSError,ValueError) as error:
            QMessageBox.warning(self,self.t('protocol.title'),str(error))
