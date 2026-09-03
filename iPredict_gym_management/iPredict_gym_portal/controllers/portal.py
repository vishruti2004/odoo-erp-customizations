# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request

class GymPortal(http.Controller):
    def _is_admin(self):
        return request.env.user.has_group("base.group_system")

    def _is_portal_user(self):
        return request.env.user.has_group("base.group_portal")

    def _get_member(self):
        if not self._is_portal_user():
            return request.env["res.partner"].browse([])
        partner = request.env.user.partner_id
        return request.env["res.partner"].sudo().search([
            ("id", "=", partner.id),
            ("is_gym_member", "=", True),
        ], limit=1)

    def _get_trainer(self):
        return request.env["hr.employee"].sudo().search([
            ("user_id", "=", request.env.user.id),
            ("is_trainer", "=", True),
        ], limit=1)

    def _get_portal_access(self):
        is_admin = self._is_admin()
        is_portal_user = self._is_portal_user()
        member = self._get_member()
        trainer = self._get_trainer()
        is_gym_portal_member = (
            is_portal_user
            and bool(member)
            and not is_admin
            and not trainer
        )
        return (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        )

    @http.route("/my/gym", type="http", auth="user", website=True)
    def gym_dashboard(self, **kwargs):
        (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        ) = self._get_portal_access()
        if not is_gym_portal_member:
            return request.redirect("/my")
        Measurement = request.env["gym.member.measurement"].sudo()
        MembershipHistory = request.env["gym.membership.history"].sudo()
        measurements = Measurement.search([
            ("member_ids", "=", member.id),
        ], order="measurement_date desc, id desc")
        active_membership = MembershipHistory.search([
            ("member_id", "=", member.id),
            ("status", "=", "active"),
        ], order="membership_start_date desc, id desc", limit=1)
        return request.render(
            "iPredict_gym_portal.gym_dashboard",
            {
                "partner": request.env.user.partner_id,
                "member": member,
                "trainer": trainer,
                "measurements": measurements,
                "active_membership": active_membership,
                "is_admin": is_admin,
                "is_portal_user": is_portal_user,
                "is_trainer": bool(trainer),
                "is_member": bool(member),
                "is_gym_portal_member": is_gym_portal_member,
                "page_name": "gym_management",
            },
        )

    @http.route("/my/gym/membership", type="http", auth="user", website=True)
    def gym_membership(self, **kwargs):
        (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        ) = self._get_portal_access()
        MembershipHistory = request.env["gym.membership.history"].sudo()
        if is_admin:
            histories = MembershipHistory.search(
                [],
                order="membership_start_date desc, id desc",
            )
        elif trainer:
            histories = MembershipHistory.search([
                ("member_id", "in", trainer.member_ids.ids),
            ], order="membership_start_date desc, id desc")
        elif member:
            histories = MembershipHistory.search([
                ("member_id", "=", member.id),
            ], order="membership_start_date desc, id desc")
        else:
            histories = MembershipHistory.browse([])
        return request.render(
            "iPredict_gym_portal.gym_membership",
            {
                "member": member,
                "trainer": trainer,
                "histories": histories,
                "is_admin": is_admin,
                "is_portal_user": is_portal_user,
                "is_trainer": bool(trainer),
                "is_member": bool(member),
                "is_gym_portal_member": is_gym_portal_member,
                "page_name": "gym_membership",
            },
        )

    @http.route("/my/gym/trainer", type="http", auth="user", website=True)
    def gym_trainer(self, **kwargs):
        (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        ) = self._get_portal_access()
        Trainer = request.env["hr.employee"].sudo()
        if is_admin:
            trainers = Trainer.search([
                ("is_trainer", "=", True),
            ], order="name")
        elif trainer:
            trainers = trainer
        else:
            trainers = Trainer.browse([])
        return request.render(
            "iPredict_gym_portal.gym_trainer",
            {
                "member": member,
                "trainer": trainer,
                "trainers": trainers,
                "is_admin": is_admin,
                "is_portal_user": is_portal_user,
                "is_trainer": bool(trainer),
                "is_member": bool(member),
                "is_gym_portal_member": is_gym_portal_member,
                "page_name": "gym_trainer",
            },
        )

    @http.route("/my/gym/workout", type="http", auth="user", website=True)
    def gym_workout(self, **kwargs):
        (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        ) = self._get_portal_access()
        WorkoutAssignment = request.env["gym.workout.assignment"].sudo()
        if is_admin:
            workout_plans = WorkoutAssignment.search(
                [],
                order="start_date desc, id desc",
            )
        elif trainer:
            workout_plans = WorkoutAssignment.search([
                ("member_id", "in", trainer.member_ids.ids),
            ], order="start_date desc, id desc")
        elif member:
            workout_plans = WorkoutAssignment.search([
                ("member_id", "=", member.id),
            ], order="start_date desc, id desc")
        else:
            workout_plans = WorkoutAssignment.browse([])
        return request.render(
            "iPredict_gym_portal.gym_workout",
            {
                "member": member,
                "trainer": trainer,
                "workout_plans": workout_plans,
                "is_admin": is_admin,
                "is_portal_user": is_portal_user,
                "is_trainer": bool(trainer),
                "is_member": bool(member),
                "is_gym_portal_member": is_gym_portal_member,
                "page_name": "gym_workout",
            },
        )


    @http.route("/my/gym/workout/<int:plan_id>", type="http", auth="user", website=True)
    def gym_workout_detail(self, plan_id, **kwargs):
        (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        ) = self._get_portal_access()

        if not is_gym_portal_member:
            return request.redirect("/my")

        WorkoutAssignment = request.env["gym.workout.assignment"].sudo()
        WorkoutPlan = request.env["gym.workout.plan"].sudo()

        if is_admin:
            assignments = WorkoutAssignment.search([
                ("plan_id", "=", plan_id),
            ])
        elif trainer:
            assignments = WorkoutAssignment.search([
                ("plan_id", "=", plan_id),
                ("member_id", "in", trainer.member_ids.ids),
            ])
        elif member:
            assignments = WorkoutAssignment.search([
                ("plan_id", "=", plan_id),
                ("member_id", "=", member.id),
            ])
        else:
            assignments = WorkoutAssignment.browse([])

        if not assignments:
            return request.redirect("/my/gym/workout")

        workout_plan = WorkoutPlan.browse(plan_id)

        if not workout_plan.exists():
            return request.redirect("/my/gym/workout")

        return request.render(
            "iPredict_gym_portal.gym_workout_detail",
            {
                "member": member,
                "trainer": trainer,
                "workout_plan": workout_plan,
                "assignments": assignments,
                "is_admin": is_admin,
                "is_portal_user": is_portal_user,
                "is_trainer": bool(trainer),
                "is_member": bool(member),
                "is_gym_portal_member": is_gym_portal_member,
                "page_name": "gym_workout",
            },
        )

    @http.route("/my/gym/diet", type="http", auth="user", website=True)
    def gym_diet(self, **kwargs):
        (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        ) = self._get_portal_access()

        if not is_gym_portal_member:
            return request.redirect("/my")

        DietAssignment = request.env["gym.diet.assignment"].sudo()

        if is_admin:
            diet_plans = DietAssignment.search(
                [],
                order="start_date desc, id desc",
            )
        elif trainer:
            diet_plans = DietAssignment.search([
                ("member_id", "in", trainer.member_ids.ids),
            ], order="start_date desc, id desc")
        elif member:
            diet_plans = DietAssignment.search([
                ("member_id", "=", member.id),
            ], order="start_date desc, id desc")
        else:
            diet_plans = DietAssignment.browse([])

        return request.render(
            "iPredict_gym_portal.gym_diet",
            {
                "member": member,
                "trainer": trainer,
                "diet_plans": diet_plans,
                "is_admin": is_admin,
                "is_portal_user": is_portal_user,
                "is_trainer": bool(trainer),
                "is_member": bool(member),
                "is_gym_portal_member": is_gym_portal_member,
                "page_name": "gym_diet",
            },
        )

    @http.route("/my/gym/diet/<int:plan_id>", type="http", auth="user", website=True)
    def gym_diet_detail(self, plan_id, **kwargs):
        (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        ) = self._get_portal_access()

        if not is_gym_portal_member:
            return request.redirect("/my")

        DietAssignment = request.env["gym.diet.assignment"].sudo()
        DietPlan = request.env["gym.diet.plan"].sudo()

        if is_admin:
            assignments = DietAssignment.search([
                ("plan_id", "=", plan_id),
            ])
        elif trainer:
            assignments = DietAssignment.search([
                ("plan_id", "=", plan_id),
                ("member_id", "in", trainer.member_ids.ids),
            ])
        elif member:
            assignments = DietAssignment.search([
                ("plan_id", "=", plan_id),
                ("member_id", "=", member.id),
            ])
        else:
            assignments = DietAssignment.browse([])

        if not assignments:
            return request.redirect("/my/gym/diet")

        diet_plan = DietPlan.browse(plan_id)

        if not diet_plan.exists():
            return request.redirect("/my/gym/diet")

        return request.render(
            "iPredict_gym_portal.gym_diet_detail",
            {
                "member": member,
                "trainer": trainer,
                "diet_plan": diet_plan,
                "assignments": assignments,
                "is_admin": is_admin,
                "is_portal_user": is_portal_user,
                "is_trainer": bool(trainer),
                "is_member": bool(member),
                "is_gym_portal_member": is_gym_portal_member,
                "page_name": "gym_diet",
            },
        )

    @http.route("/my/gym/members", type="http", auth="user", website=True)
    def gym_members(self, **kwargs):
        (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        ) = self._get_portal_access()
        Partner = request.env["res.partner"].sudo()
        if is_admin:
            members = Partner.search([
                ("is_gym_member", "=", True),
            ], order="name")
        elif trainer:
            members = trainer.member_ids.filtered(
                lambda m: m.is_gym_member
            ).sorted(key=lambda m: m.name or "")
        else:
            members = Partner.browse([])
        return request.render(
            "iPredict_gym_portal.gym_members",
            {
                "member": member,
                "trainer": trainer,
                "members": members,
                "is_admin": is_admin,
                "is_portal_user": is_portal_user,
                "is_trainer": bool(trainer),
                "is_member": bool(member),
                "is_gym_portal_member": is_gym_portal_member,
                "page_name": "gym_members",
            },
        )

    @http.route("/my/gym/measurement", type="http", auth="user", website=True)
    def gym_measurement(self, **kwargs):
        (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        ) = self._get_portal_access()
        Measurement = request.env["gym.member.measurement"].sudo()
        if is_admin:
            measurements = Measurement.search(
                [],
                order="measurement_date desc, id desc",
            )
        elif trainer:
            measurements = Measurement.search([
                ("member_ids", "in", trainer.member_ids.ids),
            ], order="measurement_date desc, id desc")
        elif member:
            measurements = Measurement.search([
                ("member_ids", "=", member.id),
            ], order="measurement_date desc, id desc")
        else:
            measurements = Measurement.browse([])
        return request.render(
            "iPredict_gym_portal.gym_measurement",
            {
                "member": member,
                "trainer": trainer,
                "measurements": measurements,
                "is_admin": is_admin,
                "is_portal_user": is_portal_user,
                "is_trainer": bool(trainer),
                "is_member": bool(member),
                "is_gym_portal_member": is_gym_portal_member,
                "page_name": "gym_measurement",
            },
        )

    def _get_active_membership(self, member):
        MembershipHistory = request.env["gym.membership.history"].sudo()
        return MembershipHistory.search([
            ("member_id", "=", member.id),
            ("status", "=", "active"),
        ], order="membership_start_date desc, id desc", limit=1)

    def _format_attendance_datetime(self, value):
        if not value:
            return ""
        user = request.env.user
        user_tz = user.tz or request.env.context.get("tz") or "UTC"
        localized = fields.Datetime.context_timestamp(
            user.with_context(tz=user_tz),
            value,
        )
        return localized.strftime("%d/%m/%Y %I:%M:%S %p")

    def _format_attendance_duration(self, check_in, check_out):
        if not check_in or not check_out:
            return ""

        check_in = fields.Datetime.to_datetime(check_in)
        check_out = fields.Datetime.to_datetime(check_out)

        duration = check_out - check_in
        total_minutes = int(duration.total_seconds() // 60)

        hours, minutes = divmod(total_minutes, 60)

        return f"{hours:02d}:{minutes:02d}"

    def _is_attendance_enabled(self, membership):
        return bool(
            membership
            and membership.company_id
            and membership.company_id.gym_member_attendance
        )

    @http.route(
        "/my/gym/attendance",
        type="http",
        auth="user",
        website=True,
    )
    def gym_attendance(self, **kwargs):
        (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        ) = self._get_portal_access()

        if not is_gym_portal_member:
            return request.redirect("/my")

        active_membership = self._get_active_membership(member)

        if not self._is_attendance_enabled(active_membership):
            return request.redirect("/my/gym")

        Attendance = request.env["gym.attendance"].sudo()

        try:
            page = int(kwargs.get("page", 1))
        except (TypeError, ValueError):
            page = 1

        if page < 1:
            page = 1

        per_page = 40

        domain = [
            ("member_id", "=", member.id),
        ]

        total_records = Attendance.search_count(domain)

        total_pages = (
            (total_records + per_page - 1) // per_page
            if total_records
            else 1
        )

        if page > total_pages:
            page = total_pages

        offset = (page - 1) * per_page

        attendances = Attendance.search(
            domain,
            order="check_in desc, id desc",
            limit=per_page,
            offset=offset,
        )

        attendance_datetime = {
            record.id: {
                "check_in": self._format_attendance_datetime(record.check_in),
                "check_out": self._format_attendance_datetime(record.check_out),
                "duration": self._format_attendance_duration(
                    record.check_in,
                    record.check_out,
                ),
            }
            for record in attendances
        }

        current_attendance = Attendance.search(
            [
                ("member_id", "=", member.id),
                ("status", "=", "checked_in"),
            ],
            order="check_in desc, id desc",
            limit=1,
        )

        pager_pages = []

        if total_pages <= 7:
            for page_number in range(1, total_pages + 1):
                pager_pages.append({
                    "number": page_number,
                    "is_current": page_number == page,
                })
        else:
            page_numbers = {1, total_pages}

            for page_number in range(
                max(1, page - 2),
                min(total_pages, page + 2) + 1,
            ):
                page_numbers.add(page_number)

            sorted_pages = sorted(page_numbers)

            previous_number = None

            for page_number in sorted_pages:
                if (
                    previous_number is not None
                    and page_number - previous_number > 1
                ):
                    pager_pages.append({
                        "number": "...",
                        "is_current": False,
                        "is_dots": True,
                    })

                pager_pages.append({
                    "number": page_number,
                    "is_current": page_number == page,
                    "is_dots": False,
                })

                previous_number = page_number

        return request.render(
            "iPredict_gym_portal.gym_attendance",
            {
                "member": member,
                "active_membership": active_membership,
                "attendances": attendances,
                "attendance_datetime": attendance_datetime,
                "current_attendance": current_attendance,
                "is_admin": is_admin,
                "is_portal_user": is_portal_user,
                "is_trainer": bool(trainer),
                "is_member": bool(member),
                "is_gym_portal_member": is_gym_portal_member,
                "page_name": "gym_attendance",
                "current_page": page,
                "total_pages": total_pages,
                "total_records": total_records,
                "per_page": per_page,
                "pager_pages": pager_pages,
                "format_attendance_datetime": self._format_attendance_datetime,
            },
        )

    @http.route(
        "/my/gym/attendance/check-in",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def gym_attendance_check_in(self, **kwargs):
        (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        ) = self._get_portal_access()
        if not is_gym_portal_member:
            return request.redirect("/my")
        active_membership = self._get_active_membership(member)
        if not self._is_attendance_enabled(active_membership):
            return request.redirect("/my/gym")
        Attendance = request.env["gym.attendance"].sudo()
        current_attendance = Attendance.search(
            [
                ("member_id", "=", member.id),
                ("status", "=", "checked_in"),
            ],
            order="check_in desc, id desc",
            limit=1,
        )
        if not current_attendance:
            Attendance.create({
                "member_id": member.id,
                "membership_id": active_membership.id,
                "check_in": fields.Datetime.now(),
                "company_id": active_membership.company_id.id,
                "status": "checked_in",
            })
        return request.redirect("/my")

    @http.route(
        "/my/gym/attendance/check-out",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def gym_attendance_check_out(self, **kwargs):
        (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        ) = self._get_portal_access()
        if not is_gym_portal_member:
            return request.redirect("/my")
        active_membership = self._get_active_membership(member)
        if not self._is_attendance_enabled(active_membership):
            return request.redirect("/my/gym")
        Attendance = request.env["gym.attendance"].sudo()
        current_attendance = Attendance.search(
            [
                ("member_id", "=", member.id),
                ("status", "=", "checked_in"),
            ],
            order="check_in desc, id desc",
            limit=1,
        )
        if current_attendance:
            current_attendance.write({
                "check_out": fields.Datetime.now(),
                "status": "checked_out",
            })
        return request.redirect("/my")

    @http.route(
        "/my/gym/attendance/validate-qr",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
    )
    def validate_attendance_qr(self, qr_token, action_type):
        (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        ) = self._get_portal_access()
        if not is_gym_portal_member:
            return {
                "success": False,
                "message": "You are not authorized to manage gym attendance.",
            }
        active_membership = self._get_active_membership(member)
        if not active_membership:
            return {
                "success": False,
                "message": "No active membership found.",
            }
        company = active_membership.company_id
        if not company.gym_member_attendance:
            return {
                "success": False,
                "message": "Member attendance is not enabled.",
            }
        if not company.gym_member_attendance_qr:
            return {
                "success": False,
                "message": "QR Code attendance is not enabled.",
            }
        if not company.gym_attendance_qr_token:
            return {
                "success": False,
                "message": "Attendance QR Code is not configured.",
            }
        if qr_token != company.gym_attendance_qr_token:
            return {
                "success": False,
                "message": "Invalid Gym QR Code.",
            }
        Attendance = request.env["gym.attendance"].sudo()
        current_attendance = Attendance.search(
            [
                ("member_id", "=", member.id),
                ("membership_id", "=", active_membership.id),
                ("company_id", "=", company.id),
                ("status", "=", "checked_in"),
                ("check_out", "=", False),
            ],
            order="check_in desc, id desc",
            limit=1,
        )
        if action_type == "check_in":
            if current_attendance:
                return {
                    "success": False,
                    "message": "You are already checked in.",
                }
            Attendance.create({
                "member_id": member.id,
                "membership_id": active_membership.id,
                "check_in": fields.Datetime.now(),
                "company_id": company.id,
                "status": "checked_in",
            })
            return {
                "success": True,
                "message": "Check In successful.",
            }
        if action_type == "check_out":
            if not current_attendance:
                return {
                    "success": False,
                    "message": "No active check-in found.",
                }
            current_attendance.write({
                "check_out": fields.Datetime.now(),
                "status": "checked_out",
            })
            return {
                "success": True,
                "message": "Check Out successful.",
            }
        return {
            "success": False,
            "message": "Invalid attendance action.",
        }