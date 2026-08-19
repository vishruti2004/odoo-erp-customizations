# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'
    
    check_in_image = fields.Binary(string='Check In Image', compute='_compute_images')
    check_out_image = fields.Binary(string='Check Out Image', compute='_compute_images')

    def _compute_images(self):
        IrAttachment = self.env['ir.attachment']
        for record in self:
            check_in_attach = IrAttachment.search([
                ('res_model', '=', 'hr.attendance'),
                ('res_id', '=', record.id),
                ('name', '=like', 'check_in_image_%')
            ], order='id desc', limit=1)

            check_out_attach = IrAttachment.search([
                ('res_model', '=', 'hr.attendance'),
                ('res_id', '=', record.id),
                ('name', '=like', 'check_out_image_%')
            ], order='id desc', limit=1)
            record.write({
                'check_in_image': check_in_attach.datas if check_in_attach else False,
                'check_out_image': check_out_attach.datas if check_out_attach else False,
            })
