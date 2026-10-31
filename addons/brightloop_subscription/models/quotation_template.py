from odoo import fields, models


class BrightloopQuotationTemplate(models.Model):
    _name = 'brightloop.quotation.template'
    _description = 'Quotation Template'

    name = fields.Char(required=True)
    plan_id = fields.Many2one('brightloop.plan', required=True)
    validity_days = fields.Integer(default=30)
    line_ids = fields.One2many('brightloop.quotation.template.line', 'template_id')


class BrightloopQuotationTemplateLine(models.Model):
    _name = 'brightloop.quotation.template.line'
    _description = 'Quotation Template Line'

    template_id = fields.Many2one('brightloop.quotation.template', ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True)
    quantity = fields.Float(default=1.0)
