from _test_applicationcurve import APP
from _test_training_comparison import make_dialog
from PySide6.QtCore import QEvent
from pathlib import Path
out=Path(".change_baseline_training_notice_20261020")
for code in ("de","en"):
    parent,d=make_dialog(code)
    d.resize(1150,850)
    d.show()
    d.show_error_chart.setChecked(True)
    for case in ("multiple","binary_input","binary_output","analog"):
        d.input_columns=d.input_columns[:1]
        d.input_columns[0]["data_type"]="analog"
        d.output_columns[0]["data_type"]="analog"
        if case=="multiple": d.input_columns.append(dict(d.input_columns[0]))
        if case=="binary_input": d.input_columns[0]["data_type"]="binary"
        if case=="binary_output": d.output_columns[0]["data_type"]="binary"
        d.populate_training_characteristic_controls()
        index=d.error_metric_combo.findData("characteristic")
        assert index>=0
        d.error_metric_combo.setCurrentIndex(index)
        d.update_error_metric()
        APP.processEvents()
        supported=case=="analog"
        assert d.error_metric_combo.currentData()=="characteristic"
        assert d.training_characteristic_notice.isVisible()!=supported
        assert d.training_characteristic_controls.isVisible()==supported
        assert d.training_characteristic_plot.isVisible()==supported
        assert not d.error_chart.isVisible()
        if supported: assert d.training_characteristic_plot.curve_points
        else:
            assert not d.training_characteristic_plot.curve_points
            if case=="multiple": d.grab().save(str(out/(code+"_notice.png")))
        d.error_metric_combo.setCurrentIndex(d.error_metric_combo.findData("mse"))
        APP.processEvents()
        assert d.error_chart.isVisible()
        assert not d.training_characteristic_notice.isVisible()
        assert not d.training_characteristic_controls.isVisible()
    d.close();d.deleteLater();parent.deleteLater()
    APP.sendPostedEvents(None,QEvent.Type.DeferredDelete);APP.processEvents()
APP.clipboard().clear()
print("PASS: persistent choice, centered notice, hidden controls, analog curve and MSE switching in DE/EN")
