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

class TestFraudAwareProcessor(unittest.TestCase):
    def setUp(self):
        self.detector = MagicMock()
        self.gateway = MagicMock()
        self.mailer = MagicMock()
        self.audit = MagicMock()

        self.proc = FraudAwareProcessor(
            gateway=self.gateway,
            detector=self.detector,
            mailer=self.mailer,
            audit=self.audit,
        )

    def make_tx(self, tx_id="TX-F01", user_id=1, amount=800.00):
        return Transaction(tx_id=tx_id, user_id=user_id, amount=amount)

    
    def test_high_risk_score_blocked(self):
        return FraudCheckResult(approved=True, risk_score = 0.99)

    def test_at_risk_score_blocked(self):
        return FraudCheckResult(approved=True, risk_score = 0.75)
    
    def test_low_risk_success_charge(self):
        self.detector.check.return_value = FraudCheckResult(approved=True, risk_score = 0.01)
        tx = self.make_tx()

        result = self.proc.process(tx)

        self.assertEqual(result, "success")

    def test_low_risk_declined_charge(self):
        self.gateway.charge.return_value = False
        self.detector.check.return_value = FraudCheckResult(approved=True, risk_score = 0.01)
        tx = self.make_tx()

        result = self.proc.process(tx)

        self.assertEqual(result, "declined")
    
    def test_fraud_detector_raising_connection_error(self):
        self.detector.check.side_effect = ConnectionError("Fraud API is down")
        tx = self.make_tx()

        with self.assertRaises(ConnectionError):
            self.proc.process(tx)

        self.gateway.charge.assert_not_called()
        self.mailer.send_receipt.assert_not_called()

    def test_fraud_alert_email_args(self):
        self.detector.check.return_value = FraudCheckResult(approved=False, risk_score=0.76, reason="Suspicious")
        tx = self.make_tx(tx_id="YIPEE", user_id=7, amount=1222)

        self.proc.process(tx)

        self.mailer.send_fraud_alert.assert_called_once_with(7, "YIPEE", 1222)

    def test_fraud_alert_email_args(self):
        self.detector.check.return_value = FraudCheckResult(approved=True, risk_score=0.4, reason="oki doki")
        tx = self.make_tx(tx_id="YIPEE", user_id=7, amount=1222)

        self.proc.process(tx)

        self.mailer.send_receipt.assert_called_once_with(7, "YIPEE", 1222)

class TestStatementBuilder(unittest.TestCase):
    def setUp(self):
        self.repo = MagicMock()
        self.builder = StatementBuilder(self.repo)

    def test_no_transactions(self):
        self.repo.find_by_user.return_value = []

        result = self.builder.build(user_id=9)

        self.assertEqual(result["count"],0)
        self.assertEqual(result["total_charged"],0.0)

    def test_success_sum(self):
        txs = [
            Transaction("TX1", 2, 99.99,  status="success"),
            Transaction("TX2", 2,  0.01,  status="success"),  # tiny amount
            Transaction("TX3", 2, 450.00, status="success"),
        ]
        self.repo.find_by_user.return_value = txs

        result = self.builder.build(user_id=2)

        self.assertEqual(result["total_charged"], 550.00)


    def test_only_successful_transactions_sum(self):
        txs = [
            Transaction("TX1", 10, 100.00, status="success"),
            Transaction("TX2", 10,  50.00, status="declined"),  # must be excluded
            Transaction("TX3", 10, 200.00, status="success"),
            Transaction("TX4", 10,  75.00, status="pending"),   # must be excluded
        ]

        self.repo.find_by_user.return_value = txs

        result = self.builder.build(user_id=10)

        self.assertEqual(result["total_charged"], 300.00)  # 100 + 200 only
        self.assertEqual(result["count"], 4)   

    def test_rounding(self):
        txs = [
            Transaction("TX1", 3, 10.555, status="success"),
            Transaction("TX2", 3,  0.005, status="success"),
        ]
        self.repo.find_by_user.return_value = txs

        result = self.builder.build(user_id=3)

        self.assertEqual(result["total_charged"], 10.56)

    def test_transaction_list_as_is(self):
        txs = [Transaction("TX1", 4, 100.00, status="success")]
        self.repo.find_by_user.return_value = txs

        result = self.builder.build(user_id=4)

        self.assertIs(result["transactions"], txs)





