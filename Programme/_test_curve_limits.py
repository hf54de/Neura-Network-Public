from _test_applicationcurve import APP, build, lang, drain
from _test_training_comparison import make_dialog
from graphicalexperimentdialog import GraphicalExperimentDialog
from unittest.mock import patch
from PySide6.QtCore import QEvent
from pathlib import Path
out=Path(".change_baseline_curve_limits_20261020")
for code in ("de","en"):
    parent,t=make_dialog(code)
    t.show()
    t.show_error_chart.setChecked(True)
    t.error_metric_combo.setCurrentIndex(t.error_metric_combo.findData("characteristic"))
    APP.processEvents()
    assert not t.training_characteristic_notice.isVisible()
    assert t.training_characteristic_plot.curve_points
    t.output_columns[0]["data_type"]="binary"
    assert not t.refresh_training_characteristic()
    assert t.training_characteristic_notice.isVisible()
    assert not t.training_characteristic_plot.isVisible()
    t.grab().save(str(out/("training_"+code+".png")))
    t.output_columns[0]["data_type"]="analog"
    t.refresh_training_characteristic()
    assert t.training_characteristic_plot.isVisible()
    extra=dict(t.input_columns[0])
    t.input_columns.append(extra)
    assert not t.refresh_training_characteristic()
    assert t.training_characteristic_notice.isVisible()
    t.input_columns.pop()
    t.input_columns[0]["data_type"]="binary"
    assert not t.refresh_training_characteristic()
    t.close();t.deleteLater();parent.deleteLater()
    APP.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    net,m=build()
    with patch.object(GraphicalExperimentDialog,"restore_window_geometry"):
        d=GraphicalExperimentDialog(net,m[:2],m[2:],[[-2,-2,-9],[2,2,11]],None,language_manager=lang(code))
    drain(lambda:not d.forward_calculation_running and not d.calculation_timer.isActive())
    proxy=d.curves.create();plot=proxy.widget().plot
    assert not plot.points and plot.note
    assert not d.curves.jobs
    plot.resize(440,300);plot.grab().save(str(out/("application_"+code+".png")))
    # A real single-input network restores the normal curve.
    net.remove_neuron(m[1]["neuron"])
    d.input_columns=d.input_columns[:1]
    d.forward_specification=d.create_forward_specification()
    d.curves.refresh({1:0.})
    drain(lambda:not d.curves.busy and not d.curves.pending and not d.curves.timer.isActive())
    assert len(plot.points)==161
    for mapping in (d.input_columns[0],d.output_columns[0]):
        mapping["data_type"]="binary"
        d.curves.refresh({1:0.})
        assert not plot.points and plot.point is None and plot.note
        d.curves.apply_points({1:0.,3:1.})
        assert plot.point is None
        mapping["data_type"]="analog"
        d.curves.refresh({1:0.})
        drain(lambda:not d.curves.busy and not d.curves.pending and not d.curves.timer.isActive())
        assert len(plot.points)==161
    d.stop_forward_executor()
    drain(lambda:not d.curves.busy)
    d.deleteLater();APP.sendPostedEvents(None,QEvent.Type.DeferredDelete);APP.processEvents()
APP.clipboard().clear()
print("PASS: training/application limits, binary input/output, recovery, DE/EN")
