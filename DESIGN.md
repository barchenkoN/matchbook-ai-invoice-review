---
version: alpha
name: Matchbook
description: A supplier invoice review desk with a visible three-way comparison.
colors:
  primary: "#344BC5"
  ink: "#24283F"
  muted: "#626A80"
  background: "#F4F5F9"
  surface: "#FFFFFF"
  line: "#E0E3ED"
  selected: "#EDF0FF"
  warning: "#8A5217"
  warningSurface: "#FFF3DF"
  success: "#237153"
  danger: "#AD344A"
  scrollbar: "#A8AEC3"
typography:
  sans:
    fontFamily: "Segoe UI, Arial, sans-serif"
  display:
    fontFamily: "Bahnschrift, Segoe UI, sans-serif"
  mono:
    fontFamily: "Consolas, monospace"
rounded:
  DEFAULT: "0.75rem"
  sm: "0.4rem"
spacing:
  section-gap: "1.5rem"
  page-max: "100rem"
components:
  button:
    height: "2.75rem"
  panel:
    rounded: "0.75rem"
---

## Overview
Product register: an accounts-payable review desk for a fictional wholesale company. English-reading operators and technical recruiters. No Japan market. The signature is a three-column purchase-order / received / invoiced comparison, with the original document alongside it. Numbers and their sources carry the visual interest.

This is a separate product from Relay; its pine dispatch-desk identity is intentionally not copied. A dark violet navigation rail, cool grey work surface, white document paper and restrained indigo selection express a document workbench. Discarded concept: big AI-score dashboards, because uncalibrated confidence obscures actual evidence.

Runtime source of tokens: `frontend/src/styles.css` :root; frontmatter mirrors named values and token tests detect drift. No duplicated theme system. Fonts are system-local, avoiding network dependency and layout shift.

## Colors
Primary indigo for navigation and safe actions. Amber denotes discrepancies, green denotes matched or completed, red denotes failures. All have text labels. Light theme only; forced-colors delegates to system colors. No gradients or neon AI motifs.

## Typography
Bahnschrift: product wordmark and page titles. Segoe UI: controls and readable narrative. Consolas: identifiers and tabular amounts sparingly. Base 14px/1.5, page title 30px. Sentence-case labels. No decorative uppercase paragraphs.

## Layout
Desktop: 208px sidebar, natural scrolling main document, 24px content margins. Queue table with search, filter and server pagination; review is source paper left and comparison right. Below 1100px the review stacks. Below 760px navigation becomes a compact top row. Tables own horizontal overflow; forms retain document scrolling. No full-viewport ancestor clipping.

## Elevation & Depth
Borders establish hierarchy. A subtle shadow belongs only to source paper and floating notifications. Dialog overlays are fixed with inert background. The queue and system screens reuse the same panel grammar.

## Shapes
12px panels, 6.4px controls. Badges are small rounded rectangles. Matchbook mark: two adjacent rounded document strokes, encoded as local SVG. No external image dependencies.

## Components
Shared Button, Badge, Notice, Field and Modal in `frontend/src/ui.tsx`. Native selects deliberately retain platform-owned popups. Typed ISO dates avoid calendar locale ambiguity. Modal uses native dialog showModal with focus restoration. Stable loading region; no fabricated progress percentages.

Motion: only 120ms color transitions, removed for reduced motion. Status uses text plus symbol. Dates en-GB UTC, money EUR. Source image has fixed aspect ratio and normalized evidence overlays.

## Do's and Don'ts
- Keep source, discrepancy and next action together.
- Show the configured extraction and integration modes honestly.
- Never turn simulated draft creation into an ERPNext success claim.
- No invented savings, client logos or accuracy scores.
