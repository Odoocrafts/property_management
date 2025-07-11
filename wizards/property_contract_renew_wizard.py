# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import timedelta


class PropertyContractRenewWizard(models.TransientModel):
    _name = 'property.contract.renew.wizard'
    _description = 'Property Contract Renewal Wizard'

    contract_id = fields.Many2one('property.contract', string='Contract', required=True)
    property_id = fields.Many2one(related='contract_id.property_id', string='Property', readonly=True)
    unit_id = fields.Many2one(related='contract_id.unit_id', string='Property Unit', readonly=True)
    tenant_id = fields.Many2one('res.partner', string='Tenant', required=True)
    
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date')
    
    currency_id = fields.Many2one(related='contract_id.currency_id', string='Currency')
    rent_amount = fields.Monetary(string='Rent Amount', required=True)
    security_deposit = fields.Monetary(string='Security Deposit')
    billing_cycle = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('biannual', 'Bi-Annual'),
        ('annual', 'Annual')
    ], string='Billing Cycle', required=True, default='monthly')
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms')

    @api.model
    def default_get(self, fields_list):
        res = super(PropertyContractRenewWizard, self).default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            contract = self.env['property.contract'].browse(active_id)
            res.update({
                'contract_id': contract.id,
                'tenant_id': contract.tenant_id.id,
                'start_date': contract.end_date + timedelta(days=1) if contract.end_date else fields.Date.today(),
                'end_date': contract.end_date + timedelta(days=365) if contract.end_date else fields.Date.today() + timedelta(days=365),
                'rent_amount': contract.rent_amount,
                'security_deposit': contract.security_deposit,
                'billing_cycle': contract.billing_cycle,
                'payment_term_id': contract.payment_term_id.id if contract.payment_term_id else False,
            })
        return res

    def action_renew_contract(self):
        """Create a new contract based on the current one but with renewed dates and terms"""
        self.ensure_one()
        
        new_contract = self.env['property.contract'].create({
            'property_id': self.property_id.id,
            'unit_id': self.unit_id.id,
            'tenant_id': self.tenant_id.id,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'rent_amount': self.rent_amount,
            'security_deposit': self.security_deposit,
            'billing_cycle': self.billing_cycle,
            'payment_term_id': self.payment_term_id.id if self.payment_term_id else False,
            'previous_contract_id': self.contract_id.id,
            'is_renewal': True,
            'contract_type': self.contract_id.contract_type,
            'company_id': self.contract_id.company_id.id,
        })
        
        # Update the old contract
        self.contract_id.write({
            'renewed_contract_id': new_contract.id,
            'state': 'renewed'
        })
        
        # Open the new contract form view
        return {
            'name': _('Renewed Contract'),
            'view_mode': 'form',
            'res_model': 'property.contract',
            'res_id': new_contract.id,
            'type': 'ir.actions.act_window',
        }
