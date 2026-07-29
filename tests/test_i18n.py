"""Tests for the dashboard translation catalog."""

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
