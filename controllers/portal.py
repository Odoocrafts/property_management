from odoo import http, _
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.http import request
from odoo.osv.expression import OR, AND
from odoo.exceptions import AccessError, MissingError
from collections import OrderedDict

# Constants for model names
PROPERTY_MAINTENANCE_MODEL = 'property.maintenance'
PROPERTY_UNIT_MODEL = 'property.unit'


class PropertyPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        
        if 'maintenance_count' in counters:
            maintenance_count = request.env[PROPERTY_MAINTENANCE_MODEL].search_count(
                self._get_maintenance_domain()
            ) if request.env.user.has_group('base.group_portal') else 0
            values['maintenance_count'] = maintenance_count
            
        if 'property_unit_count' in counters:
            unit_count = request.env[PROPERTY_UNIT_MODEL].search_count(
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
        property_unit_model = request.env[PROPERTY_UNIT_MODEL]
        
        domain = self._get_unit_domain()
        
        # Count for pager
        unit_count = property_unit_model.search_count(domain)
        
        # Pager
        pager = portal_pager(
            url="/my/properties",
            url_args={},
            total=unit_count,
            page=page,
            step=self._items_per_page
        )
        
        # Content - ensure units is at least an empty list
        units = property_unit_model.search(domain, limit=self._items_per_page, offset=pager['offset']) or []
        
        values.update({
            'units': units,
            'page_name': 'property',
            'pager': pager,
            'default_url': '/my/properties',
            # Add empty defaults for any value that might be accessed in the template
            'searchbar_sortings': {},
            'searchbar_filters': {},
            'sortby': sortby or '',
            'filterby': '',
            'date': date_begin,
        })
        return request.render("property_management.portal_my_properties", values)
        
    @http.route(['/my/property/<int:unit_id>'], type='http', auth="user", website=True)
    def portal_my_property_detail(self, unit_id=None, **kw):
        try:
            unit_sudo = self._document_check_access(PROPERTY_UNIT_MODEL, unit_id)
        except (AccessError, MissingError):
            return request.redirect('/my')
            
        values = self._prepare_portal_layout_values()
        values.update({
            'unit': unit_sudo,
            'page_name': 'property_detail',
            # Add empty defaults for any value that might be accessed in the template
            'maintenance_requests': [],
            'pager': {'page_count': 0},
            'searchbar_sortings': {},
            'searchbar_filters': {},
            'sortby': '',
            'filterby': '',
            'default_url': '/my/property/' + str(unit_id),
        })
        return request.render("property_management.portal_property_detail", values)
        
    @http.route(['/my/maintenance', '/my/maintenance/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_maintenance(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        values = self._prepare_portal_layout_values()
        maintenance_model = request.env[PROPERTY_MAINTENANCE_MODEL]
        
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
        maintenance_count = maintenance_model.search_count(domain)
        
        # Pager
        pager = portal_pager(
            url="/my/maintenance",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby},
            total=maintenance_count,
            page=page,
            step=self._items_per_page
        )
        
        # Content - ensure maintenance_requests is at least an empty list
        maintenance_requests = maintenance_model.search(domain, order=order, limit=self._items_per_page, offset=pager['offset']) or []
        
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
            # Add other default values to prevent undefined issues
            'units': [],
        })
        return request.render("property_management.portal_my_maintenance", values)
        
    @http.route(['/my/maintenance/<int:maintenance_id>'], type='http', auth="user", website=True)
    def portal_my_maintenance_detail(self, maintenance_id=None, **kw):
        try:
            maintenance_sudo = self._document_check_access(PROPERTY_MAINTENANCE_MODEL, maintenance_id)
        except (AccessError, MissingError):
            return request.redirect('/my')
            
        values = self._prepare_portal_layout_values()
        values.update({
            'maintenance': maintenance_sudo,
            'page_name': 'maintenance_detail',
            # Add empty defaults for any value that might be accessed in the template
            'units': [],
            'pager': {'page_count': 0},
            'searchbar_sortings': {},
            'searchbar_filters': {},
            'sortby': '',
            'filterby': '',
            'default_url': '/my/maintenance/' + str(maintenance_id),
        })
        return request.render("property_management.portal_maintenance_detail", values)
