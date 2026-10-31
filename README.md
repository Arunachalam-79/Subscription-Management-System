# Brightloop Subscriptions - Odoo 17 starter

## Run it (Windows, Docker Desktop)
1. Install Docker Desktop (enable the WSL2 backend) and restart if asked.
2. Unzip this folder, open a terminal inside it (VS Code: Terminal > New Terminal).
3. `docker compose up -d`
4. Open http://localhost:8069 -> Create database
   - Master password: `admin`, DB name e.g. `brightloop`, tick "Demo data" OFF
   - Set your email/password.
5. Settings > Activate the Developer Mode.
6. Apps > Update Apps List > remove the "Apps" filter > search "Brightloop" > Install.
   (Installing pulls in Sales/Invoicing dependencies automatically.)
7. Open the Brightloop menu.

## Daily dev commands
- Logs:                `docker compose logs -f odoo`
- Restart after .py edits: `docker compose restart odoo`
- Upgrade module after model/XML edits:
  `docker compose exec odoo odoo -c /etc/odoo/odoo.conf -d brightloop -u brightloop_subscription --stop-after-init`
  then `docker compose restart odoo`
- Stop: `docker compose down`   (add `-v` to wipe all data)

## Quick test of the core flow
1. Invoicing/Sales: create product "Odoo CRM" with attribute Brand = Odoo/Other, price extra 560 on Odoo.
2. Brightloop > Configuration > Plans: create "Monthly" (monthly, 100).
3. Subscriptions > New: customer, plan, add a line, start date today.
4. Click Make Quotation > Confirm > Activate.
5. Configuration > Run Billing Now -> invoice appears. Run again -> no duplicate.

## Folder map
- docker-compose.yml, config/odoo.conf  : Odoo + Postgres
- addons/brightloop_subscription/       : your module
  - models/   plan, discount, quotation_template, subscription(+billing), account_move
  - security/ groups (Admin/Staff), access rights, portal record rule
  - data/     sequence + cron (daily billing) + "Run Billing Now"
  - views/    list/form views and menus
