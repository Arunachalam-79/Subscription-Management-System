from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class BrightloopPlan(models.Model):
    _name = 'brightloop.plan'
    _description = 'Recurring Plan'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(help='Shown to staff when picking a plan.')
    price = fields.Float(string='Reference Price', required=True,
                         help='Informational list price. Billing is driven by the subscription lines.')
    billing_period = fields.Selection(
        [('daily', 'Daily'), ('weekly', 'Weekly'),
         ('monthly', 'Monthly'), ('yearly', 'Yearly')],
        required=True, default='monthly')
    min_quantity = fields.Integer(
        default=1, help='Minimum total quantity a subscription must have to be confirmed.')
    date_start = fields.Date(string='Available From')
    date_end = fields.Date(string='Available Until')
    auto_close = fields.Boolean(help='Close the subscription automatically when it expires.')
    closable = fields.Boolean(string='Can be closed early')
    pausable = fields.Boolean()
    renewable = fields.Boolean()
    auto_post = fields.Boolean(
        string='Auto-confirm invoices',
        help='Post generated invoices automatically instead of leaving them as drafts.')
    auto_send = fields.Boolean(
        string='Email invoices',
        help='Email the invoice to the customer when it is auto-confirmed.')
    active = fields.Boolean(default=True)
    subscription_count = fields.Integer(compute='_compute_subscription_count')

    @api.constrains('price', 'min_quantity')
    def _check_values(self):
        for plan in self:
            if plan.price < 0:
                raise ValidationError(_('The plan price cannot be negative.'))
            if plan.min_quantity < 0:
                raise ValidationError(_('The minimum quantity cannot be negative.'))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for plan in self:
            if plan.date_start and plan.date_end and plan.date_end < plan.date_start:
                raise ValidationError(_('"Available Until" must be after "Available From".'))

    def _compute_subscription_count(self):
        for plan in self:
            plan.subscription_count = self.env['brightloop.subscription'].search_count(
                [('plan_id', '=', plan.id)])

    def _check_available(self, date):
        """Raise if the plan cannot be sold on the given date."""
        for plan in self:
            if (plan.date_start and date < plan.date_start) or \
                    (plan.date_end and date > plan.date_end):
                raise UserError(_('The plan "%s" is not available on %s.', plan.name, date))

    def action_view_subscriptions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Subscriptions'),
            'res_model': 'brightloop.subscription',
            'view_mode': 'tree,form',
            'domain': [('plan_id', '=', self.id)],
            'context': {'default_plan_id': self.id},
        }
