import unittest
from unittest.mock import patch,Mock
from _test_applicationcurve import APP,build,lang
from neuron import Neuron
from connection import Connection
from neurontype import NeuronType
from graphicalexperimentdialog import GraphicalExperimentDialog,SimplifiedNetworkCard
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QEvent

class NetworkLimitTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        APP.clipboard().clear()

    def tearDown(self):
        APP.processEvents()
        APP.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        APP.processEvents()

    def network(self,count):
        net,m=build()
        for i in range(4,count+1):
            n=Neuron(i,0,0,'N'+str(i));n.neuron_type=NeuronType.HIDDEN;net.add_neuron(n)
            net.add_connection(Connection(i*2,net.get_neuron(1),n,.1))
            net.add_connection(Connection(i*2+1,n,net.get_neuron(3),.1))
        return net,m

    def test_limit_boundary_and_skip_expensive_preparation(self):
        net,_=self.network(50)
        card=SimplifiedNetworkCard(net,lambda de,en:de)
        self.assertEqual(card.neuron_count,50)
        self.assertTrue(card.cached_layers)
        card.deleteLater()
        for code in ('de','en'):
            net,_=self.network(51)
            with patch.object(net,'get_topological_layers',side_effect=AssertionError('must not build large view')):
                card=SimplifiedNetworkCard(net,lambda de,en:de if code=='de' else en)
            self.assertEqual(card.cached_layers,[])
            self.assertEqual(card.cached_connections,[])
            self.assertIn('50',card.limit_message());self.assertIn('51',card.limit_message())
            card.resize(430,300);card.show();APP.processEvents()
            self.assertEqual(card.node_hit_areas,[])
            if code=='de':card.grab().save('diagnostics/application_network_limit_checked.png')
            card.close();card.deleteLater()

    def test_rejected_insertion_and_saved_element_preserved(self):
        net,m=self.network(51)
        with patch.object(GraphicalExperimentDialog,'restore_window_geometry'):
            d=GraphicalExperimentDialog(net,m[:2],m[2:],language_manager=lang('de'))
        try:
            d.edit_mode=True
            proxy=d.network_view_card
            proxy.setVisible(False)
            with patch.object(QMessageBox,'information') as message,patch.object(d,'begin_history_action') as history:
                d.request_existing_element_placement(proxy)
                d.add_existing_element(proxy)
                self.assertEqual(message.call_count,2)
                history.assert_not_called()
                self.assertFalse(proxy.isVisible())
            proxy.setPos(123,234);proxy.setVisible(True)
            state=d.layout_state()['network_view_element']
            self.assertTrue(state['visible'])
            self.assertEqual((state['x'],state['y']),(123,234))
            self.assertIs(d.network_view_card,proxy)
            self.assertEqual(len(net.get_neurons()),51)
        finally:
            d._allow_close=True;d.hide();d.deleteLater();APP.processEvents()

if __name__=='__main__':unittest.main()
