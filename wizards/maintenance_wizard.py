from odoo import models, fields, api, _

class MaintenanceWizard(models.TransientModel):
    _name = 'property.maintenance.wizard'
    _description = 'Create Maintenance Request'
    
    property_id = fields.Many2one('property.property', string='Property', required=True)
    unit_id = fields.Many2one('property.unit', string='Unit', 
                            domain="[('property_id', '=', property_id)]")
    description = fields.Text(string='Description', required=True)
    maintenance_type = fields.Selection([
        ('corrective', 'Corrective'),
        ('preventive', 'Preventive'),
        ('emergency', 'Emergency'),
        ('inspection', 'Inspection'),
        ('renovation', 'Renovation'),
        ('other', 'Other'),
    ], string='Maintenance Type', default='corrective', required=True)
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], string='Priority', default='1')
    schedule_date = fields.Date(string='Scheduled Date')
    request_by = fields.Many2one('res.partner', string='Requested By')
    cost = fields.Float(string='Estimated Cost')
    
    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        if self.unit_id and self.unit_id.tenant_id:
            self.request_by = self.unit_id.tenant_id.id
    
    def action_create_maintenance(self):
        self.ensure_one()
        
        vals = {
            'description': self.description,
            'property_id': self.property_id.id,
            'maintenance_type': self.maintenance_type,
            'priority': self.priority,
            'state': 'new',
            'cost': self.cost,
        }
        
        if self.unit_id:
            vals['unit_id'] = self.unit_id.id
            
        if self.request_by:
            vals['request_by'] = self.request_by.id
            
        if self.schedule_date:
            vals['schedule_date'] = self.schedule_date
            
        maintenance = self.env['property.maintenance'].create(vals)
        
        return {
            'name': _('Maintenance Request'),
            'view_mode': 'form',
            'res_model': 'property.maintenance',
            'res_id': maintenance.id,
            'type': 'ir.actions.act_window',
        }
