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
