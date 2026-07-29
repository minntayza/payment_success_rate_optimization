# Local AI Operations Brief Design

## Goal

Add a button-triggered English operations summary to the local Streamlit
dashboard. The feature uses Ollama on the same Mac and never requires an API
key, cloud service, or transmission of raw transaction rows.

## User Experience

An **AI Operations Brief** section appears after the KPI cards. Clicking
**Generate AI Brief** displays a spinner and then an English brief containing:

- Executive summary
- Best- and worst-performing simulated gateways
- Important success-rate, alert, failure, or latency observation
- Largest failure segment
- Suggested simulated routing action
- Academic-demo disclaimer

The brief reflects the current replay position and display filters. It remains
visible across unrelated Streamlit reruns but is invalidated when the underlying
filtered view changes. Generating a new brief always requires a button click.

## Local Model Connection

The app sends one non-streaming HTTP request to Ollama's local generate endpoint.
Defaults are:

```text
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:1b
```

The 1B model is selected for responsiveness on the detected 8 GB Apple M2 Mac.
Both settings can be overridden through environment variables.

The HTTP client uses Python's standard library, avoiding another runtime
dependency. It applies a finite timeout and validates the JSON response before
returning generated text.

## Components and Data Flow

`payment_dashboard/ai_brief.py` owns four boundaries:

1. Convert a filtered DataFrame and alert snapshot into a JSON-serializable
   aggregate facts object.
2. Build a strict English prompt from those facts.
3. Call the configured Ollama endpoint.
4. Validate and return the generated response.

The facts include transaction count, overall success rate, average latency,
gateway summaries, active alerts, and failure breakdowns by transaction type
and device. Raw transaction IDs, timestamps, individual amounts, and customer
or row-level records are never included.

`payment_dashboard/ui/sections.py` renders the section. `app.py` passes the
current dashboard state and stores the response plus a deterministic facts
fingerprint in `st.session_state`.

## Prompt Safety and Accuracy

The prompt instructs the model to:

- Use only supplied facts and never invent metrics
- State when evidence is insufficient
- Treat gateway assignments as simulated
- Avoid claims about real banks, customers, or production routing
- Produce concise Markdown with the required six parts

The deterministic facts remain available in an expandable evidence panel so a
reviewer can compare the generated prose with its source metrics.

## Error Handling

Connection refusal or timeout displays guidance to start Ollama and pull the
configured model. HTTP failures, invalid JSON, missing response text, and empty
responses produce concise user-facing errors without terminating the dashboard.
No fallback cloud request is attempted.

## Testing

Unit tests use real DataFrames to verify aggregation, raw-row exclusion, prompt
constraints, deterministic fingerprinting, and empty-data behavior. HTTP tests
mock only the local network boundary and cover success, connection refusal,
timeout, HTTP errors, malformed JSON, and blank responses.

Streamlit integration tests verify button-triggered generation, session-state
retention, invalidation when filters change, evidence display, and graceful
Ollama failure. Full lint, test, clean-checkout, and local browser checks remain
required.

## Non-Goals

This version does not train a model, translate AI output into Burmese, stream
tokens, send raw rows, call cloud APIs, automatically regenerate, or provide
real financial advice.
