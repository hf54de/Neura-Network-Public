"""Read editable DE/EN run blocks and import settings only after confirmation."""
import math
import re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

LABELS = {
    'gewichte':'weight_initialization','weights':'weight_initialization',
    'bias':'bias_initialization','neu initialisieren':'initialize_network','reinitialize':'initialize_network',
    'lernrate':'learning_rate','learning rate':'learning_rate','momentum':'momentum',
    'fehlergrenze':'error_limit','error limit':'error_limit','maximale epochen':'maximum_epochs',
    'maximum epochs':'maximum_epochs','optimierungsverfahren':'solver','optimizer':'solver',
    'ziel':'training_target_mode','target':'training_target_mode',
}


def block_at(text, line):
    lines=text.splitlines()
    if not 0 <= line < len(lines):return ''
    separator=lambda s:bool(re.fullmatch(r'\s*[-=]{5,}\s*',s))
    if separator(lines[line]):return ''
    start=line
    while start>0 and not separator(lines[start-1]):start-=1
    end=line+1
    while end<len(lines) and not separator(lines[end]):end+=1
    return '\n'.join(lines[start:end])


def parse_parameters(block):
    if not re.search(r'NEUER TRAININGSLAUF|NEW TRAINING RUN',block,re.I):
        raise ValueError('Trainingslauf / Training run')
    result={}
    for line in block.splitlines():
        if ':' not in line:continue
        label,value=line.split(':',1)
        key=LABELS.get(label.strip().casefold())
        if not key:continue
        if key in result:raise ValueError(label)
        value=value.strip();fold=value.casefold()
        if key in ('weight_initialization','bias_initialization'):
            choices={'automatisch nach aktivierung':'auto','automatic by activation':'auto',
                     'xavier/glorot':'xavier','he':'he','0':'zero'}
            value=choices.get(fold)
            if value is None or (key=='bias_initialization' and value not in ('xavier','zero')):
                raise ValueError(label)
        elif key=='initialize_network':
            if fold not in ('ja','nein','yes','no'):raise ValueError(label)
            value=fold in ('ja','yes')
        elif key=='solver':
            value={'adam':'adam','sgd mit momentum':'sgd','sgd with momentum':'sgd'}.get(fold)
            if value is None:raise ValueError(label)
        elif key=='training_target_mode':
            if fold in ('fehlergrenze','error limit'):value='limit'
            elif fold in ('1 epoche','1 epoch'):value='one'
            else:
                match=re.fullmatch(r'(\d+)\s+(?:Epochen|epochs)',value,re.I)
                if not match:raise ValueError(label)
                result['training_section_epochs']=int(match[1]);value='epochs'
        else:
            try:value=float(value.replace(',','.'))
            except ValueError:raise ValueError(label) from None
            if not math.isfinite(value):raise ValueError(label)
            if key=='maximum_epochs':
                if not value.is_integer():raise ValueError(label)
                value=int(value)
        result[key]=value
    if 'solver' not in result and 'momentum' in result:result['solver']='sgd'
    required={'weight_initialization','bias_initialization','initialize_network','solver',
              'learning_rate','error_limit','maximum_epochs','training_target_mode'}
    if result.get('solver')=='sgd':required.add('momentum')
    missing=required-result.keys()
    if missing:raise ValueError(', '.join(sorted(missing)))
    return result


def import_parameters(training, block, parent, *, values=None, partial=False):
    t=training.language.text
    if training.is_training:return False
    try:
        values=parse_parameters(block) if values is None else dict(values)
        required={'solver','weight_initialization','bias_initialization','initialize_network',
                  'learning_rate','error_limit','maximum_epochs','training_target_mode'}
        if values.get('solver')=='sgd':required.add('momentum')
        preserved=[]
        if partial:
            defaults=training.get_training_settings()
            for key in required | {'training_section_epochs'}:
                if key not in values and key in defaults:
                    values[key]=defaults[key];preserved.append(t('protocol.param.'+key))
        if required-values.keys():raise ValueError(', '.join(sorted(required-values.keys())))
        if (values['solver'] not in ('sgd','adam') or values['weight_initialization'] not in ('auto','zero','he','xavier')
                or values['bias_initialization'] not in ('zero','xavier')
                or type(values['initialize_network']) is not bool
                or values['training_target_mode'] not in ('one','epochs','limit')
                or (values['training_target_mode']=='epochs' and 'training_section_epochs' not in values)):
            raise ValueError(t('protocol.parameters'))
        for key in ('learning_rate','momentum','error_limit','maximum_epochs','training_section_epochs'):
            if key not in values:continue
            widget=training.epoch_count if key=='training_section_epochs' else getattr(training,key)
            value=values[key]
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError(t("protocol.param."+key))
            if key in ('maximum_epochs','training_section_epochs') and int(value)!=value:raise ValueError(t('protocol.param.'+key))
            if key in ('maximum_epochs','training_section_epochs'):values[key]=int(value)
            if not widget.minimum() <= value <= widget.maximum():raise ValueError(t('protocol.param.'+key))
            if hasattr(widget,'decimals') and not math.isclose(round(value,widget.decimals()),value,rel_tol=0,abs_tol=1e-12):
                raise ValueError(t('protocol.param.'+key))
    except ValueError as error:
        QMessageBox.warning(parent,t('protocol.import.action'),t('protocol.import.invalid',detail=str(error)))
        return False
    labels={
        'weight_initialization':t('training.initialization.weights').rstrip(':'),
        'bias_initialization':t('training.initialization.bias').rstrip(':'),
        'initialize_network':t('protocol.run_reinitialize'),
        'solver':t('protocol.param.solver'),
    }
    def display(key,value):
        if key=='solver':return t('adam.solver.'+value)
        if key.endswith('_initialization'):
            return {'auto':t('training.initialization.auto_short'),'zero':'0','he':'He','xavier':'Xavier/Glorot'}[value]
        if key=='initialize_network':return t('common.yes' if value else 'common.no')
        if key=='training_target_mode':return t('training.view.target_'+value,epochs=values.get('training_section_epochs'))
        text=str(value)
        return text.replace('.',',') if training.language.current_language=='de' else text
    lines=[]
    for key in ('solver','weight_initialization','bias_initialization','initialize_network',
                'learning_rate','momentum','error_limit','maximum_epochs','training_target_mode'):
        if key not in values or (key=='momentum' and values['solver']=='adam'):continue
        if key=='training_target_mode':lines.append(display(key,values[key]))
        else:lines.append(labels.get(key,t('protocol.param.'+key))+': '+display(key,values[key]))
    question=QMessageBox(parent)
    question.setWindowTitle(t('protocol.import.action'))
    question.setText(t('protocol.import.confirm')+'\n\n'+
        (t('protocol.rebuild.kept',fields=', '.join(sorted(preserved)))+'\n\n' if preserved else '')+'\n'.join(lines))
    question.setStandardButtons(QMessageBox.StandardButton.Ok|QMessageBox.StandardButton.Cancel)
    question.button(QMessageBox.StandardButton.Ok).setText(t('protocol.import.apply'))
    question.button(QMessageBox.StandardButton.Cancel).setText(t('common.cancel'))
    question.setDefaultButton(QMessageBox.StandardButton.Cancel)
    result=question.exec();question.deleteLater()
    if result!=QMessageBox.StandardButton.Ok or training.is_training:return False
    training.restore_solver_selection(values['solver'])
    training.learning_rate.setValue(values['learning_rate'])
    training._solver_rates[values['solver']]=values['learning_rate']
    for key in ('momentum','error_limit','maximum_epochs'):
        if key in values:getattr(training,key).setValue(values[key])
    training.initialize_network.setChecked(values['initialize_network'])
    for key,widget in (('weight_initialization',training.weight_initialization_combo),
                       ('bias_initialization',training.bias_initialization_combo)):
        widget.setCurrentIndex(widget.findData(values[key]))
    if 'training_section_epochs' in values:training.epoch_count.setValue(values['training_section_epochs'])
    training.select_training_target(values['training_target_mode'])
    return True


def install_parameter_menu(editor, training, parent):
    editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    def show_menu(position):
        block=block_at(editor.toPlainText(),editor.cursorForPosition(position).blockNumber())
        menu=editor.createStandardContextMenu()
        menu.addSeparator()
        action=menu.addAction(training.language.text('protocol.import.action'))
        action.setEnabled(not training.is_training)
        if menu.exec(editor.viewport().mapToGlobal(position))==action:
            import_parameters(training,block,parent)
        menu.deleteLater()
    editor.customContextMenuRequested.connect(show_menu)
