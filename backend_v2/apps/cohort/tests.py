from unittest.mock import Mock, patch

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
class RescheduleAssessmentEndpointTests(SimpleTestCase):
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
