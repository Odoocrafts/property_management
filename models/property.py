from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime

class Property(models.Model):
    _name = 'property.property'
    _description = 'Property'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'name'

    name = fields.Char(string='Property Name', required=True, tracking=True)
    code = fields.Char(string='Property Code', readonly=True, copy=False, default=lambda self: _('New'))
    
    # Property Location and Structure
    building_name = fields.Char(string='Building Name', tracking=True)
    street = fields.Char(string='Street', tracking=True)
    street2 = fields.Char(string='Street 2', tracking=True)
    city = fields.Char(string='City', tracking=True)
    state_id = fields.Many2one('res.country.state', string='State', tracking=True)
    zip = fields.Char(string='ZIP', tracking=True)
    country_id = fields.Many2one('res.country', string='Country', tracking=True)

    # Property Details
    type = fields.Selection([
        ('apartment', 'Apartment'),
        ('house', 'House'),
        ('commercial', 'Commercial Space'),
        ('other', 'Other'),
    ], string='Property Type', default='apartment', tracking=True, required=True)
    
    ownership_type = fields.Selection([
        ('owned', 'Owned'),
        ('leased', 'Leased'),
    ], string='Ownership Type', default='leased', tracking=True, required=True)
    
    total_area = fields.Float(string='Total Area (sqm)', tracking=True)
    
    description = fields.Text(string='Description')
    
    # Dates
    acquisition_date = fields.Date(string='Acquisition Date', tracking=True)
    
    # Financial Info
    purchase_price = fields.Float(string='Purchase/Lease Price', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id.id)
    
    # Status Info
    state = fields.Selection([
        ('draft', 'Draft'),
        ('available', 'Available'),
        ('occupied', 'Fully Occupied'),
        ('partially_occupied', 'Partially Occupied'),
        ('under_maintenance', 'Under Maintenance'),
        ('inactive', 'Inactive'),
    ], string='Status', default='draft', tracking=True)
    
    # Owner/Landlord
    partner_id = fields.Many2one('res.partner', string='Landlord/Owner', tracking=True)
    
    # Company (multi-company support)
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company.id)
    
    # Units/Rooms
    unit_ids = fields.One2many('property.unit', 'property_id', string='Units')
    unit_count = fields.Integer(string='Number of Units', compute='_compute_unit_count', store=True)
    
    # Maintenance
    maintenance_ids = fields.One2many('property.maintenance', 'property_id', string='Maintenance Requests')
    maintenance_count = fields.Integer(string='Maintenance Count', compute='_compute_maintenance_count')
    
    # Financial Overview
    total_expected_revenue = fields.Monetary(string='Total Expected Revenue', compute='_compute_financial_overview', store=True)
    total_expenses = fields.Monetary(string='Total Expenses', compute='_compute_financial_overview', store=True)
    monthly_cash_flow = fields.Monetary(string='Monthly Cash Flow', compute='_compute_monthly_cash_flow', store=True)
    
    # Documents
    attachment_ids = fields.Many2many('ir.attachment', string='Documents')
    
    # Image
    image = fields.Binary(string="Property Image", attachment=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('property.property') or _('New')
        return super(Property, self).create(vals_list)
    
    @api.depends('unit_ids')
    def _compute_unit_count(self):
        for property in self:
            property.unit_count = len(property.unit_ids)
            
            # Update property status based on unit occupancy
            if property.unit_count == 0:
                property.state = 'available'
            else:
                occupied_units = property.unit_ids.filtered(lambda u: u.state == 'occupied')
                if not occupied_units:
                    property.state = 'available'
                elif len(occupied_units) == property.unit_count:
                    property.state = 'occupied'
                else:
                    property.state = 'partially_occupied'
    
    def _compute_maintenance_count(self):
        for property in self:
            property.maintenance_count = len(property.maintenance_ids)
            
    @api.depends('unit_ids.expected_revenue', 'unit_ids.expenses')
    def _compute_financial_overview(self):
        for property in self:
            property.total_expected_revenue = sum(property.unit_ids.mapped('expected_revenue'))
            property.total_expenses = sum(property.unit_ids.mapped('expenses'))
            
    @api.depends('total_expected_revenue', 'total_expenses')
    def _compute_monthly_cash_flow(self):
        for property in self:
            property.monthly_cash_flow = (property.total_expected_revenue - property.total_expenses) / 12 if property.total_expected_revenue or property.total_expenses else 0
            
    def action_view_units(self):
        return {
            'name': _('Property Units'),
            'view_mode': 'tree,form',
            'res_model': 'property.unit',
            'domain': [('property_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_property_id': self.id},
        }
        
    def action_view_maintenance(self):
        return {
            'name': _('Maintenance Requests'),
            'view_mode': 'tree,form',
            'res_model': 'property.maintenance',
            'domain': [('property_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_property_id': self.id},
        }
    
    def action_set_under_maintenance(self):
        self.write({'state': 'under_maintenance'})
    
    def action_set_available(self):
        self.write({'state': 'available'})
    
    def action_set_inactive(self):
        self.write({'state': 'inactive'})
