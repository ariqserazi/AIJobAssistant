#!/usr/bin/env python3
"""
submission_verifier.py - Validates employer confirmation screens and error states.
"""

import time

CONFIRMATION_PHRASES = [
    "thank you for applying",
    "application submitted",
    "application was successfully submitted",
    "your application was successfully submitted",
    "successfully submitted",
    "we'll contact you if there are next steps",
    "we have received your application",
    "we've received your application",
    "thanks for applying",
    "your application has been received",
    "submission successful",
    "application received"
]

ERROR_PHRASES = [
    "please fix the following errors",
    "there was an error submitting your application",
    "there was an error submitting",
    "please check the required fields",
    "an error occurred"
]

class SubmissionVerifier:
    """Verifies whether an application was confirmed submitted or encountered errors."""

    @staticmethod
    def is_confirmed(page, max_wait_seconds: int = 15) -> bool:
        """Polls page for confirmation signals."""
        start = time.time()
        while time.time() - start < max_wait_seconds:
            # 1. URL check
            current_url = page.url.lower()
            if any(k in current_url for k in ["/submitted", "/thank-you", "/thank_you", "/success", "/complete"]):
                return True

            # 2. Text inspection
            try:
                body_text = page.evaluate("() => document.body ? document.body.innerText.toLowerCase() : ''")
                if any(phrase in body_text for phrase in CONFIRMATION_PHRASES):
                    return True
            except Exception:
                time.sleep(0.5)
                continue

            # 3. Success modal or checkmark icon
            try:
                if page.locator("[class*='confirmation'], [class*='successMessage'], [data-qa*='success']").is_visible():
                    return True
            except Exception:
                pass

            time.sleep(0.5)

        return False

    @staticmethod
    def get_visible_errors(page) -> list:
        """Returns any visible error message texts from the form."""
        errors = []
        error_elements = page.query_selector_all(
            "[class*='error-message'], [class*='errorMessage'], [role='alert'], [class*='fieldError']"
        )
        for el in error_elements:
            txt = el.inner_text().strip()
            if txt and txt not in errors:
                errors.append(txt)
        return errors
