from odoo import models, fields, api
from odoo.exceptions import UserError
import io
import base64
import pandas as pd
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment
from openpyxl.cell.rich_text import TextBlock, CellRichText
from openpyxl.cell.text import InlineFont
from datetime import datetime
from odoo.exceptions import UserError, ValidationError



class AppointmentSummaryWizard(models.TransientModel):
    _name = 'appointment.summary.wizard'
    _description = 'Appointment Summary Wizard'

    start_date = fields.Datetime(string="Start Date")
    end_date = fields.Datetime(string="End Date")

    doctor_ids = fields.Many2many('hospital.doctor', string="Doctors")
    patient_ids = fields.Many2many('hospital.patient', string="Patients")

    is_doctor_user = fields.Boolean(
        string="Is Doctor User",
        compute="_compute_is_doctor_user"
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('request', 'Requested'),
        ('confirm', 'Confirmed'),
        ('consult', 'In Consultation'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string="Status")

    group_by = fields.Selection([
        ('doctor_id', 'Doctor'),
        ('patient_id', 'Patient'),
        ('state', 'Status'),
    ], string="Group By")

    sort_by = fields.Selection([
        ('start_datetime', 'Appointment Date'),
        ('doctor_id', 'Doctor'),
        ('patient_id', 'Patient'),
    ], string="Sort By", default='start_datetime')

    def _compute_is_doctor_user(self):
        for rec in self:
            rec.is_doctor_user = self.env.user.has_group(
                'hospital_management.group_doctor'
            )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        if self.env.user.has_group('hospital_management.group_doctor'):
            doctor = self.env['hospital.doctor'].search(
                [('user_id', '=', self.env.user.id)],
                # limit=1
            )
            if doctor:
                res['doctor_ids'] = [(6, 0, [doctor.id])]

        return res

    # ---------------- DOMAIN ----------------
    def _build_domain(self):
        self.ensure_one()
        domain = []
        if self.doctor_ids:
            domain.append(('doctor_id', 'in', self.doctor_ids.ids))
        
        if self.patient_ids:
            domain.append(('patient_id', 'in', self.patient_ids.ids))
            
        if self.start_date:
            domain.append(('start_datetime', '>=', self.start_date))
        if self.end_date:
            domain.append(('start_datetime', '<=', self.end_date))
        if self.state:
            domain.append(('state', '=', self.state))
        return domain

    # ---------------- PDF ----------------
    def action_generate_pdf(self):
        self.ensure_one()

        current_doctor = self.env['hospital.doctor'].search([('user_id', '=', self.env.user.id)])

        # Validation Logic
        if self.patient_ids and current_doctor:
            for patient in self.patient_ids:
                has_appointment = self.env['hospital.appointment'].search_count([
                    ('patient_id', '=', patient.id), 
                    ('doctor_id', '=', current_doctor.id)
                ])
                
                if not has_appointment:
                    raise ValidationError(
                        f"Patient '{patient.name}' has no appointments with Dr. {current_doctor.name}."
                    )

        appointments = self.env['hospital.appointment'].search(
            self._build_domain(),
            order=self.sort_by
        )

        if not appointments:
            raise UserError("No records found for selected filters.")

        return self.env.ref('hospital_management.action_appointment_summary_pdf').report_action(appointments)

    # ---------------- VIEW DATA ----------------
    def action_view_data(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Appointments',
            'res_model': 'hospital.appointment',
            'view_mode': 'list,form',
            'domain': self._build_domain(),
            'context': {'group_by': self.group_by},
            'target': 'current',
        }

    # ---------------- PDF ----------------
    # def action_generate_pdf(self):
    #     self.ensure_one()

    #     appointments = self.env['hospital.appointment'].search(
    #         self._build_domain(),
    #         order=self.sort_by
    #     )

    #     if not appointments:
    #         raise UserError("No records found for selected filters.")

    #     report = self.env.ref(
    #         'hospital_management.action_appointment_summary_pdf'
    #     )

    #     return report.report_action(appointments)


    

    # ---------------- XLSX ----------------
    def action_download_xlsx(self):
        self.ensure_one()

        appointments = self.env['hospital.appointment'].search(
            self._build_domain(),
            order=self.sort_by
        )

        if not appointments:
            raise UserError("No records found for selected filters.")

        data = []

        for rec in appointments:
            local_start = fields.Datetime.context_timestamp(self, rec.start_datetime)
            local_start = local_start.replace(tzinfo=None)

            status_dict = dict(rec._fields['state'].selection)
            status_value = status_dict.get(rec.state, rec.state)
            if status_value:
                status_value = status_value.title()

            data.append({
                "Appointment ID": rec.name,
                "Appointment Date": local_start,
                "Doctor": rec.doctor_id.display_name,
                "Patient": rec.patient_id.display_name,
                "Status": status_value,
            })

        df = pd.DataFrame(data)

        output = io.BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Summary', startrow=1)

            worksheet = writer.sheets['Summary']

            worksheet.merge_cells('A1:C1')
            worksheet['A1'] = "Appointment Summary Report"
            worksheet['A1'].font = Font(bold=True, size=14)
            worksheet['A1'].alignment = Alignment(horizontal='center', vertical='center')

            worksheet.merge_cells('D1:E1')
            now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
            now = now.replace(tzinfo=None)
            worksheet['D1'] = f"Generate Date: {now.strftime('%d-%m-%Y %I:%M %p')}"
            worksheet['D1'].font = Font(bold=True, size=11)
            worksheet['D1'].alignment = Alignment(horizontal='center', vertical='center')

            for col_num in range(1, 6):
                cell = worksheet.cell(row=2, column=col_num)
                cell.font = Font(bold=True, size=11)
                cell.alignment = Alignment(horizontal='center', vertical='center')

            bold_inline = InlineFont(b=True)

            for row_num in range(3, len(df) + 3):
                date_cell = worksheet.cell(row=row_num, column=2)
                if date_cell.value:
                    if isinstance(date_cell.value, datetime):
                        date_cell.number_format = 'DD-MM-YYYY hh:mm AM/PM'
                    date_cell.alignment = Alignment(horizontal='center', vertical='center')

                doctor_cell = worksheet.cell(row=row_num, column=3)
                if doctor_cell.value and '[' in str(doctor_cell.value):
                    value = str(doctor_cell.value)
                    if '] ' in value:
                        parts = value.split('] ', 1)
                        code_part = parts[0] + ']'
                        name_part = '\n' + parts[1]

                        doctor_cell.value = CellRichText(
                            TextBlock(bold_inline, code_part),
                            name_part
                        )
                        doctor_cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

                patient_cell = worksheet.cell(row=row_num, column=4)
                if patient_cell.value and '[' in str(patient_cell.value):
                    value = str(patient_cell.value)
                    if '] ' in value:
                        parts = value.split('] ', 1)
                        code_part = parts[0] + ']'
                        name_part = '\n' + parts[1]

                        patient_cell.value = CellRichText(
                            TextBlock(bold_inline, code_part),
                            name_part
                        )
                        patient_cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

                worksheet.cell(row=row_num, column=1).alignment = Alignment(horizontal='center', vertical='center')
                worksheet.cell(row=row_num, column=5).alignment = Alignment(horizontal='center', vertical='center')

            column_widths = {
                'A': 15,
                'B': 22,
                'C': 30,
                'D': 30,
                'E': 18,
            }

            for col, width in column_widths.items():
                worksheet.column_dimensions[col].width = width

            worksheet.freeze_panes = 'A3'

        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': 'Appointment_Summary_Report.xlsx',
            'datas': base64.b64encode(output.read()),
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }