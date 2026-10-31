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
<img width="668" height="280" alt="image" src="https://github.com/user-attachments/assets/ebb24f8a-e278-4a5f-ad90-065085cec4be" />


The key transitions:

- **Make Quotation** validates that the plan is available on today's date and that at least one line exists.
- **Confirm** enforces the plan's minimum quantity — the system blocks confirmation if the total quantity falls short.
- **Activate** sets the first billing date and immediately creates an invoice if one is due. From here, the daily job takes over.
- **Pause / Resume** stops and restarts billing; when resuming, the next invoice date is moved forward to today so the customer is not charged for the paused window.
- **Renew** copies the subscription as a new Draft linked to the original, ready to go through the cycle again.
- **Close** is blocked before the expiry date unless the plan explicitly allows early closing.

## Configuration

Brightloop provides a dedicated Configuration menu to manage subscription-related settings.

The available configuration options include:

- **Plans:** Create and manage subscription plans, billing intervals, pricing, minimum quantities and availability periods.
- **Discounts:** Configure discounts that can be applied to subscriptions.
- **Quotation Templates:** Create reusable quotation templates for subscription orders.
- **Run Billing Now:** Manually trigger the billing process instead of waiting for the scheduled automation.
- **Load Demo Data:** Populate the database with sample subscriptions, invoices and historical records.

## Automated Billing and Expiry

Brightloop uses scheduled daily automation to manage recurring subscription activities.

The automated process handles:

- Checking active subscriptions for upcoming invoice dates.
- Generating invoices when billing is due.
- Updating the next invoice date.
- Checking subscription expiry dates.
- Processing applicable subscription lifecycle updates.

This reduces the need for manual billing operations and helps maintain consistent subscription records.

## Demo Data

Brightloop includes a built-in demo-data loader to help users explore the system without manually creating every record.

Navigate to:

**Brightloop → Configuration → Load Demo Data**

The demo loader generates:

| Data | Records |
|---|---:|
| Subscriptions | 13 |
| Invoices | 49 |
| Historical data | 12 months |

**Note:** The demo-data loader runs once per database. For a fresh demonstration environment, create a new database or reset the existing Docker environment.

## Invoice Management

Brightloop integrates subscription billing with Odoo's invoicing functionality.

Each subscription can generate invoices based on its billing schedule.

The invoice workflow includes:

1. Creating an invoice from a subscription.
2. Associating the invoice with the relevant customer.
3. Calculating the invoice amount based on subscription lines.
4. Managing invoice dates and due dates.
5. Tracking invoice and payment status.

Invoices can be accessed through the **Invoices** menu.

## Revenue Analysis

The Analysis section provides an overview of subscription revenue and related performance information.

Users can explore subscription revenue information and monitor recurring revenue through the available reporting features.

The subscription form also displays Monthly Recurring Revenue (MRR), helping users understand the recurring revenue associated with subscriptions.

## Project Structure

The project is organized around an Odoo module and its supporting configuration.

```text
brightloop-odoo-starter/
│
└── brightloop/
    ├── docker-compose.yml
    ├── addons/
    │   └── brightloop/
    │       ├── __init__.py
    │       ├── __manifest__.py
    │       ├── models/
    │       ├── views/
    │       ├── security/
    │       ├── data/
    │       └── demo/
    │
    └── README.md
```

*Note: The directory structure above is illustrative. Actual filenames and folders may vary depending on your project version.*

## Technologies Used

| Technology | Purpose |
|---|---|
| Odoo 17 Community | ERP platform and subscription management |
| Python | Backend business logic |
| PostgreSQL | Database management |
| XML | Odoo views and module configuration |
| Docker | Containerized development environment |
| Docker Compose | Running Odoo and PostgreSQL together |

## Troubleshooting

### Odoo is not starting

- Ensure Docker Desktop is running.
- Verify that Docker Engine is active.
- Run `docker compose ps` to check container status.
- Review logs using `docker compose logs -f odoo`.

### Brightloop is not visible in Apps

- Activate Developer Mode.
- Open Apps.
- Click Update Apps List.
- Remove the Apps filter.
- Search for Brightloop again.

### Demo data is not loading

- Verify that the Brightloop module is installed.
- Check whether the demo loader has already been executed.
- Review the Odoo logs for errors.

### Subscription confirmation fails

- Verify that the selected plan is available on the current date.
- Ensure that at least one subscription line exists.
- Check whether the total quantity meets the plan's minimum quantity.

### Recurring invoice is not generated

- Verify that the subscription is Active.
- Check the Next Invoice Date.
- Confirm that scheduled automation is running.
- Review the Odoo server logs.

## Resetting the Development Environment

To completely reset the local Docker environment:

```bash
docker compose down -v
docker compose up -d
```

**Warning:** The `-v` option removes Docker Compose-managed volumes, including the database volume. All database records stored there may be permanently lost.

Use this command only when you intentionally want to start with a fresh development environment.

## Future Enhancements

Potential improvements for future versions include:

- Online payment gateway integration.
- Customer self-service subscription portal.
- Automated renewal notifications.
- Email reminders for upcoming payments.
- Advanced revenue analytics.
- Subscription cancellation requests.
- Customer membership history.
- Enhanced subscription reporting.

## Author

**Arunachalam.S**

Project: Brightloop Subscriptions  
Platform: Odoo 17 Community Edition

## License

This project is developed as an educational and demonstration project. Refer to the repository's license file for applicable usage and distribution terms.

---

**Brightloop Subscriptions — Simplifying Membership and Recurring Billing Management with Odoo.**
