# Textile Mill — Decisions Log

Judgment calls made while implementing the build guide. Newest at the bottom of each phase.

## Phase 0 — Scaffold

| # | Topic | Decision | Why |
|---|---|---|---|
| 0.1 | Bench / version | App lives on the v15 bench (`/home/frappe/frappe-bench`, Frappe 15.107 / ERPNext 15.107). | Guide targets ERPNext v15; the v16 bench is used by other apps. |
| 0.2 | Site name | `textile.codecrestsolutions.com` instead of `demo.local`. | Requested hostname; the site is served publicly behind nginx + Let's Encrypt. |
| 0.3 | Roles | All roles from Part B §5.1 and Part C §2 (`CEO`, `CFO`, `Board Viewer`) are created by `setup/install.py` on install **and** on every migrate, instead of Role fixtures. | Idempotent, works on existing sites, and avoids fixture-sync overwriting role settings (e.g. desk access) changed by admins. |
| 0.4 | Settings defaults | Numeric defaults live in the DocType JSON; `set_settings_defaults()` only fills fields never stored before, so a value an admin sets to 0 is not reset. `utility_absorbed_account` and grade maps are filled in Phase 1 (they need the company, accounts and items). | Link defaults on a Single are validated during install before the linked records exist. |
| 0.5 | Stage list | `textile_mill.constants.PRODUCTION_STAGES` is the single source for stage names; Select options in DocType JSON are kept in sync with it. Home textile and knitting stages are appended in Phases 6–7. | Frappe Select options are static strings in JSON. |
| 0.6 | Fiscal year | Company fiscal year Jul 1 – Jun 30 (2026-2027 covers the demo dates). | Part B §3.1. |

## Phase 1 — Masters & settings

| # | Topic | Decision | Why |
|---|---|---|---|
| 1.1 | Masters as data | Masters are plain Python data (`setup/master_data*.py`) applied by idempotent `setup/masters*.py`; `masters.run()` builds denim, then home textile, then knitting. | Re-runnable on any site; no fixture drift. |
| 1.2 | Plant | `Mill Plant` is an Accounting Dimension (label "Plant"); stock entries get their plant from the stage. | Plant-wise P&L without extra cost-center trees. |
| 1.3 | Workstation costing | Hour rate split 40 % electricity, 35 % labour, 15 % consumables, 10 % rent; planned 24 h/day; `production_capacity` 50. | One summary job card per shift document overlaps others on the same workstation. |
| 1.4 | Variants | Textile fields (stage, shade, GSM…) are added to Item Variant Settings so variants inherit them. | Garment sizes are variants of a style template. |
| 1.5 | Demo D0 | D0 = today − 25 days, stored once in the site default `textile_demo_d0`. | All demo dates stay in the past and stable across re-runs. |

## Phase 2 — Dye Recipe + BOMs

| # | Topic | Decision | Why |
|---|---|---|---|
| 2.1 | Recipe → BOM | Only a `Production Approved` recipe (workflow) can generate its BOM; output qty = base × expected yield, rounded to 0.1. | Part B §6.3; avoids 999.99-kg BOMs. |
| 2.2 | Routes | Operations and QI template per process type come from `constants.DYE_PROCESS_ROUTES` (Fiber Dyeing, Indigo, Processing, Printing, Knit Dyeing). | One place to change a dye route. |
| 2.3 | Basis | Chemicals are grams per base unit; `basis_uom` is `per kg` or `per m` and must match the base item's stock UOM. | Printing recipes are per metre of sheeting. |

## Phase 3 — Shop-floor DocTypes & overrides

| # | Topic | Decision | Why |
|---|---|---|---|
| 3.1 | Loom-level job cards | Loom Shift Production posts one summary job card and one Manufacture entry per shift; loom run time comes from the shift sheet (8 h − stops). | Part B §14: ERPNext has one job card per operation/workstation. |
| 3.2 | Grade valuation | Fabric Roll Inspection repacks the lot into A/B/Rejected items with value split by relative sales value; the last row absorbs rounding so totals equal the source exactly. | Part B §6.6. |
| 3.3 | Stage on stock entries | `Stock Entry.before_validate` resolves the stage (explicit, Work Order, Cut Plan), sets the stage cost center and plant, and keeps exactly one "Utilities (absorbed)" additional-cost row. | Re-validation must not duplicate absorption. |
| 3.4 | Cut Plan | FIFO roll allocation (whole rolls, last one partial); one Work Order per size; fabric split across sizes by pieces × standard fabric; bundles of `bundle_size`. | Part B §6.7. |
| 3.5 | Server-built Work Orders | Operations are copied from the BOM on the server. | Only the Work Order form script does it in standard ERPNext. |

## Phase 4 / 4b — Reports, workspace, dashboards

| # | Topic | Decision | Why |
|---|---|---|---|
| 4.1 | Shared queries | Script reports and dashboard KPIs call the same functions (`reports_lib*.py`). | A KPI always equals its report. |
| 4.2 | Report names | Names use "and" instead of "&" ("CTP Yield and Grading", "Carton and Shipment Summary"). | Frappe scrubs names to folder names and keeps "&", which is not a valid module path. |
| 4.3 | Workspace | Workspace, number cards and charts are generated JSON (standard, module Textile Mill). | Reproducible; synced by migrate. |
| 4.4 | Dashboards | Desk pages (`dm-*`) with their own bundle; results cached 5 min per dashboard + filters + roles; role check per dashboard. | Part C §4. |
| 4.5 | RAG | Thresholds are absolute values and the KPI direction decides the bad side; `WEIGHT_VARIANCE_PCT` is judged on its absolute value. | Over- and under-weight are both bad. |
| 4.6 | History | 12 months of synthetic snapshots before D0 are flagged `is_synthetic`; sample downtime logs, budgets and reorder levels carry "Sample history". | Trends need history; synthetic data must be identifiable. |

## Phase 5 — Denim demo journey

| # | Topic | Decision | Why |
|---|---|---|---|
| 5.1 | Idempotency | Every demo document carries a `[DEMO-…]` tag; each step skips itself when its tagged output exists; posting dates strictly increase. | Safe to re-run after a partial failure. |
| 5.2 | Reset | `demo.reset` cancels and deletes demo transactions in reverse order and needs the site config flag `textile_mill_allow_reset`. | Destructive; must be opted into per site. |

## Phase 6 — Home textile

| # | Topic | Decision | Why |
|---|---|---|---|
| 6.1 | Printing WIP | Added a `Printing WIP` warehouse (not in Part D §D1). | Printing work orders need their own WIP so the WIP report is per stage. |
| 6.2 | Journey dates | HT-01 posts on D0 + 2, between denim entries; back-dated valuation is settled with `repost_entries()` at the end of the journey. | The story must fit before today; shared items (cotton, caustic) need reposting. |
| 6.3 | Grey terry QI | The grey-terry BOM requires a QI, so the loom-shift Manufacture entry stays draft until the inspection is submitted (HT-05 does this). | ERPNext blocks submitting an FG row without its QI. |
| 6.4 | CTP consumption | A CTP entry consumes exactly the fabric batches issued plus trims for the pieces cut; seconds, rags and cutting waste are scrap rows at item valuation; sheet seconds go to `WST-CTP`. | Yield must be measured on what was actually cut. |
| 6.5 | SSCC | GS1 company prefix `8960001` (Pakistan range, demo only); serial from `getseries("SSCC8960001", 9)`; barcode is GS1-128 (FNC1 + AI 00) drawn as inline SVG. | No external barcode service; prints in PDFs. |
| 6.6 | Loom types | Loom efficiency, OEE and loom ranking filter by `loom_type`; denim KPIs use Air-jet Denim only, terry efficiency is weighted by kg. | Mixing terry kg and denim metres distorted denim OEE. |
| 6.7 | Opening stock | HT opening stock raises hemming thread to 60 cones and adds caustic (100 kg) and wetting agent (20 kg). | The recipe and trims need them; denim stock is not borrowed. |
| 6.8 | Packing line | Workstation PCK-01 is rated against stage `Set Assembly`. | Set work orders post output under Set Assembly; rating it under Packing showed 0 % performance. |
| 6.9 | Business lines | Dashboards take a `business_line` filter (Denim default, Home Textile, Knitting, All); the value chain shows one row per flow (towels, bed linen). Production tiles (plan attainment, downtime, re-dye, open WOs) follow the line's stages. | Part D §D9. |
| 6.10 | Stage buffers | `constants.STAGE_WAREHOUSES` covers home-textile stages; the denim demo only uses its denim entries. | WIP-waiting tiles for every stage. |

## Phase 7 — Knitting

| # | Topic | Decision | Why |
|---|---|---|---|
| 7.1 | Shift sheets | Knitting Shift Production mirrors Loom Shift Production: one Manufacture entry and one greige batch per shift, roll numbers in `Batch.dm_roll_list` (`CK-01/R1-Rn`). OEE treats knitting like looms (`SHIFT_STAGES`). | Part E §E5. |
| 7.2 | Machine load | Two 1,000-kg jets: the demo dyes 600 + 590 kg (≈ 60 % load) so `DYE_MACHINE_LOAD_PCT` shows under-loading. | Part E §E6–E7. |
| 7.3 | Sizes | New attribute `T-Shirt Size` (S/M/L/XL); BOM per size with 0.20/0.22/0.24/0.26 kg finished knit. | Garment Size holds denim waist sizes. |
| 7.4 | Cut Plan in kg | Cut Plan takes UOM, GSM and width from the fabric item; knit plans use the knit stores and stage; denim cutting-variance KPIs exclude knit plans. | Metres and kg must not be summed. |
| 7.5 | Over-cut | 1:2:2:1 marker × 834 plies = 5,004 pieces for a 5,000-piece order; 4 pieces stay in Knit FG Store. | 5,000 is not a multiple of 6. |
| 7.6 | Tests | Tests are `FrappeTestCase`s that use pure functions, read-only demo checks and rolled-back writes, so they run on the demo site without test fixtures. | `bench run-tests` would create `_Test` records in the live demo company. |
