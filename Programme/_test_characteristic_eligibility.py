"""Analysis eligibility and recovery of the one-input characteristic."""
from pathlib import Path
from PySide6.QtCore import QEvent
from PySide6.QtTest import QTest
from _test_applicationcurve import APP, build, lang, runtime
from resultanalysisdialog import ResultAnalysisDialog

out=Path(".change_baseline_characteristic_eligibility_20261019")
for code in ("de","en"):
    net,m=build()
    before=runtime(net)
    source=dict(label="Training",kind="training",inputs=m[:2],outputs=m[2:],
                records=[[-2.,0.,0.],[2.,0.,8.]])
    d=ResultAnalysisDialog(net,[source],language_manager=lang(code))
    d.tabs.setCurrentWidget(d.characteristic_tab)
    d.resize(930,740)
    d.show()
    APP.processEvents()
    assert d.characteristic_unavailable.isVisible()
    assert not d.characteristic_content.isVisible()
    assert not d.characteristic_slider.isVisible()
    assert not d.characteristic_plot.isVisible()
    assert d.output_combo.isVisible()
    assert not d.characteristic_marker_timer.isActive()
    d.grab().save(str(out/("notice_"+code+".png")))
    # A single analog input restores the existing plot and interpolation.
    net.remove_neuron(m[1]["neuron"])
    before=runtime(net)
    source["inputs"]=m[:1]
    d.populate_characteristic_inputs()
    d.refresh_characteristic()
    assert not d.characteristic_unavailable.isVisible()
    assert d.characteristic_content.isVisible()
    d.characteristic_slider.setValue(7500)
    QTest.qWait(120)
    assert d.characteristic_plot.reference_point==(1.,6.), (d.characteristic_plot.reference_point,d.characteristic_context.text(),d.characteristic_values)
    assert d.characteristic_plot.operating_point==(1.,3.)
    assert d.characteristic_plot.comparison_active
    # Binary input or output shows the notice; returning to analog restores it.
    for mapping in (m[0],m[2]):
        previous=mapping.get("data_type")
        mapping["data_type"]="binary"
        d.refresh_characteristic()
        assert d.characteristic_unavailable.isVisible()
        assert not d.characteristic_content.isVisible()
        mapping["data_type"]=previous
        d.refresh_characteristic()
        assert d.characteristic_content.isVisible()
    # Multiple outputs are permitted, depending on the selected output type.
    extra=dict(m[0],column_index=1,column_name="Binary output",data_type="binary")
    source["outputs"].append(extra)
    d.output_combo.addItem("Binary output",extra["neuron"].id)
    d.output_combo.setCurrentIndex(d.output_combo.count()-1)
    APP.processEvents()
    assert d.characteristic_unavailable.isVisible()
    d.output_combo.setCurrentIndex(d.output_combo.findData(m[2]["neuron"].id))
    APP.processEvents()
    assert d.characteristic_content.isVisible()
    assert runtime(net)==before
    d.characteristic_marker_timer.stop()
    d.close()
    d.deleteLater()
    APP.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    APP.processEvents()
APP.clipboard().clear()
print("PASS: DE/EN notice, hidden controls, analog interpolation, binary input/output, output switching, runtime unchanged")
