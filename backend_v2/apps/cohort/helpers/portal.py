import logging
import re
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_APPROVAL_STATUS_ALIASES: dict[str, str] = {
    "accepted": "approved",
    "approved": "approved",
    "active": "approved",
    "rejected": "rejected",
    "declined": "rejected",
    "revoked": "revoked",
    "suspended": "revoked",
    "pending": "pending",
    "in_review": "pending",
}


def _retryable_status_codes() -> set[int]:
    status_codes = getattr(
        settings, "PORTAL_REQUEST_RETRY_STATUS_CODES", (429, 500, 502, 503, 504)
    )
    return {int(code) for code in status_codes}


def _should_retry_request_error(exc: requests.RequestException) -> bool:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True

    response = getattr(exc, "response", None)
    if response is None:
        return False

    return int(response.status_code) in _retryable_status_codes()


def is_zk_course_name(course_name):
    name_lc = (course_name or "").lower().strip()
    return bool(re.search(r"\bzk\b|\bzero[- ]?knowledge\b", name_lc))


def normalize_approval_status(raw_status):
    status_lc = (raw_status or "").lower().strip()
    if not status_lc:
        return "approved"
    return _APPROVAL_STATUS_ALIASES.get(status_lc, "approved")


def create_portal_onboarding_invite(participant):
    """
    Legacy API-based invite helper.

    Source of truth for onboarding is portal_backend DB-coupled cron.
    This helper remains for backward compatibility and tests.
    """
    course = getattr(participant, "course", None)
    course_name = getattr(course, "name", "")

    if is_zk_course_name(course_name):
        return None

    portal_onboarding_url = getattr(settings, "PORTAL_ONBOARDING_URL", "")
    internal_api_key = getattr(settings, "PORTAL_INTERNAL_API_KEY", "")
    timeout = getattr(settings, "PORTAL_REQUEST_TIMEOUT", 10)
    max_retries = max(0, int(getattr(settings, "PORTAL_REQUEST_MAX_RETRIES", 2)))
    backoff_seconds = float(
        getattr(settings, "PORTAL_REQUEST_RETRY_BACKOFF_SECONDS", 0.5)
    )

    if not portal_onboarding_url or not internal_api_key:
        logger.warning(
            "Portal onboarding invite skipped for participant %s because portal config is incomplete",
            getattr(participant, "id", None),
        )
        return None

    payload = {
        "email": participant.email,
        "full_name": participant.name,
        "cohort": participant.cohort,
        "course_name": course_name,
        "external_student_id": str(participant.id),
        "source_system": "backend_v2",
        "source_email": participant.email,
        "approval_status": normalize_approval_status(getattr(participant, "status", None)),
    }

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                portal_onboarding_url,
                json=payload,
                headers={"X-Internal-API-Key": internal_api_key},
                timeout=timeout,
            )
            response.raise_for_status()
            response_data = response.json()
            break
        except requests.RequestException as exc:
            is_last_attempt = attempt >= max_retries
            if is_last_attempt or not _should_retry_request_error(exc):
                logger.exception(
                    "Portal onboarding invite failed for participant %s after %s attempt(s)",
                    getattr(participant, "id", None),
                    attempt + 1,
                )
                return None

            sleep_seconds = backoff_seconds * (2**attempt)
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
        except ValueError:
            logger.exception(
                "Portal onboarding invite returned non-JSON response for participant %s",
                getattr(participant, "id", None),
            )
            return None

    activation_url = response_data.get("activation_url")
    if not activation_url:
        logger.warning(
            "Portal onboarding invite response missing activation_url for participant %s",
            getattr(participant, "id", None),
        )
    return activation_url
