"""Tests for the dashboard translation catalog."""

import pytest

from payment_dashboard.i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    TRANSLATIONS,
    translate,
)


def test_translation_catalogs_have_matching_keys() -> None:
    assert set(TRANSLATIONS["en"]) == set(TRANSLATIONS["my"])


def test_english_is_default_and_burmese_is_supported() -> None:
    assert DEFAULT_LANGUAGE == "en"
    assert SUPPORTED_LANGUAGES == ("en", "my")
    assert translate("dashboard.title") == "Payment Success Monitor"
    assert translate("dashboard.title", "my") == "ငွေပေးချေမှု အောင်မြင်နှုန်း စောင့်ကြည့်စနစ်"


def test_unknown_language_and_blank_translation_fall_back_to_english() -> None:
    assert translate("dashboard.title", "fr") == "Payment Success Monitor"
    assert translate("test.fallback", "my") == "Fallback"


def test_load_error_and_recovery_guidance_are_translated() -> None:
    assert (
        translate("errors.load_data", exc="missing gateway data")
        == "Unable to load dashboard data: missing gateway data"
    )
    assert translate("errors.load_data", "my", exc="gateway data မရှိပါ") == (
        "Dashboard data ကို မဖွင့်နိုင်ပါ: gateway data မရှိပါ"
    )
    assert translate("errors.prepare_data_guidance", "my") == (
        "`python -m payment_dashboard.prepare_data` ဖြင့် ပြင်ဆင်ထားသော dataset ကို "
        "ဖန်တီးပြီး ဤစာမျက်နှာကို ပြန်လည်ဖွင့်ပါ။"
    )


def test_burmese_gateway_success_chart_label_matches_the_ui_contract() -> None:
    assert translate("charts.success_rate_by_gateway", "my") == (
        "ဂိတ်ဝေးအလိုက် အောင်မြင်နှုန်း"
    )


def test_gateway_table_header_is_translated() -> None:
    assert translate("table.gateway") == "Gateway"
    assert translate("table.gateway", "my") == "ဂိတ်ဝေး"


@pytest.mark.parametrize(
    ("key", "english", "burmese"),
    [
        ("table.transaction_id", "Transaction ID", "ငွေပေးချေမှု ID"),
        ("table.timestamp", "Timestamp", "အချိန်မှတ်တမ်း"),
        (
            "table.transaction_type",
            "Transaction Type",
            "ငွေပေးချေမှု အမျိုးအစား",
        ),
        (
            "table.transaction_status",
            "Transaction Status",
            "ငွေပေးချေမှု အခြေအနေ",
        ),
        ("table.transaction_amount", "Transaction Amount", "ငွေပမာဏ"),
        ("table.device_used", "Device Used", "အသုံးပြုသည့် စက်"),
        ("table.latency_ms", "Latency (ms)", "တုံ့ပြန်ချိန် (ms)"),
        ("table.fraud_flag", "Fraud Flag", "လိမ်လည်မှု အမှတ်အသား"),
    ],
)
def test_recent_transaction_table_headers_are_translated(
    key: str,
    english: str,
    burmese: str,
) -> None:
    assert translate(key) == english
    assert translate(key, "my") == burmese
