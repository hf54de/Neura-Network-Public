from _test_applicationcurve import APP, build, lang, drain
from _test_training_comparison import make_dialog
from graphicalexperimentdialog import GraphicalExperimentDialog
from applicationcurve import CurveSettings
from unittest.mock import patch
from PySide6.QtCore import QEvent
from pathlib import Path
out=Path(".change_baseline_curve_insertion_20261020")
for code in ("de","en"):
    parent,t=make_dialog(code)
    t.show()
    assert t.error_metric_combo.findData("characteristic")>=0
    t.show_error_chart.setChecked(True)
    t.error_metric_combo.setCurrentIndex(t.error_metric_combo.findData("characteristic"))
    APP.processEvents()
    assert t.training_characteristic_plot.curve_points
    t.output_columns[0]["data_type"]="binary"
    t.populate_training_characteristic_controls()
    assert t.error_metric_combo.findData("characteristic")==-1
    assert t.error_metric_combo.currentData()!="characteristic"
    assert not t.training_characteristic_notice.isVisible()
    assert not t.training_characteristic_plot.isVisible()
    assert not t.training_characteristic_controls.isVisible()
    t.grab().save(str(out/("training_"+code+".png")))
    t.output_columns[0]["data_type"]="analog"
    t.populate_training_characteristic_controls()
    assert t.error_metric_combo.findData("characteristic")>=0
    # Only analog outputs are offered, regardless of output ordering.
    t.output_columns.insert(0,dict(t.output_columns[0],data_type="binary"))
    t.populate_training_characteristic_controls()
    assert t.training_characteristic_output.count()==1
    t.output_columns.pop(0)
    t.input_columns.append(dict(t.input_columns[0]))
    t.populate_training_characteristic_controls()
    assert t.error_metric_combo.findData("characteristic")==-1
    t.input_columns.pop()
    t.input_columns[0]["data_type"]="binary"
    t.populate_training_characteristic_controls()
    assert t.error_metric_combo.findData("characteristic")==-1
    t.close();t.deleteLater();parent.deleteLater()
    APP.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    net,m=build()
    with patch.object(GraphicalExperimentDialog,"restore_window_geometry"):
        d=GraphicalExperimentDialog(net,m[:2],m[2:],[[-2,-2,-9],[2,2,11]],None,language_manager=lang(code))
    drain(lambda:not d.forward_calculation_running and not d.calculation_timer.isActive())
    d.mode_combo.setCurrentIndex(d.mode_combo.findData("edit"))
    with patch("applicationcurve.QMessageBox.information") as message, patch.object(d,"begin_history_action") as history:
        d.curves.add()
        assert message.call_count==1
        assert not d.curves.proxies and not history.called
        assert "genau einem Eingang" in message.call_args.args[2] if code=="de" else "exactly one input" in message.call_args.args[2]
    # Stored cards are retained and serialized with original visibility.
    stored=dict(settings=dict(input_id=1,output_id=3),visible=True,x=13,y=29)
    proxy=d.curves.create(stored)
    assert not proxy.isVisible()
    saved=d.curves.data(proxy)
    assert saved["visible"] is True and saved["x"]==13
    hidden=d.curves.create(dict(stored,visible=False))
    assert not hidden.isVisible() and not d.curves.data(hidden)["visible"]
    net.remove_neuron(m[1]["neuron"])
    d.input_columns=d.input_columns[:1]
    d.forward_specification=d.create_forward_specification()
    d.curves.refresh({1:0.})
    drain(lambda:not d.curves.busy and not d.curves.pending and not d.curves.timer.isActive())
    assert proxy.isVisible() and len(proxy.widget().plot.points)==161
    assert not hidden.isVisible()
    for mapping in (d.input_columns[0],d.output_columns[0]):
        mapping["data_type"]="binary"
        d.curves.refresh({1:0.})
        assert not proxy.isVisible() and d.curves.data(proxy)["visible"]
        with patch("applicationcurve.QMessageBox.information") as message:
            count=len(d.curves.proxies)
            d.curves.add()
            assert message.called and len(d.curves.proxies)==count
        mapping["data_type"]="analog"
        d.curves.refresh({1:0.})
        drain(lambda:not d.curves.busy and not d.curves.pending and not d.curves.timer.isActive())
        assert proxy.isVisible() and len(proxy.widget().plot.points)==161
    # Default and settings both select an analog output in a mixed-output network.
    d.output_columns.insert(0,dict(d.output_columns[0],data_type="binary",neuron=d.input_columns[0]["neuron"]))
    new=d.curves.create()
    assert new.widget().plot.settings["output_id"]==3
    settings=CurveSettings(d,new.widget().plot.settings)
    assert settings.outputs.count()==1 and settings.outputs.currentData()==3
    settings.deleteLater()
    d.stop_forward_executor();drain(lambda:not d.curves.busy)
    d.deleteLater();APP.sendPostedEvents(None,QEvent.Type.DeferredDelete);APP.processEvents()
APP.clipboard().clear()
print("PASS: DE/EN insertion rejection, hidden saved cards preserved/recovered, training availability, analog output filtering")
