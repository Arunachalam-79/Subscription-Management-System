import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

PERIODS = {
    'daily': relativedelta(days=1),
    'weekly': relativedelta(weeks=1),
    'monthly': relativedelta(months=1),
    'yearly': relativedelta(years=1),
}
# How many "billing periods" fit in one month, used to normalise revenue (MRR).
MRR_FACTOR = {'daily': 365.0 / 12, 'weekly': 52.0 / 12, 'monthly': 1.0, 'yearly': 1.0 / 12}
REMINDER_DAYS = 14  # warn the salesperson this many days before expiry


class BrightloopSubscription(models.Model):
    _name = 'brightloop.subscription'
    _description = 'Subscription'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(default=lambda s: _('New'), readonly=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='Customer',
                                 required=True, tracking=True, index=True)
    user_id = fields.Many2one('res.users', string='Salesperson', tracking=True,
                              default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True)
    template_id = fields.Many2one('brightloop.quotation.template', string='Quotation Template')
    plan_id = fields.Many2one('brightloop.plan', required=True, tracking=True)
    origin_id = fields.Many2one('brightloop.subscription', string='Renewal Of',
                                copy=False, readonly=True)
    start_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    expiry_date = fields.Date(tracking=True)
    next_invoice_date = fields.Date(copy=False, index=True, tracking=True)
    close_date = fields.Date(copy=False, readonly=True)
    expiry_reminder_sent = fields.Boolean(copy=False)
    payment_term_id = fields.Many2one('account.payment.term')
    discount_id = fields.Many2one('brightloop.discount')
    note = fields.Html(string='Terms & Notes')
    state = fields.Selection(
        [('draft', 'Draft'), ('quotation', 'Quotation'), ('confirmed', 'Confirmed'),
         ('active', 'Active'), ('paused', 'Paused'), ('closed', 'Closed')],
        default='draft', required=True, tracking=True, index=True, copy=False)
    line_ids = fields.One2many('brightloop.subscription.line', 'subscription_id', copy=True)

    # plan switches, mirrored so the form can show/hide buttons
    plan_pausable = fields.Boolean(related='plan_id.pausable')
    plan_closable = fields.Boolean(related='plan_id.closable')
    plan_renewable = fields.Boolean(related='plan_id.renewable')

    amount_untaxed = fields.Monetary(compute='_compute_amount', store=True)
    amount_tax = fields.Monetary(compute='_compute_amount', store=True)
    amount_total = fields.Monetary(compute='_compute_amount', store=True)
    mrr = fields.Monetary(string='MRR', compute='_compute_mrr', store=True,
                          help='Monthly recurring revenue (untaxed). Only active subscriptions count.')

    invoice_ids = fields.One2many('account.move', 'subscription_id')
    invoice_count = fields.Integer(compute='_compute_invoice_stats', store=True)
    unpaid_count = fields.Integer(compute='_compute_invoice_stats', store=True)
    amount_due = fields.Monetary(compute='_compute_invoice_stats', store=True)

    # ------------------------------------------------------------ computes
    @api.depends('line_ids.subtotal', 'line_ids.price_tax', 'line_ids.price_total')
    def _compute_amount(self):
        for rec in self:
            rec.amount_untaxed = sum(rec.line_ids.mapped('subtotal'))
            rec.amount_tax = sum(rec.line_ids.mapped('price_tax'))
            rec.amount_total = sum(rec.line_ids.mapped('price_total'))

    @api.depends('state', 'amount_untaxed', 'plan_id.billing_period')
    def _compute_mrr(self):
        for rec in self:
            factor = MRR_FACTOR.get(rec.plan_id.billing_period, 0.0)
            rec.mrr = rec.amount_untaxed * factor if rec.state == 'active' else 0.0

    @api.depends('invoice_ids.state', 'invoice_ids.amount_residual')
    def _compute_invoice_stats(self):
        for rec in self:
            invoices = rec.sudo().invoice_ids
            unpaid = invoices.filtered(lambda m: m.state == 'posted' and m.amount_residual > 0)
            rec.invoice_count = len(invoices)
            rec.unpaid_count = len(unpaid)
            rec.amount_due = sum(unpaid.mapped('amount_residual'))

    @api.constrains('start_date', 'expiry_date')
    def _check_dates(self):
        for rec in self:
            if rec.expiry_date and rec.expiry_date < rec.start_date:
                raise ValidationError(_('The expiry date cannot be before the start date.'))

    # ------------------------------------------------------------ ORM
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('brightloop.subscription') or _('New')
        return super().create(vals_list)

    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id:
            self.plan_id = self.template_id.plan_id
            self.expiry_date = fields.Date.add(
                fields.Date.context_today(self), days=self.template_id.validity_days)
            self.line_ids = [(5, 0, 0)] + [
                (0, 0, {'product_id': l.product_id.id, 'quantity': l.quantity,
                        'price_unit': l.product_id.lst_price,
                        'tax_ids': [(6, 0, l.product_id.taxes_id.ids)]})
                for l in self.template_id.line_ids]

    # ------------------------------------------------------------ lifecycle
    def _transition(self, from_states, to_state):
        if isinstance(from_states, str):
            from_states = (from_states,)
        for rec in self:
            if rec.state not in from_states:
                raise UserError(_('%(name)s cannot move to "%(to)s" from its current state.',
                                  name=rec.name, to=dict(self._fields['state'].selection)[to_state]))
        self.write({'state': to_state})

    def action_quotation(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('Add at least one line to %s before making a quotation.', rec.name))
            rec.plan_id._check_available(fields.Date.context_today(rec))
        self._transition('draft', 'quotation')

    def action_confirm(self):
        for rec in self:
            qty = sum(rec.line_ids.mapped('quantity'))
            if qty < rec.plan_id.min_quantity:
                raise UserError(_(
                    'The plan "%(plan)s" requires a total quantity of at least %(min)s '
                    '(this subscription has %(qty)s).',
                    plan=rec.plan_id.name, min=rec.plan_id.min_quantity, qty=qty))
        self._transition('quotation', 'confirmed')

    def action_activate(self):
        self._transition('confirmed', 'active')
        for rec in self:
            rec.next_invoice_date = rec.start_date
            rec.message_post(body=_('Subscription activated.'))
        # bill the first period right away if it is already due
        self._bill_due()

    def action_draft(self):
        self._transition(('quotation', 'confirmed'), 'draft')

    def action_pause(self):
        for rec in self:
            if not rec.plan_id.pausable:
                raise UserError(_('The plan "%s" does not allow pausing.', rec.plan_id.name))
        self._transition('active', 'paused')
        for rec in self:
            rec.message_post(body=_('Subscription paused. No invoices are generated while paused.'))

    def action_resume(self):
        self._transition('paused', 'active')
        today = fields.Date.context_today(self)
        for rec in self:
            # do not bill the time it was paused
            if rec.next_invoice_date and rec.next_invoice_date < today:
                rec.next_invoice_date = today
            rec.message_post(body=_('Subscription resumed.'))

    def action_close(self):
        today = fields.Date.context_today(self)
        for rec in self:
            expired = rec.expiry_date and rec.expiry_date <= today
            if not rec.plan_id.closable and not expired:
                raise UserError(_(
                    '"%s" cannot be closed before its expiry date because the plan does '
                    'not allow early closing.', rec.name))
        self._do_close()

    def _do_close(self):
        self._transition(('active', 'paused'), 'closed')
        today = fields.Date.context_today(self)
        for rec in self:
            rec.close_date = today
            rec.next_invoice_date = False
            rec.message_post(body=_('Subscription closed.'))

    def action_renew(self):
        self.ensure_one()
        if not self.plan_id.renewable:
            raise UserError(_('The plan "%s" is not renewable.', self.plan_id.name))
        if self.state not in ('active', 'closed'):
            raise UserError(_('Only active or closed subscriptions can be renewed.'))
        today = fields.Date.context_today(self)
        if self.expiry_date and self.expiry_date >= today:
            new_start = self.expiry_date + relativedelta(days=1)
        else:
            new_start = today
        new_expiry = False
        if self.expiry_date:
            new_expiry = new_start + (self.expiry_date - self.start_date)
        renewal = self.copy({'start_date': new_start, 'expiry_date': new_expiry,
                             'origin_id': self.id})
        self.message_post(body=_('Renewed as %s.', renewal.name))
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': renewal.id,
            'view_mode': 'form',
        }

    # ------------------------------------------------------------ quotation
    def action_send_quotation(self):
        self.ensure_one()
        template = self.env.ref('brightloop_subscription.mail_template_quotation',
                                raise_if_not_found=False)
        ctx = {
            'default_model': self._name,
            'default_res_ids': self.ids,
            'default_composition_mode': 'comment',
            'default_email_layout_xmlid': 'mail.mail_notification_light',
        }
        if template:
            ctx['default_template_id'] = template.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    # ------------------------------------------------------------ billing
    def _prepare_invoice_vals(self, period_start):
        self.ensure_one()
        discount = self.discount_id
        apply_discount = discount and discount._is_applicable(self, period_start)
        lines = []
        for line in self.line_ids:
            rule_pct = 0.0
            if apply_discount and discount.discount_type == 'percent' and (
                    discount.apply_to == 'subscription' or line.product_id in discount.product_ids):
                rule_pct = discount.value
            # stack the line discount and the rule discount
            pct = 100.0 * (1 - (1 - (line.discount or 0.0) / 100.0) * (1 - rule_pct / 100.0))
            lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.product_id.display_name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'discount': pct,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
            }))
        if apply_discount and discount.discount_type == 'fixed':
            lines.append((0, 0, {
                'name': _('Discount: %s', discount.name),
                'quantity': 1, 'price_unit': -discount.value, 'tax_ids': [],
            }))
        return {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_payment_term_id': self.payment_term_id.id,
            'invoice_date': period_start,
            'subscription_id': self.id,
            'billing_period_start': period_start,
            'invoice_origin': self.name,
            'invoice_user_id': self.user_id.id,
            'invoice_line_ids': lines,
        }, bool(apply_discount)

    def _generate_invoice(self):
        """Create the invoice for the current period (idempotent)."""
        self.ensure_one()
        period_start = self.next_invoice_date
        # Staff are not accountants: invoices are created with elevated rights.
        Move = self.env['account.move'].sudo().with_company(self.company_id)
        exists = Move.search_count([
            ('subscription_id', '=', self.id),
            ('billing_period_start', '=', period_start)])
        if not exists:
            vals, used = self._prepare_invoice_vals(period_start)
            move = Move.create(vals)
            if used:
                self.discount_id.sudo().usage_count += 1
            self.message_post(body=_('Invoice %(inv)s generated for the period starting %(date)s.',
                                     inv=move.name if move.name != '/' else _('(draft)'),
                                     date=period_start))
            if self.plan_id.auto_post:
                move.action_post()
                if self.plan_id.auto_send:
                    self._send_invoice_mail(move)
        self.next_invoice_date = period_start + PERIODS[self.plan_id.billing_period]
        if self.expiry_date and self.next_invoice_date > self.expiry_date:
            # Last period billed. The subscription stays active until its expiry
            # date; the daily housekeeping job closes it then (if auto_close).
            self.next_invoice_date = False

    def _send_invoice_mail(self, move):
        template = self.env.ref('account.email_template_edi_invoice', raise_if_not_found=False)
        if not (template and move.partner_id.email):
            return
        try:
            with self.env.cr.savepoint():
                template.sudo().send_mail(move.id, force_send=False)
        except Exception:
            _logger.exception('Could not queue the invoice email for %s', move.name)

    def _bill_due(self, today=None):
        """Generate every invoice that is due (catches up missed periods)."""
        today = today or fields.Date.context_today(self)
        for sub in self:
            while sub.state == 'active' and sub.next_invoice_date \
                    and sub.next_invoice_date <= today:
                sub._generate_invoice()

    @api.model
    def _cron_generate_invoices(self):
        today = fields.Date.context_today(self)
        due = self.search([('state', '=', 'active'),
                           ('next_invoice_date', '!=', False),
                           ('next_invoice_date', '<=', today)])
        for sub in due:
            try:
                with self.env.cr.savepoint():
                    sub._bill_due(today)
            except Exception:
                _logger.exception('Billing failed for %s', sub.name)

    @api.model
    def _cron_housekeeping(self):
        """Close expired subscriptions and warn about those about to expire."""
        today = fields.Date.context_today(self)
        expired = self.search([('state', 'in', ('active', 'paused')),
                               ('expiry_date', '<', today),
                               ('plan_id.auto_close', '=', True)])
        for sub in expired:
            try:
                with self.env.cr.savepoint():
                    sub._do_close()
            except Exception:
                _logger.exception('Auto-close failed for %s', sub.name)

        soon = self.search([('state', '=', 'active'),
                            ('expiry_date', '>=', today),
                            ('expiry_date', '<=', today + relativedelta(days=REMINDER_DAYS)),
                            ('expiry_reminder_sent', '=', False)])
        for sub in soon:
            try:
                with self.env.cr.savepoint():
                    sub.activity_schedule(
                        'mail.mail_activity_data_todo',
                        date_deadline=sub.expiry_date,
                        summary=_('Subscription %s expires soon', sub.name),
                        note=_('Contact %s about renewing this subscription.', sub.partner_id.name),
                        user_id=(sub.user_id or self.env.user).id)
                    sub.expiry_reminder_sent = True
            except Exception:
                _logger.exception('Expiry reminder failed for %s', sub.name)

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('subscription_id', '=', self.id)],
            'context': {'default_move_type': 'out_invoice'},
        }

    def action_view_unpaid_invoices(self):
        action = self.action_view_invoices()
        action['name'] = _('Unpaid Invoices')
        action['domain'] = [('subscription_id', '=', self.id),
                            ('state', '=', 'posted'), ('amount_residual', '>', 0)]
        return action


class BrightloopSubscriptionLine(models.Model):
    _name = 'brightloop.subscription.line'
    _description = 'Subscription Line'

    subscription_id = fields.Many2one('brightloop.subscription', ondelete='cascade', index=True)
    currency_id = fields.Many2one(related='subscription_id.currency_id')
    product_id = fields.Many2one('product.product', required=True)
    quantity = fields.Float(default=1.0)
    price_unit = fields.Float(string='Unit Price')
    discount = fields.Float(string='Disc. %')
    tax_ids = fields.Many2many('account.tax', string='Taxes')
    subtotal = fields.Monetary(string='Subtotal', compute='_compute_amounts', store=True)
    price_tax = fields.Monetary(string='Tax', compute='_compute_amounts', store=True)
    price_total = fields.Monetary(string='Total', compute='_compute_amounts', store=True)

    @api.constrains('quantity', 'discount')
    def _check_values(self):
        for rec in self:
            if rec.quantity < 0:
                raise ValidationError(_('The quantity cannot be negative.'))
            if not 0.0 <= rec.discount <= 100.0:
                raise ValidationError(_('The discount must be between 0 and 100%.'))

    @api.depends('quantity', 'price_unit', 'discount', 'tax_ids',
                 'subscription_id.partner_id', 'subscription_id.currency_id')
    def _compute_amounts(self):
        for rec in self:
            price = rec.price_unit * (1 - (rec.discount or 0.0) / 100.0)
            taxes = rec.tax_ids.compute_all(
                price, currency=rec.currency_id or None, quantity=rec.quantity,
                product=rec.product_id, partner=rec.subscription_id.partner_id)
            rec.subtotal = taxes['total_excluded']
            rec.price_tax = taxes['total_included'] - taxes['total_excluded']
            rec.price_total = taxes['total_included']

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.lst_price  # includes variant price extra
            self.tax_ids = self.product_id.taxes_id
