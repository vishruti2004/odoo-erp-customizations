# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class LockerAccessController(http.Controller):

    # Find person endpoint
    @http.route("/locker/access/find_person", type="json", auth="user", methods=["POST"])
    def find_person(self, identity=None):
        if not identity:
            return {"success": False, "message": "Please enter name, email or phone number."}

        identity = str(identity).strip()
        if not identity:
            return {"success": False, "message": "Please enter name, email or phone number."}

        Partner = request.env["res.partner"].sudo()
        Allocation = request.env["locker.allocation"].sudo()
        Credential = request.env["locker.access.credential"].sudo()

        partners = Partner.search([
            "|", "|",
            ("name", "ilike", identity),
            ("email", "ilike", identity),
            ("phone", "ilike", identity),
        ])

        if not partners:
            return {"success": False, "message": "No person found."}

        allocations = Allocation.search([
            ("state", "=", "allocated"),
            "|",
            ("partner_id", "in", partners.ids),
            ("authorized_partner_ids", "in", partners.ids),
        ])

        if not allocations:
            return {"success": False, "message": "No active locker allocation found for this person."}

        persons = []
        for allocation in allocations:
            allowed_partners = allocation.partner_id | allocation.authorized_partner_ids
            for partner in allowed_partners:
                credential = Credential.search([
                    ("allocation_id", "=", allocation.id),
                    ("partner_id", "=", partner.id),
                    ("active", "=", True),
                ], limit=1)

                persons.append({
                    "partner_id": partner.id,
                    "partner_name": partner.display_name,
                    "email": partner.email or "",
                    "phone": partner.phone or "",
                    "allocation_id": allocation.id,
                    "locker_id": allocation.locker_id.id,
                    "locker_name": allocation.locker_id.display_name,
                    "profile_id": allocation.profile_id.id,
                    "profile_name": allocation.profile_id.display_name,
                    "access_method": allocation.access_method,
                    "has_credential": bool(credential),
                })

        if not persons:
            return {"success": False, "message": "No authorized person found."}

        return {"success": True, "persons": persons}

    # Authenticate endpoint
    @http.route("/locker/access/authenticate", type="json", auth="user", methods=["POST"])
    def authenticate(self, identity=None, partner_id=None, allocation_id=None):
        if not identity:
            return {"success": False, "message": "Please enter or scan your authentication credential."}

        if not partner_id:
            return {"success": False, "message": "Please select a person first."}

        if not allocation_id:
            return {"success": False, "message": "Locker allocation is required."}

        identity = str(identity).strip()
        if not identity:
            return {"success": False, "message": "Please enter or scan your authentication credential."}

        Partner = request.env["res.partner"].sudo()
        Allocation = request.env["locker.allocation"].sudo()
        Credential = request.env["locker.access.credential"].sudo()
        Access = request.env["locker.access"].sudo()

        partner = Partner.browse(int(partner_id)).exists()
        allocation = Allocation.browse(int(allocation_id)).exists()

        if not partner:
            return {"success": False, "message": "Person not found."}

        if not allocation:
            return {"success": False, "message": "Locker allocation not found."}

        if allocation.state != "allocated":
            return {"success": False, "message": "This locker is not currently allocated."}

        allowed_partner_ids = allocation.authorized_partner_ids.ids + [allocation.partner_id.id]

        if partner.id not in allowed_partner_ids:
            return {"success": False, "message": "This person is not authorized for this locker."}

        credential = Credential.search([
            ("allocation_id", "=", allocation.id),
            ("partner_id", "=", partner.id),
            ("active", "=", True),
        ], limit=1)

        if not credential:
            return {"success": False, "message": "No active authentication credential found for this person."}

        access_method = credential.access_method
        credential_valid = False

        if access_method == "pin":
            credential_valid = credential.pin_code == identity
        elif access_method == "rfid":
            credential_valid = credential.rfid_uid == identity
        elif access_method == "qr":
            credential_valid = credential.qr_token == identity
        elif access_method == "biometric":
            credential_valid = credential.biometric_id == identity
        elif access_method == "physical_key":
            credential_valid = True

        if not credential_valid:
            return {"success": False, "message": "Invalid authentication credential."}

        active_access = Access.search([
            ("allocation_id", "=", allocation.id),
            ("authenticated_partner_id", "=", partner.id),
            ("state", "=", "checked_in"),
        ], limit=1, order="id desc")

        if active_access:
            access_status = "Checked In"
            can_check_in = False
            can_check_out = True
        else:
            access_status = "Checked Out"
            can_check_in = True
            can_check_out = False

        return {
            "success": True,
            "message": "Identity verified successfully.",
            "allocation": {
                "id": allocation.id,
                "partner_id": allocation.partner_id.id,
                "partner_name": allocation.partner_id.display_name,
                "authenticated_partner_id": partner.id,
                "authenticated_partner_name": partner.display_name,
                "locker_id": allocation.locker_id.id,
                "locker_name": allocation.locker_id.display_name,
                "profile_id": allocation.profile_id.id,
                "profile_name": allocation.profile_id.display_name,
                "access_method": access_method,
                "access_status": access_status,
                "can_check_in": can_check_in,
                "can_check_out": can_check_out,
            },
        }

    # Action endpoint (Check In / Check Out)
    @http.route("/locker/access/action", type="json", auth="user", methods=["POST"])
    def access_action(self, allocation_id=None, action=None, authenticated_partner_id=None):
        if not allocation_id:
            return {"success": False, "message": "Locker allocation is required."}

        if action not in ("check_in", "check_out"):
            return {"success": False, "message": "Invalid access action."}

        if not authenticated_partner_id:
            return {"success": False, "message": "Authenticated person is required."}

        Allocation = request.env["locker.allocation"].sudo()
        Access = request.env["locker.access"].sudo()

        allocation = Allocation.browse(int(allocation_id)).exists()

        if not allocation:
            return {"success": False, "message": "Locker allocation not found."}

        if allocation.state != "allocated":
            return {"success": False, "message": "This locker is not currently allocated."}

        partner = request.env["res.partner"].sudo().browse(int(authenticated_partner_id)).exists()

        if not partner:
            return {"success": False, "message": "Authenticated person not found."}

        allowed_partner_ids = allocation.authorized_partner_ids.ids + [allocation.partner_id.id]

        if partner.id not in allowed_partner_ids:
            return {"success": False, "message": "This person is not authorized for this locker."}

        active_access = Access.search([
            ("allocation_id", "=", allocation.id),
            ("authenticated_partner_id", "=", partner.id),
            ("state", "=", "checked_in"),
        ], limit=1, order="id desc")

        if action == "check_in":
            if active_access:
                return {"success": False, "message": "This person is already checked in."}

            access = Access.create({
                "partner_id": allocation.partner_id.id,
                "authenticated_partner_id": partner.id,
                "allocation_id": allocation.id,
                "state": "checked_out",
            })

            access.action_check_in()

            return {
                "success": True,
                "message": "Check In successful.",
                "allocation": {
                    "id": allocation.id,
                    "partner_id": allocation.partner_id.id,
                    "partner_name": allocation.partner_id.display_name,
                    "authenticated_partner_id": partner.id,
                    "authenticated_partner_name": partner.display_name,
                    "locker_id": allocation.locker_id.id,
                    "locker_name": allocation.locker_id.display_name,
                    "profile_id": allocation.profile_id.id,
                    "profile_name": allocation.profile_id.display_name,
                    "access_method": allocation.access_method,
                    "access_status": "Checked In",
                    "can_check_in": False,
                    "can_check_out": True,
                },
            }

        if not active_access:
            return {"success": False, "message": "This person is not currently checked in."}

        active_access.action_check_out()

        return {
            "success": True,
            "message": "Check Out successful.",
            "allocation": {
                "id": allocation.id,
                "partner_id": allocation.partner_id.id,
                "partner_name": allocation.partner_id.display_name,
                "authenticated_partner_id": partner.id,
                "authenticated_partner_name": partner.display_name,
                "locker_id": allocation.locker_id.id,
                "locker_name": allocation.locker_id.display_name,
                "profile_id": allocation.profile_id.id,
                "profile_name": allocation.profile_id.display_name,
                "access_method": allocation.access_method,
                "access_status": "Checked Out",
                "can_check_in": True,
                "can_check_out": False,
            },
        }