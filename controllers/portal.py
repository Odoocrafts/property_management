from odoo import http, _
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.http import request
from odoo.osv.expression import OR, AND
from odoo.exceptions import AccessError, MissingError
from collections import OrderedDict


class PropertyPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        
        if 'maintenance_count' in counters:
            maintenance_count = request.env['property.maintenance'].search_count(
                self._get_maintenance_domain()
            ) if request.env.user.has_group('base.group_portal') else 0
            values['maintenance_count'] = maintenance_count
            
        if 'property_unit_count' in counters:
            unit_count = request.env['property.unit'].search_count(
                self._get_unit_domain()
            ) if request.env.user.has_group('base.group_portal') else 0
            values['property_unit_count'] = unit_count
            
        return values
    
    def _get_maintenance_domain(self):
        partner = request.env.user.partner_id
        domain = [
            ('request_by', '=', partner.id)
        ]
        return domain
        
    def _get_unit_domain(self):
        partner = request.env.user.partner_id
        domain = [
            ('tenant_id', '=', partner.id)
        ]
        return domain
        
    @http.route(['/my/properties', '/my/properties/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_properties(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        PropertyUnit = request.env['property.unit']
        
        domain = self._get_unit_domain()
        
        # Count for pager
        unit_count = PropertyUnit.search_count(domain)
        
        # Pager
        pager = portal_pager(
            url="/my/properties",
            url_args={},
            total=unit_count,
            page=page,
            step=self._items_per_page
        )
        
        # Content
        units = PropertyUnit.search(domain, limit=self._items_per_page, offset=pager['offset'])
        
        values.update({
            'units': units,
            'page_name': 'property',
            'pager': pager,
            'default_url': '/my/properties',
        })
        return request.render("property_management.portal_my_properties", values)
        
    @http.route(['/my/property/<int:unit_id>'], type='http', auth="user", website=True)
    def portal_my_property_detail(self, unit_id=None, **kw):
        try:
            unit_sudo = self._document_check_access('property.unit', unit_id)
        except (AccessError, MissingError):
            return request.redirect('/my')
            
        values = {
            'unit': unit_sudo,
            'page_name': 'property_detail',
        }
        return request.render("property_management.portal_property_detail", values)
        
    @http.route(['/my/maintenance', '/my/maintenance/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_maintenance(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        Maintenance = request.env['property.maintenance']
        
        domain = self._get_maintenance_domain()
        
        searchbar_sortings = {
            'date': {'label': _('Request Date'), 'order': 'request_date desc'},
            'priority': {'label': _('Priority'), 'order': 'priority desc'},
            'state': {'label': _('Status'), 'order': 'state'},
        }
        
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'new': {'label': _('New'), 'domain': [('state', '=', 'new')]},
            'assigned': {'label': _('Assigned'), 'domain': [('state', '=', 'assigned')]},
            'in_progress': {'label': _('In Progress'), 'domain': [('state', '=', 'in_progress')]},
            'done': {'label': _('Done'), 'domain': [('state', '=', 'done')]},
        }
        
        # Default sort by date
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        
        # Default filter by value
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']
        
        # Count for pager
        maintenance_count = Maintenance.search_count(domain)
        
        # Pager
        pager = portal_pager(
            url="/my/maintenance",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby},
            total=maintenance_count,
            page=page,
            step=self._items_per_page
        )
        
        # Content
        maintenance_requests = Maintenance.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        
        values.update({
            'date': date_begin,
            'maintenance_requests': maintenance_requests,
            'page_name': 'maintenance',
            'pager': pager,
            'default_url': '/my/maintenance',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
        })
        return request.render("property_management.portal_my_maintenance", values)
        
    @http.route(['/my/maintenance/<int:maintenance_id>'], type='http', auth="user", website=True)
    def portal_my_maintenance_detail(self, maintenance_id=None, **kw):
        try:
            maintenance_sudo = self._document_check_access('property.maintenance', maintenance_id)
        except (AccessError, MissingError):
            return request.redirect('/my')
            
        values = {
            'maintenance': maintenance_sudo,
            'page_name': 'maintenance_detail',
        }
        return request.render("property_management.portal_maintenance_detail", values)
