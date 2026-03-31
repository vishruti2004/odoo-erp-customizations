# from odoo import http
# from odoo.http import request

# class HospitalController(http.Controller):
    
#     @http.route('/hospital/get_doctors', type='json', auth='public', methods=['POST'], website=True)
#     def get_doctors(self, specialization_id):
#         domain = []
        
#         if specialization_id and specialization_id != 0:
#             domain.append(('specialization_id', '=', specialization_id))
        
#         doctors = request.env['hospital.doctor'].sudo().search(domain)
        
#         result = []
#         for doc in doctors:
#             result.append({
#                 'id': doc.id,
#                 'name': doc.name,
#                 'specialization_name': doc.specialization_id.name if doc.specialization_id else '',
#                 'image': '/web/image/hospital.doctor/%s/image_1920' % doc.id if doc.image_1920 else '',
#             })
        
#         return result