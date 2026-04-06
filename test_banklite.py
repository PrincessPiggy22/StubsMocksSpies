import pytest
import unittest
from unittest.mock import MagicMock, call, Mock
from banklite import *

class TestPaymentProcessor(unittest.TestCase):
    def setUp(self):
        self.gateway = MagicMock()
        self.audit   = MagicMock()
        self.proc    = PaymentProcessor(self.gateway, self.audit)

    def _make_tx(self, amount=100.00, tx_id="TX-001", user_id=1):
        return Transaction(tx_id=tx_id, user_id=user_id, amount=amount)

    def test_success_charge(self):
        # make charge return true
        tx = self._make_tx()
        self.gateway.charge.return_value = True

        result = self.proc.process(tx)
        self.assertEqual(result, "success")

    def test_declined_charge(self):
        tx = self._make_tx()
        self.gateway.charge.return_value = False

        result = self.proc.process(tx)
        self.assertEqual(result, "declined")

    def test_zero_amount_value_error(self):
        tx = self._make_tx(amount=0.00)

        with pytest.raises(ValueError):
            result = self.proc.process(tx)
        self.gateway.charge.assert_not_called()

    def test_negative_amount_value_error(self):
        tx = self._make_tx(amount = -0.01)

        with pytest.raises(ValueError):
            result = self.proc.process(tx)
        self.gateway.charge.assert_not_called()

    def test_exceeded_amount_value_error(self):
        tx = self._make_tx(amount = 10000.01)

        with pytest.raises(ValueError):
            result = self.proc.process(tx)

    def test_audit_success(self):
        self.gateway.charge.return_value = True
        tx = self._make_tx(tx_id="TX-67", amount=110.89)

        self.proc.process(tx)

        self.audit.record.assert_called_once_with(
         "CHARGED", tx.tx_id, {"amount": tx.amount}
        )

    def test_audit_decline(self):
        self.gateway.charge.return_value = False
        tx = self._make_tx(tx_id="TX-33", amount= 67)

        self.proc.process(tx)

        self.audit.record.assert_called_once_with(
        "DECLINED", tx.tx_id, {"amount": tx.amount}
        )

    def test_audit_not_called_invalid_input(self):

        tx = self._make_tx(amount = 10000.01)

        with pytest.raises(ValueError):
            result = self.proc.process(tx)
        self.audit.record.assert_not_called()