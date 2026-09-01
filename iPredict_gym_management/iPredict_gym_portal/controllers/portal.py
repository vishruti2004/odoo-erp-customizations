# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class GymPortal(http.Controller):

    # =========================================================
    # USER ACCESS HELPERS
    # =========================================================

    def _is_admin(self):
        return request.env.user.has_group("base.group_system")

    def _is_portal_user(self):
        return request.env.user.has_group("base.group_portal")

    def _get_member(self):
        """
        Return the logged-in user's gym member record.
        Only portal users are considered gym members for portal access.
        """
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

        # Only a PORTAL USER + GYM MEMBER can see gym blocks.
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

    # =========================================================
    # GYM MANAGEMENT DASHBOARD
    # =========================================================

    @http.route("/my/gym", type="http", auth="user", website=True)
    def gym_dashboard(self, **kwargs):
        (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        ) = self._get_portal_access()

        # Gym dashboard is ONLY for Gym Member Portal User.
        if not is_gym_portal_member:
            return request.redirect("/my")

        Measurement = request.env["gym.member.measurement"].sudo()
        MembershipHistory = request.env["gym.membership.history"].sudo()

        measurements = Measurement.search([
            ("member_ids", "=", member.id),
        ], order="measurement_date desc, id desc")

        # Get only the currently active membership.
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

    # =========================================================
    # MEMBERSHIP
    # =========================================================

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

    # =========================================================
    # TRAINER
    # =========================================================

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

    # =========================================================
    # WORKOUT PLANS
    # =========================================================

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

    # =========================================================
    # DIET PLANS
    # =========================================================

    @http.route("/my/gym/diet", type="http", auth="user", website=True)
    def gym_diet(self, **kwargs):
        (
            is_admin,
            is_portal_user,
            member,
            trainer,
            is_gym_portal_member,
        ) = self._get_portal_access()

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

    # =========================================================
    # MEMBERS
    # =========================================================

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

    # =========================================================
    # MEASUREMENT HISTORY
    # =========================================================

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