from odoo import api, fields, models


class BrightloopDiscount(models.Model):
    _name = 'brightloop.discount'
    _description = 'Discount Rule'

    name = fields.Char(required=True)
    discount_type = fields.Selection(
        [('percent', 'Percentage'), ('fixed', 'Fixed Amount')],
        required=True, default='percent')
    value = fields.Float(required=True)
    min_purchase = fields.Float(string='Minimum Purchase')
    min_quantity = fields.Float(string='Minimum Quantity')
    date_start = fields.Date()
    date_end = fields.Date()
    usage_limit = fields.Integer(help='0 = unlimited')
    usage_count = fields.Integer(readonly=True, copy=False)
    apply_to = fields.Selection(
        [('subscription', 'Whole Subscription'), ('product', 'Specific Products')],
        default='subscription', required=True)
    product_ids = fields.Many2many('product.product', string='Products')
    active = fields.Boolean(default=True)

    def _is_applicable(self, subscription, today=None):
        """True if this rule currently applies to the given subscription."""
        self.ensure_one()
        today = today or fields.Date.context_today(self)
        if not self.active:
            return False
        if self.date_start and today < self.date_start:
            return False
        if self.date_end and today > self.date_end:
            return False
        if self.usage_limit and self.usage_count >= self.usage_limit:
            return False
        lines = subscription.line_ids
        if self.apply_to == 'product':
            lines = lines.filtered(lambda l: l.product_id in self.product_ids)
            if not lines:
                return False
        if self.min_purchase and sum(lines.mapped('subtotal')) < self.min_purchase:
            return False
        if self.min_quantity and sum(lines.mapped('quantity')) < self.min_quantity:
            return False
        return True
