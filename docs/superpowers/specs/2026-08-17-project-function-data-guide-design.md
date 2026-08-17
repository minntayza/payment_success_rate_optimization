# Project Function and Dataset Guide Design

**Date:** 2026-08-17  
**Status:** Approved design; guide pending

## Objective

Create one end-to-end Markdown guide that explains this repository as a data
analysis and management project. It must help non-technical readers understand
what the system does and help new developers or project judges trace how data is
validated, transformed, stored, analyzed, presented, and governed.

The guide will be saved as `docs/project-function-and-data-guide.md`.

## Audience

The document serves two audiences through progressive detail:

1. non-technical users who need to understand the dashboard views, metrics,
   alerts, and limitations; and
2. new developers and project judges who need an accurate architectural,
   functional, and data-management explanation.

Plain-language sections appear first. Technical modules, function names, and
contracts appear afterward so readers can stop at the depth they need.

## Project Framing

The guide must describe the system as a data analysis and management project,
not only a Streamlit dashboard. Its core story is:

- manage a traceable payment transaction dataset;
- validate and prepare it through deterministic transformations;
- provide bounded demo and live MongoDB access paths;
- calculate operational metrics and statistically gated alerts;
- simulate and evaluate routing policies without presenting synthetic results as
  causal production evidence;
- persist reproducible routing-run artifacts;
- protect sensitive fields and preserve mutation audit history; and
- present the governed outputs through focused operational views.

## Document Structure

### 1. Project overview

Explain the problem, intended users, major capabilities, and the distinction
between descriptive payment analytics, data management, and synthetic routing
evaluation.

### 2. Plain-language dashboard tour

Explain Overview, Gateways, Routing Lab, Transactions, and Admin. Describe what
each view answers, how filters behave, and which evidence users should inspect.

### 3. Dataset lifecycle

Trace the full flow:

1. source dataset and manifest;
2. raw schema validation;
3. deterministic gateway simulation and metadata;
4. prepared-file validation;
5. demo repository or MongoDB import;
6. repository snapshot and filters;
7. analytics, alerts, AI brief, and routing benchmark;
8. dashboard presentation; and
9. governed admin mutations and audit records.

Use a compact Mermaid flowchart because the sequence and branching are easier to
understand visually than as prose alone.

### 4. Dataset fields and management controls

Group fields by source transaction data, simulated gateway fields, metadata, and
routing-run artifacts. Explain provenance, checksums, schema validation, version
lineage, sensitive-field removal, MongoDB normalization, soft deletion, audit
records, and minimized persisted routing contexts.

Do not reproduce real account values, credentials, PINs, or generated data files.

### 5. Functional architecture

Organize modules by responsibility rather than listing every internal helper:

- preparation and validation;
- repositories and MongoDB access;
- analytics and alerting;
- routing simulation, optimization, evaluation, statistics, and run storage;
- AI operations brief;
- administration, authentication, mutations, and audits; and
- application shell, views, charts, styling, and translations.

For each responsibility, identify important public or load-bearing functions,
their inputs, outputs, and why they matter. Avoid unstable line-number references.

### 6. Analytical definitions

Explain success rate, failure count, average latency, gateway comparisons,
alert baseline and latest-50 windows, the 200-row minimum baseline, confidence
interval gating, and why insufficient-history rows display unavailable evidence.

Explain the routing benchmark's chronological bucket split, candidate routes,
constraints, policies, expected and realized evidence, uncertainty, sensitivity,
and synthetic/non-causal limitation.

### 7. How to run and verify

Document the supported Make targets and the minimum sequence for:

- local setup;
- dataset preparation;
- safe demo mode;
- MongoDB import and live mode;
- tests, lint, formatting, and browser smoke; and
- administrator password hash configuration without disclosing a password.

Reference existing specialized setup documents instead of duplicating their full
instructions.

### 8. Interpretation and troubleshooting

Include common operational questions, especially:

- Gateway B-style insufficient history (`173/50` does not satisfy the required
  `200/50` comparison);
- demo versus live data;
- missing or mixed simulation metadata;
- unavailable routing evidence;
- MongoDB connectivity;
- admin authentication; and
- the meaning and limits of synthetic optimization results.

## Accuracy Rules

- Derive module and function descriptions from the current code, not historical
  design promises.
- Distinguish current behavior from recommendations or known limitations.
- State exact thresholds and field names only after verifying their configured
  values.
- Keep the pandas and MongoDB paths distinct where their presentation behavior
  differs.
- Use relative Markdown links to repository files and existing documentation.
- Include no secrets, credentials, generated datasets, or personal payment data.

## Verification

The completed guide must pass:

- a placeholder and ambiguity scan;
- a link/path existence check for local references;
- a comparison against current entry points, Make targets, dataset constants,
  alert thresholds, routing report fields, and UI views;
- `git diff --check`; and
- the repository documentation-sensitive test and lint gates where applicable.

## Acceptance Criteria

The guide is complete when a non-technical reader can explain what each view
means, while a new developer or judge can trace a transaction from source data
through validation, storage, analytics, routing evidence, presentation, and
audited administration without reading the full codebase.
