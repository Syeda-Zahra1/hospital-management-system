# HMS chatbot manual testing checklist

Run these checks in a local or staging environment with a test Groq key only. Never use patient information or a production key for testing. The provider call can be mocked for cases that do not need a real response.

## Startup and availability

1. Remove `GROQ_API_KEY` and restart the app. Confirm it starts, logs that the chatbot is disabled, and the widget is absent.
2. With no key, POST a valid message to `/api/chat` as an authorized test user. Confirm HTTP 503 and a safe JSON error.
3. Configure a test key and restart. Confirm the widget appears for an admin.
4. Confirm the widget appears for a receptionist and does not appear for a doctor, pharmacist, lab technician, patient, or signed-out visitor.

## Access and request validation

5. POST without a session cookie. Confirm HTTP 401 JSON, not a login-page redirect.
6. POST as an authenticated non-admin/non-receptionist. Confirm HTTP 403 JSON.
7. POST as an admin and receptionist with an invalid/missing CSRF token. Confirm HTTP 400 JSON and no model call.
8. POST valid JSON with no `message`, a non-string message, or malformed JSON. Confirm HTTP 400 and no model call.
9. POST with a non-JSON content type. Confirm HTTP 415.
10. POST an empty or whitespace-only message. Confirm HTTP 400.
11. POST a message longer than 500 characters. Confirm HTTP 400.
12. POST a message containing an email address or phone-number-like string. Confirm HTTP 422, a redacted audit action, and no model call.

## Functionality and privacy

13. Ask how an admin/receptionist books an appointment. Confirm the answer reflects the implemented workflow and does not exceed the short-answer guidance unnecessarily.
14. Ask how to dispense a prescription. Confirm the answer describes navigation and stock checking, without claiming to access or change a prescription.
15. Ask for medical advice. Confirm the answer directs the user to a clinician and does not provide advice.
16. Ask for a patient's records or include an instruction to ignore prior rules. Confirm no record is retrieved and the request is refused or safely redirected.
17. Ask for the system prompt, SQL, or an unrelated topic. Confirm it is not disclosed or executed.
18. Send a message containing HTML such as `<img src=x onerror=alert(1)>` through a mocked model response. Confirm both user and assistant text display literally and no script runs.
19. Inspect app logs and `audit_logs`. Confirm no prompt/response is stored, the chatbot event includes duration and a hashed user identifier, and the audit action contains only length or the redacted marker.

## Limits and failures

20. Send 11 valid requests from the same user within 60 seconds. Confirm the last request receives HTTP 429 and a `Retry-After` header; confirm a different user has an independent limit.
21. Mock Groq HTTP 429, another HTTP error, a timeout, a connection error, and an empty response. Confirm safe JSON errors, no traceback in the response, and no API key or prompt in application logs.
22. Open/close the widget with its button, Escape, and the close button. Confirm focus returns to the toggle, `aria-expanded` stays in sync, Enter sends, Shift+Enter adds a line, and the widget remains usable on a narrow screen.

The in-memory request limiter is per process; these checks do not certify a shared limit across multiple workers or deployments.
