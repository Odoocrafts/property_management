from odoo import http, _
from odoo.http import request


class PropertyWebsite(http.Controller):
    @http.route(['/properties'], type='http', auth="public", website=True)
    def public_properties(self, **post):
        """Display available properties on the website"""
        properties = request.env['property.property'].sudo().search([
            ('state', '=', 'available')
        ])
        
        return request.render("property_management.website_properties", {
            'properties': properties,
        })

    @http.route(['/properties/<model("property.property"):property>'], type='http', auth="public", website=True)
    def public_property_detail(self, property, **post):
        """Display property details on the website"""
        # Get available units
        available_units = request.env['property.unit'].sudo().search([
            ('property_id', '=', property.id),
            ('state', '=', 'vacant')
        ])
        
        return request.render("property_management.website_property_detail", {
            'property': property,
            'available_units': available_units,
        })
        
    @http.route(['/maintenance/request'], type='http', auth="public", website=True)
    def maintenance_request_form(self, **kw):
        """Display maintenance request form"""
        properties = request.env['property.property'].sudo().search([])
        
        return request.render("property_management.website_maintenance_request", {
            'properties': properties,
        })
    
    @http.route(['/maintenance/submit'], type='http', auth="public", website=True)
    def maintenance_request_submit(self, **post):
        """Handle maintenance request form submission"""
        vals = {
            'property_id': int(post.get('property_id', False)),
            'unit_id': int(post.get('unit_id', False)) if post.get('unit_id') else False,
            'description': post.get('description'),
            'priority': post.get('priority', '1'),
            'maintenance_type': post.get('maintenance_type', 'corrective'),
            'state': 'new',
        }
        
        # If user is logged in, associate the request with their partner
        if not request.env.user._is_public():
            vals['request_by'] = request.env.user.partner_id.id
        # Otherwise, try to find or create a partner based on provided information
        elif post.get('name') and post.get('email'):
            partner = request.env['res.partner'].sudo().search([
                ('email', '=', post.get('email'))
            ], limit=1)
            
            if not partner:
                partner = request.env['res.partner'].sudo().create({
                    'name': post.get('name'),
                    'email': post.get('email'),
                    'phone': post.get('phone', False),
                })
                
            vals['request_by'] = partner.id
        
        # Create the maintenance request
        maintenance = request.env['property.maintenance'].sudo().create(vals)
        
        return request.render("property_management.website_maintenance_thanks", {
            'maintenance': maintenance,
        })
    
    @http.route(['/units/get_by_property'], type='json', auth="public", website=True)
    def get_units_by_property(self, property_id=None, **kw):
        """Get available units for a property (used by the form)"""
        if not property_id:
            return []
            
        units = request.env['property.unit'].sudo().search([
            ('property_id', '=', int(property_id)),
        ])
        
        return [{'id': unit.id, 'name': unit.name} for unit in units]
