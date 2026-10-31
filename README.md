Odoo 17 Community module for end-to-end subscription management — plans, recurring billing, discounts, revenue analysis and lifecycle automation.

## Quick Start

**Prerequisites:** Docker Desktop running (Engine running in the status bar).

```bash
# 1. Unzip and enter the project folder
cd brightloop-odoo-starter/brightloop

# 2. Start Odoo + Postgres
docker compose up -d

# 3. Watch until ready (Ctrl+C to stop watching — Odoo keeps running)
docker compose logs -f odoo
# Wait for: "HTTP service running on ..."
```

**Create the database** at http://localhost:8069:

| Field | Value |
| --- | --- |
| Master password | `admin` |
| Database name | `brightloop` |
| Demo data | **unticked** |

**Install the module:**

1. Settings → Activate Developer Mode (or add `?debug=1` to the URL)
2. Apps → Update Apps List → confirm
3. Remove the "Apps" filter, search **Brightloop**, click **Install**

**Load demo data** (recommended for first use):

Brightloop → Configuration → **Load Demo Data** — one click, \~20 seconds. Creates 13 subscriptions, 49 invoices and 12 months of history.

> The loader runs once per database. To reset, run `docker compose down -v` and start again.

## How the Subscription Cycle Works

Every subscription follows the path below. Daily automation handles billing and expiry with no manual work.

&#91;embedded content: subscription lifecycle · 5 states, 2 automated jobs\]

The key transitions:

- **Make Quotation** validates that the plan is available on today's date and that at least one line exists.
- **Confirm** enforces the plan's minimum quantity — the system blocks confirmation if the total quantity falls short.
- **Activate** sets the first billing date and immediately creates an invoice if one is due. From here, the daily job takes over.
- **Pause / Resume** stops and restarts billing; when resuming, the next invoice date is moved forward to today so the customer is not charged for the paused window.
- **Renew** copies the subscription as a new Draft linked to the original, ready to go through the cycle again.
- **Close** is blocked before the expiry date unless the plan explicitly allows early closing.
