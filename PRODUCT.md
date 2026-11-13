# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Shoppers in Saudi Arabia** discovering independent stores and buying physical products or booking services, in Arabic (RTL) or English (LTR), paying in SAR.
- **Independent Saudi merchants** who register a store, list products and services, fulfil orders, manage delivery zones and pickup, and follow their earnings and settlements.
- **Marketplace administrators** who approve merchants, moderate the catalog, and oversee orders, payments, refunds, chargebacks, settlements, reconciliation and audit logs.

Lead layout (inferred, not confirmed by the owner): Arabic RTL on a phone is treated as an equal first-class target alongside English desktop, because the market is Saudi Arabia and the app ships as a PWA.

## Product Purpose

A multi-vendor marketplace connecting customers with independent Saudi merchants. Each merchant runs an independent store with its own catalog, pricing, orders and financial records. The operator earns a configurable commission on successful transactions. Success means shoppers complete purchases across several stores in one checkout, and merchants receive their proceeds directly.

## Positioning

Payments are split at the provider: the merchant's share settles directly into the merchant's own registered Saudi bank account and the platform only takes its commission. The platform never pools customer money and pays sellers out later. Every movement is recorded in an immutable double-entry ledger.

## Operating Context

- One cart can hold items from several stores; checkout pays each store separately.
- Physical products and services have different fulfilment workflows (delivery zones, fees, pickup points versus service bookings).
- Merchants onboard through verification before selling; administrators approve them.
- Runs with a mock payment provider by default; Moyasar for Platforms is the intended live provider, subject to approval. Test-mode payments are flagged in the UI.

## Capabilities and Constraints

- Stack: SvelteKit 3 (Svelte 5 runes), Tailwind CSS 4, shadcn-svelte components in `src/lib/components/ui`, app components in `src/lib/components/app`.
- Design tokens live in `apps/frontend/src/routes/layout.css`; shadcn token names are the source of truth.
- All copy lives in `src/lib/i18n/messages/{en,ar}.ts`; both catalogues must stay in sync.
- Arabic must be a true RTL layout (logical properties, mirrored directional icons), not flipped text alignment.
- Light and dark themes are both required (`<html data-theme>`: light, dark, system).
- Currency is SAR; phone numbers are +966; addresses use Saudi regions and cities.
- Playwright end-to-end tests cover checkout, dashboards, delivery, i18n and PWA and must keep passing.
- Homepage hero copy, promotions and testimonials are administrator-editable settings, not hard-coded.

## Brand Commitments

- Name: **Souq Collective**. Tagline: "Independent Saudi stores, one marketplace".
- Logo mark: `docs/logo/logo.svg` (two interlocking angular forms knocked out of a square tile). It stays.
- The previous look (a Shop-app style reference in `.claude/design.md`: white canvas, single violet accent, pill-soft 28px cards) is being replaced with an identity of its own. The owner approved replacement on 2026-11-13.
- Standing visual preference (owner's choice, 2026-11-13): the familiar marketplace layout, executed at the craft level of Airbnb, Stripe / Linear and Noon / Amazon.sa, rather than an unconventional visual concept.
- Owner's stated ambition for the redesign: every component and page consistent, with considered animation, tabs, and toggles for menus, at a premium level.

## Evidence on Hand

- Demo catalog from `make seed` (store `najd-oud` and others) with product imagery served from `/media`.
- No real testimonials, customer counts, press or performance figures exist. Do not invent them. Testimonials shown on the homepage come only from administrator settings.

## Product Principles

1. Merchants are the heroes: stores are presented as independent businesses with their own identity, never as anonymous listings.
2. Money is always legible: prices, fees, commission, delivery and per-store totals are shown plainly and consistently.
3. Arabic and English are equals: neither language is a translation afterthought in layout or typography.
4. Trust through plainness: verification, payment status and test mode are stated directly.
5. One system across shop, merchant and admin surfaces: the same tokens and components everywhere.

## Accessibility & Inclusion

- WCAG AA contrast in light and dark themes.
- Full keyboard operation and visible focus.
- `prefers-reduced-motion` is honoured for all animation.
