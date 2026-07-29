# Friendly Language Toggle Design

## Goal

Make the existing English/Burmese language control immediately understandable,
visually distinct, and accessible without changing its language-selection or
filter-preservation behavior.

## Interaction

The control remains above the dashboard title and continues to use Streamlit's
native toggle. English is off/default and Burmese is on. Its stable
`language_toggle` key remains unchanged so existing session behavior and tests
continue to apply.

The control appears inside a compact visual card containing:

- The bilingual label `Language / ဘာသာစကား`
- A current-language status: `Current: English` in English mode and
  `လက်ရှိ: မြန်မာ` in Burmese mode
- The native switch with an accessible bilingual label

Changing language reruns the app immediately. Replay position, filters, and date
range remain selected across the rerun.

## Visual Design

English mode uses blue `#2563EB`; Burmese mode uses gold `#D4A017`. The active
mode color applies to the switch track and a subtle card accent. The card uses
the dashboard's existing surface, border, spacing, and rounded-corner language
so it feels like part of the application rather than a separate widget.

Text and controls must remain legible in both light and dark Streamlit themes.
The native input retains keyboard operation and receives a visible focus
outline. Styling uses local CSS only: no JavaScript, external fonts, images, or
UI libraries.

## Architecture

`payment_dashboard/app.py` remains responsible for rendering the control and
returning the selected language. Translation keys for the label and status live
in `payment_dashboard/i18n.py`. `payment_dashboard/ui/style.py` owns the
language-control CSS. Styling may use a mode-specific class or a small
state-derived CSS variable, but must not replace the native Streamlit input.

CSS selectors should be scoped to the language-control container so other
toggles, labels, or cards are unaffected. If Streamlit's generated DOM prevents
reliable container scoping, prefer a stable `data-testid`-based selector with a
narrow ancestor relationship and cover it with a browser smoke test.

## Testing

Automated tests verify:

- English remains the default
- The stable `language_toggle` widget key is preserved
- English and Burmese status text is correct
- Translation catalogs retain matching keys
- Existing dashboard filters remain selected after switching languages

A browser check verifies the card position, blue English state, gold Burmese
state, visible bilingual label, keyboard focus, and readable light/dark-theme
contrast.

## Non-Goals

This change does not redesign other controls, introduce language persistence,
add more languages, alter translations elsewhere, or change dashboard
analytics and data.
