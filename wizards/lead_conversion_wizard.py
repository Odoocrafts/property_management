# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

# Constants
PROPERTY_LEAD_MODEL = 'property.lead'
RES_PARTNER_MODEL = 'res.partner'
MAIL_ACTIVITY_TODO = 'mail.mail_activity_data_todo'
ACTION_WINDOW_TYPE = 'ir.actions.act_window'


class LeadConversionWizard(models.TransientModel):
    """Wizard for converting leads to customers or bookings."""
    
    _name = 'property.lead.conversion.wizard'
    _description = 'Lead Conversion Wizard'

    lead_id = fields.Many2one(PROPERTY_LEAD_MODEL, string='Lead', required=True)
    conversion_type = fields.Selection([
        ('customer', 'Customer'),
        ('booking', 'Booking'),
    ], string='Convert To', required=True, default='customer')
    
    # Customer Fields
    customer_name = fields.Char(string='Customer Name')
    customer_email = fields.Char(string='Email')
    customer_phone = fields.Char(string='Phone')
    customer_mobile = fields.Char(string='Mobile')
    
    # Address Fields
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street 2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    zip = fields.Char(string='ZIP')
    country_id = fields.Many2one('res.country', string='Country')
    
    # Booking Fields
    property_id = fields.Many2one('property.property', string='Property')
    unit_id = fields.Many2one('property.unit', string='Unit')
    booking_date = fields.Date(string='Booking Date', default=fields.Date.today)
    move_in_date = fields.Date(string='Expected Move-in Date')
    lease_duration = fields.Integer(string='Lease Duration (Months)', default=12)
    monthly_rent = fields.Monetary(string='Monthly Rent', currency_field='currency_id')
    security_deposit = fields.Monetary(string='Security Deposit', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                  default=lambda self: self.env.company.currency_id)
    
    # Additional Fields
    notes = fields.Text(string='Notes')
    create_contract = fields.Boolean(string='Create Contract', default=True)

    @api.onchange('lead_id')
    def _onchange_lead_id(self):
        """Populate wizard fields from lead data."""
        if self.lead_id:
            self.customer_name = self.lead_id.contact_name
            self.customer_email = self.lead_id.email
            self.customer_phone = self.lead_id.phone
            self.customer_mobile = self.lead_id.mobile
            self.street = self.lead_id.street
            self.street2 = self.lead_id.street2
            self.city = self.lead_id.city
            self.state_id = self.lead_id.state_id
            self.zip = self.lead_id.zip
            self.country_id = self.lead_id.country_id

    @api.onchange('property_id')
    def _onchange_property_id(self):
        """Update available units when property changes."""
        if self.property_id:
            # Filter available units for the selected property
            available_units = self.env['property.unit'].search([
                ('property_id', '=', self.property_id.id),
                ('state', '=', 'available')
            ])
            return {
                'domain': {
                    'unit_id': [('id', 'in', available_units.ids)]
                }
            }
        else:
            return {
                'domain': {
                    'unit_id': [('id', '=', False)]
                }
            }

    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        """Set default rent from unit."""
        if self.unit_id and self.unit_id.monthly_rent:
            self.monthly_rent = self.unit_id.monthly_rent
            # Set security deposit as 2 times monthly rent (common practice)
            self.security_deposit = self.monthly_rent * 2

    def action_convert(self):
        """Execute the conversion process."""
        self.ensure_one()
        
        if not self.lead_id:
            raise UserError(_('No lead selected for conversion.'))
        
        if self.lead_id.is_converted:
            raise UserError(_('This lead has already been converted.'))
        
        if self.conversion_type == 'customer':
            return self._convert_to_customer()
        elif self.conversion_type == 'booking':
            return self._convert_to_booking()

    def _create_customer(self):
        """Helper method to create customer."""
        customer_vals = {
            'name': self.customer_name or self.lead_id.contact_name,
            'email': self.customer_email or self.lead_id.email,
            'phone': self.customer_phone or self.lead_id.phone,
            'mobile': self.customer_mobile or self.lead_id.mobile,
            'street': self.street or self.lead_id.street,
            'street2': self.street2 or self.lead_id.street2,
            'city': self.city or self.lead_id.city,
            'state_id': self.state_id.id or self.lead_id.state_id.id,
            'zip': self.zip or self.lead_id.zip,
            'country_id': self.country_id.id or self.lead_id.country_id.id,
            'is_company': False,
            'customer_rank': 1,
            'comment': f'Converted from lead: {self.lead_id.code}',
        }
        return self.env[RES_PARTNER_MODEL].create(customer_vals)

    def _convert_to_customer(self):
        """Convert lead to customer."""
        customer = self._create_customer()
        
        # Update lead
        self.lead_id.write({
            'partner_id': customer.id,
            'is_converted': True,
            'converted_date': fields.Datetime.now(),
            'converted_to': 'customer',
            'state': 'won',
        })
        
        # Log activity
        self.lead_id.activity_schedule(
            MAIL_ACTIVITY_TODO,
            summary=_('Lead Converted to Customer'),
            note=_('Lead %s has been successfully converted to customer %s') % (
                self.lead_id.code, customer.name
            ),
            user_id=self.lead_id.assigned_to.id or self.env.user.id,
        )
        
        return {
            'type': ACTION_WINDOW_TYPE,
            'name': _('Customer'),
            'res_model': RES_PARTNER_MODEL,
            'res_id': customer.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _create_contract(self, customer):
        """Helper method to create contract."""
        contract_vals = {
            'tenant_id': customer.id,
            'unit_id': self.unit_id.id,
            'start_date': self.move_in_date or self.booking_date,
            'duration_months': self.lease_duration,
            'monthly_rent': self.monthly_rent,
            'security_deposit': self.security_deposit,
            'notes': self.notes,
            'state': 'draft',
        }
        return self.env['property.contract'].create(contract_vals)

    def _convert_to_booking(self):
        """Convert lead to booking with contract."""
        if not self.unit_id:
            raise UserError(_('Please select a unit for booking.'))
        
        if self.unit_id.state != 'available':
            raise UserError(_('Selected unit is not available for booking.'))
        
        # Create customer
        customer = self._create_customer()
        
        # Create contract if requested
        contract = None
        if self.create_contract:
            contract = self._create_contract(customer)
        
        # Update unit status
        self.unit_id.write({
            'state': 'booked',
            'tenant_id': customer.id,
        })
        
        # Update lead
        self.lead_id.write({
            'partner_id': customer.id,
            'booking_id': contract.id if contract else False,
            'is_converted': True,
            'converted_date': fields.Datetime.now(),
            'converted_to': 'booking',
            'state': 'won',
        })
        
        # Log activity
        self.lead_id.activity_schedule(
            MAIL_ACTIVITY_TODO,
            summary=_('Lead Converted to Booking'),
            note=_('Lead %s has been successfully converted to booking for unit %s') % (
                self.lead_id.code, self.unit_id.name
            ),
            user_id=self.lead_id.assigned_to.id or self.env.user.id,
        )
        
        if contract:
            return {
                'type': ACTION_WINDOW_TYPE,
                'name': _('Property Contract'),
                'res_model': 'property.contract',
                'res_id': contract.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': ACTION_WINDOW_TYPE,
                'name': _('Customer'),
                'res_model': RES_PARTNER_MODEL,
                'res_id': customer.id,
                'view_mode': 'form',
                'target': 'current',
            }


class LeadQualificationWizard(models.TransientModel):
    """Wizard for qualifying leads."""
    
    _name = 'property.lead.qualification.wizard'
    _description = 'Lead Qualification Wizard'

    lead_id = fields.Many2one(PROPERTY_LEAD_MODEL, string='Lead', required=True)
    qualification_result = fields.Selection([
        ('qualified', 'Qualified'),
        ('not_qualified', 'Not Qualified'),
    ], string='Qualification Result', required=True)
    
    # Qualification Criteria
    budget_confirmed = fields.Boolean(string='Budget Confirmed')
    timeline_confirmed = fields.Boolean(string='Timeline Confirmed')
    authority_confirmed = fields.Boolean(string='Authority Confirmed')
    need_confirmed = fields.Boolean(string='Need Confirmed')
    
    # Additional Fields
    qualification_notes = fields.Text(string='Qualification Notes')
    next_action = fields.Selection([
        ('schedule_site_visit', 'Schedule Site Visit'),
        ('send_proposal', 'Send Proposal'),
        ('follow_up_call', 'Follow-up Call'),
        ('no_action', 'No Action Required'),
    ], string='Next Action')
    
    next_activity_date = fields.Datetime(string='Next Activity Date')
    assigned_to = fields.Many2one('res.users', string='Assign To')

    @api.onchange('lead_id')
    def _onchange_lead_id(self):
        """Set default assigned user."""
        if self.lead_id:
            self.assigned_to = self.lead_id.assigned_to or self.env.user

    def action_qualify(self):
        """Execute the qualification process."""
        self.ensure_one()
        
        if not self.lead_id:
            raise UserError(_('No lead selected for qualification.'))
        
        # Update lead stage and state
        if self.qualification_result == 'qualified':
            qualified_stage = self.env['property.lead.stage'].search([
                ('name', 'ilike', 'qualified')
            ], limit=1)
            
            self.lead_id.write({
                'state': 'qualified',
                'stage_id': qualified_stage.id if qualified_stage else False,
                'notes': (self.lead_id.notes or '') + '\n\n' + (self.qualification_notes or ''),
            })
        else:
            lost_stage = self.env['property.lead.stage'].search([
                ('name', 'ilike', 'lost')
            ], limit=1)
            
            self.lead_id.write({
                'state': 'lost',
                'stage_id': lost_stage.id if lost_stage else False,
                'notes': (self.lead_id.notes or '') + '\n\n' + (self.qualification_notes or ''),
            })
        
        # Schedule next activity if specified
        if self.next_action != 'no_action' and self.next_activity_date:
            activity_summary = {
                'schedule_site_visit': _('Schedule Site Visit'),
                'send_proposal': _('Send Proposal'),
                'follow_up_call': _('Follow-up Call'),
            }.get(self.next_action, _('Follow-up'))
            
            self.lead_id.activity_schedule(
                MAIL_ACTIVITY_TODO,
                summary=activity_summary,
                note=self.qualification_notes or '',
                date_deadline=self.next_activity_date.date(),
                user_id=self.assigned_to.id,
            )
        
        # Log qualification activity
        self.lead_id.message_post(
            body=_('Lead qualification completed: %s') % self.qualification_result,
            message_type='notification',
        )
        
        return {'type': 'ir.actions.act_window_close'}


class LeadMergeWizard(models.TransientModel):
    """Wizard for merging duplicate leads."""
    
    _name = 'property.lead.merge.wizard'
    _description = 'Lead Merge Wizard'

    lead_ids = fields.Many2many(PROPERTY_LEAD_MODEL, string='Leads to Merge', required=True)
    master_lead_id = fields.Many2one(PROPERTY_LEAD_MODEL, string='Master Lead', required=True)
    merge_notes = fields.Text(string='Merge Notes')

    @api.onchange('lead_ids')
    def _onchange_lead_ids(self):
        """Set master lead as the one with highest score."""
        if self.lead_ids:
            master = max(self.lead_ids, key=lambda l: l.score)
            self.master_lead_id = master

    def action_merge(self):
        """Execute the merge process."""
        self.ensure_one()
        
        if len(self.lead_ids) < 2:
            raise UserError(_('Please select at least 2 leads to merge.'))
        
        if self.master_lead_id not in self.lead_ids:
            raise UserError(_('Master lead must be one of the selected leads.'))
        
        # Get other leads to merge
        other_leads = self.lead_ids - self.master_lead_id
        
        # Merge data into master lead
        for lead in other_leads:
            # Merge activities
            lead.activity_ids.write({'res_id': self.master_lead_id.id})
            
            # Merge messages
            lead.message_ids.write({'res_id': self.master_lead_id.id})
            
            # Merge attachments
            if hasattr(lead, 'attachment_ids'):
                lead.attachment_ids.write({'res_id': self.master_lead_id.id})
            
            # Log merge information
            merge_info = _(
                'Merged from lead %s (Contact: %s, Email: %s, Phone: %s)'
            ) % (lead.code, lead.contact_name, lead.email, lead.phone)
            
            current_notes = self.master_lead_id.notes or ''
            self.master_lead_id.notes = current_notes + '\n\n' + merge_info
        
        # Add merge notes if provided
        if self.merge_notes:
            current_notes = self.master_lead_id.notes or ''
            self.master_lead_id.notes = current_notes + '\n\n' + self.merge_notes
        
        # Log merge activity
        self.master_lead_id.message_post(
            body=_('Leads merged: %s') % ', '.join(other_leads.mapped('code')),
            message_type='notification',
        )
        
        # Archive other leads
        other_leads.write({'active': False})
        
        return {
            'type': ACTION_WINDOW_TYPE,
            'name': _('Merged Lead'),
            'res_model': PROPERTY_LEAD_MODEL,
            'res_id': self.master_lead_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
