"""Translation catalog and lookup helpers for the payment dashboard."""

from typing import Final, Literal

Language = Literal["en", "my"]

DEFAULT_LANGUAGE: Final[Language] = "en"
SUPPORTED_LANGUAGES: Final[tuple[Language, ...]] = ("en", "my")

TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "language.label": "Language",
        "language.english": "English",
        "language.burmese": "မြန်မာ",
        "language.control_label": "Language / ဘာသာစကား",
        "language.current": "Current: {name}",
        "dashboard.title": "Payment Success Monitor",
        "dashboard.description": (
            "Track transaction health, compare simulated gateways, and investigate "
            "payment failures from one local dashboard."
        ),
        "dashboard.disclaimer": (
            "Academic demo · Gateway labels are randomly simulated and do not "
            "represent real bank or gateway performance."
        ),
        "sidebar.controls": "Dashboard controls",
        "sidebar.replay_description": (
            "Replay transactions chronologically, then narrow the visible analysis."
        ),
        "sidebar.replayed_transactions": "Replayed transactions",
        "sidebar.replay_help": (
            "Controls how many chronological transactions have arrived."
        ),
        "sidebar.replay_count": "{replay_count:,} of {total_count:,} transactions",
        "sidebar.display_filters": "Display filters",
        "sidebar.gateway": "Gateway",
        "sidebar.all_gateways": "All gateways",
        "sidebar.transaction_type": "Transaction type",
        "sidebar.all_transaction_types": "All transaction types",
        "sidebar.device": "Device",
        "sidebar.all_devices": "All devices",
        "sidebar.status": "Status",
        "sidebar.all_statuses": "All statuses",
        "sidebar.date_range": "Date range",
        "sidebar.filter_note": (
            "Filters change the charts and KPIs. Alert calculations always use "
            "the unfiltered replay stream."
        ),
        "kpi.transactions": "Transactions",
        "kpi.success_rate": "Success rate",
        "kpi.failed": "Failed",
        "kpi.average_latency": "Average latency",
        "kpi.active_alerts": "Active alerts",
        "health.title": "Gateway health",
        "health.description": (
            "An alert triggers when a gateway's latest 50 transactions fall at "
            "least 10 percentage points below its full-data baseline."
        ),
        "health.no_alert": "No gateway currently exceeds the 10-point alert threshold.",
        "health.action_required": (
            "Action required: success-rate degradation detected for {names}."
        ),
        "health.insufficient_history": "Insufficient history",
        "health.alert": "Alert",
        "health.healthy": "Healthy",
        "health.baseline": "Baseline",
        "health.latest_50": "Latest 50",
        "health.drop": "Drop",
        "charts.gateway_performance": "Gateway performance",
        "charts.success_rate_by_gateway": "Success rate by gateway",
        "charts.transaction_volume_by_gateway": "Transaction volume by gateway",
        "charts.success_trend": "Success trend",
        "charts.failures_by": "Failures by {title}",
        "dimensions.gateway": "Gateway",
        "dimensions.timestamp": "Timestamp",
        "dimensions.fraud_flag": "Fraud flag",
        "dimensions.latency_band": "Latency band",
        "dimensions.device": "Device",
        "dimensions.transaction_type": "Transaction type",
        "sections.failure_analysis": "Failure analysis",
        "sections.failure_analysis_description": (
            "Break down failed transactions to identify recurring patterns."
        ),
        "table.gateway": "Gateway",
        "table.transaction_id": "Transaction ID",
        "table.timestamp": "Timestamp",
        "table.transaction_type": "Transaction Type",
        "table.transaction_status": "Transaction Status",
        "table.transaction_amount": "Transaction Amount",
        "table.device_used": "Device Used",
        "table.latency_ms": "Latency (ms)",
        "table.fraud_flag": "Fraud Flag",
        "table.recent_transactions": "Recent transactions",
        "guide.title": "How to interpret this dashboard",
        "guide.content": (
            "- **Baseline** is each gateway's success rate across the complete "
            "dataset.\n"
            "- **Latest 50** is the gateway's success rate in its newest 50 replayed "
            "transactions.\n"
            "- **Drop** is baseline minus latest-50 performance.\n"
            "- Gateway assignment is random, so comparisons are for demonstration only."
        ),
        "errors.no_matching_transactions": (
            "No transactions match the selected filters. Clear one or more "
            "sidebar filters to continue."
        ),
        "errors.load_data": "Unable to load dashboard data: {exc}",
        "errors.prepare_data_guidance": (
            "Generate the prepared dataset with "
            "`python -m payment_dashboard.prepare_data` and refresh this page."
        ),
        "test.fallback": "Fallback",
    },
    "my": {
        "language.label": "ဘာသာစကား",
        "language.english": "English",
        "language.burmese": "မြန်မာ",
        "language.control_label": "Language / ဘာသာစကား",
        "language.current": "လက်ရှိ: {name}",
        "dashboard.title": "ငွေပေးချေမှု အောင်မြင်နှုန်း စောင့်ကြည့်စနစ်",
        "dashboard.description": (
            "ငွေပေးချေမှု အခြေအနေကို စောင့်ကြည့်ပြီး gateway များကို နှိုင်းယှဉ်ကာ "
            "ပျက်ကွက်မှုများကို dashboard တစ်ခုတည်းမှ စစ်ဆေးပါ။"
        ),
        "dashboard.disclaimer": (
            "ပညာရေးသရုပ်ပြ · Gateway အမည်များကို ကျပန်းဖန်တီးထားပြီး အမှန်တကယ် "
            "ဘဏ် သို့မဟုတ် gateway စွမ်းဆောင်ရည်ကို ကိုယ်စားမပြုပါ။"
        ),
        "sidebar.controls": "Dashboard ထိန်းချုပ်မှုများ",
        "sidebar.replay_description": (
            "ငွေပေးချေမှုများကို အချိန်စဉ်အတိုင်း ပြန်ဖွင့်ပြီး မြင်ကွင်းခွဲခြမ်းမှုကို စစ်ထုတ်ပါ။"
        ),
        "sidebar.replayed_transactions": "ပြန်ဖွင့်ထားသော ငွေပေးချေမှုများ",
        "sidebar.replay_help": "အချိန်စဉ် ငွေပေးချေမှု မည်မျှ ရောက်ရှိပြီးပြီကို ထိန်းချုပ်သည်။",
        "sidebar.replay_count": "ငွေပေးချေမှု {total_count:,} ခုအနက် {replay_count:,} ခု",
        "sidebar.display_filters": "ပြသမှု စစ်ထုတ်မှုများ",
        "sidebar.gateway": "Gateway",
        "sidebar.all_gateways": "Gateway အားလုံး",
        "sidebar.transaction_type": "ငွေပေးချေမှု အမျိုးအစား",
        "sidebar.all_transaction_types": "ငွေပေးချေမှု အမျိုးအစားအားလုံး",
        "sidebar.device": "အသုံးပြုသည့် စက်",
        "sidebar.all_devices": "စက်အားလုံး",
        "sidebar.status": "အခြေအနေ",
        "sidebar.all_statuses": "အခြေအနေအားလုံး",
        "sidebar.date_range": "ရက်စွဲအပိုင်းအခြား",
        "sidebar.filter_note": (
            "စစ်ထုတ်မှုများသည် ဇယားများနှင့် KPI များကို ပြောင်းလဲသည်။ သတိပေးချက် "
            "တွက်ချက်မှုများသည် စစ်မထုတ်ထားသော replay stream ကို အမြဲအသုံးပြုသည်။"
        ),
        "kpi.transactions": "ငွေပေးချေမှုများ",
        "kpi.success_rate": "အောင်မြင်နှုန်း",
        "kpi.failed": "မအောင်မြင်သော",
        "kpi.average_latency": "ပျမ်းမျှ ကြာချိန်",
        "kpi.active_alerts": "လက်ရှိ သတိပေးချက်များ",
        "health.title": "Gateway အခြေအနေ",
        "health.description": (
            "Gateway တစ်ခု၏ နောက်ဆုံး ငွေပေးချေမှု ၅၀ ခုသည် dataset တစ်ခုလုံး၏ "
            "အခြေခံနှုန်းထက် အနည်းဆုံး ရာခိုင်နှုန်း ၁၀ မှတ် လျော့နည်းလျှင် သတိပေးချက် ပေါ်သည်။"
        ),
        "health.no_alert": "Gateway တစ်ခုမျှ ၁၀ မှတ် သတိပေးချက် သတ်မှတ်ချက်ကို မကျော်လွန်ပါ။",
        "health.action_required": "ဆောင်ရွက်ရန်လိုအပ်သည်- {names} တွင် အောင်မြင်နှုန်း လျော့ကျမှု တွေ့ရှိသည်။",
        "health.insufficient_history": "မှတ်တမ်းမလုံလောက်ပါ",
        "health.alert": "သတိပေးချက်",
        "health.healthy": "ကောင်းမွန်",
        "health.baseline": "အခြေခံနှုန်း",
        "health.latest_50": "နောက်ဆုံး ၅၀",
        "health.drop": "လျော့ကျမှု",
        "charts.gateway_performance": "Gateway စွမ်းဆောင်ရည်",
        "charts.success_rate_by_gateway": "ဂိတ်ဝေးအလိုက် အောင်မြင်နှုန်း",
        "charts.transaction_volume_by_gateway": "ဂိတ်ဝေးအလိုက် ငွေပေးချေမှုပမာဏ",
        "charts.success_trend": "အောင်မြင်နှုန်း လမ်းကြောင်း",
        "charts.failures_by": "{title} အလိုက် မအောင်မြင်မှုများ",
        "dimensions.gateway": "ဂိတ်ဝေး",
        "dimensions.timestamp": "အချိန်မှတ်တမ်း",
        "dimensions.fraud_flag": "လိမ်လည်မှု အမှတ်အသား",
        "dimensions.latency_band": "တုံ့ပြန်ချိန် အပိုင်းအခြား",
        "dimensions.device": "အသုံးပြုသည့် စက်",
        "dimensions.transaction_type": "ငွေပေးချေမှု အမျိုးအစား",
        "sections.failure_analysis": "မအောင်မြင်မှု ခွဲခြမ်းစိတ်ဖြာခြင်း",
        "sections.failure_analysis_description": (
            "ထပ်တလဲလဲ ဖြစ်ပေါ်နေသော ပုံစံများကို ရှာဖွေရန် မအောင်မြင်သော ငွေပေးချေမှုများကို ခွဲခြမ်းပါ။"
        ),
        "table.gateway": "ဂိတ်ဝေး",
        "table.transaction_id": "ငွေပေးချေမှု ID",
        "table.timestamp": "အချိန်မှတ်တမ်း",
        "table.transaction_type": "ငွေပေးချေမှု အမျိုးအစား",
        "table.transaction_status": "ငွေပေးချေမှု အခြေအနေ",
        "table.transaction_amount": "ငွေပမာဏ",
        "table.device_used": "အသုံးပြုသည့် စက်",
        "table.latency_ms": "တုံ့ပြန်ချိန် (ms)",
        "table.fraud_flag": "လိမ်လည်မှု အမှတ်အသား",
        "table.recent_transactions": "နောက်ဆုံး ငွေပေးချေမှုများ",
        "guide.title": "ဤ dashboard ကို နားလည်ရန်",
        "guide.content": (
            "- **အခြေခံနှုန်း** သည် dataset တစ်ခုလုံးရှိ gateway တစ်ခုစီ၏ အောင်မြင်နှုန်းဖြစ်သည်။\n"
            "- **နောက်ဆုံး ၅၀** သည် replay လုပ်ထားသော နောက်ဆုံး ငွေပေးချေမှု ၅၀ ခု၏ "
            "အောင်မြင်နှုန်းဖြစ်သည်။\n"
            "- **လျော့ကျမှု** သည် အခြေခံနှုန်းမှ နောက်ဆုံး ၅၀ ၏ စွမ်းဆောင်ရည်ကို နုတ်ထားခြင်းဖြစ်သည်။\n"
            "- Gateway ခန့်အပ်မှုသည် ကျပန်းဖြစ်သောကြောင့် နှိုင်းယှဉ်မှုများသည် သရုပ်ပြရန်သာဖြစ်သည်။"
        ),
        "errors.no_matching_transactions": (
            "ရွေးချယ်ထားသော စစ်ထုတ်မှုများနှင့် ကိုက်ညီသော ငွေပေးချေမှုမရှိပါ။ ဆက်လက်ရန် "
            "ဘေးဘားစစ်ထုတ်မှုတစ်ခု သို့မဟုတ် တစ်ခုထက်ပို၍ ရှင်းလင်းပါ။"
        ),
        "errors.load_data": "Dashboard data ကို မဖွင့်နိုင်ပါ: {exc}",
        "errors.prepare_data_guidance": (
            "`python -m payment_dashboard.prepare_data` ဖြင့် ပြင်ဆင်ထားသော dataset ကို "
            "ဖန်တီးပြီး ဤစာမျက်နှာကို ပြန်လည်ဖွင့်ပါ။"
        ),
        "test.fallback": "",
    },
}


def translate(key: str, language: str = DEFAULT_LANGUAGE, **values: object) -> str:
    """Return a localized string, falling back to English for missing values."""
    english = TRANSLATIONS["en"].get(key, key)
    localized = TRANSLATIONS.get(language, TRANSLATIONS["en"]).get(key, english)
    template = localized or english
    return template.format(**values)
