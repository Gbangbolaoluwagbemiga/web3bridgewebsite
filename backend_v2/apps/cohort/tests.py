from unittest.mock import MagicMock, Mock, patch

import requests
from django.test import SimpleTestCase, TestCase, override_settings
from django.template.loader import render_to_string
from django.urls import reverse
from rest_framework.test import APIClient

from .helpers.portal import (
    create_portal_onboarding_invite,
    is_zk_course_name,
    normalize_approval_status,
)


class PortalInviteHelperTests(SimpleTestCase):
    def test_is_zk_course_name_detects_zk_course(self):
        self.assertTrue(is_zk_course_name("Zero Knowledge Bootcamp"))
        self.assertTrue(is_zk_course_name("ZK Cohort XIV"))
        self.assertFalse(is_zk_course_name("Web3 Cohort XIV"))

    @override_settings(PORTAL_ONBOARDING_URL="", PORTAL_INTERNAL_API_KEY="")
    def test_create_portal_onboarding_invite_returns_none_without_config(self):
        participant = Mock(
            id=12,
            email="student@example.com",
            cohort="Cohort-XIV",
            status="accepted",
            course=Mock(),
        )
        participant.name = "Student Example"
        participant.course.name = "Web3 Cohort XIV"

        activation_url = create_portal_onboarding_invite(participant)

        self.assertIsNone(activation_url)

    def test_normalize_approval_status_aliases(self):
        self.assertEqual(normalize_approval_status("accepted"), "approved")
        self.assertEqual(normalize_approval_status("APPROVED"), "approved")
        self.assertEqual(normalize_approval_status("declined"), "rejected")
        self.assertEqual(normalize_approval_status("suspended"), "revoked")
        self.assertEqual(normalize_approval_status(""), "approved")


class RegistrationEmailTemplateTests(SimpleTestCase):
    def test_non_zk_templates_render_activation_url_when_present(self):
        activation_url = "https://portal.example.com/activate?token=abc"
        template_names = [
            "cohort/web2_registration_email.html",
            "cohort/web3_registration_email.html",
            "cohort/rust_registration_email.html",
            "other_registration_email.html",
        ]

        for template_name in template_names:
            with self.subTest(template_name=template_name):
                rendered = render_to_string(
                    template_name,
                    {"name": "Student Example", "activation_url": activation_url},
                )

                self.assertIn("Activate your student portal account", rendered)
                self.assertIn(activation_url, rendered)

    def test_non_zk_templates_hide_activation_url_when_missing(self):
        template_names = [
            "cohort/web2_registration_email.html",
            "cohort/web3_registration_email.html",
            "cohort/rust_registration_email.html",
            "other_registration_email.html",
        ]

        for template_name in template_names:
            with self.subTest(template_name=template_name):
                rendered = render_to_string(
                    template_name,
                    {"name": "Student Example", "activation_url": None},
                )

                self.assertNotIn("Activate your student portal account", rendered)
                self.assertNotIn("portal.example.com/activate", rendered)

    @patch("apps.cohort.helpers.portal.requests.post")
    @override_settings(
        PORTAL_ONBOARDING_URL="http://localhost:8000/api/v1/onboarding/invite",
        PORTAL_INTERNAL_API_KEY="secret-key",
        PORTAL_REQUEST_TIMEOUT=5,
    )
    def test_create_portal_onboarding_invite_returns_activation_url(self, mock_post):
        response = Mock()
        response.json.return_value = {
            "activation_url": "https://portal.example.com/activate?token=abc"
        }
        response.raise_for_status.return_value = None
        mock_post.return_value = response

        participant = Mock(
            id=22,
            email="student@example.com",
            cohort="Cohort-XIV",
            status="accepted",
            course=Mock(),
        )
        participant.name = "Student Example"
        participant.course.name = "Web3 Cohort XIV"

        activation_url = create_portal_onboarding_invite(participant)

        self.assertEqual(
            activation_url, "https://portal.example.com/activate?token=abc"
        )
        mock_post.assert_called_once_with(
            "http://localhost:8000/api/v1/onboarding/invite",
            json={
                "email": "student@example.com",
                "full_name": "Student Example",
                "cohort": "Cohort-XIV",
                "course_name": "Web3 Cohort XIV",
                "external_student_id": "22",
                "source_system": "backend_v2",
                "source_email": "student@example.com",
                "approval_status": "approved",
            },
            headers={"X-Internal-API-Key": "secret-key"},
            timeout=5,
        )

    @patch("apps.cohort.helpers.portal.requests.post")
    @override_settings(
        PORTAL_ONBOARDING_URL="http://localhost:8000/api/v1/onboarding/invite",
        PORTAL_INTERNAL_API_KEY="secret-key",
        PORTAL_REQUEST_TIMEOUT=5,
    )
    def test_create_portal_onboarding_invite_skips_zk_courses(self, mock_post):
        participant = Mock(
            id=30,
            email="zkstudent@example.com",
            cohort="ZK-XIV",
            status="accepted",
            course=Mock(),
        )
        participant.name = "ZK Student"
        participant.course.name = "ZK Cohort XIV"

        activation_url = create_portal_onboarding_invite(participant)

        self.assertIsNone(activation_url)
        mock_post.assert_not_called()

    @patch("apps.cohort.helpers.portal.requests.post")
    @override_settings(
        PORTAL_ONBOARDING_URL="http://localhost:8000/api/v1/onboarding/invite",
        PORTAL_INTERNAL_API_KEY="secret-key",
        PORTAL_REQUEST_TIMEOUT=5,
    )
    def test_create_portal_onboarding_invite_returns_none_on_request_failure(
        self, mock_post
    ):
        mock_post.side_effect = requests.RequestException("network failure")

        participant = Mock(
            id=44,
            email="student@example.com",
            cohort="Cohort-XIV",
            status="accepted",
            course=Mock(),
        )
        participant.name = "Student Example"
        participant.course.name = "Web3 Cohort XIV"

        activation_url = create_portal_onboarding_invite(participant)

        self.assertIsNone(activation_url)

    @patch("apps.cohort.helpers.portal.requests.post")
    @override_settings(
        PORTAL_ONBOARDING_URL="http://localhost:8000/api/v1/onboarding/invite",
        PORTAL_INTERNAL_API_KEY="secret-key",
        PORTAL_REQUEST_TIMEOUT=5,
        PORTAL_REQUEST_MAX_RETRIES=2,
        PORTAL_REQUEST_RETRY_BACKOFF_SECONDS=0,
        PORTAL_REQUEST_RETRY_STATUS_CODES=(503,),
    )
    def test_create_portal_onboarding_invite_retries_retryable_http_error(self, mock_post):
        retryable_response = Mock(status_code=503)
        retryable_error = requests.HTTPError(response=retryable_response)

        success_response = Mock()
        success_response.raise_for_status.return_value = None
        success_response.json.return_value = {
            "activation_url": "https://portal.example.com/activate?token=retry-success"
        }

        first_response = Mock()
        first_response.raise_for_status.side_effect = retryable_error

        mock_post.side_effect = [first_response, success_response]

        participant = Mock(
            id=46,
            email="student@example.com",
            cohort="Cohort-XIV",
            status="accepted",
            course=Mock(),
        )
        participant.name = "Student Example"
        participant.course.name = "Web3 Cohort XIV"

        activation_url = create_portal_onboarding_invite(participant)

        self.assertEqual(
            activation_url,
            "https://portal.example.com/activate?token=retry-success",
        )
        self.assertEqual(mock_post.call_count, 2)

    @patch("apps.cohort.helpers.portal.requests.post")
    @override_settings(
        PORTAL_ONBOARDING_URL="http://localhost:8000/api/v1/onboarding/invite",
        PORTAL_INTERNAL_API_KEY="secret-key",
        PORTAL_REQUEST_TIMEOUT=5,
        PORTAL_REQUEST_MAX_RETRIES=3,
        PORTAL_REQUEST_RETRY_BACKOFF_SECONDS=0,
        PORTAL_REQUEST_RETRY_STATUS_CODES=(503,),
    )
    def test_create_portal_onboarding_invite_does_not_retry_non_retryable_http_error(
        self, mock_post
    ):
        non_retryable_response = Mock(status_code=400)
        non_retryable_error = requests.HTTPError(response=non_retryable_response)

        failed_response = Mock()
        failed_response.raise_for_status.side_effect = non_retryable_error
        mock_post.return_value = failed_response

        participant = Mock(
            id=47,
            email="student@example.com",
            cohort="Cohort-XIV",
            status="accepted",
            course=Mock(),
        )
        participant.name = "Student Example"
        participant.course.name = "Web3 Cohort XIV"

        activation_url = create_portal_onboarding_invite(participant)

        self.assertIsNone(activation_url)
        self.assertEqual(mock_post.call_count, 1)


@override_settings(SECURE_SSL_REDIRECT=False)
class RescheduleAssessmentEndpointTests(TestCase):
    """
    Tests for POST /api/v2/cohort/participant/reschedule/
    No DB needed — the endpoint only validates input and sends an email.
    Email sending is mocked so no real SMTP calls are made.
    """

    ENDPOINT = "/api/v2/cohort/participant/reschedule/"

    VALID_PAYLOAD = {
        "email": "student@example.com",
        "name": "John Doe",
        "cohort": "Web3 Cohort XIV",
        "assessment_link": "https://calendly.com/web3bridge/assessment",
    }

    def setUp(self):
        self.client = APIClient()

    @patch("cohort.views.send_reschedule_assessment_email")
    def test_valid_request_returns_200_and_sends_email(self, mock_send):
        response = self.client.post(self.ENDPOINT, self.VALID_PAYLOAD, format="json")

        self.assertEqual(response.status_code, 200)
        mock_send.assert_called_once_with(
            "student@example.com",
            "John Doe",
            "Web3 Cohort XIV",
            "https://calendly.com/web3bridge/assessment",
        )

    @patch("cohort.views.send_reschedule_assessment_email")
    def test_response_contains_success_message(self, mock_send):
        response = self.client.post(self.ENDPOINT, self.VALID_PAYLOAD, format="json")

        self.assertIn("email sent", response.json()["data"]["message"].lower())

    @patch("cohort.views.send_reschedule_assessment_email")
    def test_missing_email_returns_400(self, mock_send):
        payload = {**self.VALID_PAYLOAD}
        payload.pop("email")
        response = self.client.post(self.ENDPOINT, payload, format="json")

        self.assertEqual(response.status_code, 400)
        mock_send.assert_not_called()

    @patch("cohort.views.send_reschedule_assessment_email")
    def test_missing_name_returns_400(self, mock_send):
        payload = {**self.VALID_PAYLOAD}
        payload.pop("name")
        response = self.client.post(self.ENDPOINT, payload, format="json")

        self.assertEqual(response.status_code, 400)
        mock_send.assert_not_called()

    @patch("cohort.views.send_reschedule_assessment_email")
    def test_missing_cohort_returns_400(self, mock_send):
        payload = {**self.VALID_PAYLOAD}
        payload.pop("cohort")
        response = self.client.post(self.ENDPOINT, payload, format="json")

        self.assertEqual(response.status_code, 400)
        mock_send.assert_not_called()

    @patch("cohort.views.send_reschedule_assessment_email")
    def test_missing_assessment_link_returns_400(self, mock_send):
        payload = {**self.VALID_PAYLOAD}
        payload.pop("assessment_link")
        response = self.client.post(self.ENDPOINT, payload, format="json")

        self.assertEqual(response.status_code, 400)
        mock_send.assert_not_called()

    @patch("cohort.views.send_reschedule_assessment_email")
    def test_invalid_email_returns_400(self, mock_send):
        payload = {**self.VALID_PAYLOAD, "email": "not-an-email"}
        response = self.client.post(self.ENDPOINT, payload, format="json")

        self.assertEqual(response.status_code, 400)
        mock_send.assert_not_called()

    @patch("cohort.views.send_reschedule_assessment_email")
    def test_invalid_assessment_link_returns_400(self, mock_send):
        payload = {**self.VALID_PAYLOAD, "assessment_link": "not-a-url"}
        response = self.client.post(self.ENDPOINT, payload, format="json")

        self.assertEqual(response.status_code, 400)
        mock_send.assert_not_called()

    @patch("cohort.views.send_reschedule_assessment_email")
    def test_second_reschedule_is_blocked(self, mock_send):
        # First reschedule — should succeed
        self.client.post(self.ENDPOINT, self.VALID_PAYLOAD, format="json")

        # Second reschedule with same email — should be blocked
        response = self.client.post(self.ENDPOINT, self.VALID_PAYLOAD, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("already rescheduled", response.json()["message"].lower())
        # Email sent only once (first request)
        mock_send.assert_called_once()

    @patch("cohort.views.send_reschedule_assessment_email")
    def test_different_email_can_still_reschedule(self, mock_send):
        # First participant reschedules
        self.client.post(self.ENDPOINT, self.VALID_PAYLOAD, format="json")

        # Different participant — should be allowed
        different_payload = {**self.VALID_PAYLOAD, "email": "other@example.com"}
        response = self.client.post(self.ENDPOINT, different_payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_send.call_count, 2)


class RescheduleAssessmentTemplateTests(SimpleTestCase):
    """Verify the email template renders all key content correctly."""

    TEMPLATE = "cohort/reschedule_assessment_email.html"

    def test_template_renders_student_name(self):
        rendered = render_to_string(self.TEMPLATE, {
            "name": "John Doe",
            "cohort": "Web3 Cohort XIV",
            "assessment_link": "https://calendly.com/web3bridge/assessment",
        })
        self.assertIn("John Doe", rendered)

    def test_template_renders_cohort(self):
        rendered = render_to_string(self.TEMPLATE, {
            "name": "John Doe",
            "cohort": "Web3 Cohort XIV",
            "assessment_link": "https://calendly.com/web3bridge/assessment",
        })
        self.assertIn("Web3 Cohort XIV", rendered)

    def test_template_renders_assessment_link(self):
        link = "https://calendly.com/web3bridge/assessment"
        rendered = render_to_string(self.TEMPLATE, {
            "name": "John Doe",
            "cohort": "Web3 Cohort XIV",
            "assessment_link": link,
        })
        self.assertIn(link, rendered)

    def test_template_mentions_3_days(self):
        rendered = render_to_string(self.TEMPLATE, {
            "name": "John Doe",
            "cohort": "Web3 Cohort XIV",
            "assessment_link": "https://calendly.com/web3bridge/assessment",
        })
        self.assertIn("3 days", rendered)


@override_settings(SECURE_SSL_REDIRECT=False)
class SubmitAssessmentEndpointTests(TestCase):
    """Tests for POST /api/v2/cohort/participant/submit-assessment/"""

    ENDPOINT = "/api/v2/cohort/participant/submit-assessment/"
    API_KEY = "EY63JDFEE9GKNJDBDJ"

    def setUp(self):
        self.client = APIClient()
        # Create prerequisite objects
        from cohort.models import Registration, Course, Participant
        self.registration = Registration.objects.create(
            name="Web3 Cohort XIV", cohort="Cohort-XIV", is_open=True
        )
        self.course = Course.objects.create(
            name="Web3 Development",
            description="Learn Web3",
            extra_info="Extra",
            registration=self.registration,
        )
        self.participant = Participant.objects.create(
            name="John Doe",
            email="john@example.com",
            wallet_address="0x123",
            registration=self.registration,
            course=self.course,
            cohort="Cohort-XIV",
            venue="online",
        )

    def _post(self, payload, api_key=None):
        key = api_key if api_key is not None else self.API_KEY
        return self.client.post(
            self.ENDPOINT, payload, format="json", headers={"API-Key": key}
        )

    def _post_no_key(self, payload):
        return self.client.post(self.ENDPOINT, payload, format="json")

    @patch("cohort.views.send_assessment_passed_email")
    def test_pass_creates_assessment_and_sends_passed_email(self, mock_passed):
        payload = {"email": "john@example.com", "score": "85.50", "passed": True}
        response = self._post(payload)

        self.assertEqual(response.status_code, 201)
        from cohort.models import Assessment
        self.assertTrue(Assessment.objects.filter(participant=self.participant, passed=True).exists())
        mock_passed.assert_called_once()

    @patch("cohort.views.send_assessment_passed_email")
    def test_breakdown_persisted_and_passed_to_email(self, mock_passed):
        breakdown = {"logic": 40, "solidity": 45}
        payload = {
            "email": "john@example.com",
            "score": "85.50",
            "passed": True,
            "breakdown": breakdown,
        }
        response = self._post(payload)

        self.assertEqual(response.status_code, 201)
        from cohort.models import Assessment
        a = Assessment.objects.get(participant=self.participant)
        self.assertEqual(a.breakdown, breakdown)
        mock_passed.assert_called_once()
        self.assertEqual(mock_passed.call_args.kwargs.get("breakdown"), breakdown)

    @patch("cohort.views.send_assessment_failed_email")
    def test_fail_creates_assessment_and_sends_failed_email(self, mock_failed):
        payload = {"email": "john@example.com", "score": "40.00", "passed": False}
        response = self._post(payload)

        self.assertEqual(response.status_code, 201)
        from cohort.models import Assessment
        self.assertTrue(Assessment.objects.filter(participant=self.participant, passed=False).exists())
        mock_failed.assert_called_once()

    @patch("cohort.views.send_assessment_passed_email")
    def test_duplicate_assessment_same_cohort_is_blocked(self, mock_passed):
        payload = {"email": "john@example.com", "score": "85.50", "passed": True}
        self._post(payload)
        response = self._post(payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("already submitted", response.json()["message"].lower())

    @patch("cohort.views.send_assessment_passed_email")
    def test_missing_api_key_returns_401(self, mock_passed):
        payload = {"email": "john@example.com", "score": "85.50", "passed": True}
        response = self._post_no_key(payload)

        self.assertEqual(response.status_code, 401)
        mock_passed.assert_not_called()

    @patch("cohort.views.send_assessment_passed_email")
    def test_wrong_api_key_returns_401(self, mock_passed):
        payload = {"email": "john@example.com", "score": "85.50", "passed": True}
        response = self._post(payload, api_key="wrong-key")

        self.assertEqual(response.status_code, 401)
        mock_passed.assert_not_called()

    @patch("cohort.views.send_assessment_passed_email")
    def test_unknown_email_returns_404(self, mock_passed):
        payload = {"email": "nobody@example.com", "score": "85.50", "passed": True}
        response = self._post(payload)

        self.assertEqual(response.status_code, 404)
        mock_passed.assert_not_called()

    @patch("cohort.views.send_assessment_passed_email")
    def test_invalid_score_returns_400(self, mock_passed):
        payload = {"email": "john@example.com", "score": "not-a-number", "passed": True}
        response = self._post(payload)

        self.assertEqual(response.status_code, 400)
        mock_passed.assert_not_called()


class PaymentActivationEmailTests(SimpleTestCase):
    """
    Verify that after a successful payment, the portal activation URL
    is fetched and passed into the registration success email for non-ZK students.
    ZK students must NOT receive the activation URL.
    """

    @patch("cohort.helpers.model.base.render_to_string")
    @patch("cohort.helpers.model.base.EmailMessage")
    @patch("cohort.views.create_portal_onboarding_invite")
    def test_activation_url_passed_to_email_for_web3_course(
        self, mock_invite, mock_email_cls, mock_render
    ):
        mock_invite.return_value = "https://portal.web3bridge.com/activate/onboard?token=abc"
        mock_render.return_value = "<html></html>"
        mock_email_cls.return_value = MagicMock()

        with patch("cohort.models.Course") as mock_course_cls:
            mock_course = MagicMock()
            mock_course.name = "Web3 Development"
            mock_course_cls.objects.get.return_value = mock_course

            from cohort.helpers.model.base import send_registration_success_mail
            send_registration_success_mail(
                "student@example.com", 1, "John Doe",
                activation_url="https://portal.web3bridge.com/activate/onboard?token=abc"
            )

        call_kwargs = mock_render.call_args
        context = call_kwargs[0][1]
        self.assertEqual(
            context.get("activation_url"),
            "https://portal.web3bridge.com/activate/onboard?token=abc"
        )

    @patch("cohort.helpers.model.base.render_to_string")
    @patch("cohort.helpers.model.base.EmailMessage")
    def test_activation_url_is_none_for_zk_course(self, mock_email_cls, mock_render):
        mock_render.return_value = "<html></html>"
        mock_email_cls.return_value = MagicMock()

        with patch("cohort.models.Course") as mock_course_cls:
            mock_course = MagicMock()
            mock_course.name = "ZK Cohort XIV"
            mock_course_cls.objects.get.return_value = mock_course

            from cohort.helpers.model.base import send_registration_success_mail
            send_registration_success_mail(
                "zk@example.com", 1, "ZK Student",
                activation_url="https://portal.web3bridge.com/activate/onboard?token=zk"
            )

        call_kwargs = mock_render.call_args
        context = call_kwargs[0][1]
        self.assertIsNone(context.get("activation_url"))

    @patch("cohort.views.send_registration_success_mail")
    @patch("cohort.views.send_participant_details")
    @patch("cohort.views.create_portal_onboarding_invite")
    def test_handle_payment_success_calls_portal_invite(
        self, mock_invite, mock_details, mock_mail
    ):
        from cohort.views import handle_payment_success
        from unittest.mock import MagicMock

        mock_invite.return_value = "https://portal.web3bridge.com/activate/onboard?token=xyz"

        participant = MagicMock()
        serialized = {
            "email": "student@example.com",
            "name": "John Doe",
            "course": {"id": 1},
        }
        serializer_class = MagicMock()

        handle_payment_success(participant, serialized, serializer_class)

        # Portal invite must be called with the participant object
        mock_invite.assert_called_once_with(participant)
        # Mail must be called with the activation_url
        mock_mail.assert_called_once_with(
            "student@example.com", 1, "John Doe",
            activation_url="https://portal.web3bridge.com/activate/onboard?token=xyz"
        )


class SubmitAssessmentTemplateTests(SimpleTestCase):
    """Verify pass/fail email templates render correctly."""

    def test_passed_template_renders_name_score_payment_link(self):
        rendered = render_to_string("cohort/assessment_passed_email.html", {
            "name": "John Doe",
            "cohort": "Web3 Cohort XIV",
            "score": "85.50",
            "payment_link": "https://payment.web3bridgeafrica.com",
            "breakdown_display": None,
        })
        self.assertIn("John Doe", rendered)
        self.assertIn("85.50", rendered)
        self.assertIn("https://payment.web3bridgeafrica.com", rendered)

    def test_passed_template_renders_breakdown_when_present(self):
        rendered = render_to_string("cohort/assessment_passed_email.html", {
            "name": "John Doe",
            "cohort": "Web3 Cohort XIV",
            "score": "85.50",
            "payment_link": "https://payment.web3bridgeafrica.com",
            "breakdown_display": '{\n  "a": 40\n}',
        })
        self.assertIn("Score breakdown", rendered)
        self.assertIn('"a": 40', rendered)

    def test_failed_template_renders_name_score_and_encouragement(self):
        rendered = render_to_string("cohort/assessment_failed_email.html", {
            "name": "John Doe",
            "cohort": "Web3 Cohort XIV",
            "score": "40.00",
            "breakdown_display": None,
        })
        self.assertIn("John Doe", rendered)
        self.assertIn("40.00", rendered)
        self.assertIn("next cohort", rendered.lower())

    def test_failed_template_renders_breakdown_when_present(self):
        rendered = render_to_string("cohort/assessment_failed_email.html", {
            "name": "John Doe",
            "cohort": "Web3 Cohort XIV",
            "score": "40.00",
            "breakdown_display": "Section A: 10 / 30",
        })
        self.assertIn("Score breakdown", rendered)
        self.assertIn("Section A: 10 / 30", rendered)
