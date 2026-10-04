# 🍽️ RestoAuto — Restaurant Automation System

A Flask-based learning project that runs an end-to-end restaurant: menu, orders,
kitchen, billing, and reports. Built incrementally over five phases, each adding
one new feature on top of the last.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Flask 3, application-factory pattern, one Blueprint per feature |
| Database | SQLAlchemy 2.x + SQLite (Postgres-ready) |
| Auth | Flask-Login (sessions), Werkzeug password hashing |
| Forms | Flask-WTF / WTForms (CSRF + validation) |
| Templates | Jinja2 with Bootstrap 5 (CDN, no build step) |
| PDF | ReportLab (one-page A4 receipts) |
| CSV | stdlib `csv` (no extra deps) |

## Project layout

```
restaurant_automation/
├── app/
│   ├── __init__.py            # create_app() factory + error handlers
│   ├── config.py              # Config class (env-driven)
│   ├── extensions.py          # db, login_manager, csrf
│   ├── models.py              # 7 models: User, Category, MenuItem, Table, Order, OrderItem, Bill
│   ├── auth/                  # login, register, logout, user list
│   ├── main/                  # landing, dashboard, search
│   ├── menu/                  # categories + items CRUD, 86'ing
│   ├── orders/                # tables, take order, status flow, kitchen
│   ├── billing/               # generate, pay, void, PDF
│   ├── reports/               # sales report, CSV, print view
│   ├── templates/             # base, auth, main, menu, orders, billing, reports, search, errors
│   └── static/css/app.css
├── run.py                     # dev entry point
├── seed.py                    # populate sample data
├── requirements.txt
├── .gitignore
└── README.md
```

## Setup

```bash
cd restaurant_automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed.py              # creates restaurant.db with sample data
python run.py               # open http://127.0.0.1:5000
```

### Troubleshooting: `Address already in use` on port 5000

macOS Monterey+ runs an **AirPlay Receiver** on port 5000. Either disable it
(System Settings → AirDrop & Handoff → AirPlay Receiver → off), or run on a
different port:

```bash
FLASK_RUN_PORT=5050 python run.py
```

…and visit <http://127.0.0.1:5050>.

## Default users (from seed)

| Username | Password    | Role     | Can do                                       |
|----------|-------------|----------|----------------------------------------------|
| admin    | admin123    | admin    | everything + manage users                   |
| manager  | manager123  | manager  | menu, reports, all orders, bills, void       |
| waiter   | waiter123   | waiter   | take orders, see own, mark served, take money|
| chef     | chef123     | chef     | kitchen view, mark ready (no money ops)      |

## Features

### ✅ Phase 1 — Foundation
- App factory + 7 models
- Login / logout / register (admin-only), role-based access
- Bootstrap base template with role-aware nav
- Dashboard with 4 KPI cards

### ✅ Phase 2 — Menu management
- Categories + items CRUD, availability toggle ("86 it" / "un-86")
- Per-item veg flag, prep time, image URL, price
- Filters: available only, veg only
- Manager writes; everyone reads

### ✅ Phase 3 — Orders & kitchen
- Tables page with color-coded status (free / open / disabled)
- New order flow: pick items, qty, per-item notes
- Order state machine: `pending → preparing → ready → served → paid`
- Role-gated transitions (waiter, chef, manager)
- Kitchen view for the chef queue (oldest first)
- Order detail with line items, add/remove items while pending/preparing

### ✅ Phase 4 — Billing
- Generate bill from a `served` order (tax %, discount Rs.)
- Mark bill paid (cash / card / UPI) → order auto-flips to `paid`
- Void an unpaid bill (admin/manager)
- Single-page A4 PDF receipt via ReportLab
- Print-friendly HTML view (`?print=1`)
- Bills list with All / Unpaid / Paid / Today / Mine filters

### ✅ Phase 5 — Reports, search, polish
- Sales report at `/reports/sales` with date-range presets + custom range
- Daily breakdown table, top 10 items, payment-method breakdown
- CSV export of the same report
- Print view of the report
- Global search (`/search?q=…`) across menu / orders / bills (manager+)
- Real dashboard widgets: 7-day revenue bar chart, top items, recent bills,
  86'd items with one-click un-86 (manager)
- Active-page highlighting in nav, sticky top nav, footer
- Inline-SVG favicon (no extra request)

## Architecture notes

1. **Price-at-time-of-order** is captured on `OrderItem.unit_price` so menu
   price changes don't rewrite history.
2. **One blueprint per feature** keeps phases additive — every commit is a
   clean diff.
3. **Roles are strings on `User.role`**, with `is_admin` / `is_manager` /
   `is_chef` helpers. No permission system framework; readability wins.
4. **State machine is a dict of allowed transitions** in
   `app/orders/routes.py` — adding a state is a one-line change.
5. **Bills snapshot totals** at generation time. A paid bill is a historical
   record; subsequent order edits don't affect it.
6. **No JS framework** — vanilla JS + Bootstrap only, no build tooling.

## Switching to PostgreSQL

Set `DATABASE_URL=postgresql+psycopg://user:pass@host/dbname` in a `.env` file
and `pip install psycopg[binary]`. No code changes needed.

## Map of the app

```
URL                       Blueprint.endpoint                Who
------------------------  --------------------------------  --------------------
/                         main.index                        anyone
/auth/login               auth.login                        anyone
/auth/register            auth.register                     admin
/auth/users               auth.list_users                   admin
/auth/logout              auth.logout                       authenticated
/                         main.index (→ dashboard)          authenticated
/dashboard                main.dashboard                    authenticated
/search?q=…               main.search                       manager+
/menu/                    menu.list_items                   authenticated
/menu/items/<id>          menu.item_detail                  authenticated
/menu/categories/new      menu.category_new                 manager+
/menu/categories/<id>/edit menu.category_edit               manager+
/menu/categories/<id>/delete menu.category_delete           admin
/menu/items/new           menu.item_new                     manager+
/menu/items/<id>/edit     menu.item_edit                    manager+
/menu/items/<id>/toggle-availability  menu.item_toggle_…    manager+
/menu/items/<id>/delete   menu.item_delete                  admin
/orders/                  orders.list_orders                manager+ (waiter: own only)
/orders/tables            orders.tables                     authenticated
/orders/kitchen           orders.kitchen                    authenticated
/orders/new?table_id=N    orders.new_order                  any except chef
/orders/<id>              orders.order_detail               authenticated
/orders/<id>/items        orders.add_item                   any except chef
/orders/<id>/items/<iid>/remove  orders.remove_item         waiter (own) or manager
/orders/<id>/status       orders.change_status              role-gated
/orders/<id>/cancel       orders.cancel                     manager+
/billing/                 billing.list_bills                authenticated
/billing/orders/<id>/generate  billing.generate             any except chef
/billing/bills/<id>       billing.bill_detail               authenticated
/billing/bills/<id>/pay   billing.pay                       any except chef
/billing/bills/<id>/void  billing.void                      manager+
/billing/bills/<id>/pdf   billing.pdf                       authenticated
/reports/sales            reports.sales                     manager+
/reports/sales.csv        reports.sales_csv                 manager+
/reports/sales/print      reports.sales_print               manager+
```

## License

MIT — do whatever you want with it.
