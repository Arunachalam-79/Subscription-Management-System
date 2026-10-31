import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEMO_REF = 'BL-DEMO'

CUSTOMERS = [
    'Madras Analytics Pvt Ltd', 'Kaveri Foods', 'Marina Logistics', 'Chola Retail',
    'Zenith Textiles', 'Coromandel Pharma', 'Bay Bridge Media', 'Sundaram Steel',
    'Nilgiri Tea Co', 'Velachery Labs', 'Anna Nagar Bakers', 'Mylapore Ventures',
    'Triplicane Tech',
]

PRODUCTS = {  # key: (name, price)
    'starter': ('Brightloop Starter Seat', 499.0),
    'pro': ('Brightloop Pro Seat', 1299.0),
    'support': ('Priority Support', 2999.0),
    'analytics': ('Analytics Add-on', 1999.0),
}

PLANS = {  # key: values
    'starter': dict(name='Starter Monthly', price=499, billing_period='monthly', min_quantity=1,
                    closable=True, renewable=True, pausable=False, auto_post=True, sequence=10,
                    description='Entry plan for small teams. Billed monthly.'),
    'pro': dict(name='Pro Monthly', price=1299, billing_period='monthly', min_quantity=3,
                closable=True, renewable=True, pausable=True, auto_post=True, sequence=20,
                description='For growing teams (3+ seats). Can be paused and renewed.'),
    'annual': dict(name='Business Annual', price=14999, billing_period='yearly', min_quantity=5,
                   closable=False, renewable=True, pausable=False, auto_close=True,
                   auto_post=True, sequence=30,
                   description='Yearly commitment (5+ seats). Locked in, closes at expiry.'),
    'weekly': dict(name='Weekly Pilot', price=250, billing_period='weekly', min_quantity=1,
                   closable=True, renewable=False, pausable=True, auto_post=True, sequence=40,
                   description='Short pilot billed every week.'),
}

# customer, plan, lines [(product, qty)], start offset, discount key, final state, expiry, payment policy
SUBSCRIPTIONS = [
    ('Madras Analytics Pvt Ltd', 'pro', [('pro', 6), ('support', 1)], {'months': 8}, 'welcome', 'active', None, 'except_last'),
    ('Kaveri Foods', 'starter', [('starter', 4)], {'months': 6}, None, 'active', None, 'all'),
    ('Marina Logistics', 'annual', [('pro', 10), ('analytics', 1)], {'months': 11}, None, 'active', {'days': 10}, 'all'),
    ('Chola Retail', 'pro', [('pro', 5), ('analytics', 1)], {'months': 5}, None, 'active', None, 'except_last2'),
    ('Zenith Textiles', 'pro', [('pro', 3)], {'months': 3}, None, 'paused', None, 'all'),
    ('Coromandel Pharma', 'starter', [('starter', 2)], {'months': 7}, None, 'closed', {'months': -2}, 'all'),
    ('Bay Bridge Media', 'weekly', [('starter', 2)], {'weeks': 6}, None, 'active', None, 'except_last2'),
    ('Sundaram Steel', 'pro', [('pro', 8), ('support', 1), ('analytics', 1)], {'months': 3}, 'loyalty', 'active', None, 'except_last'),
    ('Nilgiri Tea Co', 'starter', [('starter', 5)], {'months': 2}, None, 'active', None, 'none'),
    ('Triplicane Tech', 'pro', [('pro', 4), ('support', 1)], {'months': 1}, None, 'active', None, 'all'),
    ('Velachery Labs', 'pro', [('pro', 3), ('analytics', 1)], {}, None, 'quotation', None, 'all'),
    ('Anna Nagar Bakers', 'starter', [('starter', 3)], {}, None, 'confirmed', None, 'all'),
    ('Mylapore Ventures', 'annual', [('pro', 6)], {}, None, 'draft', None, 'all'),
]


class BrightloopDemo(models.AbstractModel):
    _name = 'brightloop.demo'
    _description = 'Brightloop Demo Data Loader'

    @api.model
    def load(self):
        """Create customers, products, plans, discounts, templates and subscriptions
        in every state, with backdated invoices and payments, so every screen has data."""
        self = self.sudo()
        if self.env['res.partner'].search_count([('ref', '=', DEMO_REF)]):
            raise UserError(_('Demo data is already loaded. To start over, create a new database.'))

        today = fields.Date.context_today(self)
        env = self.env
        term = env['account.payment.term'].search([('name', 'ilike', '30 Days')], limit=1)

        partners = {}
        for name in CUSTOMERS:
            slug = ''.join(c for c in name.lower() if c.isalnum())
            partners[name] = env['res.partner'].create({
                'name': name, 'ref': DEMO_REF, 'company_type': 'company',
                'email': 'billing@%s.example.com' % slug})

        products = {k: env['product.product'].create({
            'name': n, 'type': 'service', 'lst_price': p}) for k, (n, p) in PRODUCTS.items()}
        plans = {k: env['brightloop.plan'].create(v) for k, v in PLANS.items()}

        discounts = {
            'welcome': env['brightloop.discount'].create({
                'name': 'WELCOME10 - 10% off', 'discount_type': 'percent', 'value': 10,
                'usage_limit': 100}),
            'loyalty': env['brightloop.discount'].create({
                'name': 'LOYALTY500 - 500 off orders above 5000', 'discount_type': 'fixed',
                'value': 500, 'min_purchase': 5000}),
        }
        env['brightloop.quotation.template'].create([
            {'name': 'Starter Team (3 seats)', 'plan_id': plans['starter'].id, 'validity_days': 30,
             'line_ids': [(0, 0, {'product_id': products['starter'].id, 'quantity': 3})]},
            {'name': 'Pro Bundle', 'plan_id': plans['pro'].id, 'validity_days': 30,
             'line_ids': [(0, 0, {'product_id': products['pro'].id, 'quantity': 5}),
                          (0, 0, {'product_id': products['support'].id, 'quantity': 1})]},
        ])

        created = invoices = paid = 0
        for (cust, plan_key, lines, offset, disc_key, final, expiry, policy) in SUBSCRIPTIONS:
            start = today - relativedelta(**offset) if offset else today
            expiry_date = False
            if expiry:
                # closed one: expiry in the past relative to start; others: relative to today
                expiry_date = (start + relativedelta(months=5)) if final == 'closed' \
                    else today + relativedelta(**expiry)
            sub = env['brightloop.subscription'].create({
                'partner_id': partners[cust].id,
                'plan_id': plans[plan_key].id,
                'start_date': start,
                'expiry_date': expiry_date,
                'payment_term_id': term.id,
                'discount_id': discounts[disc_key].id if disc_key else False,
                'line_ids': [(0, 0, {
                    'product_id': products[p].id, 'quantity': q,
                    'price_unit': products[p].lst_price,
                    'tax_ids': [(6, 0, products[p].taxes_id.ids)]}) for p, q in lines],
            })
            created += 1
            if final != 'draft':
                sub.action_quotation()
            if final in ('confirmed', 'active', 'paused', 'closed'):
                sub.action_confirm()
            if final in ('active', 'paused', 'closed'):
                sub.action_activate()
                n_inv, n_paid = self._settle(sub, policy, today)
                invoices += n_inv
                paid += n_paid
                if final == 'paused':
                    sub.action_pause()
                elif final == 'closed':
                    sub._do_close()
                    sub.close_date = expiry_date

        # schedules the "expiring soon" to-do for the annual subscription
        env['brightloop.subscription']._cron_housekeeping()

        message = _('%(subs)s subscriptions, %(inv)s invoices (%(paid)s paid) created. '
                    'Open Brightloop > Subscriptions.', subs=created, inv=invoices, paid=paid)
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': _('Demo data loaded'), 'message': message,
                       'type': 'success', 'sticky': False,
                       'next': {'type': 'ir.actions.client', 'tag': 'reload'}},
        }

    @api.model
    def _settle(self, sub, policy, today):
        """Register payments on the subscription's invoices according to the policy."""
        invoices = sub.invoice_ids.sorted(lambda m: m.billing_period_start)
        to_pay = {
            'all': invoices,
            'none': invoices.browse(),
            'except_last': invoices[:-1],
            'except_last2': invoices[:-2],
        }[policy]
        paid = 0
        for inv in to_pay:
            if inv.state != 'posted' or inv.payment_state in ('paid', 'in_payment'):
                continue
            try:
                with self.env.cr.savepoint():
                    wizard = self.env['account.payment.register'].with_context(
                        active_model='account.move', active_ids=inv.ids).create({
                            'payment_date': min(inv.invoice_date + timedelta(days=3), today)})
                    wizard.action_create_payments()
                    paid += 1
            except Exception:
                _logger.warning('Demo payment failed for %s', inv.name, exc_info=True)
        return len(invoices), paid
