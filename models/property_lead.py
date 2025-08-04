from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date, timedelta

# Constants
PROPERTY_LEAD_STAGE_MODEL = 'property.lead.stage'
ACTION_WINDOW_TYPE = 'ir.actions.act_window'
COLOR_INDEX_STRING = 'Color Index'

class PropertyLead(models.Model):
    _name = 'property.lead'
    _description = 'Property Lead'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, priority desc'
    _rec_name = 'lead_name'

    # Basic Information
    lead_name = fields.Char(string='Lead Name', required=True, tracking=True)
    code = fields.Char(string='Lead Code', readonly=True, copy=False, default=lambda self: _('New'))
    
    # Contact Information
    contact_name = fields.Char(string='Contact Person', required=True, tracking=True)
    email = fields.Char(string='Email', tracking=True)
    phone = fields.Char(string='Phone', tracking=True)
    mobile = fields.Char(string='Mobile', tracking=True)
    
    # Address Information
    street = fields.Char(string='Street', tracking=True)
    street2 = fields.Char(string='Street 2', tracking=True)
    city = fields.Char(string='City', tracking=True)
    state_id = fields.Many2one('res.country.state', string='State', tracking=True)
    zip = fields.Char(string='ZIP', tracking=True)
    country_id = fields.Many2one('res.country', string='Country', tracking=True)
    
    # Marketing fields (made optional to avoid dependency issues)
    campaign_id = fields.Many2one('utm.campaign', string='Campaign', required=False)
    medium_id = fields.Many2one('utm.medium', string='Medium', required=False)
    source_id = fields.Many2one('utm.source', string='Source', required=False)
    
    # Lead source tracking
    source = fields.Selection([
        ('website', 'Website'),
        ('phone', 'Phone Call'),
        ('email', 'Email'),
        ('walkin', 'Walk-in'),
        ('referral', 'Referral'),
        ('advertisement', 'Advertisement'),
        ('social_media', 'Social Media'),
        ('exhibition', 'Exhibition'),
        ('broker', 'Broker'),
        ('other', 'Other')
    ], string='Lead Source', required=True, default='website', tracking=True)
    
    source_details = fields.Text(string='Source Details', help='Additional information about the lead source')
    
    # Lead Classification
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Hot'),
    ], string='Priority', default='1', tracking=True)
    
    lead_type = fields.Selection([
        ('individual', 'Individual'),
        ('corporate', 'Corporate'),
        ('investor', 'Investor'),
        ('reseller', 'Reseller')
    ], string='Lead Type', default='individual', required=True, tracking=True)
    
    # Customer Requirements
    budget_min = fields.Float(string='Budget Min', tracking=True)
    budget_max = fields.Float(string='Budget Max', tracking=True)
    budget_range = fields.Selection([
        ('below_50l', 'Below 50 Lakhs'),
        ('50l_1cr', '50 Lakhs - 1 Crore'),
        ('1cr_2cr', '1 - 2 Crores'),
        ('2cr_5cr', '2 - 5 Crores'),
        ('above_5cr', 'Above 5 Crores')
    ], string='Budget Range', compute='_compute_budget_range', store=True)
    
    unit_type_preference = fields.Selection([
        ('studio', 'Studio'),
        ('1bhk', '1 BHK'),
        ('2bhk', '2 BHK'),
        ('3bhk', '3 BHK'),
        ('4bhk', '4+ BHK'),
        ('villa', 'Villa'),
        ('plot', 'Plot'),
        ('commercial', 'Commercial')
    ], string='Unit Type Preference', tracking=True)
    
    location_preference = fields.Char(string='Location Preference', tracking=True)
    timeline = fields.Selection([
        ('immediate', 'Immediate (0-3 months)'),
        ('short', 'Short term (3-6 months)'),
        ('medium', 'Medium term (6-12 months)'),
        ('long', 'Long term (1+ years)')
    ], string='Purchase Timeline', default='medium', tracking=True)
    
    investment_purpose = fields.Selection([
        ('own_use', 'Own Use'),
        ('investment', 'Investment'),
        ('resale', 'Resale'),
        ('rental', 'Rental Income')
    ], string='Investment Purpose', default='own_use', tracking=True)
    
    family_size = fields.Integer(string='Family Size', tracking=True)
    
    # Lead Management
    assigned_to = fields.Many2one('res.users', string='Assigned To', tracking=True)
    # Removed team_id to avoid dependency on CRM module
    # team_id = fields.Many2one('crm.team', string='Sales Team', tracking=True)
    
    # Lead Status and Workflow
    stage_id = fields.Many2one(PROPERTY_LEAD_STAGE_MODEL, string='Stage',
                              tracking=True)
    
    state = fields.Selection([
        ('new', 'New'),
        ('qualified', 'Qualified'),
        ('proposal', 'Proposal'),
        ('negotiation', 'Negotiation'),
        ('won', 'Won'),
        ('lost', 'Lost'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='new', tracking=True)
    
    # Lead Scoring
    score = fields.Integer(string='Lead Score', compute='_compute_lead_score', store=True)
    score_details = fields.Text(string='Scoring Details', compute='_compute_lead_score')
    
    # Follow-up
    next_activity_date = fields.Date(string='Next Activity Date', tracking=True)
    last_activity_date = fields.Date(string='Last Activity Date', tracking=True)
    follow_up_count = fields.Integer(string='Follow-up Count', default=0)
    
    # Conversion
    is_converted = fields.Boolean(string='Converted', default=False, tracking=True)
    converted_date = fields.Date(string='Conversion Date', tracking=True)
    converted_to = fields.Selection([
        ('booking', 'Booking'),
        ('customer', 'Customer'),
        ('partner', 'Partner')
    ], string='Converted To', tracking=True)
    
    # Re-enabled now that property.booking model exists
    booking_id = fields.Many2one('property.booking', string='Related Booking')
    partner_id = fields.Many2one('res.partner', string='Related Customer')
    
    # Properties of Interest
    interested_properties = fields.Many2many('property.property', string='Properties of Interest')
    interested_units = fields.Many2many('property.unit', string='Units of Interest')
    
    # Additional Information
    description = fields.Text(string='Description')
    notes = fields.Text(string='Internal Notes')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    tag_ids = fields.Many2many('property.lead.tag', string='Tags')
    
    # UI Fields
    color = fields.Integer(string='Color Index', default=0)
    
    # Company
    company_id = fields.Many2one('res.company', string='Company',
                                default=lambda self: self.env.company.id)
    
    # Computed Fields
    days_since_creation = fields.Integer(string='Days Since Creation', compute='_compute_days_since_creation')
    probability = fields.Float(string='Probability (%)', compute='_compute_probability', store=True)
    
    # Referral Information
    referral_partner_id = fields.Many2one('res.partner', string='Referred By')
    referral_commission_applicable = fields.Boolean(string='Commission Applicable', default=False)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('property.lead') or _('New')
        return super(PropertyLead, self).create(vals_list)
    
    @api.depends('budget_min', 'budget_max')
    def _compute_budget_range(self):
        for lead in self:
            if lead.budget_max:
                budget = lead.budget_max / 100000  # Convert to lakhs
                if budget < 50:
                    lead.budget_range = 'below_50l'
                elif budget <= 100:
                    lead.budget_range = '50l_1cr'
                elif budget <= 200:
                    lead.budget_range = '1cr_2cr'
                elif budget <= 500:
                    lead.budget_range = '2cr_5cr'
                else:
                    lead.budget_range = 'above_5cr'
            else:
                lead.budget_range = False
    
    @api.depends('source', 'budget_range', 'timeline', 'lead_type', 'follow_up_count', 'stage_id')
    def _compute_lead_score(self):
        for lead in self:
            score = 0
            details = []
            
            # Source scoring
            source_scores = {
                'website': 10, 'referral': 20, 'broker': 15,
                'phone': 8, 'walk_in': 25, 'digital_marketing': 12,
                'social_media': 8, 'exhibition': 18, 'other': 5
            }
            if lead.source:
                score += source_scores.get(lead.source, 5)
                details.append(f"Source ({lead.source}): +{source_scores.get(lead.source, 5)}")
            
            # Budget scoring
            budget_scores = {
                'below_50l': 5, '50l_1cr': 10, '1cr_2cr': 15,
                '2cr_5cr': 20, 'above_5cr': 25
            }
            if lead.budget_range:
                score += budget_scores.get(lead.budget_range, 0)
                details.append(f"Budget ({lead.budget_range}): +{budget_scores.get(lead.budget_range, 0)}")
            
            # Timeline scoring
            timeline_scores = {
                'immediate': 25, 'short': 20, 'medium': 15, 'long': 10
            }
            if lead.timeline:
                score += timeline_scores.get(lead.timeline, 0)
                details.append(f"Timeline ({lead.timeline}): +{timeline_scores.get(lead.timeline, 0)}")
            
            # Lead type scoring
            type_scores = {
                'individual': 15, 'corporate': 20, 'investor': 25, 'reseller': 10
            }
            if lead.lead_type:
                score += type_scores.get(lead.lead_type, 0)
                details.append(f"Type ({lead.lead_type}): +{type_scores.get(lead.lead_type, 0)}")
            
            # Follow-up activity scoring
            if lead.follow_up_count > 0:
                followup_score = min(lead.follow_up_count * 2, 10)
                score += followup_score
                details.append(f"Follow-ups ({lead.follow_up_count}): +{followup_score}")
            
            # Stage progression scoring
            if lead.stage_id and hasattr(lead.stage_id, 'sequence'):
                stage_score = (lead.stage_id.sequence or 0) * 2
                score += stage_score
                details.append(f"Stage progress: +{stage_score}")
            
            lead.score = min(score, 100)  # Cap at 100
            lead.score_details = '\n'.join(details)
    
    @api.depends('state', 'score', 'stage_id')
    def _compute_probability(self):
        for lead in self:
            if lead.state == 'won':
                lead.probability = 100
            elif lead.state in ['lost', 'cancelled']:
                lead.probability = 0
            else:
                # Base probability on score and stage
                base_prob = lead.score * 0.8  # Score contributes 80%
                stage_prob = 0
                if lead.stage_id and hasattr(lead.stage_id, 'sequence'):
                    stage_prob = (lead.stage_id.sequence or 0) * 5  # Stage contributes 20%
                lead.probability = min(base_prob + stage_prob, 95)
    
    @api.depends('create_date')
    def _compute_days_since_creation(self):
        today = fields.Date.today()
        for lead in self:
            if lead.create_date:
                create_date = lead.create_date.date()
                lead.days_since_creation = (today - create_date).days
            else:
                lead.days_since_creation = 0
    
    def _get_default_stage(self):
        """Get the first stage for leads"""
        try:
            stage = self.env[PROPERTY_LEAD_STAGE_MODEL].search([('is_default', '=', True)], limit=1)
            if stage:
                return stage.id
            # If no default stage, get the first stage
            first_stage = self.env[PROPERTY_LEAD_STAGE_MODEL].search([], order='sequence', limit=1)
            return first_stage.id if first_stage else False
        except Exception:
            return False
    
    @api.model
    def create(self, vals):
        """Override create to set default stage if not provided"""
        if 'stage_id' not in vals or not vals['stage_id']:
            vals['stage_id'] = self._get_default_stage()
        return super(PropertyLead, self).create(vals)
    
    def action_qualify(self):
        """Qualify the lead"""
        self.write({
            'state': 'qualified',
            'last_activity_date': fields.Date.today()
        })
        
    def action_create_proposal(self):
        """Move to proposal stage"""
        self.write({
            'state': 'proposal',
            'last_activity_date': fields.Date.today()
        })
    
    def action_mark_won(self):
        """Mark lead as won"""
        self.write({
            'state': 'won',
            'last_activity_date': fields.Date.today()
        })
    
    def action_mark_lost(self):
        """Mark lead as lost"""
        self.write({
            'state': 'lost',
            'last_activity_date': fields.Date.today()
        })
    
    def action_convert_to_booking(self):
        """Convert lead to booking"""
        return {
            'name': _('Convert to Booking'),
            'type': ACTION_WINDOW_TYPE,
            'res_model': 'property.lead.convert.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
                'default_conversion_type': 'booking'
            }
        }
    
    def action_convert_to_customer(self):
        """Convert lead to customer"""
        return {
            'name': _('Convert to Customer'),
            'type': ACTION_WINDOW_TYPE,
            'res_model': 'property.lead.convert.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
                'default_conversion_type': 'customer'
            }
        }
    
    def action_schedule_activity(self):
        """Schedule next activity"""
        return {
            'name': _('Schedule Activity'),
            'type': ACTION_WINDOW_TYPE,
            'res_model': 'mail.activity',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'default_user_id': self.assigned_to.id or self.env.user.id
            }
        }
    
    def increment_follow_up(self):
        """Increment follow-up counter"""
        self.follow_up_count += 1
        self.last_activity_date = fields.Date.today()


class PropertyLeadStage(models.Model):
    _name = PROPERTY_LEAD_STAGE_MODEL
    _description = 'Lead Stage'
    _order = 'sequence, name'
    
    name = fields.Char(string='Stage Name', required=True)
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    is_default = fields.Boolean(string='Default Stage', default=False)
    fold = fields.Boolean(string='Folded in Kanban')
    
    # Colors for kanban view
    color = fields.Integer(string=COLOR_INDEX_STRING, default=0)
    
    @api.model
    def create(self, vals):
        if vals.get('is_default'):
            # Remove default from other stages
            self.search([('is_default', '=', True)]).write({'is_default': False})
        return super().create(vals)
    
    def write(self, vals):
        if vals.get('is_default'):
            # Remove default from other stages
            self.search([('is_default', '=', True), ('id', '!=', self.id)]).write({'is_default': False})
        return super().write(vals)


class PropertyLeadTag(models.Model):
    """Model for lead tags/categories."""
    
    _name = 'property.lead.tag'
    _description = 'Lead Tag'
    _order = 'name'

    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer(string=COLOR_INDEX_STRING, default=0)
    active = fields.Boolean(string='Active', default=True)
