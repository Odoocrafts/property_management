# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta

# Model constants
PROPERTY_BOOKING_MODEL = 'property.booking'
PROPERTY_BOOKING_PAYMENT_MODEL = 'property.booking.payment'
PROPERTY_PAYMENT_PLAN_MODEL = 'property.payment.plan'
RES_COMPANY_MODEL = 'res.company'
ACTION_WINDOW_TYPE = 'ir.actions.act_window'

class PropertyBooking(models.Model):
    _name = PROPERTY_BOOKING_MODEL
    _description = 'Property Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    
    name = fields.Char(string='Booking Reference', required=True, copy=False, 
                      readonly=True, default='New')
    
    # Basic booking information
    property_id = fields.Many2one('property.property', string='Property', required=True, tracking=True)
    unit_id = fields.Many2one('property.unit', string='Unit', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, tracking=True)
    lead_id = fields.Many2one('property.lead', string='Source Lead', tracking=True)
    
    # Booking details
    booking_date = fields.Date(string='Booking Date', default=fields.Date.today, required=True, tracking=True)
    booking_type = fields.Selection([
        ('token', 'Token Booking'),
        ('advance', 'Advance Booking'),
        ('full', 'Full Payment Booking')
    ], string='Booking Type', default='token', required=True, tracking=True)
    
    # Financial information
    unit_price = fields.Float(string='Unit Price', required=True, tracking=True)
    token_amount = fields.Float(string='Token Amount', required=True, tracking=True)
    advance_amount = fields.Float(string='Advance Amount', tracking=True)
    total_paid = fields.Float(string='Total Paid', compute='_compute_payment_totals', store=True)
    balance_amount = fields.Float(string='Balance Amount', compute='_compute_payment_totals', store=True)
    
    # Payment tracking
    payment_ids = fields.One2many(PROPERTY_BOOKING_PAYMENT_MODEL, 'booking_id', string='Payments')
    payment_plan_id = fields.Many2one(PROPERTY_PAYMENT_PLAN_MODEL, string='Payment Plan')
    
    # Timeline and deadlines
    token_validity_days = fields.Integer(string='Token Validity (Days)', default=30)
    token_expiry_date = fields.Date(string='Token Expiry Date', compute='_compute_token_expiry', store=True)
    confirmation_deadline = fields.Date(string='Confirmation Deadline', tracking=True)
    possession_date = fields.Date(string='Expected Possession Date', tracking=True)
    
    # Booking status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('token_paid', 'Token Paid'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('converted', 'Converted to Sale')
    ], string='Status', default='draft', tracking=True)
    
    # Documents and agreements
    booking_agreement = fields.Binary(string='Booking Agreement')
    booking_agreement_filename = fields.Char(string='Agreement Filename')
    terms_accepted = fields.Boolean(string='Terms & Conditions Accepted', tracking=True)
    terms_acceptance_date = fields.Datetime(string='Terms Acceptance Date')
    
    # Additional information
    special_requirements = fields.Text(string='Special Requirements')
    internal_notes = fields.Text(string='Internal Notes')
    cancellation_reason = fields.Text(string='Cancellation Reason')
    
    # Computed fields
    is_expired = fields.Boolean(string='Is Expired', compute='_compute_expiry_status', store=True)
    days_to_expiry = fields.Integer(string='Days to Expiry', compute='_compute_expiry_status', store=True)
    
    # Company and currency
    company_id = fields.Many2one(RES_COMPANY_MODEL, string='Company', 
                                default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                 related='company_id.currency_id')
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code(PROPERTY_BOOKING_MODEL) or 'New'
        return super(PropertyBooking, self).create(vals)
    
    @api.depends('booking_date', 'token_validity_days')
    def _compute_token_expiry(self):
        for booking in self:
            if booking.booking_date and booking.token_validity_days:
                booking.token_expiry_date = booking.booking_date + timedelta(days=booking.token_validity_days)
            else:
                booking.token_expiry_date = False
    
    @api.depends('payment_ids.amount', 'unit_price')
    def _compute_payment_totals(self):
        for booking in self:
            booking.total_paid = sum(booking.payment_ids.filtered(
                lambda p: p.state == 'confirmed'
            ).mapped('amount'))
            booking.balance_amount = booking.unit_price - booking.total_paid
    
    @api.depends('token_expiry_date', 'state')
    def _compute_expiry_status(self):
        today = fields.Date.today()
        for booking in self:
            if booking.token_expiry_date and booking.state in ['draft', 'token_paid']:
                booking.days_to_expiry = (booking.token_expiry_date - today).days
                booking.is_expired = booking.days_to_expiry < 0
            else:
                booking.days_to_expiry = 0
                booking.is_expired = False
    
    def action_pay_token(self):
        """Pay token amount and move to token_paid state"""
        self.ensure_one()
        if self.state == 'draft':
            # Create payment record
            payment_vals = {
                'booking_id': self.id,
                'amount': self.token_amount,
                'payment_type': 'token',
                'payment_date': fields.Date.today(),
                'state': 'confirmed'
            }
            self.env[PROPERTY_BOOKING_PAYMENT_MODEL].create(payment_vals)
            
            self.write({
                'state': 'token_paid',
                'booking_date': fields.Date.today()
            })
            
            # Update related lead if any
            if self.lead_id:
                self.lead_id.write({
                    'state': 'won',
                    'is_converted': True,
                    'converted_to': 'booking',
                    'converted_date': fields.Date.today()
                })
        return True
    
    def action_confirm_booking(self):
        """Confirm the booking after advance payment"""
        self.ensure_one()
        if self.state == 'token_paid':
            self.write({'state': 'confirmed'})
            
            # Generate booking agreement
            self._generate_booking_agreement()
        return True
    
    def action_cancel_booking(self):
        """Cancel the booking"""
        self.ensure_one()
        return {
            'name': 'Cancel Booking',
            'type': ACTION_WINDOW_TYPE,
            'res_model': 'property.booking.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_booking_id': self.id}
        }
    
    def action_convert_to_sale(self):
        """Convert booking to sale contract"""
        self.ensure_one()
        if self.state == 'confirmed':
            # Create sale contract
            contract_vals = {
                'partner_id': self.partner_id.id,
                'property_id': self.property_id.id,
                'unit_id': self.unit_id.id,
                'contract_type': 'sale',
                'start_date': fields.Date.today(),
                'total_amount': self.unit_price,
                'booking_id': self.id,
                'state': 'draft'
            }
            
            contract = self.env['property.contract'].create(contract_vals)
            
            self.write({'state': 'converted'})
            
            return {
                'name': 'Sale Contract',
                'type': ACTION_WINDOW_TYPE,
                'res_model': 'property.contract',
                'res_id': contract.id,
                'view_mode': 'form',
                'target': 'current'
            }
        return True
    
    def action_extend_token_validity(self):
        """Extend token validity period"""
        self.ensure_one()
        return {
            'name': 'Extend Token Validity',
            'type': ACTION_WINDOW_TYPE,
            'res_model': 'property.booking.extend.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_booking_id': self.id}
        }
    
    def action_view_payments(self):
        """Show all payments for this booking"""
        self.ensure_one()
        return {
            'name': 'Booking Payments',
            'type': ACTION_WINDOW_TYPE,
            'res_model': PROPERTY_BOOKING_PAYMENT_MODEL,
            'view_mode': 'list,form',
            'domain': [('booking_id', '=', self.id)],
            'context': {
                'default_booking_id': self.id,
                'create': True,
                'edit': True,
                'delete': True
            },
            'target': 'current'
        }
    
    def action_view_balance(self):
        """Show balance amount details"""
        self.ensure_one()
        return {
            'name': f'Balance Details - {self.name}',
            'type': ACTION_WINDOW_TYPE,
            'res_model': PROPERTY_BOOKING_MODEL,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_initial_mode': 'readonly'}
        }
    
    def _generate_booking_agreement(self):
        """Generate booking agreement document"""
        # This would typically generate a PDF agreement
        # For now, we'll just mark that an agreement exists
        self.write({
            'booking_agreement_filename': f'Booking_Agreement_{self.name}.pdf'
        })
    
    @api.model
    def _cron_check_expired_bookings(self):
        """Cron job to check and mark expired bookings"""
        today = fields.Date.today()
        expired_bookings = self.search([
            ('state', 'in', ['draft', 'token_paid']),
            ('token_expiry_date', '<', today)
        ])
        
        for booking in expired_bookings:
            booking.write({'state': 'expired'})
            
            # Send notification to sales team
            booking.message_post(
                body=f"Booking {booking.name} has expired. Token validity ended on {booking.token_expiry_date}.",
                subject="Booking Expired"
            )


class PropertyBookingPayment(models.Model):
    _name = PROPERTY_BOOKING_PAYMENT_MODEL
    _description = 'Property Booking Payment'
    _order = 'payment_date desc'
    
    booking_id = fields.Many2one(PROPERTY_BOOKING_MODEL, string='Booking', required=True, ondelete='cascade')
    amount = fields.Float(string='Amount', required=True)
    payment_date = fields.Date(string='Payment Date', default=fields.Date.today, required=True)
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('card', 'Credit/Debit Card'),
        ('online', 'Online Payment'),
        ('upi', 'UPI'),
        ('demand_draft', 'Demand Draft')
    ], string='Payment Method', default='bank_transfer')
    
    payment_type = fields.Selection([
        ('token', 'Token Amount'),
        ('advance', 'Advance Payment'),
        ('installment', 'Installment'),
        ('final', 'Final Payment')
    ], string='Payment Type', required=True)
    
    reference = fields.Char(string='Payment Reference')
    bank_details = fields.Text(string='Bank Details')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft')
    
    # Receipt and documentation
    receipt_image = fields.Binary(string='Payment Receipt')
    receipt_filename = fields.Char(string='Receipt Filename')
    
    notes = fields.Text(string='Notes')
    
    # Company and currency
    company_id = fields.Many2one(RES_COMPANY_MODEL, string='Company',
                                related='booking_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                 related='company_id.currency_id')
    
    def action_confirm_payment(self):
        """Confirm the payment"""
        self.write({'state': 'confirmed'})
        return True
    
    def action_cancel_payment(self):
        """Cancel the payment"""
        self.write({'state': 'cancelled'})
        return True


class PropertyPaymentPlan(models.Model):
    _name = PROPERTY_PAYMENT_PLAN_MODEL
    _description = 'Property Payment Plan'
    
    name = fields.Char(string='Plan Name', required=True)
    description = fields.Text(string='Description')
    
    plan_type = fields.Selection([
        ('construction_linked', 'Construction Linked'),
        ('time_linked', 'Time Linked'),
        ('down_payment_emi', 'Down Payment + EMI'),
        ('milestone_based', 'Milestone Based'),
        ('custom', 'Custom Plan')
    ], string='Plan Type', required=True)
    
    total_installments = fields.Integer(string='Total Installments')
    installment_ids = fields.One2many('property.payment.installment', 'plan_id', string='Installments')
    
    # Percentages
    token_percentage = fields.Float(string='Token %', default=1.0)
    advance_percentage = fields.Float(string='Advance %', default=20.0)
    
    active = fields.Boolean(string='Active', default=True)
    
    company_id = fields.Many2one(RES_COMPANY_MODEL, string='Company',
                                default=lambda self: self.env.company)


class PropertyPaymentInstallment(models.Model):
    _name = 'property.payment.installment'
    _description = 'Property Payment Installment'
    _order = 'sequence'
    
    plan_id = fields.Many2one(PROPERTY_PAYMENT_PLAN_MODEL, string='Payment Plan', 
                             required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Installment Name', required=True)
    percentage = fields.Float(string='Percentage of Total', required=True)
    
    # Timing
    due_after_days = fields.Integer(string='Due After (Days)', default=0)
    milestone = fields.Char(string='Construction Milestone')
    
    description = fields.Text(string='Description')
