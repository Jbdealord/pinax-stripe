import decimal

from django.core.urlresolvers import reverse
from django.test import TestCase
from django.utils import timezone

from django.contrib.auth import authenticate, login, logout, get_user_model

from mock import Mock

from ..conf import settings
from ..middleware import ActiveSubscriptionMiddleware
from ..actions import CustomerProxy, CurrentSubscriptionProxy


class DummySession(dict):

    def cycle_key(self):
        return

    def flush(self):
        return


class ActiveSubscriptionMiddlewareTests(TestCase):
    urls = 'pinax.stripe.tests.test_urls'

    def setUp(self):
        self.middleware = ActiveSubscriptionMiddleware()
        self.request = Mock()
        self.request.META = {}
        self.request.session = DummySession()

        self.old_urls = settings.PINAX_STRIPE_SUBSCRIPTION_REQUIRED_EXCEPTION_URLS
        settings.PINAX_STRIPE_SUBSCRIPTION_REQUIRED_EXCEPTION_URLS += (
            'signup',
            'password_reset'
        )

        user = get_user_model().objects.create_user(username="patrick")
        user.set_password("eldarion")
        user.save()
        user = authenticate(username="patrick", password="eldarion")
        login(self.request, user)

    def tearDown(self):
        settings.PINAX_STRIPE_SUBSCRIPTION_REQUIRED_EXCEPTION_URLS = self.old_urls

    def test_authed_user_with_no_customer_redirects_on_non_exempt_url(self):
        self.request.path = "/the/app/"
        response = self.middleware.process_request(self.request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response._headers["location"][1],
            reverse(settings.PINAX_STRIPE_SUBSCRIPTION_REQUIRED_REDIRECT)
        )

    def test_authed_user_with_no_customer_passes_with_exempt_url(self):
        self.request.path = "/accounts/signup/"
        response = self.middleware.process_request(self.request)
        self.assertIsNone(response)

    def test_authed_user_with_no_customer_passes_with_exempt_url_containing_pattern(self):
        self.request.path = "/password/reset/confirm/test-token/"
        response = self.middleware.process_request(self.request)
        self.assertIsNone(response)

    def test_authed_user_with_no_active_subscription_passes_with_exempt_url(self):
        CustomerProxy.objects.create(stripe_id="cus_1", user=self.request.user)
        self.request.path = "/accounts/signup/"
        response = self.middleware.process_request(self.request)
        self.assertIsNone(response)

    def test_authed_user_with_no_active_subscription_redirects_on_non_exempt_url(self):
        CustomerProxy.objects.create(stripe_id="cus_1", user=self.request.user)
        self.request.path = "/the/app/"
        response = self.middleware.process_request(self.request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response._headers["location"][1],
            reverse(settings.PINAX_STRIPE_SUBSCRIPTION_REQUIRED_REDIRECT)
        )

    def test_authed_user_with_active_subscription_redirects_on_non_exempt_url(self):
        customer = CustomerProxy.objects.create(
            stripe_id="cus_1",
            user=self.request.user
        )
        CurrentSubscriptionProxy.objects.create(
            customer=customer,
            plan="pro",
            quantity=1,
            start=timezone.now(),
            status="active",
            cancel_at_period_end=False,
            amount=decimal.Decimal("19.99"),
            currency="usd"
        )
        self.request.path = "/the/app/"
        response = self.middleware.process_request(self.request)
        self.assertIsNone(response)

    def test_unauthed_user_passes(self):
        logout(self.request)
        self.request.path = "/the/app/"
        response = self.middleware.process_request(self.request)
        self.assertIsNone(response)

    def test_staff_user_passes(self):
        self.request.user.is_staff = True
        self.request.path = "/the/app/"
        response = self.middleware.process_request(self.request)
        self.assertIsNone(response)
