# Playful Analyst Dashboard Redesign

## Objective

Redesign the existing bilingual Streamlit dashboard into a creative, lovable,
and approachable academic banking demo without changing its analytics,
MongoDB behavior, or administrator authorization. The interface and generated
AI brief must remain trustworthy, readable, responsive, and usable in English
and Myanmar.

## Visual Direction

Use a **Playful Analyst** personality on a warm off-white main canvas. Purple is
the primary action and feature color; apricot adds cheerful emphasis; mint
communicates healthy states; soft rose identifies failures. Rounded cards,
gentle shadows, and controlled accent shapes create warmth without obscuring
data.

Typography must provide a strong hierarchy and support both languages. Page and
section headings may be expressive, while metric labels and body text remain
compact and highly legible. Decorative emoji and the existing red-panda mascot
appear selectively in summaries, guidance, and empty states. They must not
appear in dense tables or critical alerts.

The dark sidebar remains for contrast but gains clearer grouping, more spacing,
and an obvious reset action. The language control stays labeled and visible in
the top area.

## Page Structure

Use the approved **story-first overview**:

1. Compact top bar with product identity, database status, and language switch.
2. Friendly hero card summarizing the current filtered results in plain language.
3. Five KPI cards with icons, concise labels, and contextual state colors.
4. Gateway health and gateway performance in one focused analysis area.
5. Success trend and failure analysis side by side on wide screens and stacked
   on narrow screens.
6. Purple AI Operations Brief card with explicit idle, loading, success, and
   error states. Its generated output follows the language currently selected
   by the user: English in English mode and Myanmar in Myanmar mode.
7. Recent transactions and interpretation guidance.
8. Visually separated administrator management panel.

Sidebar filters continue to update every relevant summary, KPI, chart, and
table immediately. Narrow layouts must stack cards and charts without horizontal
page scrolling.

## Implementation Boundaries

- `payment_dashboard/ui/style.py` owns design tokens and CSS for typography,
  layout, cards, buttons, alerts, tables, sidebar controls, and responsiveness.
- `payment_dashboard/ui/sections.py` owns the hero summary, KPI presentation,
  grouped analytical sections, AI brief presentation, and friendly empty states.
- `payment_dashboard/app.py` retains data loading, language state, filter state,
  section ordering, and database integration.
- `payment_dashboard/ai_brief.py` receives the selected language and builds an
  explicit language-specific prompt. The response is generated directly in the
  selected language rather than translated after generation.
- Existing calculation functions, MongoDB reads and mutations, AI requests,
  authentication, and soft-delete semantics remain unchanged.

Prefer semantic HTML wrappers with stable class names over fragile generated
Streamlit selectors where practical. Keep presentation logic separate from data
calculation so metrics remain independently testable.

## States and Error Handling

Database fallback notices must be readable, visually distinct, and actionable.
Loading states explain the current operation. Errors use plain language and
never reveal credentials or connection strings. Empty filtered results show the
mascot with a suggestion to reset or broaden filters. Critical alerts retain
strong contrast and must not rely on color alone.

If the AI provider returns an empty or unusable response, the interface shows a
localized error and retains the previous valid brief where possible. Generated
text must not mix languages unless a proper noun, gateway label, or technical
term has no natural Myanmar equivalent.

## Verification

Add regression tests for stable CSS hooks, bilingual UI labels, section output,
and database fallback presentation. Preserve existing analytics and integration
tests. Completion requires the full pytest suite, Ruff lint and formatting
checks, and browser verification at desktop and narrow viewport widths. Verify
English and Myanmar modes, filter updates, AI brief states, fallback messaging,
and administrator panel separation. AI tests must verify that the selected
language reaches the prompt, English mode requests English output, and Myanmar
mode requests Myanmar output.

## Out of Scope

This redesign does not change transaction schemas, generated gateway data,
analytics definitions, MongoDB collections, authentication rules, AI model
provider configuration, or deployment architecture.
