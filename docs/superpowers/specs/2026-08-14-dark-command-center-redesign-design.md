# Dark Payment Command Center Redesign

**Date:** 2026-08-14  
**Status:** Approved design; implementation pending  
**Application:** Streamlit payment success-rate dashboard

## Objective

Replace the current light, long-form dashboard with a dark fintech command center
that helps payment operators scan system health, investigate gateways, evaluate
routing evidence, browse transactions, and perform administration without those
workflows competing on one page.

The redesign changes presentation and view composition only. It must preserve the
existing repository boundaries, metric definitions, routing calculations, data
lineage checks, audit behavior, and authentication controls.

## Approved Direction

The selected direction is a top-navigation control tower with:

- a near-black navy visual system;
- a persistent compact filter bar below the navigation;
- five focused views: Overview, Gateways, Routing Lab, Transactions, and Admin;
- compact, information-dense panels designed for daily operational use; and
- cyan, emerald, amber, and rose status colors with accessible contrast.

The rejected alternatives are a persistent left navigation and a guided
executive-story layout. The top-navigation design keeps more horizontal chart
space than the first and supports faster expert scanning than the second.

## Information Architecture

### Application shell

The shell contains, in order:

1. a product mark and dashboard name;
2. top-level view navigation;
3. live/demo source status and language control;
4. a compact analytical filter bar when the active view supports filters; and
5. the active view content.

Navigation is implemented with Streamlit-native controls and session state, not
URL routing. The selected view and filter values survive Streamlit reruns during
the session. Each view has one stable session-state key namespace to prevent
widget collisions.

The compact filter bar provides date range, gateway, transaction type, device,
and status controls plus a reset action. It appears on Overview, Gateways, and
Transactions. Routing Lab uses the complete eligible benchmark context and must
not silently inherit display filters. Admin operates on its own selectors and
must not inherit analytical filters.

### Overview

Overview answers: "Is payment processing healthy, and what needs attention?"

It contains:

- four primary KPI cards: success rate, transaction volume, average latency, and
  active alerts;
- success-rate trend;
- compact gateway-health summary;
- active alert evidence; and
- recent transactions.

Failed-transaction count remains available as supporting evidence rather than a
fifth equal-weight KPI. The view favors scanability and immediate triage.

### Gateways

Gateways answers: "Which gateway is driving the current result?"

It contains:

- success-rate and volume comparison;
- latency and operational-state evidence;
- normal and degraded-period evidence;
- failure analysis; and
- alert evidence with sample sizes, time boundaries, intervals, and status.

Charts and tables share gateway colors consistently within the view. Status
colors retain their semantic meaning and are not reused merely for decoration.

### Routing Lab

Routing Lab answers: "Does the simulated routing policy outperform the approved
baselines, and how reliable is that evidence?"

It contains:

- run identity, source, simulator version, and input digest;
- policy-comparison metrics;
- capacity, fee, infeasible, unassigned, and degraded-period evidence;
- paired confidence intervals and changes versus baselines;
- probability-sensitivity scenarios; and
- saved-run provenance.

The view continues to state that the benchmark is synthetic and non-causal. It
must not substitute display-filtered data for the approved complete benchmark
context.

### Transactions

Transactions answers: "Which records make up the current operational picture?"

It contains:

- a compact searchable and filterable transaction table;
- explicit pagination controls and page summary;
- status and fraud badges; and
- a selected-transaction detail panel when practical with Streamlit's table
  selection support.

The redesign does not expose fields that existing minimization rules prohibit.

### Admin

Admin contains authentication and transaction mutation tools only. Login,
session expiry, throttling, actor identity, validation, audit writes, and MongoDB
transaction behavior remain unchanged.

Add, edit, and delete operations remain separated. Destructive actions keep an
explicit confirmation step. Admin forms use view-scoped widget keys to avoid the
duplicate-key regressions previously seen in this project.

## Visual System

### Design tokens

The base palette is:

- canvas: `#07111F`;
- surface: `#0D1B2A`;
- raised surface: `#122235`;
- border: `#24364B`;
- primary text: `#F8FAFC`;
- secondary text: `#94A3B8`;
- analytical accent: `#22D3EE`;
- healthy/success: `#34D399`;
- degraded/warning: `#FBBF24`; and
- failed/critical: `#FB7185`.

The implementation may make small luminance adjustments where browser contrast
testing requires them, but the semantic mapping must remain stable.

Surfaces use thin borders and restrained shadows. Large purple gradients,
cream/white page backgrounds, playful decorative circles, and oversized hero
cards are removed. Border radii remain moderate so the interface feels modern
without resembling a consumer marketing page.

### Typography and density

Use Inter with Noto Sans Myanmar and Myanmar Text fallbacks. Headings are compact
and clear; labels use secondary text; values use tabular numerals where the
browser supports them. English and Myanmar content must remain readable without
clipping or forced single-line layout.

Cards use tighter vertical rhythm than the current UI. Important metric values
remain prominent, while captions, units, provenance, and uncertainty stay
visually subordinate but readable.

### Charts

A single chart-theme helper applies:

- transparent plot and paper backgrounds;
- primary and secondary text colors;
- muted grid lines;
- consistent margins, font sizes, hover styling, and legends; and
- the approved analytical and status palette.

Chart constructors continue to own their data transformations. The theme helper
only changes presentation. Charts must not encode success and failure by color
alone; labels, values, symbols, or status text provide redundant cues.

### Components

Reusable presentation units include:

- top navigation;
- source/status badge;
- compact filter bar;
- section header with optional supporting text;
- KPI card;
- panel container;
- semantic status badge;
- empty/loading/error state; and
- chart-theme helper.

These components accept already-computed display values or Streamlit callbacks.
They do not query MongoDB or recalculate analytics. This keeps presentation
independent from data access and metric definitions.

## Data and Rendering Flow

`render_app` remains responsible for page configuration, secrets, language,
repository creation, validated snapshot loading, and top-level exception
classification. It delegates shell and active-view composition to focused UI
functions.

The rendering flow is:

1. configure the page and apply the dark theme;
2. render navigation and determine the active view;
3. render or recover that view's filter state;
4. load the validated snapshot needed by the active view;
5. compute any existing report required by that view; and
6. render only the active view.

Routing reports should be built lazily when Routing Lab is active. MongoDB admin
resources should be created only when required by the live source or Admin view.
This view isolation reduces unnecessary work while preserving current behavior.

If a safe first implementation cannot defer a resource without changing an
existing contract, it may retain eager loading temporarily; the visible view
isolation and data correctness take priority over performance refactoring.

## Error, Empty, and Loading States

Errors are contained within the view that caused them:

- a routing-context failure disables Routing Lab evidence but does not hide the
  operational overview;
- a MongoDB diagnostic renders the existing classified message in the affected
  view;
- invalid or mixed simulation lineage remains a hard validation error and is
  never visually downgraded to a warning;
- an empty filtered result renders a reset-filter action;
- an empty underlying dataset renders source-aware preparation guidance; and
- an expired admin session returns the user to the Admin login state.

No error state silently substitutes demo data for live data. Status panels use
the same semantic colors as the rest of the interface and always include text.

## Responsive and Accessible Behavior

Desktop is the primary operating environment. On narrower widths:

- top navigation may wrap or become a horizontally scrollable native control;
- the filter bar wraps into additional rows without horizontal page overflow;
- KPI cards move from four columns to two, then one;
- multi-column chart layouts collapse to one column; and
- tables retain horizontal scrolling inside their own container.

All interactive elements keep visible keyboard focus. Text and essential UI
boundaries target WCAG AA contrast. Motion is limited to subtle hover and state
transitions and respects reduced-motion preferences. Icons are decorative unless
they carry an accessible label. English and Myanmar controls remain fully usable.

## Testing and Verification

Focused tests cover:

- stable view navigation and default Overview selection;
- session-state persistence for the active view and filter values;
- view-scoped widget keys;
- correct filter-bar visibility by view;
- isolation of Routing Lab and Admin from analytical display filters;
- dark-theme tokens and responsive CSS rules;
- centralized chart-theme application;
- loading, empty, classified-error, and authorization states;
- English and Myanmar labels; and
- preservation of existing admin, audit, lineage, alert, and routing behavior.

Completion requires:

- Ruff lint and format checks;
- strict mypy;
- the complete pytest suite;
- the existing dashboard smoke test; and
- visual browser checks at a desktop width and a narrow mobile width.

## Non-Goals

This redesign does not:

- change metric definitions, alert thresholds, routing objectives, or simulator
  assumptions;
- replace Streamlit with another frontend framework;
- add new database collections or external services;
- redesign authentication or authorization policy;
- introduce real-time push updates; or
- change the synthetic and non-causal interpretation of Routing Lab results.

## Acceptance Criteria

The redesign is accepted when:

1. the application uses the approved dark fintech visual system with no light
   page canvas;
2. users can move among the five approved views without losing session filters;
3. the compact filter bar is present only on its approved analytical views;
4. each existing workflow appears in the correct focused view;
5. charts, cards, tables, forms, alerts, and empty/error states remain readable in
   English and Myanmar at desktop and narrow widths;
6. analytical, lineage, security, and audit contracts remain unchanged; and
7. all automated and browser verification gates pass.
