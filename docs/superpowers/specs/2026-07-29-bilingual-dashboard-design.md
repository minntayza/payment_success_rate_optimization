# Bilingual Dashboard Design

## Goal

Make the local Streamlit dashboard usable in English and Burmese without
changing the transaction dataset, analytical calculations, or simulated gateway
behavior. English is the default language. A language toggle at the top of the
main page switches all presentation text immediately.

## Scope

The selected language applies to:

- Page title, description, and academic-demo disclaimer
- Sidebar headings, control labels, placeholders, help text, and filter guidance
- KPI labels, section headings, captions, alerts, and empty states
- Chart titles and visible axis labels
- Display-only table headings and gateway-health status values
- Recent-transactions heading and dashboard interpretation guide

Raw dataset values remain unchanged. Gateway labels, transaction types, devices,
transaction statuses, internal DataFrame columns, and metric keys continue to
use their existing English values. This keeps filters and analytical functions
independent of the selected display language.

## Architecture

Add `payment_dashboard/i18n.py` as the single localization boundary. It will
define:

- Supported language identifiers for English and Burmese
- A nested or flat translation dictionary keyed by stable semantic identifiers,
  such as `dashboard.title` and `sidebar.date_range`
- A small translation helper that accepts a key and language identifier
- English fallback behavior for a missing Burmese value

English and Burmese dictionaries must have matching keys. UI modules request
strings by key rather than containing translated literals.

The selected language is created by a compact `English / မြန်မာ` toggle rendered
before the dashboard title. Its default is English. The language identifier is
then passed explicitly to `_render_sidebar` and each section renderer. Chart
builders receive either the language identifier or the translated labels they
need; they do not translate dataset columns or category values.

## User Experience

Changing the toggle causes Streamlit to rerun and redraw the entire interface in
the chosen language. No submit button or page reload is required. The toggle
remains in the same top-of-page location in both languages.

Burmese text uses the existing page styling with a system font stack that
includes Burmese-capable fonts. No web font or network dependency is added.
Numbers, percentages, dates, gateway names, and raw category values retain their
current formatting.

## Error Handling

Unknown language identifiers fall back to English. Missing translation keys
also return the English value when one exists, preventing a partially broken
dashboard. Development tests enforce key parity so missing Burmese translations
are normally caught before runtime. Data-loading and validation errors keep
their current control flow but their user-facing wrapper messages are localized.

## Testing

Unit tests will verify:

- English is the default language
- English and Burmese dictionaries contain the same keys
- Representative keys return the correct English and Burmese strings
- Unknown languages and missing Burmese values fall back to English
- Chart and section renderers use localized display labels
- Raw filter options and dataset values are not translated

The existing Streamlit smoke test will continue to confirm that the complete app
starts without exception. A bilingual UI test will select Burmese and assert
that representative Burmese headings appear while neutral dataset values remain
available.

## Non-Goals

This change does not translate uploaded CSV content, alter the schema, localize
numeric/date formats, add automatic browser-language detection, or introduce a
third-party internationalization framework. It does not persist the selected
language across new browser sessions.
