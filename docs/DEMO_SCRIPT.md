# Textile Mill — Demo Script

Click paths for a 30–40 minute walkthrough of the demo company **Demo Textile Mills (Pvt) Ltd**. Document names are
the ones the demo journeys create on a fresh site; search by the `[DEMO-…]` tag in remarks if numbering differs.
Dashboard trends before D0 are "Sample history" (synthetic) and are marked as such on the charts.

## 0. Prepare (once)

```bash
bench --site <site> execute textile_mill.setup.masters.run
bench --site <site> execute textile_mill.demo.run_journey.run_all
```

Log in as Administrator (or a user with CEO / Production Director roles) and open the **Textile Mill** workspace.

## 1. Denim — fibre to jeans (Part B)

1. **Sales Order** `DEMO-SO-JNS` (Urban Threads LLC, jeans) and `DEMO-SO-FAB` (Lahore Fashion Fabrics, fabric).
2. **Dye Recipe** `DR-IND-001` → workflow state *Production Approved* → **Create BOM**.
3. **Loom Shift Production** `LSP-26-00001` → per-loom picks, efficiency and stops; the linked Manufacture entry.
4. **Fabric Roll Inspection** `FRI-26-00001` → points/100 m², A/B/Rejected repack valued by relative sales value.
   Print **Fabric Roll Tag**.
5. **Cut Plan** `CUT-26-00001` → FIFO roll allocation, size work orders, bundles; print **Bundle Ticket Label**,
   then scan a bundle on the **Bundle Scan** page.
6. Reports: **Stage Yield Report**, **Production Cost per Unit**, **Recipe Consumption Variance**,
   **Loom Efficiency**, **Fabric Grade Analysis**, **Corrective Report**, **Utility Absorption vs Actual**.
7. **Batch Genealogy** on a delivered jeans batch → back to recycled cotton (`CW-PRE`) and its supplier.
8. **Order Cost and Profitability** for `DEMO-SO-JNS`.

## 2. Home textile — Order → Weight Check → CTP grading → Set Completion → Carton labels → Profitability (Part D)

1. **Order** — Sales Orders `DEMO-SO-TWL` (Nordic Home AB, towels) and `DEMO-SO-BED` (Home Comforts UK, bed-linen
   sets). Show the customer item codes and the Customer Label Spec on the customer.
2. **Weight Check** — **Piece Weight Check** `PWC-26-00001…3`: sample weights against the GSM target and tolerance;
   then the **Weight Compliance** report (variance %, give-away kg, pass/fail).
3. **CTP grading** — **CTP Production Entry** `CTP-26-00001…5`: pieces cut, A / seconds / rags, cutting waste and the
   linked Manufacture entry; then **CTP Yield and Grading**.
4. **Set Completion** — the **Set Completion** report: sets ordered vs. components available vs. sets assembled
   per Sales Order (no open sets left after the demo).
5. **Carton labels** — **Carton Packing List** `CPL-26-00001` / `CPL-26-00002`: cartons with SSCC; print
   **Carton Label** (GS1-128 barcode) and **Packing List**; then **Carton and Shipment Summary**.
6. **Profitability** — **Order Cost and Profitability** for `DEMO-SO-TWL` and `DEMO-SO-BED`; **Batch Genealogy**
   on a towel set back to `VC-RAW` and Sindh Cotton Ginners.

## 3. Knitting — yarn to T-shirts (Part E)

1. **Sales Order** `DEMO-SO-TSH` (Metro Retail, TSH-CREW-NAVY S/M/L/XL, 5,000 pcs).
2. **Knitting Shift Production** `KSP-26-00001…3` (shifts A/B/C, CK machines, rolls, defects); the greige batch
   shows its roll list.
3. **Dye Recipe** `DR-KNAVY` → two jet batches (≈ 60 % load, shown red on the Knit Dyeing dashboard).
4. Knit finishing Manufacture entry with the **QIT-KNIT-FIN** inspection (GSM, shrinkage, spirality).
5. **Cut Plan** `CUT-26-00002` in kg (marker 1:2:2:1, 834 plies → 5,004 pieces), stitching, delivery and invoice.

## 4. Director dashboards (Part C)

1. **Command Center** → switch **Business line**: Denim (default), Home Textile, Knitting, All. The value chain shows
   one row per flow (towels, bed linen).
2. **Production** → OEE, downtime, plan attainment and WIP aging follow the selected line.
3. **Finance**, **Sales**, **Procurement**, **Quality and Inventory**.
4. **Stage** dashboard → pick a stage: Weaving (air-jet looms), Terry Weaving, Cut-to-Piece, Packing, Knitting,
   Knit Dyeing, Knit Finishing, Knit Garments.
5. Click a KPI tile → it opens the report it is computed from (same numbers).

## Re-running

| Command | Effect |
|---|---|
| `bench --site <site> execute textile_mill.demo.run_journey.run_all` | Runs any missing step of all three journeys and the dashboard history. |
| `bench --site <site> execute textile_mill.demo.run_journey_ht.run_all` | Home textile only (HT-01…16). |
| `bench --site <site> execute textile_mill.demo.run_journey_knit.run_all` | Knitting only (K-01…08). |
| `bench --site <site> execute textile_mill.demo.seed_history.run` | Rebuilds sample history and KPI snapshots. |
| `bench --site <site> set-config textile_mill_allow_reset 1` then `bench --site <site> execute textile_mill.demo.reset.reset_demo` | Deletes all demo transactions (masters kept). Dev sites only. |
