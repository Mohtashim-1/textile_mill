### Textile Mill

Integrated denim, home textile and knitting mill on ERPNext v15: batch traceability, actual costing, stage yields,
quality, director dashboards and a scripted end-to-end demo. Nothing in `frappe` or `erpnext` is modified.

#### Install

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench --site <site> install-app textile_mill
bench --site <site> migrate
```

Requires ERPNext v15 on the site.

#### Demo

```bash
bench --site <site> execute textile_mill.setup.masters.run           # denim + home textile + knitting masters, KPIs
bench --site <site> execute textile_mill.demo.run_journey.run_all    # denim, then home textile, knitting and dashboard history
```

The journeys can also run on their own: `textile_mill.demo.run_journey_ht.run_all` (HT-01…16) and
`textile_mill.demo.run_journey_knit.run_all` (K-01…08). Every step is idempotent. Click paths are in
[`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).

#### Tests

The tests use the demo data and roll back their writes, so they run on a demo site:

```bash
cd sites && ../env/bin/python -c "import frappe, unittest; frappe.init(site='<site>', sites_path='.'); frappe.connect(); \
unittest.main(module=None, argv=['x', 'discover', '-s', '../apps/textile_mill/textile_mill/tests', '-t', '../apps/textile_mill'])"
```

#### Build status

| Phase | Scope | Status |
|---|---|---|
| 0 | Scaffold, roles, Textile Mill Settings, docs | Done |
| 1 | Masters & settings (denim) | Done |
| 2 | Dye Recipe + BOMs | Done |
| 3 | Shop-floor DocTypes & overrides | Done |
| 4 / 4b | Reports, workspace, print formats, director dashboards | Done |
| 5 | Denim demo journey | Done |
| 6 | Home textile (masters, CTP, weight checks, cartons/SSCC, reports, KPIs, business-line dashboards, demo HT-01…16) | Done |
| 7 | Knitting (masters, Knitting Shift Production, DR-KNAVY, T-shirts, KPIs, stage dashboards, demo K-01…08) | Done |
| 8 | Process-depth backlog (Part F) | Not started — prioritise with the client |

Design decisions are logged in [`docs/DECISIONS.md`](docs/DECISIONS.md).

#### License

MIT
