# Textile Mill — Report Catalogue

35 script reports, all under **Textile Mill → Reports / Critical Reports / Operations Reports** in the workspace.
Every report takes the company and (unless noted) a date range. Reports, KPI tiles and dashboards share the same query
functions (`reports_lib*.py`), so a number is the same wherever it appears.

Legend — **Data**: the DocTypes the report reads. **Act when**: the condition the report is built to surface.

## 1. Core reports (Part B §9, Part D §D8)

| # | Report | What it shows | Data |
|---|---|---|---|
| 1 | Stage Yield Report | Input, output, scrap, invisible loss and yield % per manufacture entry / work order and per stage | Stock Entry (Manufacture) |
| 2 | Production Cost per Unit | Actual vs BOM-standard cost per unit, by work order and by stage | Stock Entry, BOM |
| 3 | Recipe Consumption Variance | Chemicals per dye recipe: standard g/kg vs actual, variance qty and value | Dye Recipe, Stock Entry |
| 4 | Loom Efficiency | Per loom and shift: picks, metres/kg, efficiency, warp/weft breaks per 100k picks, stops | Loom Shift Production |
| 5 | Fabric Grade Analysis | Rolls and metres by grade (A/B/Rejected), average points, top defects per inspection | Fabric Roll Inspection |
| 6 | Corrective Report | Each re-dye / re-process job with hours, cost and reason; re-process % by stage | Job Card (corrective) |
| 7 | Utility Absorption vs Actual | Utilities absorbed into production vs utility bills logged, per stage | Stock Entry, Utility Consumption Log |
| 8 | Batch Genealogy | Backward (shipment → raw lot → supplier) or forward (lot → products → customers) trace | Batch, Serial and Batch Bundle |
| 9 | Order Cost and Profitability | Revenue, material, conversion, utilities and margin for one sales order | Sales Order, Stock Entry, Sales Invoice |
| 10 | Inventory Between Processes | Stock and value per stage buffer / WIP warehouse | Bin, Warehouse |
| 11 | CTP Yield and Grading | Cut-to-piece: pieces cut, A / seconds / rags, cutting waste, CTP yield | CTP Production Entry |
| 12 | Weight Compliance | Towel and sheet piece weights vs target, CV %, implied GSM, cotton give-away | Piece Weight Check |
| 13 | Set Completion | Sets ordered vs components available vs sets assembled | Sales Order, Work Order |
| 14 | Carton and Shipment Summary | Cartons, SSCCs, pieces and weight per packing list and shipment | Carton Packing List |

## 2. Critical reports — exceptions to act on

| # | Report | What it shows | Act when | Data |
|---|---|---|---|---|
| 15 | **Yield Loss Exceptions** | Work orders below the stage yield target, loss vs target in qty and PKR, RAG status | Any row; sort by loss value | Stock Entry, KPI Target |
| 16 | **Late Order Risk** | Open SO lines: pending, in stock, in production, shortfall, days to due; Overdue / At Risk / On Track | Overdue or At Risk | Sales Order, Bin, Work Order |
| 17 | **Material Shortage vs Plan** | Material still to issue to open work orders vs free stock and open POs | Status *Short* (raise PO) or *Covered by PO* (expedite) | Work Order Item, Bin, Purchase Order |
| 18 | **Margin Erosion** | Work orders whose actual unit cost is ≥ X % over BOM standard, with excess cost and SO | Excess cost above tolerance | Stock Entry, BOM |
| 19 | **Aged and Stuck WIP** | Batches in WIP / QC Hold / B-Grade warehouses with value and age bucket | Age above the stage norm | Serial and Batch Bundle, Batch |
| 20 | **Quality Hold** | Draft manufacture entries awaiting QI, rejected inspections, stock in QC-Hold / Rejected stores | Any row | Stock Entry, Quality Inspection, Batch |
| 21 | **Corrective Cost Summary** | Re-dye / re-process cost grouped by stage, machine and operation, with stage re-dye % | Re-dye % above target | Job Card |
| 22 | **Lot Recall Trace** | For one lot: every customer, shipment and product it reached (washed jeans matched by size) | Supplier or quality complaint on a lot | Batch genealogy, Delivery Note |
| 23 | **Give-away Cost** | Over-weight give-away per item: checks, failures, average variance, kg and PKR per 1,000 pcs | Give-away value rising | Piece Weight Check |
| 24 | **Downtime and MTBF** | Per machine: stops, downtime h, run h, availability, MTBF, MTTR, top reason | Low MTBF or high MTTR | Machine Downtime Log, shift sheets, Job Card |

## 3. Operations reports — detail registers

| # | Report | What it shows | Data |
|---|---|---|---|
| 25 | Shift Production Register | Machine-level output per shift for looms and circular knitting: operator, output, efficiency, breaks/defects, stops | Loom / Knitting Shift Production |
| 26 | Operator Performance | Weaver / knitter league table: shifts, output per shift, output-weighted efficiency, faults per shift | Loom / Knitting Shift Production |
| 27 | Defect Pareto | Fabric defects by type: occurrences, points, share, cumulative share, vital-few flag (80 %) | Fabric Roll Inspection |
| 28 | Dye House Batch Log | Every dye-house batch: machine, recipe, input/output, yield, chemical cost per unit, jet load %, re-dyed | Work Order, Stock Entry |
| 29 | Chemical Consumption per Unit | Chemicals and dyes per stage: qty, value, qty per 1,000 units of output, cost per output unit | Stock Entry |
| 30 | Utility Cost per Unit | Absorbed vs actual utilities per stage and per unit of output | Stock Entry, Utility Consumption Log |
| 31 | Waste and By-product Recovery | Waste generated per item and stage vs sold: qty, book value, sales value, sold %, realised rate | Stock Entry, Sales Invoice |
| 32 | Subcontract Reconciliation | Per subcontracting order: FG ordered / received / pending; material sent / consumed / returned / still with supplier | Subcontracting Order |
| 33 | Marker Efficiency and Over-cut | Cut plans: marker, plies, pieces cut vs ordered (over-cut), fabric per piece, cutting variance, end-bit % | Cut Plan, Sales Order |
| 34 | Bundle Line WIP | Bundles by cut plan, size, stitching line and status, with pieces and age | Bundle Ticket |
| 35 | Order Book by Business Line | Open order lines by line (Denim / Home Textile / Knitting): pending qty and value, due date, risk status | Sales Order |

## 4. Not built yet (needs new data capture)

| Report | Missing data |
|---|---|
| Customer Complaints and Returns | A complaint / return DocType (defect, lot, customer, cost, root cause) |
| Lab Test Results (colour fastness, tensile, pilling) | A lab test DocType or extra Quality Inspection templates per test |

## Notes on the demo data

The demo journeys deliver every sales order and close every work order, so **Late Order Risk**, **Material Shortage vs
Plan** and **Order Book by Business Line** are empty on a freshly seeded site. They fill as soon as a new order or work
order is open. **Utility Cost per Unit** shows actual utility bills only for the stages covered by the demo utility log
(denim); the other stages show absorbed cost only.
