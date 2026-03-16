from odoo.addons.portal.controllers.portal import (
    CustomerPortal,
    pager,
    get_records_pager,
)
from odoo.http import request, route
from odoo import fields
from odoo.fields import Datetime
from odoo.tools import groupby as groupbyelem
import pytz
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import get_records_pager


class PortalAppointments(CustomerPortal):

    @route(
        ["/my/appointments", "/my/appointments/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_appointments(
        self,
        page=1,
        sortby="id",
        filterby="all",
        groupby="none",
        search="",
        search_in="all",
        **kw,
    ):

        values = self._prepare_portal_layout_values()

        Appointment = request.env["hospital.appointment"]

        today = datetime.today()

        # DATE

        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_start - timedelta(days=1)

        month_start = today.replace(day=1)
        month_end = month_start + relativedelta(months=1) - timedelta(days=1)

        last_month_start = month_start - relativedelta(months=1)
        last_month_end = month_start - timedelta(days=1)

        year_start = today.replace(month=1, day=1)
        year_end = today.replace(month=12, day=31)

        # SORTING

        searchbar_sortings = {
            "id": {"label": "Appointment ID", "order": "id desc"},
            # 'doctor': {
            #     'label': 'Doctor',
            #     'order': 'doctor_id'
            # },
            # 'patient': {
            #     'label': 'Patient',
            #     'order': 'patient_id'
            # },
            "specialization": {"label": "Specialization", "order": "specialization_id"},
            "status": {"label": "Status", "order": "state"},
        }

        sort_order = searchbar_sortings.get(sortby)["order"]

        # FILTERS

        searchbar_filters = {
            "all": {"label": "All", "domain": []},
            "draft": {"label": "Draft", "domain": [("state", "=", "draft")]},
            "request": {"label": "Requested", "domain": [("state", "=", "request")]},
            "confirm": {"label": "Confirmed", "domain": [("state", "=", "confirm")]},
            "consult": {
                "label": "In Consultation",
                "domain": [("state", "=", "consult")],
            },
            "done": {"label": "Done", "domain": [("state", "=", "done")]},
            "cancel": {"label": "Cancelled", "domain": [("state", "=", "cancel")]},
            "this_week": {
                "label": "This Week",
                "domain": [
                    ("start_datetime", ">=", week_start),
                    ("start_datetime", "<=", week_end),
                ],
            },
            "last_week": {
                "label": "Last Week",
                "domain": [
                    ("start_datetime", ">=", last_week_start),
                    ("start_datetime", "<=", last_week_end),
                ],
            },
            "this_month": {
                "label": "This Month",
                "domain": [
                    ("start_datetime", ">=", month_start),
                    ("start_datetime", "<=", month_end),
                ],
            },
            "last_month": {
                "label": "Last Month",
                "domain": [
                    ("start_datetime", ">=", last_month_start),
                    ("start_datetime", "<=", last_month_end),
                ],
            },
            "this_year": {
                "label": "This Year",
                "domain": [
                    ("start_datetime", ">=", year_start),
                    ("start_datetime", "<=", year_end),
                ],
            },
        }

        domain = list(searchbar_filters.get(filterby)["domain"])

        # GROUP BY

        searchbar_groupby = {
            "none": {"label": "None"},
            "doctor_id": {"label": "Doctor"},
            "patient_id": {"label": "Patient"},
            "specialization_id": {"label": "Specialization"},
            "state": {"label": "Status"},
        }

        # SEARCH INPUTS

        searchbar_inputs = {
            "all": {"input": "all", "label": "Search All"},
            "patient": {"input": "patient", "label": "Patient"},
            "doctor": {"input": "doctor", "label": "Doctor"},
            "appointment": {"input": "appointment", "label": "Appointment"},
            "specialization": {"input": "specialization", "label": "Specialization"},
        }

        # SEARCH LOGIC

        if search:

            if search_in == "patient":

                domain += [
                    "|",
                    ("patient_id.patient_code", "ilike", search),
                    ("patient_id.partner_id.name", "ilike", search),
                ]

            elif search_in == "doctor":

                domain += [
                    "|",
                    ("doctor_id.doctor_code", "ilike", search),
                    ("doctor_id.partner_id.name", "ilike", search),
                ]

            elif search_in == "appointment":

                domain += ["|", ("name", "ilike", search), ("id", "ilike", search)]

            elif search_in == "specialization":

                domain += [("specialization_id.name", "ilike", search)]

            else:

                domain += [
                    "|",
                    "|",
                    "|",
                    "|",
                    "|",
                    ("name", "ilike", search),
                    ("id", "ilike", search),
                    ("doctor_id.doctor_code", "ilike", search),
                    ("doctor_id.partner_id.name", "ilike", search),
                    ("patient_id.patient_code", "ilike", search),
                    ("patient_id.partner_id.name", "ilike", search),
                ]

        # COUNT

        appointment_count = Appointment.search_count(domain)

        # PAGER

        pager_data = pager(
            url="/my/appointments",
            url_args={
                "sortby": sortby,
                "filterby": filterby,
                "groupby": groupby,
                "search": search,
                "search_in": search_in,
            },
            total=appointment_count,
            page=page,
            step=10,
        )

        # RECORDS

        appointments = Appointment.search(
            domain, order=sort_order, limit=10, offset=pager_data["offset"]
        )

        # GROUPING

        grouped_appointments = []

        if groupby != "none":

            if groupby == "state":

                appointments = appointments.sorted(key=lambda r: r.state or "")

            else:

                appointments = appointments.sorted(
                    key=lambda r: r[groupby].id if r[groupby] else 0
                )

            for key, group in groupbyelem(appointments, lambda r: r[groupby]):

                grouped_appointments.append(
                    {
                        "group_name": key.display_name if groupby != "state" else key,
                        "records": Appointment.concat(*group),
                    }
                )

        else:

            grouped_appointments.append({"group_name": False, "records": appointments})

        # VALUES

        values.update(
            {
                "appointments": appointments,
                "grouped_appointments": grouped_appointments,
                "page_name": "appointment",
                "pager": pager_data,
                "default_url": "/my/appointments",
                "searchbar_sortings": searchbar_sortings,
                "searchbar_filters": searchbar_filters,
                "searchbar_groupby": searchbar_groupby,
                "searchbar_inputs": searchbar_inputs,
                "search": search,
                "search_in": search_in,
                "sortby": sortby,
                "filterby": filterby,
                "groupby": groupby,
            }
        )

        return request.render("hospital_management.portal_my_appointments", values)

    @route(
        ["/my/appointment/<int:appointment_id>"], type="http", auth="user", website=True
    )
    def portal_my_appointment_detail(
        self,
        appointment_id,
        access_token=None,
        report_type=None,
        download=False,
        **kwargs,
    ):

        # Appointment = request.env['hospital.appointment'].sudo()
        # appointment = Appointment.browse(appointment_id)

        # if not appointment.exists():
        #     return request.render("website.404")

        # _document_check_access method automatic check security,record rules and give error if record is not exits

        appointment = self._document_check_access(
            "hospital.appointment", appointment_id, access_token
        )

        history = request.session.get("my_appointments_history", [])
        pager = get_records_pager(history, appointment)

        # download report

        if report_type in ("html", "pdf", "text"):
            return self._show_report(
                model=appointment,
                report_type=report_type,
                report_ref="hospital_management.report_appointment_document",
                download=download,
            )

        values = {
            "appointment": appointment,
            "prev_record": pager.get("prev_record"),
            "next_record": pager.get("next_record"),
            "page_name": "appointment_detail",
        }

        return request.render("hospital_management.portal_appointment_page", values)

    @route(["/my/appointment/add"], type="http", auth="user", website=True)
    def portal_add_appointment(
        self, specialization_id=None, doctor_id=None, error_msg=None, **kwargs
    ):

        values = self._prepare_portal_layout_values()

        specializations = request.env["hospital.specialization"].sudo().search([])
        patients = request.env["hospital.patient"].sudo().search([])

        # LOGIN USER
        user = request.env.user

        # FIND LOGIN DOCTOR
        login_doctor = (
            request.env["hospital.doctor"]
            .sudo()
            .search([("user_id", "=", user.id)], limit=1)
        )

        # FIND LOGIN PATIENT
        login_patient = (
            request.env["hospital.patient"]
            .sudo()
            .search([("partner_id", "=", user.partner_id.id)], limit=1)
        )
        print("LOGIN PATIENT >>>", login_patient)

        spec_id = specialization_id or kwargs.get("specialization_id")
        doc_id = doctor_id or kwargs.get("doctor_id")

        # If doctor selected but specialization not selected
        if doc_id and not spec_id:
            selected_doctor = request.env["hospital.doctor"].sudo().browse(int(doc_id))
            spec_id = selected_doctor.specialization_id.id

        # If doctor login and nothing selected → auto select
        if login_doctor and not spec_id:
            spec_id = login_doctor.specialization_id.id
            doc_id = login_doctor.id

        # LOAD ALL DOCTORS
        doctors = request.env["hospital.doctor"].sudo().search([])

        selected_doctor = (
            request.env["hospital.doctor"].sudo().browse(int(doc_id))
            if doc_id
            else False
        )

        values.update(
            {
                "specializations": specializations,
                "doctors": doctors,
                "patients": patients,
                "login_patient": login_patient,
                "selected_spec_id": int(spec_id) if spec_id else False,
                "selected_doc": selected_doctor,
                "error_msg": error_msg,
                "post_data": kwargs,
                "page_name": "appointment_new",
            }
        )

        return request.render("hospital_management.portal_add_appointment", values)

    @route(
        ["/my/appointment/add/submit"],
        type="http",
        auth="user",
        website=True,
        csrf=True,
    )
    def portal_add_appointment_submit(self, **post):

        try:
            raw_start = post.get("start_datetime").replace("T", " ")
            raw_end = post.get("end_datetime").replace("T", " ")

            naive_start = Datetime.to_datetime(raw_start)
            naive_end = Datetime.to_datetime(raw_end)

            user_tz = pytz.timezone(request.env.user.tz or "Asia/Kolkata")

            start_dt_utc = (
                user_tz.localize(naive_start).astimezone(pytz.utc).replace(tzinfo=None)
            )
            end_dt_utc = (
                user_tz.localize(naive_end).astimezone(pytz.utc).replace(tzinfo=None)
            )

            vals = {
                "specialization_id": (
                    int(post.get("specialization_id"))
                    if post.get("specialization_id")
                    else False
                ),
                "doctor_id": (
                    int(post.get("doctor_id")) if post.get("doctor_id") else False
                ),
                "patient_id": (
                    int(post.get("patient_id")) if post.get("patient_id") else False
                ),
                "start_datetime": start_dt_utc,
                "end_datetime": end_dt_utc,
                "description": post.get("description"),
            }

            Appointment = request.env["hospital.appointment"].with_context(
                tz=request.env.user.tz
            )

            appointment_id = post.get("appointment_id")

            if appointment_id:
                appointment = Appointment.browse(int(appointment_id))
                appointment.write(vals)
            else:
                Appointment.create(vals)

            return request.redirect("/my/appointments")

        except Exception as e:
            return self.portal_add_appointment(error_msg=str(e), **post)

    @route(
        ["/my/appointment/edit/<int:appointment_id>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_edit_appointment(self, appointment_id, **kwargs):

        appointment = request.env["hospital.appointment"].browse(appointment_id)

        if not appointment.exists():
            return request.render("website.404")

        specializations = request.env["hospital.specialization"].sudo().search([])
        patients = request.env["hospital.patient"].sudo().search([])

        doctors = (
            request.env["hospital.doctor"]
            .sudo()
            .search([("specialization_id", "=", appointment.specialization_id.id)])
        )

        values = {
            "appointment": appointment,
            "specializations": specializations,
            "doctors": doctors,
            "patients": patients,
            "selected_spec_id": appointment.specialization_id.id,
            "selected_doc": appointment.doctor_id,
            "post_data": {},
            "page_name": "appointment_edit",
            "context_timestamp": lambda dt: fields.Datetime.context_timestamp(
                request.env.user, dt
            ),
        }

        return request.render("hospital_management.portal_add_appointment", values)

    @route(
        ["/my/appointment/action/<int:appointment_id>/<string:action>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_appointment_action(self, appointment_id, action, **kw):

        appointment = request.env["hospital.appointment"].browse(appointment_id)

        if action == "request":
            appointment.action_requested()

        elif action == "confirm":
            appointment.action_confirm()

        elif action == "consult":
            appointment.action_consult()

        elif action == "done":
            doc_desc = kw.get("doc_description")

            if not doc_desc:
                return request.render(
                    "website.500",
                    {
                        "error_message": "please add consultation description before Done"
                    },
                )

            appointment.write({"doc_description": doc_desc})

            appointment.action_done()

        elif action == "cancel":

            cancel_reason = kw.get("cancel_reason")

            appointment.write({"state": "cancel", "cancel_reason": cancel_reason})

        elif action == "reset":
            appointment.action_reset_to_draft()

        return request.redirect(f"/my/appointment/{appointment_id}")
