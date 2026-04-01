import unittest
from unittest.mock import MagicMock, call, Mock
from banklite import *

class TestPaymentProcessor(unittest.TestCase):
    def setUp(self):
        self.gateway = MagicMock()
        self.audit   = MagicMock()
        self.proc    = PaymentProcessor(self.gateway, self.audit)

    def test_success_charge(self):
        # make charge return true
        self.gateway.charge.return_value = True

       # result = self.gateway.charge(tx = 100)
        result2 = self.proc.process(tx = 100)
        assert result2 == "success"

    def test_declined_charge(self):
        # make charge return False
        self.gateway.charge.return_value = False

        result = self.my_service.process_payment(amount = 100)
        assert result == "declined"

    def test_zero_amount_value_error(self):
        with pytest.raises(ValueError):
            result = self.my_service.process_payment(amount = 0.00)
        self.gateway.charge.assert_not_called()

    def test_negative_amount_value_error(self):
        with pytest.raises(ValueError):
            result = self.my_service.process_payment(amount = -0.01)
        self.gateway.charge.assert_not_called()

    def test_exceeded_amount_value_error(self):
        with pytest.raises(ValueError):
            result = self.my_service.process_payment(amount = 10000.01)

    def test_audit_success(self):
        self.audit.record.assert_called_once_with(
         "CHARGED", tx.tx_id, {"amount": tx.amount}
        )

    def test_audit_decline(self):
        self.audit.record.assert_called_once_with(
        "DECLINED", tx.tx_id, {"amount": tx.amount}
        )

    def test_audit_not_called_invalid_input(self):
        with pytest.raises(ValueError):
            result = self.my_service.process_payment(amount = 10000.01)
        self.audit.record.assert_not_called()