---
version: 1
slug: "apps-frontend-src-routes-shop-page-svelte"
primary_target: "apps/frontend/src/routes/(shop)/+page.svelte"
related_targets: ["apps/frontend/src/routes/layout.css"]
---

# Storefront home and shared shell

Scope: the customer storefront home (`/`) plus the shared tokens, header, footer and component library every other route inherits (shop, merchant, admin). Visitor mode: Persuade on the home page; Operate on cart, checkout, account, merchant and admin.

Audience and job: Saudi shoppers finding a store, product or service and buying it in Arabic or English; merchants and administrators running their work in the dashboards.

Constraints: copy stays in the i18n catalogues, hero copy/promotions/testimonials come from admin settings, e2e test ids and flows keep working, light and dark themes, true RTL.

Owner's choice: the category standard, taken deliberately on 2026-11-13. Quality bar named by the owner: Airbnb, Stripe / Linear, Noon / Amazon.sa.

## Direction contract

THESIS: A marketplace shoppers already know how to use, finished to the level of the best in the category. It refuses the previous floating-card constellation hero and pill-soft look-alike styling in favour of plain structure: search first, categories as tabs, product rails.

OWN-WORLD: White ground, cool-green-tinted neutrals, near-black ink, one emerald brand colour for actions and selection, one warm red reserved for discounts. 10px controls, 14px cards, hairline borders with a soft two-layer shadow only on raised things. One sans family at all sizes with tabular numerals for money. Segmented toggles and tabs share one sliding indicator.

STORY: The visitor sees what is sold and by whom, searches or picks a category, and trusts that each store is paid directly.

FIRST VIEWPORT: Sticky two-row header: logo, wide search, language and theme segmented toggles, account, cart; beneath it a category tab row with a sliding underline. Below: a banner split into headline with primary action on the start side and a featured product image on the end side, then the first product rail starting inside the fold.

SIGNATURE INTERACTION: the sliding selection indicator, one motion shared by category tabs, segmented toggles and dashboard navigation; page changes cross-fade and a product image carries from card to product page.

FORM: category standard (standing exit, chosen by the owner); seed: seed:c44e59a5d5f5ceca.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
