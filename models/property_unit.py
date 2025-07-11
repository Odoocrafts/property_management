from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date

class PropertyUnit(models.Model):
    _name = 'property.unit'
    _description = 'Property Unit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Unit Number/Name', required=True, tracking=True)
    code = fields.Char(string='Unit Code', readonly=True, copy=False, default=lambda self: _('New'))
    
    # Property Relationship
    property_id = fields.Many2one('property.property', string='Property', required=True, tracking=True)
    property_code = fields.Char(related='property_id.code', string='Property Code', store=True)
    property_building_name = fields.Char(related='property_id.building_name', string='Building Name', store=True)
    
    # Unit Details
    type = fields.Selection([
        ('studio', 'Studio'),
        ('1bhk', '1 Bedroom'),
        ('2bhk', '2 Bedroom'),
        ('3bhk', '3 Bedroom'),
        ('4bhk', '4+ Bedroom'),
        ('room', 'Single Room'),
        ('commercial', 'Commercial Space'),
        ('other', 'Other'),
    ], string='Unit Type', default='room', tracking=True)
    
    area = fields.Float(string='Area (sqm)', tracking=True)
    floor = fields.Integer(string='Floor Number', tracking=True)
    
    furnishing = fields.Selection([
        ('unfurnished', 'Unfurnished'),
        ('semifurnished', 'Semi-Furnished'),
        ('furnished', 'Fully Furnished'),
    ], string='Furnishing', default='unfurnished', tracking=True)
    
    description = fields.Text(string='Description')
    
    # Status
    state = fields.Selection([
        ('vacant', 'Vacant'),
        ('occupied', 'Occupied'),
        ('under_maintenance', 'Under Maintenance'),
        ('reserved', 'Reserved'),
        ('unavailable', 'Unavailable'),
    ], string='Status', default='vacant', tracking=True)
    
    # Amenities
    amenities = fields.Many2many('property.amenity', string='Amenities')
    
    # Financial Information
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id.id)
    
    rental_price = fields.Monetary(string='Rental Price', tracking=True)
    security_deposit = fields.Monetary(string='Security Deposit', tracking=True)
    
    expected_revenue = fields.Monetary(string='Expected Annual Revenue', compute='_compute_financial_metrics', store=True)
    expenses = fields.Monetary(string='Annual Expenses', compute='_compute_financial_metrics', store=True)
    
    # Contract Information
    active_contract_id = fields.Many2one('property.contract', string='Active Contract', 
                                       compute='_compute_active_contract', store=True)
    contract_ids = fields.One2many('property.contract', 'unit_id', string='Contracts')
    tenant_id = fields.Many2one('res.partner', string='Current Tenant', 
                               compute='_compute_active_contract', store=True)
    contract_start_date = fields.Date(related='active_contract_id.start_date', string='Contract Start', store=True)
    contract_end_date = fields.Date(related='active_contract_id.end_date', string='Contract End', store=True)
    days_to_expire = fields.Integer(string='Days to Expire', compute='_compute_days_to_expire')
    
    # Maintenance
    maintenance_ids = fields.One2many('property.maintenance', 'unit_id', string='Maintenance Requests')
    maintenance_count = fields.Integer(string='Maintenance Count', compute='_compute_maintenance_count')
    
    # Company (multi-company support)
    company_id = fields.Many2one('res.company', string='Company',
                                default=lambda self: self.env.company.id)
    
    # Images
    image = fields.Binary(string="Unit Image", attachment=True)
    
    # Utilities
    has_electricity_meter = fields.Boolean(string='Has Electricity Meter')
    electricity_meter_number = fields.Char(string='Electricity Meter Number')
    has_water_meter = fields.Boolean(string='Has Water Meter')
    water_meter_number = fields.Char(string='Water Meter Number')
    has_gas_meter = fields.Boolean(string='Has Gas Meter')
    gas_meter_number = fields.Char(string='Gas Meter Number')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('property.unit') or _('New')
        return super(PropertyUnit, self).create(vals_list)
    
    @api.depends('contract_ids', 'contract_ids.state')
    def _compute_active_contract(self):
        today = fields.Date.today()
        for unit in self:
            active_contract = unit.contract_ids.filtered(
                lambda c: c.state == 'active' and 
                c.start_date <= today and 
                (not c.end_date or c.end_date >= today)
            )
            unit.active_contract_id = active_contract[0] if active_contract else False
            unit.tenant_id = unit.active_contract_id.tenant_id if unit.active_contract_id else False
            
            # Update unit state based on contract status
            if unit.active_contract_id:
                unit.state = 'occupied'
            else:
                # Only change to vacant if it's not under maintenance or reserved
                if unit.state not in ['under_maintenance', 'reserved', 'unavailable']:
                    unit.state = 'vacant'
    
    def _compute_days_to_expire(self):
        today = fields.Date.today()
        for unit in self:
            if unit.active_contract_id and unit.active_contract_id.end_date and unit.active_contract_id.end_date >= today:
                unit.days_to_expire = (unit.active_contract_id.end_date - today).days
            else:
                unit.days_to_expire = 0
    
    @api.depends('rental_price', 'active_contract_id.rent_amount', 'active_contract_id.billing_cycle')
    def _compute_financial_metrics(self):
        for unit in self:
            # Calculate expected revenue based on rental price or active contract
            if unit.active_contract_id:
                if unit.active_contract_id.billing_cycle == 'monthly':
                    unit.expected_revenue = unit.active_contract_id.rent_amount * 12
                elif unit.active_contract_id.billing_cycle == 'quarterly':
                    unit.expected_revenue = unit.active_contract_id.rent_amount * 4
                elif unit.active_contract_id.billing_cycle == 'biannual':
                    unit.expected_revenue = unit.active_contract_id.rent_amount * 2
                else:  # annual
                    unit.expected_revenue = unit.active_contract_id.rent_amount
            else:
                # If no active contract, use the monthly rental price * 12
                unit.expected_revenue = unit.rental_price * 12
            
            # For expenses, for now we'll calculate from maintenance costs
            maintenance_expenses = sum(unit.maintenance_ids.filtered(
                lambda m: m.state in ['completed', 'in_progress'] and 
                m.date >= fields.Date.today().replace(month=1, day=1)
            ).mapped('cost'))
            unit.expenses = maintenance_expenses
    
    def _compute_maintenance_count(self):
        for unit in self:
            unit.maintenance_count = len(unit.maintenance_ids)
    
    def action_view_contracts(self):
        return {
            'name': _('Contracts'),
            'view_mode': 'tree,form',
            'res_model': 'property.contract',
            'domain': [('unit_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_unit_id': self.id, 'default_property_id': self.property_id.id},
        }
    
    def action_view_maintenance(self):
        return {
            'name': _('Maintenance Requests'),
            'view_mode': 'tree,form',
            'res_model': 'property.maintenance',
            'domain': [('unit_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_unit_id': self.id, 'default_property_id': self.property_id.id},
        }
    
    def action_set_under_maintenance(self):
        self.write({'state': 'under_maintenance'})
    
    def action_set_vacant(self):
        self.write({'state': 'vacant'})
    
    def action_set_reserved(self):
        self.write({'state': 'reserved'})


class PropertyAmenity(models.Model):
    _name = 'property.amenity'
    _description = 'Property Amenity'
    
    name = fields.Char(string='Amenity', required=True)
    description = fields.Text(string='Description')
    icon = fields.Char(string='Icon', help="Font Awesome icon name")
    
    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Amenity name already exists!"),
    ]
