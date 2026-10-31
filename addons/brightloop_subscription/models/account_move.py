from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    subscription_id = fields.Many2one('brightloop.subscription', index=True, copy=False)
    billing_period_start = fields.Date(copy=False)

    _sql_constraints = [
        ('brightloop_unique_period',
         'unique(subscription_id, billing_period_start)',
         'This subscription was already invoiced for this period.'),
    ]
