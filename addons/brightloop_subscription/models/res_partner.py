from odoo import _, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    subscription_count = fields.Integer(compute='_compute_subscription_count')

    def _compute_subscription_count(self):
        Subscription = self.env['brightloop.subscription']
        for partner in self:
            partner.subscription_count = Subscription.search_count(
                [('partner_id', 'child_of', partner.commercial_partner_id.id)]
            ) if partner.id else 0

    def action_view_subscriptions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Subscriptions'),
            'res_model': 'brightloop.subscription',
            'view_mode': 'tree,form',
            'domain': [('partner_id', 'child_of', self.commercial_partner_id.id)],
            'context': {'default_partner_id': self.id},
        }
