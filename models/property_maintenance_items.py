# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class MaintenanceChecklistItem(models.Model):
    _name = 'maintenance.checklist.item'
    _description = 'Maintenance Checklist Item'
    
    name = fields.Char(string='Task', required=True)
    is_done = fields.Boolean(string='Completed')
    done_date = fields.Datetime(string='Completion Date', readonly=True)
    maintenance_id = fields.Many2one('property.maintenance', string='Maintenance Request')
    
    @api.onchange('is_done')
    def _onchange_is_done(self):
        if self.is_done and not self.done_date:
            self.done_date = fields.Datetime.now()
        elif not self.is_done:
            self.done_date = False


class MaintenanceMaterial(models.Model):
    _name = 'maintenance.material'
    _description = 'Maintenance Material'
    
    product_id = fields.Many2one('product.product', string='Material', required=True)
    quantity = fields.Float(string='Quantity', default=1.0)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure', 
                                related='product_id.uom_id')
    price_unit = fields.Float(string='Unit Price')
    currency_id = fields.Many2one('res.currency', related='maintenance_id.currency_id', store=True)
    subtotal = fields.Monetary(string='Subtotal', compute='_compute_subtotal', store=True)
    maintenance_id = fields.Many2one('property.maintenance', string='Maintenance Request')
    
    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = record.quantity * record.price_unit
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.standard_price
