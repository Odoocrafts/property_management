# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Property-specific prospect fields
    is_property_prospect = fields.Boolean(string='Is Property Prospect', default=False)
    is_property_customer = fields.Boolean(string='Is Property Customer', default=False)
    is_property_investor = fields.Boolean(string='Is Property Investor', default=False)
    
    # Prospect classification
    prospect_type = fields.Selection([
        ('individual', 'Individual'),
        ('corporate', 'Corporate'),
        ('investor', 'Investor'),
        ('reseller', 'Reseller/Broker')
    ], string='Prospect Type', help='Type of prospect for property business')
    
    # Budget and investment preferences
    budget_min = fields.Float(string='Budget Min', help='Minimum budget for property purchase')
    budget_max = fields.Float(string='Budget Max', help='Maximum budget for property purchase')
    budget_range = fields.Selection([
        ('below_50l', 'Below 50 Lakhs'),
        ('50l_1cr', '50 Lakhs - 1 Crore'),
        ('1cr_2cr', '1 Crore - 2 Crore'),
        ('2cr_5cr', '2 Crore - 5 Crore'),
        ('above_5cr', 'Above 5 Crore')
    ], string='Budget Range', compute='_compute_budget_range', store=True)
    
    # Location preferences
    preferred_locations = fields.Text(string='Preferred Locations', 
                                    help='Comma-separated list of preferred locations')
    preferred_areas = fields.Char(string='Preferred Areas')
    
    # Investment purpose and requirements
    investment_purpose = fields.Selection([
        ('own_use', 'Own Use/Self Occupation'),
        ('investment', 'Investment/Rental Income'),
        ('commercial', 'Commercial Use'),
        ('resale', 'Resale/Appreciation')
    ], string='Investment Purpose')
    
    # Family and lifestyle requirements
    family_size = fields.Integer(string='Family Size', help='Number of family members')
    preferred_unit_type = fields.Selection([
        ('1bhk', '1 BHK'),
        ('2bhk', '2 BHK'),
        ('3bhk', '3 BHK'),
        ('4bhk', '4 BHK'),
        ('5bhk', '5+ BHK'),
        ('villa', 'Villa'),
        ('penthouse', 'Penthouse'),
        ('studio', 'Studio Apartment'),
        ('commercial', 'Commercial Space')
    ], string='Preferred Unit Type')
    
    # Property requirements
    preferred_amenities = fields.Text(string='Preferred Amenities',
                                    help='List of preferred amenities (Pool, Gym, etc.)')
    carpet_area_min = fields.Float(string='Min Carpet Area (sq ft)')
    carpet_area_max = fields.Float(string='Max Carpet Area (sq ft)')
    
    # Financing information
    financing_required = fields.Boolean(string='Financing Required', default=False)
    loan_pre_approved = fields.Boolean(string='Loan Pre-approved', default=False)
    preferred_banks = fields.Text(string='Preferred Banks')
    down_payment_ready = fields.Boolean(string='Down Payment Ready', default=False)
    
    # Timeline and urgency
    purchase_timeline = fields.Selection([
        ('immediate', 'Immediate (Within 1 month)'),
        ('3months', 'Within 3 months'),
        ('6months', 'Within 6 months'),
        ('1year', 'Within 1 year'),
        ('flexible', 'Flexible timeline')
    ], string='Purchase Timeline')
    
    # Relationship and referral tracking
    referral_source = fields.Many2one('res.partner', string='Referred By')
    referral_commission_rate = fields.Float(string='Referral Commission %')
    broker_license = fields.Char(string='Broker License Number')
    
    # Property interest tracking
    property_leads_count = fields.Integer(string='Leads Count', compute='_compute_property_stats')
    properties_purchased_count = fields.Integer(string='Properties Purchased', compute='_compute_property_stats')
    total_investment_value = fields.Float(string='Total Investment Value', compute='_compute_property_stats')
    
    # Property relationships
    property_leads = fields.One2many('property.lead', 'partner_id', string='Property Leads')
    property_contracts = fields.One2many('property.contract', 'partner_id', string='Property Contracts')
    
    # Communication preferences
    preferred_communication = fields.Selection([
        ('phone', 'Phone'),
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
        ('sms', 'SMS'),
        ('in_person', 'In Person')
    ], string='Preferred Communication', default='phone')
    
    # Customer scoring and classification (temporarily commented to avoid upgrade issues)
    # customer_score = fields.Integer(string='Customer Score', compute='_compute_customer_score', store=True)
    # customer_category = fields.Selection([
    #     ('hot', 'Hot Lead'),
    #     ('warm', 'Warm Lead'),
    #     ('cold', 'Cold Lead'),
    #     ('customer', 'Existing Customer'),
    #     ('investor', 'Investor'),
    #     ('vip', 'VIP Customer')
    # ], string='Customer Category', compute='_compute_customer_category', store=True)
    
    @api.depends('budget_min', 'budget_max')
    def _compute_budget_range(self):
        for partner in self:
            if partner.budget_max:
                amount = partner.budget_max
                if amount < 5000000:  # Below 50 Lakhs
                    partner.budget_range = 'below_50l'
                elif amount < 10000000:  # 50L - 1Cr
                    partner.budget_range = '50l_1cr'
                elif amount < 20000000:  # 1Cr - 2Cr
                    partner.budget_range = '1cr_2cr'
                elif amount < 50000000:  # 2Cr - 5Cr
                    partner.budget_range = '2cr_5cr'
                else:  # Above 5Cr
                    partner.budget_range = 'above_5cr'
            else:
                partner.budget_range = False
    
    @api.depends('property_leads', 'property_contracts')
    def _compute_property_stats(self):
        for partner in self:
            partner.property_leads_count = len(partner.property_leads)
            partner.properties_purchased_count = len(partner.property_contracts.filtered(
                lambda c: c.contract_type == 'sale'
            ))
            partner.total_investment_value = sum(
                partner.property_contracts.filtered(
                    lambda c: c.contract_type == 'sale'
                ).mapped('total_amount')
            )
    
    # Temporarily commented out computed methods to avoid upgrade issues
    # @api.depends('budget_range', 'investment_purpose', 'purchase_timeline', 'property_leads_count')
    # def _compute_customer_score(self):
    #     for partner in self:
    #         score = 0
    #         
    #         # Budget scoring
    #         budget_scores = {
    #             'below_50l': 10, '50l_1cr': 20, '1cr_2cr': 30,
    #             '2cr_5cr': 40, 'above_5cr': 50
    #         }
    #         if partner.budget_range:
    #             score += budget_scores.get(partner.budget_range, 0)
    #         
    #         # Timeline urgency scoring
    #         timeline_scores = {
    #             'immediate': 30, '3months': 25, '6months': 20,
    #             '1year': 15, 'flexible': 10
    #         }
    #         if partner.purchase_timeline:
    #             score += timeline_scores.get(partner.purchase_timeline, 0)
    #         
    #         # Lead activity scoring
    #         score += min(partner.property_leads_count * 5, 20)
    #         
    #         # Investment purpose scoring
    #         purpose_scores = {
    #             'own_use': 25, 'investment': 20, 'commercial': 30, 'resale': 15
    #         }
    #         if partner.investment_purpose:
    #             score += purpose_scores.get(partner.investment_purpose, 0)
    #         
    #         partner.customer_score = score
    # 
    # @api.depends('customer_score', 'properties_purchased_count', 'total_investment_value')
    # def _compute_customer_category(self):
    #     for partner in self:
    #         if partner.properties_purchased_count > 0:
    #             if partner.total_investment_value > 50000000:  # Above 5Cr
    #                 partner.customer_category = 'vip'
    #             elif partner.total_investment_value > 20000000:  # Above 2Cr
    #                 partner.customer_category = 'investor'
    #             else:
    #                 partner.customer_category = 'customer'
    #         else:
    #             if partner.customer_score >= 80:
    #                 partner.customer_category = 'hot'
    #             elif partner.customer_score >= 60:
    #                 partner.customer_category = 'warm'
    #             else:
    #                 partner.customer_category = 'cold'
    
    def action_convert_to_prospect(self):
        """Convert partner to property prospect"""
        self.write({
            'is_property_prospect': True,
            'customer': True
        })
        return True
    
    def action_convert_to_customer(self):
        """Convert prospect to property customer"""
        self.write({
            'is_property_customer': True,
            'is_property_prospect': False
        })
        return True
    
    def action_view_property_leads(self):
        """View property leads for this partner"""
        action = self.env.ref('property_management.property_lead_action').read()[0]
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {'default_partner_id': self.id}
        return action
    
    def action_view_property_contracts(self):
        """View property contracts for this partner"""
        action = self.env.ref('property_management.property_contract_action').read()[0]
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {'default_partner_id': self.id}
        return action
