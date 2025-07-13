from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date, timedelta

class PropertyMaintenance(models.Model):
    _name = 'property.maintenance'
    _description = 'Property Maintenance'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'request_date desc, priority desc'
    
    name = fields.Char(string='Reference', required=True, copy=False, 
                      readonly=True, default=lambda self: _('New'))
    
    # Basic Information
    description = fields.Text(string='Description')
    solution = fields.Text(string='Solution')
    
    # Relations
    property_id = fields.Many2one('property.property', string='Property', tracking=True)
    unit_id = fields.Many2one('property.unit', string='Unit', 
                            domain="[('property_id', '=', property_id)]", tracking=True)
    request_by = fields.Many2one('res.partner', string='Requested By', tracking=True)
    assign_to = fields.Many2one('res.users', string='Assigned To', tracking=True)
    
    # Dates
    request_date = fields.Date(string='Request Date', default=fields.Date.today, tracking=True)
    schedule_date = fields.Date(string='Scheduled Date', tracking=True)
    start_date = fields.Datetime(string='Start Date', tracking=True)
    end_date = fields.Datetime(string='End Date', tracking=True)
    
    # Priority
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], string='Priority', default='1', tracking=True)
    
    # Type
    maintenance_type = fields.Selection([
        ('corrective', 'Corrective'),
        ('preventive', 'Preventive'),
        ('emergency', 'Emergency'),
        ('inspection', 'Inspection'),
        ('renovation', 'Renovation'),
        ('other', 'Other'),
    ], string='Maintenance Type', default='corrective', required=True, tracking=True)
    
    # Status
    state = fields.Selection([
        ('new', 'New'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='new', tracking=True)
    
    # Financial Information
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id.id)
    cost = fields.Monetary(string='Actual Cost', tracking=True)
    labor_cost = fields.Monetary(string='Labor Cost', tracking=True)
    materials_cost = fields.Monetary(string='Materials Cost', compute='_compute_materials_cost')
    total_cost = fields.Monetary(string='Total Cost', compute='_compute_total_cost')
    
    # Additional Details
    attachment_ids = fields.Many2many('ir.attachment', string='Documents')
    
    # Company (multi-company support)
    company_id = fields.Many2one('res.company', string='Company',
                                default=lambda self: self.env.company.id)
    
    # Checklist Items
    checklist_ids = fields.One2many('maintenance.checklist.item', 'maintenance_id', string='Checklist Items')
    
    # Materials
    material_ids = fields.One2many('maintenance.material', 'maintenance_id', string='Materials')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('property.maintenance') or _('New')
        return super(PropertyMaintenance, self).create(vals_list)
    
    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        if self.unit_id and self.unit_id.tenant_id:
            self.request_by = self.unit_id.tenant_id
    
    @api.depends('material_ids.subtotal')
    def _compute_materials_cost(self):
        for record in self:
            record.materials_cost = sum(record.material_ids.mapped('subtotal'))
    
    @api.depends('materials_cost', 'labor_cost')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = record.materials_cost + record.labor_cost
    
    def action_assign(self):
        self.write({
            'state': 'assigned',
        })
    
    def action_start(self):
        self.write({
            'state': 'in_progress',
            'start_date': fields.Datetime.now(),
        })
    
    def action_complete(self):
        self.write({
            'state': 'done',
            'end_date': fields.Datetime.now(),
        })
        
        # Update unit status if it was under maintenance
        if self.unit_id and self.unit_id.state == 'under_maintenance':
            # Check if there are any other open maintenance requests for this unit
            open_maintenance = self.search([
                ('unit_id', '=', self.unit_id.id),
                ('state', 'in', ['new', 'assigned', 'in_progress']),
                ('id', '!=', self.id)
            ], limit=1)
            
            if not open_maintenance:
                self.unit_id.write({'state': 'vacant'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def action_reopen(self):
        self.write({'state': 'new'})
    
    def action_create_invoice(self):
        """Create a vendor invoice for this maintenance request"""
        self.ensure_one()
        
        # You would add your vendor invoice creation logic here
        return {
            'name': _('Create Invoice'),
            'view_mode': 'form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'context': {
                'default_move_type': 'in_invoice',
                'default_ref': self.name,
            }
        }

    def _compute_access_url(self):
        super(PropertyMaintenance, self)._compute_access_url()
        for maintenance in self:
            maintenance.access_url = '/my/maintenance/%s' % maintenance.id

    def _get_report_base_filename(self):
        self.ensure_one()
        return '%s %s' % (_('Maintenance'), self.name)
