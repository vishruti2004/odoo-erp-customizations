from odoo import http
from odoo.http import request

class HospitalDoctorController(http.Controller):

    @http.route('/hospital/get_filtered_doctors', type='jsonrpc', auth='public', website=True)
    def get_filtered_doctors(self, spec_id=0, **kwargs):
        print("==========1 RECEIVED:", spec_id, kwargs)
        
        domain = [('active', '=', True)]
        
        if spec_id and spec_id != '0':
            try:
                s_id = int(spec_id)
                domain.append(('specialization_id', '=', s_id))
            except (ValueError, TypeError):
                # Jo String (jem ke 'NEURO') avti hoy:
                domain.append(('specialization_id.name', 'ilike', spec_id))
        
        # Search doctors
        doctors = request.env['hospital.doctor'].sudo().search(domain)
        print("==========2 DOCTORS FOUND:", doctors)

        html = request.env['ir.qweb'].sudo()._render(
            "hospital_management.doctor_card_template", 
            {'doctors': doctors}
        )
        
        return {'html': html}
