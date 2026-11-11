# HMS workflow chatbot security notes

## Scope and access

The assistant is available only to signed-in `admin` and `receptionist` users. The server independently checks those roles on every `/api/chat` request; hiding the widget is not an authorization control. The route is POST-only, requires JSON, validates a non-empty message of at most 500 characters, and remains protected by Flask-WTF CSRF. Do not exempt this route from CSRF protection.

The assistant is workflow help only. It has no database connection, tool calls, or conversation history. It receives a static HMS knowledge base and one user message. The model instruction prohibits medical advice, patient-specific responses, data changes, SQL, and unrelated topics. Prompt instructions are not a security boundary by themselves; do not grant the model access to records or actions.

## Data handling

Never enter patient names, identifiers, contact details, appointment details, diagnoses, or other protected information. Email addresses and phone-number-like strings are detected, recorded only as a redacted audit action, rejected before the Groq request, and not sent to the model. This simple pattern check cannot identify every kind of sensitive information, so it does not make entering patient information safe.

For other valid requests, the submitted text is sent to Groq using the configured API key. Do not assume provider-side retention or processing terms; follow the organization's provider and privacy review before enabling the feature with real users. The application does not store chatbot prompts or responses. Existing `audit_logs` records the actor and a message-length-only action (or the redacted marker); application chatbot logs use a truncated HMAC of the user identifier and record action/duration without question text. Never add prompt or response contents to logs.

The browser renders both messages and responses using `textContent`, not HTML. Keep this behavior if changing the widget.

## Configuration and operation

Set `GROQ_API_KEY` in the deployment environment or a local, ignored `.env` file. Never commit the key. Without it, startup succeeds and the widget is hidden; `/api/chat` returns HTTP 503. The widget is enabled only when the key is configured at application startup.

The request timeout is 10 seconds, and the per-user limit is 10 requests per 60 seconds. That limiter is in process memory, so it is reset on restart and is not shared across workers or serverless instances. Use a shared limiter store (for example Redis) and review proxy-aware client identity before relying on this limit in a multi-instance deployment. Flask-Limiter's existing global limits are separate.

## Incident and change review

If the provider key may have been exposed, revoke it with the provider and replace the deployment secret. Review provider access and application logs without copying patient information into incident notes. Before changing the model, prompt, knowledge base, logging, or request handling, retest role enforcement, CSRF, sensitive-input rejection, safe rendering, rate limiting, and error responses using `TESTING_CHECKLIST.md`.
