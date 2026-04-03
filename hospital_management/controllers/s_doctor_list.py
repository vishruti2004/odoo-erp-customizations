from odoo import http
from odoo.http import request

class HospitalDoctorController(http.Controller):
    
    @http.route('/hospital/get_filtered_doctors', 
                type='jsonrpc', 
                auth='public',
                methods=['POST'],
                csrf=False)
    def get_filtered_doctors(self, specialization_id=None, **kw):
        
        domain = [('active', '=', True)]
        
        if specialization_id and specialization_id != '0':
            domain.append(('specialization_id.code', '=', specialization_id))
        
        doctors = request.env['hospital.doctor'].search(domain)
        
        html = request.env['ir.ui.view']._render_template(
            "hospital_management.doctor_card_template", 
            {'doctors': doctors}
        )
        
        return {
            'result': html,
            'count': len(doctors)
        }