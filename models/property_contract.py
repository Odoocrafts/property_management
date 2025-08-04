from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date

class PropertyContract(models.Model):
    _name = 'property.contract'
    _description = 'Property Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, id desc'
    
    name = fields.Char(string='Contract Reference', required=True, copy=False, 
                      default=lambda self: _('New'))
    
    # Contract Type
    contract_type = fields.Selection([
        ('rental', 'Rental Contract'),
        ('lease', 'Lease Contract'),
        ('sale', 'Sale Contract'),
    ], string='Contract Type', default='rental', required=True, tracking=True)
    
    # Relations
    property_id = fields.Many2one('property.property', string='Property', required=True, tracking=True)
    unit_id = fields.Many2one('property.unit', string='Property Unit', required=True, tracking=True,
                            domain="[('property_id', '=', property_id), ('state', 'not in', ['occupied', 'unavailable'])]")
    tenant_id = fields.Many2one('res.partner', string='Tenant', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Customer', tracking=True)  # For sale contracts
    booking_id = fields.Many2one('property.booking', string='Source Booking', tracking=True)
    
    # Contract Duration
    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', tracking=True)
    duration_months = fields.Integer(string='Duration (months)', compute='_compute_duration', store=True)
    is_renewable = fields.Boolean(string='Renewable', default=True)
    
    # Financial Details
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id.id)
    rent_amount = fields.Monetary(string='Rent Amount', required=True, tracking=True)
    security_deposit = fields.Monetary(string='Security Deposit', tracking=True)
    
    billing_cycle = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('biannual', 'Bi-Annual'),
        ('annual', 'Annual'),
    ], string='Billing Cycle', default='monthly', required=True)
    
    # Payment Terms
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms')
    next_invoice_date = fields.Date(string='Next Invoice Date', compute='_compute_next_invoice_date')
    
    # Documents
    attachment_ids = fields.Many2many('ir.attachment', string='Documents')
    notes = fields.Text(string='Terms and Conditions')
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
        ('renewed', 'Renewed'),
    ], string='Status', default='draft', tracking=True)
    
    # Invoice Tracking
    invoice_ids = fields.One2many('account.move', 'property_contract_id', string='Invoices')
    invoice_count = fields.Integer(string='Invoice Count', compute='_compute_invoice_count')
    
    # Company (multi-company support)
    company_id = fields.Many2one('res.company', string='Company',
                                default=lambda self: self.env.company.id)
    
    # Related Contract (for renewals)
    previous_contract_id = fields.Many2one('property.contract', string='Previous Contract')
    renewed_contract_id = fields.Many2one('property.contract', string='Renewed Contract')
    is_renewal = fields.Boolean(string='Is Renewal', default=False)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('property.contract') or _('New')
        
        # Verify no active contracts exist for the unit
        for vals in vals_list:
            if 'unit_id' in vals and 'state' in vals and vals['state'] == 'active':
                unit = self.env['property.unit'].browse(vals['unit_id'])
                if unit.active_contract_id and unit.active_contract_id.state == 'active':
                    raise ValidationError(_('This unit already has an active contract. Please terminate it before creating a new one.'))
        
        contracts = super(PropertyContract, self).create(vals_list)
        
        # Update unit status when contract becomes active
        for contract in contracts:
            if contract.state == 'active':
                contract.unit_id.write({'state': 'occupied'})
                
        return contracts
    
    def write(self, vals):
        # If changing to active state, check that no other active contract exists for this unit
        if vals.get('state') == 'active':
            for contract in self:
                if contract.state != 'active':
                    unit = contract.unit_id
                    active_contract = self.search([
                        ('unit_id', '=', unit.id),
                        ('state', '=', 'active'),
                        ('id', '!=', contract.id)
                    ], limit=1)
                    if active_contract:
                        raise ValidationError(_('This unit already has an active contract. Please terminate it before activating this one.'))
        
        result = super(PropertyContract, self).write(vals)
        
        # Update unit status based on contract state changes
        if 'state' in vals:
            for contract in self:
                if vals['state'] == 'active':
                    contract.unit_id.write({'state': 'occupied'})
                elif vals['state'] in ['expired', 'terminated'] and contract.unit_id.state == 'occupied':
                    other_active = self.search([
                        ('unit_id', '=', contract.unit_id.id),
                        ('state', '=', 'active'),
                        ('id', '!=', contract.id)
                    ], limit=1)
                    if not other_active:
                        contract.unit_id.write({'state': 'vacant'})
        
        return result
    
    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for contract in self:
            if contract.start_date and contract.end_date:
                # Calculate months between dates
                months = (contract.end_date.year - contract.start_date.year) * 12
                months += contract.end_date.month - contract.start_date.month
                
                # Adjust for partial months
                if contract.end_date.day < contract.start_date.day:
                    months -= 1
                
                contract.duration_months = months
            else:
                contract.duration_months = 0
    
    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for contract in self:
            contract.invoice_count = len(contract.invoice_ids)
    
    def _compute_next_invoice_date(self):
        today = fields.Date.today()
        for contract in self:
            if contract.state != 'active':
                contract.next_invoice_date = False
                continue
                
            # Find the most recent invoice
            last_invoice = self.env['account.move'].search([
                ('property_contract_id', '=', contract.id),
                ('move_type', '=', 'out_invoice'),
                ('invoice_date', '<=', today)
            ], order='invoice_date desc', limit=1)
            
            if not last_invoice:
                # If no invoice yet, next invoice is the start date
                contract.next_invoice_date = contract.start_date
                continue
                
            # Calculate next invoice date based on billing cycle
            last_date = last_invoice.invoice_date
            if contract.billing_cycle == 'monthly':
                next_month = last_date.month + 1
                next_year = last_date.year
                if next_month > 12:
                    next_month = 1
                    next_year += 1
                contract.next_invoice_date = date(next_year, next_month, min(last_date.day, 28))
            elif contract.billing_cycle == 'quarterly':
                next_month = last_date.month + 3
                next_year = last_date.year
                if next_month > 12:
                    next_month = next_month - 12
                    next_year += 1
                contract.next_invoice_date = date(next_year, next_month, min(last_date.day, 28))
            elif contract.billing_cycle == 'biannual':
                next_month = last_date.month + 6
                next_year = last_date.year
                if next_month > 12:
                    next_month = next_month - 12
                    next_year += 1
                contract.next_invoice_date = date(next_year, next_month, min(last_date.day, 28))
            elif contract.billing_cycle == 'annual':
                contract.next_invoice_date = date(last_date.year + 1, last_date.month, min(last_date.day, 28))
    
    def action_view_invoices(self):
        return {
            'name': _('Invoices'),
            'view_mode': 'list,form',
            'res_model': 'account.move',
            'domain': [('property_contract_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_property_contract_id': self.id, 'default_partner_id': self.tenant_id.id},
        }
        
    def action_create_invoice(self):
        """Create an invoice for this contract"""
        self.ensure_one()
        
        invoice_vals = {
            'partner_id': self.tenant_id.id,
            'property_contract_id': self.id,
            'move_type': 'out_invoice',
            'invoice_date': fields.Date.today(),
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
        }
        
        if self.payment_term_id:
            invoice_vals['invoice_payment_term_id'] = self.payment_term_id.id
        
        # Prepare invoice line
        line_description = _('Rent for %s - %s') % (self.unit_id.name, self.property_id.name)
        if self.billing_cycle == 'monthly':
            line_description += _(' (Monthly: %s)') % fields.Date.today().strftime('%B %Y')
        elif self.billing_cycle == 'quarterly':
            quarter = ((fields.Date.today().month - 1) // 3) + 1
            line_description += _(' (Q%s %s)') % (quarter, fields.Date.today().year)
        elif self.billing_cycle == 'biannual':
            semester = 1 if fields.Date.today().month <= 6 else 2
            line_description += _(' (S%s %s)') % (semester, fields.Date.today().year)
        elif self.billing_cycle == 'annual':
            line_description += _(' (Annual: %s)') % fields.Date.today().year
        
        # Create invoice
        invoice = self.env['account.move'].create(invoice_vals)
        
        # Add invoice line
        invoice.write({
            'invoice_line_ids': [(0, 0, {
                'name': line_description,
                'quantity': 1,
                'price_unit': self.rent_amount,
            })]
        })
        
        return {
            'name': _('Invoice'),
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'type': 'ir.actions.act_window',
        }
    
    def action_activate(self):
        for contract in self:
            contract.state = 'active'
    
    def action_terminate(self):
        for contract in self:
            contract.state = 'terminated'
    
    def action_set_to_expired(self):
        for contract in self:
            contract.state = 'expired'
    
    def action_renew(self):
        """Create a new contract based on this one"""
        self.ensure_one()
        
        # Prepare new contract values based on current one
        default_end_date = False
        if self.end_date:
            # Calculate same duration from today
            months_duration = self.duration_months
            start_date = fields.Date.today()
            
            # Compute new end date based on duration
            end_year = start_date.year
            end_month = start_date.month + months_duration
            if end_month > 12:
                end_year += end_month // 12
                end_month = end_month % 12
                if end_month == 0:  # Handle case for exactly 12 months
                    end_month = 12
                    end_year -= 1
                    
            end_day = min(start_date.day, 28)  # Avoid issues with month lengths
            default_end_date = date(end_year, end_month, end_day)
        
        # Create renewal wizard
        return {
            'name': _('Renew Contract'),
            'type': 'ir.actions.act_window',
            'res_model': 'property.contract.renew.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contract_id': self.id,
                'default_property_id': self.property_id.id,
                'default_unit_id': self.unit_id.id,
                'default_tenant_id': self.tenant_id.id,
                'default_start_date': fields.Date.today(),
                'default_end_date': default_end_date,
                'default_rent_amount': self.rent_amount,
                'default_security_deposit': self.security_deposit,
                'default_billing_cycle': self.billing_cycle,
                'default_payment_term_id': self.payment_term_id.id,
            }
        }


# Add field to account.move for contract reference
class AccountMove(models.Model):
    _inherit = 'account.move'
    
    property_contract_id = fields.Many2one('property.contract', string='Rental Contract')
