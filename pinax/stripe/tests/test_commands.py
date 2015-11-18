from django.core import management
from django.test import TestCase

from django.contrib.auth import get_user_model

from mock import patch

from ..actions import CustomerProxy


class CommandTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="patrick")

    @patch("stripe.Customer.retrieve")
    @patch("stripe.Customer.create")
    def test_init_customer_creates_customer(self, CreateMock, RetrieveMock):
        CreateMock.return_value.id = "cus_XXXXX"
        CreateMock.return_value.active_card.fingerprint = "X"
        CreateMock.return_value.active_card.last4 = "1234"
        CreateMock.return_value.active_card.type = "Visa"
        management.call_command("init_customers")
        customer = CustomerProxy.get_for_user(self.user)
        self.assertEquals(customer.stripe_id, "cus_XXXXX")

    @patch("stripe.Plan.create")
    def test_plans_create(self, CreateMock):
        management.call_command("init_plans")
        self.assertEquals(CreateMock.call_count, 3)
        # order of plans creating is not important, but dict doesn't preserve it
        calls = sorted(CreateMock.mock_calls, key=lambda x: x[2]['id'])
        _, _, kwargs = calls[0]
        self.assertEqual(kwargs["id"], "entry-monthly")
        self.assertEqual(kwargs["amount"], 954)
        _, _, kwargs = calls[1]
        self.assertEqual(kwargs["id"], "premium-monthly")
        self.assertEqual(kwargs["amount"], 5999)
        _, _, kwargs = calls[2]
        self.assertEqual(kwargs["id"], "pro-monthly")
        self.assertEqual(kwargs["amount"], 1999)

    @patch("stripe.Customer.retrieve")
    @patch("pinax.stripe.actions.CustomerProxy.sync")
    @patch("pinax.stripe.actions.CustomerProxy.sync_current_subscription")
    @patch("pinax.stripe.actions.CustomerProxy.sync_invoices")
    @patch("pinax.stripe.actions.CustomerProxy.sync_charges")
    def test_sync_customers(self, SyncChargesMock, SyncInvoicesMock, SyncSubscriptionMock, SyncMock, RetrieveMock):
        user2 = get_user_model().objects.create_user(username="thomas")
        get_user_model().objects.create_user(username="altman")
        CustomerProxy.objects.create(stripe_id="cus_XXXXX", user=self.user)
        CustomerProxy.objects.create(stripe_id="cus_YYYYY", user=user2)
        management.call_command("sync_customers")
        self.assertEqual(SyncChargesMock.call_count, 2)
        self.assertEqual(SyncInvoicesMock.call_count, 2)
        self.assertEqual(SyncSubscriptionMock.call_count, 2)
        self.assertEqual(SyncMock.call_count, 2)
