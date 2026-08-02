"""Tests for aggregate-only structured AI briefs and local fallback."""

from __future__ import annotations

import json
from http.client import IncompleteRead, InvalidURL
from io import BytesIO
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pandas as pd
import pytest

import payment_dashboard.ai_brief as ai_brief
from payment_dashboard.dashboard_repository import (
    DashboardFilters,
    PageRequest,
    PandasDashboardRepository,
)


@pytest.fixture
def facts() -> dict[str, object]:
    return {
        "transaction_count": 4,
        "success_rate": 0.5,
        "failed_count": 2,
        "average_latency_ms": 22.5,
        "p95_latency_ms": 30.0,
        "gateways": [
            {"name": "Gateway A", "transactions": 2, "success_rate": 1.0},
            {"name": "Gateway B", "transactions": 2, "success_rate": 0.0},
        ],
        "active_alerts": ["Gateway B"],
        "top_failure_latency_band": {"name": "High", "failures": 2},
    }


def _provider_response(content: dict[str, object]) -> BytesIO:
    body = {
        "content": [
            {
                "type": "text",
                "text": json.dumps(content, ensure_ascii=False),
            }
        ]
    }
    return BytesIO(json.dumps(body, ensure_ascii=False).encode())


def _valid_content() -> dict[str, object]:
    return {
        "summary": "Four aggregate transactions have a 50% success rate.",
        "risks": ["Gateway B has an active simulated alert."],
        "actions": ["Review simulated routing from Gateway B to Gateway A."],
        "evidence": [
            "Overall: 4 transactions; 50.0% success rate; 2 failed; "
            "22.5 ms average latency; 30.0 ms p95 latency."
        ],
    }


def _http_error(code: int, body=None) -> HTTPError:
    return HTTPError("https://provider/v1/messages", code, "error", {}, body)


class TrackedBody(BytesIO):
    def __init__(self) -> None:
        super().__init__(b"provider error")
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1
        super().close()


class IncompleteResponse(BytesIO):
    def read(self, *_args, **_kwargs):
        raise IncompleteRead(b"partial", 10)


def test_build_brief_facts_uses_snapshot_aggregates_only(
    sample_transactions: pd.DataFrame,
) -> None:
    frame = sample_transactions.assign(
        **{
            "Timestamp": pd.to_datetime(sample_transactions["Timestamp"]),
            "Bank Gateway": ["Gateway A", "Gateway B", "Gateway A", "Gateway B"],
            "Simulation Version": ["controlled-v1"] * 4,
        }
    )
    snapshot = PandasDashboardRepository(frame).fetch(
        DashboardFilters(), PageRequest(number=1, size=1)
    )

    result = ai_brief.build_brief_facts(snapshot)
    serialized = json.dumps(result)

    assert result["transaction_count"] == 4
    assert result["gateways"]
    assert "TX1" not in serialized
    assert "Transaction ID" not in serialized
    assert "Transaction Amount" not in serialized


def test_prompt_requests_json_only_with_four_required_fields(
    facts: dict[str, object],
) -> None:
    prompt = ai_brief.build_brief_prompt(facts)

    assert "Return only one valid JSON object" in prompt
    assert '"summary"' in prompt
    assert '"risks"' in prompt
    assert '"actions"' in prompt
    assert '"evidence"' in prompt
    assert json.dumps(facts, sort_keys=True) in prompt
    assert "Use only the supplied aggregate facts" in prompt
    assert (
        "Overall: 4 transactions; 50.0% success rate; 2 failed; "
        "22.5 ms average latency; 30.0 ms p95 latency."
    ) in prompt


def test_myanmar_prompt_is_localized_and_preserves_unicode(
    facts: dict[str, object],
) -> None:
    prompt = ai_brief.build_brief_prompt({**facts, "note": "မြန်မာ"}, language="my")

    assert "မြန်မာဘာသာဖြင့်သာ" in prompt
    assert "JSON object" in prompt
    assert "\\u1019" not in prompt


def test_generate_brief_returns_validated_structure(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    monkeypatch.setattr(
        ai_brief.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _provider_response(_valid_content()),
    )

    result = ai_brief.generate_brief_result(
        facts,
        base_url="https://provider",
        api_key="x",
    )

    assert result.origin == "ai"
    assert result.content.summary
    assert result.content.actions
    assert isinstance(result.content, ai_brief.BriefContent)


def test_request_contains_only_prompted_aggregate_facts(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    captured: dict[str, object] = {}

    def provider(request, timeout, **_kwargs):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return _provider_response(_valid_content())

    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    ai_brief.generate_brief_result(
        facts,
        base_url="https://provider/",
        api_key="secret",
        model="test-model",
        timeout=4.5,
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert captured["url"] == "https://provider/v1/messages"
    assert payload["model"] == "test-model"
    assert payload["max_tokens"] == 700
    assert payload["messages"] == [
        {"role": "user", "content": ai_brief.build_brief_prompt(facts)}
    ]
    assert captured["timeout"] == 4.5
    assert "secret" not in json.dumps(payload)


def test_api_key_is_not_forwarded_by_redirect_handler(
    facts: dict[str, object],
) -> None:
    request = ai_brief._provider_request(
        "https://provider.example", "secret", "model", facts, "en", 128
    )
    redirected = ai_brief.urllib.request.HTTPRedirectHandler().redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://attacker.example/collect",
    )

    assert request.get_header("X-api-key") == "secret"
    assert redirected is not None
    assert redirected.get_header("X-api-key") is None


def test_request_forwards_a_validated_smaller_token_cap(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    """Opt-in contracts can bound provider output below the production default."""
    captured: dict[str, object] = {}

    def provider(request, **_kwargs):
        captured.update(json.loads(request.data))
        return _provider_response(_valid_content())

    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        base_url="https://provider",
        api_key="secret",
        max_tokens=128,
    )

    assert result.origin == "ai"
    assert captured["max_tokens"] == 128


@pytest.mark.parametrize("max_tokens", [0, 701, True, 1.5])
def test_invalid_token_cap_returns_local_without_provider_call(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
    max_tokens: object,
) -> None:
    """Non-integer, boolean, and out-of-range provider caps are refused."""
    provider = Mock(side_effect=AssertionError("invalid cap reached provider"))
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        base_url="https://provider",
        api_key="secret",
        max_tokens=max_tokens,  # type: ignore[arg-type]
    )

    assert result.origin == "local"


def test_invalid_base_url_returns_local_fallback(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    provider = Mock(side_effect=AssertionError("invalid URL reached transport"))
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        base_url="://invalid",
        api_key="x",
    )

    assert result.origin == "local"
    provider.assert_not_called()


def test_invalid_url_from_transport_returns_local_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    provider = Mock(side_effect=InvalidURL("nonnumeric port: 'bad'"))
    sleep = Mock()
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        base_url="http://example.com:bad",
        api_key="x",
        attempts=2,
        sleep=sleep,
    )

    assert provider.call_count == 1
    sleep.assert_not_called()
    assert result.origin == "local"


def test_retry_exhaustion_returns_local_brief(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    provider = Mock(side_effect=URLError("offline"))
    sleep = Mock()
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        base_url="https://provider",
        api_key="x",
        attempts=2,
        sleep=sleep,
    )

    assert provider.call_count == 2
    sleep.assert_called_once()
    assert result.origin == "local"
    assert result.content == ai_brief.build_local_brief(facts, "en")


def test_attempts_above_two_are_capped_at_two_provider_calls(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    provider = Mock(side_effect=URLError("offline"))
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        base_url="https://provider",
        api_key="x",
        attempts=4,
        sleep=lambda _delay: None,
    )

    assert provider.call_count == 2
    assert result.origin == "local"


def test_attempts_one_disables_retry(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    provider = Mock(side_effect=URLError("offline"))
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        base_url="https://provider",
        api_key="x",
        attempts=1,
    )

    assert provider.call_count == 1
    assert result.origin == "local"


def test_incomplete_response_read_retries_once(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    provider = Mock(
        side_effect=[IncompleteResponse(), _provider_response(_valid_content())]
    )
    sleep = Mock()
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        base_url="https://provider",
        api_key="x",
        attempts=2,
        sleep=sleep,
    )

    assert provider.call_count == 2
    sleep.assert_called_once()
    assert result.origin == "ai"


@pytest.mark.parametrize(
    "error",
    [TimeoutError("slow"), _http_error(429), _http_error(503)],
)
def test_transient_errors_retry_once_then_use_local_fallback(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
    error: Exception,
) -> None:
    provider = Mock(side_effect=error)
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        base_url="https://provider",
        api_key="x",
        attempts=2,
        sleep=lambda _delay: None,
    )

    assert provider.call_count == 2
    assert result.origin == "local"


def test_auth_error_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    provider = Mock(side_effect=_http_error(401))
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        base_url="https://provider",
        api_key="x",
        attempts=2,
        sleep=lambda _delay: None,
    )

    assert provider.call_count == 1
    assert result.origin == "local"


@pytest.mark.parametrize(("status", "expected_calls"), [(401, 1), (503, 2)])
def test_http_error_response_bodies_are_closed(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
    status: int,
    expected_calls: int,
) -> None:
    bodies = [TrackedBody() for _ in range(expected_calls)]
    errors = [_http_error(status, body) for body in bodies]
    provider = Mock(side_effect=errors)
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        base_url="https://provider",
        api_key="x",
        attempts=2,
        sleep=lambda _delay: None,
    )

    assert result.origin == "local"
    assert provider.call_count == expected_calls
    assert [body.close_count for body in bodies] == [1] * expected_calls


@pytest.mark.parametrize(
    "provider_content",
    [
        {"summary": "Missing three fields"},
        {**_valid_content(), "summary": " "},
        {**_valid_content(), "actions": []},
        {**_valid_content(), "summary": "x" * 2_001},
    ],
)
def test_invalid_structured_content_uses_local_fallback_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
    provider_content: dict[str, object],
) -> None:
    provider = Mock(return_value=_provider_response(provider_content))
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        base_url="https://provider",
        api_key="x",
        attempts=2,
    )

    assert provider.call_count == 1
    assert result.origin == "local"


def test_evidence_that_contradicts_aggregate_values_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    contradictory = {
        **_valid_content(),
        "evidence": ["4 transactions had a 99% success rate."],
    }
    provider = Mock(return_value=_provider_response(contradictory))
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        base_url="https://provider",
        api_key="x",
    )

    assert provider.call_count == 1
    assert result.origin == "local"


def test_percentage_evidence_cannot_reuse_an_unrelated_aggregate_number(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    hundred_transactions = {**facts, "transaction_count": 100}
    contradictory = {
        **_valid_content(),
        "evidence": ["100 transactions had a 100% success rate."],
    }
    provider = Mock(return_value=_provider_response(contradictory))
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        hundred_transactions,
        base_url="https://provider",
        api_key="x",
    )

    assert result.origin == "local"


def test_evidence_rejects_value_borrowed_from_another_gateway(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    unequal_gateways = {
        **facts,
        "gateways": [
            {"name": "Gateway A", "transactions": 3, "success_rate": 1.0},
            {"name": "Gateway B", "transactions": 1, "success_rate": 0.0},
        ],
    }
    mismatched = {
        **_valid_content(),
        "evidence": ["Gateway A: 1 transactions; 100.0% success rate."],
    }
    provider = Mock(return_value=_provider_response(mismatched))
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        unequal_gateways,
        base_url="https://provider",
        api_key="x",
    )

    assert result.origin == "local"


def test_evidence_rejects_unsupported_text_without_numbers(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    unsupported = {**_valid_content(), "evidence": ["Everything looks fine."]}
    provider = Mock(return_value=_provider_response(unsupported))
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        base_url="https://provider",
        api_key="x",
    )

    assert result.origin == "local"


def test_valid_myanmar_evidence_reference_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    myanmar = {
        "summary": "စုစုပေါင်းအခြေအနေကို စစ်ဆေးပြီးဖြစ်သည်။",
        "risks": ["Gateway B ကို စောင့်ကြည့်ရန် လိုသည်။"],
        "actions": ["သရုပ်ပြ routing ကို ပြန်လည်စစ်ဆေးပါ။"],
        "evidence": [
            "စုစုပေါင်း: ငွေပေးချေမှု 4 ခု; အောင်မြင်နှုန်း 50.0%; "
            "မအောင်မြင်မှု 2 ခု; ပျမ်းမျှတုံ့ပြန်ချိန် 22.5 ms; "
            "p95 တုံ့ပြန်ချိန် 30.0 ms။"
        ],
    }
    provider = Mock(return_value=_provider_response(myanmar))
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        language="my",
        base_url="https://provider",
        api_key="x",
    )

    assert result.origin == "ai"


def test_native_myanmar_numerals_cannot_bypass_evidence_whitelist(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    mismatched = {
        "summary": "စုစုပေါင်းအခြေအနေကို စစ်ဆေးပြီးဖြစ်သည်။",
        "risks": ["Gateway A အချက်အလက် မကိုက်ညီပါ။"],
        "actions": ["သရုပ်ပြ routing ကို ပြန်လည်စစ်ဆေးပါ။"],
        "evidence": ["Gateway A: ငွေပေးချေမှု ၂ ခု; အောင်မြင်နှုန်း ၀.၀%။"],
    }
    provider = Mock(return_value=_provider_response(mismatched))
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        language="my",
        base_url="https://provider",
        api_key="x",
    )

    assert result.origin == "local"


def test_non_retryable_transport_failure_returns_local_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    facts: dict[str, object],
) -> None:
    provider = Mock(side_effect=OSError("connection closed"))
    monkeypatch.setattr(ai_brief.urllib.request, "urlopen", provider)

    result = ai_brief.generate_brief_result(
        facts,
        base_url="https://provider",
        api_key="x",
        attempts=2,
    )

    assert provider.call_count == 1
    assert result.origin == "local"


def test_missing_configuration_uses_local_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    facts: dict[str, object],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = ai_brief.generate_brief_result(facts)

    assert result.origin == "local"


def test_local_brief_is_deterministic_and_bilingual(facts: dict[str, object]) -> None:
    english = ai_brief.build_local_brief(facts, "en")
    myanmar = ai_brief.build_local_brief(facts, "my")

    assert english == ai_brief.build_local_brief(facts, "en")
    assert myanmar == ai_brief.build_local_brief(facts, "my")
    assert english.summary != myanmar.summary
    assert "50.0%" in english.summary
    assert "50.0%" in myanmar.summary
    assert any("Gateway B" in risk for risk in myanmar.risks)
