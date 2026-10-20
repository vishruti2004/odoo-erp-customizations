# -*- coding: utf-8 -*-

import base64
import hashlib
import logging
import secrets
import time
import cv2
import numpy as np
import os
import onnxruntime as ort
from odoo import http
from odoo.http import request

# Allocation states in which the person is still allowed to check in / check out.
ACTIVE_ALLOCATION_STATES = ("allocated", "renewal_pending", "expired")

class LockerAccessController(http.Controller):
    _face_app = None
    _anti_spoof_session = None
    _anti_spoof_input_name = None
    _anti_spoof_output_name = None
    _anti_spoof_model_path = None
    _ANTI_SPOOF_THRESHOLD = 0.50
    _FACE_MATCH_THRESHOLD = 0.45

    @staticmethod
    def _patch_insightface_align():
        try:
            from insightface.utils import face_align
            from skimage import transform as trans
        except Exception:
            return
        if getattr(face_align, "_ipredict_patched", False):
            return
        if not hasattr(trans.SimilarityTransform, "from_estimate"):
            return
        original_estimate_norm = face_align.estimate_norm

        def estimate_norm(lmk, image_size=112, mode="arcface"):
            assert lmk.shape == (5, 2)
            assert image_size % 112 == 0 or image_size % 128 == 0
            if image_size % 112 == 0:
                ratio = float(image_size) / 112.0
                diff_x = 0
            else:
                ratio = float(image_size) / 128.0
                diff_x = 8.0 * ratio
            dst = face_align.arcface_dst * ratio
            dst[:, 0] += diff_x
            tform = trans.SimilarityTransform.from_estimate(lmk, dst)
            if not tform:
                return original_estimate_norm(lmk, image_size, mode)
            return tform.params[0:2, :]

        face_align.estimate_norm = estimate_norm
        face_align._ipredict_patched = True

    @classmethod
    def _get_face_app(cls):
        if cls._face_app is None:
            from insightface.app import FaceAnalysis
            cls._patch_insightface_align()
            cls._face_app = FaceAnalysis(
                name="buffalo_sc",
                providers=["CPUExecutionProvider"],
            )
            cls._face_app.prepare(
                ctx_id=0,
                det_size=(320, 320),
            )
        return cls._face_app

    @classmethod
    def _get_anti_spoof_session(cls):
        if cls._anti_spoof_session is None:
            model_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "lib",
                "face_antispoof",
                "MiniFASNetV2.onnx",
            )

            if not os.path.isfile(model_path):
                return None

            cls._anti_spoof_model_path = model_path

            cls._anti_spoof_session = ort.InferenceSession(
                model_path,
                providers=["CPUExecutionProvider"],
            )
            cls._anti_spoof_input_name = (
                cls._anti_spoof_session.get_inputs()[0].name
            )
            cls._anti_spoof_output_name = (
                cls._anti_spoof_session.get_outputs()[0].name
            )

        return cls._anti_spoof_session

    @staticmethod
    def _get_face_crop_box(image_width, image_height, x1, y1, x2, y2, scale=2.7):
        box_w = max(1.0, x2 - x1)
        box_h = max(1.0, y2 - y1)

        max_scale_w = (image_width - 1) / box_w
        max_scale_h = (image_height - 1) / box_h
        scale = min(scale, max_scale_w, max_scale_h)

        new_w = box_w * scale
        new_h = box_h * scale

        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0

        left = center_x - new_w / 2.0
        top = center_y - new_h / 2.0
        right = center_x + new_w / 2.0
        bottom = center_y + new_h / 2.0

        if left < 0:
            right -= left
            left = 0
        if top < 0:
            bottom -= top
            top = 0
        if right > image_width - 1:
            left -= (right - (image_width - 1))
            right = image_width - 1
        if bottom > image_height - 1:
            top -= (bottom - (image_height - 1))
            bottom = image_height - 1

        return (
            int(max(0, left)),
            int(max(0, top)),
            int(min(image_width, right)),
            int(min(image_height, bottom)),
        )

    @classmethod
    def _check_face_liveness(cls, image_bytes):
        try:
            image_array = np.frombuffer(
                image_bytes,
                dtype=np.uint8,
            )
            image = cv2.imdecode(
                image_array,
                cv2.IMREAD_COLOR,
            )

            if image is None:
                return False, 0.0, "Invalid face image."

            face_app = cls._get_face_app()
            detector = getattr(face_app, "det_model", None)

            if detector is None:
                return False, 0.0, "Face detector is not available."

            bboxes, kpss = detector.detect(
                image,
                max_num=10,
            )

            if bboxes is None or len(bboxes) == 0:
                return False, 0.0, "No face detected."

            if len(bboxes) != 1:
                return (
                    False,
                    0.0,
                    "Please keep exactly one face in the camera.",
                )

            bbox = np.asarray(
                bboxes[0],
                dtype=np.float32,
            ).reshape(-1)

            if bbox.size < 4:
                return False, 0.0, "Invalid face detection."

            x1, y1, x2, y2 = bbox[:4]

            image_height, image_width = image.shape[:2]
            crop_x1, crop_y1, crop_x2, crop_y2 = cls._get_face_crop_box(
                image_width, image_height, x1, y1, x2, y2, scale=2.7,
            )

            if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
                return (
                    False,
                    0.0,
                    "Unable to prepare the face for liveness check.",
                )

            face_crop = image[crop_y1:crop_y2, crop_x1:crop_x2]

            if face_crop.size == 0:
                return (
                    False,
                    0.0,
                    "Unable to prepare the face for liveness check.",
                )

            debug_crop_path = "/tmp/locker_anti_spoof_face.jpg"
            try:
                cv2.imwrite(
                    debug_crop_path,
                    face_crop,
                )
            except Exception:
                pass

            session = cls._get_anti_spoof_session()
            if session is None:
                return (
                    False,
                    0.0,
                    "Face liveness model is not available.",
                )

            face_crop = cv2.resize(
                face_crop,
                (80, 80),
                interpolation=cv2.INTER_LINEAR,
            )

            input_tensor = face_crop.astype(np.float32)
            input_tensor = np.transpose(
                input_tensor,
                (2, 0, 1),
            )
            input_tensor = np.expand_dims(
                input_tensor,
                axis=0,
            )
            input_tensor = np.ascontiguousarray(input_tensor)

            output = session.run(
                [cls._anti_spoof_output_name],
                {
                    cls._anti_spoof_input_name: input_tensor,
                },
            )[0]

            scores = np.asarray(
                output,
                dtype=np.float32,
            ).reshape(-1)

            if scores.size != 3 or not np.all(np.isfinite(scores)):
                return False, 0.0, "Invalid liveness model output."

            if (
                np.any(scores < 0.0)
                or np.any(scores > 1.0)
                or not np.isclose(float(scores.sum()), 1.0, atol=1e-3)
            ):
                shifted = scores - np.max(scores)
                exp_scores = np.exp(shifted)
                scores = exp_scores / np.sum(exp_scores)

            print_score = float(scores[0])
            live_score = float(scores[1])
            replay_score = float(scores[2])

            is_live = live_score >= cls._ANTI_SPOOF_THRESHOLD

            if not is_live:
                return (
                    False,
                    live_score,
                    "Spoof detected. Please use your real face.",
                )

            return True, live_score, ""

        except Exception:
            return False, 0.0, "Face liveness check failed."

    def _is_locker_admin(self):
        return request.env.user.has_group("iPredict_locker_management.group_locker_admin")

    def _can_act_for(self, partner):
        """A locker user may only use the kiosk for himself, an administrator for everybody."""
        return self._is_locker_admin() or partner.id == request.env.user.partner_id.id

    def _get_allocation_payload(
        self,
        allocation,
        partner,
        access_method=None,
    ):
        Access = request.env["locker.access"].sudo()
        active_access = Access.search(
            [
                ("allocation_id", "=", allocation.id),
                ("authenticated_partner_id", "=", partner.id),
                ("state", "=", "checked_in"),
            ],
            limit=1,
            order="id desc",
        )
        if active_access:
            access_status = "Checked In"
            can_check_in = False
            can_check_out = True
        else:
            access_status = "Checked Out"
            can_check_in = True
            can_check_out = False
        return {
            "id": allocation.id,
            "partner_id": allocation.partner_id.id,
            "partner_name": allocation.partner_id.display_name,
            "authenticated_partner_id": partner.id,
            "authenticated_partner_name": partner.display_name,
            "locker_id": allocation.locker_id.id,
            "locker_name": allocation.locker_id.display_name,
            "profile_id": allocation.profile_id.id,
            "profile_name": allocation.profile_id.display_name,
            "access_method": access_method or allocation.access_method,
            "access_status": access_status,
            "can_check_in": can_check_in,
            "can_check_out": can_check_out,
        }

    def _get_credential(self, partner_id, allocation_id):
        Credential = request.env["locker.access.credential"].sudo()
        return Credential.search(
            [
                ("allocation_id", "=", int(allocation_id)),
                ("partner_id", "=", int(partner_id)),
                ("active", "=", True),
            ],
            limit=1,
        )

    def _clear_pending_authentication(self):
        request.session.pop("locker_pending_auth", None)

    def _set_pending_authentication(self, credential, partner, allocation):
        request.session["locker_pending_auth"] = {
            "credential_id": credential.id,
            "partner_id": partner.id,
            "allocation_id": allocation.id,
        }

    def _get_pending_authentication(self):
        data = request.session.get("locker_pending_auth")
        if not data:
            return None
        try:
            credential_id = int(data.get("credential_id"))
            partner_id = int(data.get("partner_id"))
            allocation_id = int(data.get("allocation_id"))
        except (TypeError, ValueError):
            self._clear_pending_authentication()
            return None
        return {
            "credential_id": credential_id,
            "partner_id": partner_id,
            "allocation_id": allocation_id,
        }

    def _get_pending_records(self):
        pending = self._get_pending_authentication()
        if not pending:
            return None
        Partner = request.env["res.partner"].sudo()
        Allocation = request.env["locker.allocation"].sudo()
        Credential = request.env["locker.access.credential"].sudo()
        partner = Partner.browse(pending["partner_id"]).exists()
        allocation = Allocation.browse(pending["allocation_id"]).exists()
        credential = Credential.browse(pending["credential_id"]).exists()
        if not partner or not allocation or not credential:
            self._clear_pending_authentication()
            return None
        if not credential.active:
            self._clear_pending_authentication()
            return None
        if allocation.state not in ACTIVE_ALLOCATION_STATES:
            self._clear_pending_authentication()
            return None
        if credential.allocation_id.id != allocation.id:
            self._clear_pending_authentication()
            return None
        if credential.partner_id.id != partner.id:
            self._clear_pending_authentication()
            return None
        allowed_partner_ids = allocation.authorized_partner_ids.ids + [allocation.partner_id.id]
        if partner.id not in allowed_partner_ids:
            self._clear_pending_authentication()
            return None
        return {
            "partner": partner,
            "allocation": allocation,
            "credential": credential,
        }

    def _mask_phone(self, phone):
        phone = str(phone or "").strip()
        if not phone:
            return ""
        if len(phone) <= 4:
            return "*" * len(phone)
        return "*" * (len(phone) - 4) + phone[-4:]

    def _hash_otp(self, otp):
        return hashlib.sha256(str(otp).encode("utf-8")).hexdigest()

    def _get_face_embedding(self, image_bytes, label="image"):
        try:
            image_array = np.frombuffer(image_bytes, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            if image is None:
                return None, "invalid_image"
            faces = self._get_face_app().get(image)
            if not faces:
                return None, "no_face"
            if len(faces) != 1:
                return None, "multiple_faces"
            face = faces[0]
            if face.kps is None:
                return None, "no_face"
            embedding = getattr(face, "embedding", None)
            if embedding is None:
                return None, "engine_error"
            norm = np.linalg.norm(embedding)
            if not np.isfinite(norm) or norm == 0:
                return None, "no_face"
            return embedding / norm, ""
        except Exception:
            return None, "engine_error"

    def _compare_faces(self, reference_bytes, live_bytes):
        reference_embedding, reference_error = self._get_face_embedding(reference_bytes, "profile photo")
        if reference_embedding is None:
            return False, 0.0, f"reference_{reference_error}"
        live_embedding, live_error = self._get_face_embedding(live_bytes, "camera image")
        if live_embedding is None:
            return False, 0.0, f"live_{live_error}"
        similarity = float(np.dot(reference_embedding, live_embedding))
        matched = similarity >= self._FACE_MATCH_THRESHOLD
        return matched, similarity, ""

    _FACE_ERROR_MESSAGES = {
        "reference_invalid_image": "The profile photo of this person is not a valid image. Please upload it again.",
        "reference_no_face": "No face could be found in the profile photo of this person. Please upload a clear front-facing photo.",
        "reference_multiple_faces": "The profile photo contains more than one face. Please upload a photo with only this person.",
        "reference_engine_error": "The face recognition engine is not working on the server. Please contact the administrator.",
        "live_invalid_image": "The camera image could not be read. Please try again.",
        "live_no_face": "No face detected in the camera. Look straight at the camera in good light.",
        "live_multiple_faces": "More than one face detected. Please keep exactly one face in the camera.",
        "live_engine_error": "The face recognition engine is not working on the server. Please contact the administrator.",
    }

    def _get_person_method_key(self, partner_id, access_method):
        return f"{str(access_method or 'unknown').strip().lower()}:{int(partner_id)}"

    def _get_person_method_auth_state(self, partner_id, access_method):
        key = self._get_person_method_key(partner_id, access_method)
        states = dict(request.session.get("locker_person_method_auth_states_v2") or {})
        state = dict(states.get(key) or {})
        attempts = min(3, max(0, int(state.get("attempts", 0) or 0)))
        locked_until = float(state.get("locked_until", 0) or 0)
        if locked_until and time.time() >= locked_until:
            states.pop(key, None)
            request.session["locker_person_method_auth_states_v2"] = dict(states)
            return {"attempts": 0, "remaining": 3, "locked": False, "locked_until": 0}
        locked = bool(locked_until and time.time() < locked_until)
        return {
            "attempts": attempts,
            "remaining": max(0, 3 - attempts),
            "locked": locked,
            "locked_until": locked_until if locked else 0,
        }

    def _record_person_method_failure(self, partner_id, access_method):
        key = self._get_person_method_key(partner_id, access_method)
        states = dict(request.session.get("locker_person_method_auth_states_v2") or {})
        state = dict(states.get(key) or {})
        current_attempts = max(0, int(state.get("attempts", 0) or 0))
        attempts = min(3, current_attempts + 1)
        locked_until = time.time() + self._get_lock_seconds() if attempts >= 3 else 0
        states[key] = {
            "attempts": attempts,
            "locked_until": locked_until,
        }
        request.session["locker_person_method_auth_states_v2"] = dict(states)
        return {
            "attempts": attempts,
            "remaining": max(0, 3 - attempts),
            "locked": attempts >= 3,
            "locked_until": locked_until,
        }

    def _reset_person_method_attempts(self, partner_id, access_method):
        key = self._get_person_method_key(partner_id, access_method)
        states = dict(request.session.get("locker_person_method_auth_states_v2") or {})
        states.pop(key, None)
        request.session["locker_person_method_auth_states_v2"] = dict(states)

    def _get_auth_lock_state(self, credential=None):
        if not credential:
            return False, 0
        state = self._get_person_method_auth_state(
            credential.partner_id.id,
            credential.access_method,
        )
        return state["locked"], state["locked_until"] if state["locked"] else 0

    def _get_lock_seconds(self):
        try:
            seconds = int(request.env.company.sudo().locker_auth_lock_seconds or 60)
        except Exception:
            seconds = 60
        return min(300, max(1, seconds))

    @staticmethod
    def _format_duration(seconds):
        seconds = max(1, int(seconds))
        minutes, secs = divmod(seconds, 60)
        parts = []
        if minutes:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if secs:
            parts.append(f"{secs} second{'s' if secs != 1 else ''}")
        return " ".join(parts)

    def _lock_wait_text(self, locked_until=None, now=None):
        """'45 seconds' - the time left of a running lock, or the full lock time of a new one."""
        if locked_until:
            now = now if now is not None else time.time()
            remaining = int(locked_until - now)
            if locked_until - now > remaining:
                remaining += 1
            return self._format_duration(max(1, remaining))
        return self._format_duration(self._get_lock_seconds())

    def _get_remaining_minutes(self, locked_until, now=None):
        now = now if now is not None else time.time()
        remaining_seconds = max(0, int(locked_until - now))
        return max(1, (remaining_seconds + 59) // 60)

    # FIND PERSON

    @http.route("/locker/access/find_person", type="jsonrpc", auth="user", methods=["POST"])
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
            "|",
            "|",
            ("name", "ilike", identity),
            ("email", "ilike", identity),
            ("phone", "ilike", identity),
        ])
        is_admin = self._is_locker_admin()
        if not is_admin:
            partners = partners & request.env.user.partner_id
        if not partners:
            return {"success": False, "message": "No person found."}
        allocations = Allocation.search([
            ("state", "in", ["allocated", "renewal_pending", "expired"]),
            "|",
            ("partner_id", "in", partners.ids),
            ("authorized_partner_ids", "in", partners.ids),
        ])
        if not allocations:
            return {"success": False, "message": "No active locker allocation found for this person."}
        persons = []
        for allocation in allocations:
            allowed_partners = allocation.partner_id | allocation.authorized_partner_ids
            if not is_admin:
                allowed_partners = allowed_partners & request.env.user.partner_id
            for partner in allowed_partners:
                credential = Credential.search(
                    [
                        ("allocation_id", "=", allocation.id),
                        ("partner_id", "=", partner.id),
                        ("active", "=", True),
                    ],
                    limit=1,
                )
                is_otp_locked, locked_until = self._get_auth_lock_state(credential)
                method = credential.access_method if credential else allocation.access_method
                auth_state = self._get_person_method_auth_state(partner.id, method)
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
                    "otp_locked": is_otp_locked,
                    "otp_locked_until": locked_until if is_otp_locked else 0,
                    "otp_locked_message": (
                        f"You have used all 3 authentication attempts. Please try again after {self._lock_wait_text(locked_until)}."
                        if is_otp_locked else ""
                    ),
                    "auth_attempts": auth_state["attempts"],
                    "auth_attempts_remaining": auth_state["remaining"],
                })
        if not persons:
            return {"success": False, "message": "No authorized person found."}
        return {"success": True, "persons": persons}

    # CURRENTLY CHECKED-IN PEOPLE

    @http.route(
        "/locker/access/current_checked_in",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
    )
    def current_checked_in(self):
        Access = request.env["locker.access"]

        active_accesses = Access.search(
            [
                ("state", "=", "checked_in"),
                ("allocation_id.company_id", "=", request.env.company.id),
            ],
            order="id desc",
        )

        people = []
        for access in active_accesses:
            partner = access.authenticated_partner_id
            allocation = access.allocation_id

            if not partner or not allocation:
                continue

            people.append({
                "access_id": access.id,
                "partner_id": partner.id,
                "partner_name": partner.display_name,
                "locker_name": allocation.locker_id.display_name,
                "allocation_id": allocation.id,
                "access_method": allocation.access_method,
                "check_in_time": access.create_date,
                "companion_count": access.companion_count,
                "total_people": access.total_people,
            })
        

        return {
            "success": True,
            "people": people,
            "count": len(people),
        }

    # VERIFY QR

    @http.route("/locker/access/verify_qr", type="jsonrpc", auth="user", methods=["POST"])
    def verify_qr(self, qr_token=None, partner_id=None, allocation_id=None):
        if not partner_id:
            return {"success": False, "message": "Person is required."}
        try:
            partner_id = int(partner_id)
        except (TypeError, ValueError):
            return {"success": False, "message": "Invalid person."}
        if not allocation_id:
            return {"success": False, "message": "Locker allocation is required."}
        try:
            allocation_id = int(allocation_id)
        except (TypeError, ValueError):
            return {"success": False, "message": "Invalid locker allocation."}
        Partner = request.env["res.partner"].sudo()
        Allocation = request.env["locker.allocation"].sudo()
        Credential = request.env["locker.access.credential"].sudo()
        partner = Partner.browse(partner_id).exists()
        allocation = Allocation.browse(allocation_id).exists()
        if not partner:
            return {"success": False, "message": "Person not found."}
        if not allocation:
            return {"success": False, "message": "Locker allocation not found."}

        auth_state = self._get_person_method_auth_state(partner.id, "qr")
        if auth_state["locked"]:
            return {
                "success": False,
                "locked": True,
                "locked_until": auth_state["locked_until"],
                "attempts_remaining": 0,
                "message": f"You have used all 3 QR attempts. Please try again after {self._lock_wait_text(auth_state['locked_until'])}.",
            }

        def qr_failure(message):
            result = self._record_person_method_failure(partner.id, "qr")
            if result["locked"]:
                return {
                    "success": False,
                    "locked": True,
                    "locked_until": result["locked_until"],
                    "attempts_remaining": 0,
                    "message": f"QR verification failed. You have used all 3 QR attempts. Please try again after {self._lock_wait_text()}.",
                }
            return {
                "success": False,
                "locked": False,
                "attempts_remaining": result["remaining"],
                "message": f"{message} {result['remaining']} attempts remaining.",
            }

        if not qr_token or not str(qr_token).strip():
            return qr_failure("QR token is required.")
        if allocation.state not in ACTIVE_ALLOCATION_STATES:
            return qr_failure("This locker is not currently allocated.")
        if not self._can_act_for(partner):
            return {"success": False, "message": "You can only access your own locker."}
        qr_token = str(qr_token).strip()
        credential = Credential.search(
            [
                ("qr_token", "=", qr_token),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not credential:
            return qr_failure("Invalid QR code.")
        if credential.allocation_id.id != allocation.id:
            return qr_failure("This QR code does not belong to this locker allocation.")
        if credential.partner_id.id != partner.id:
            return qr_failure("This QR code does not belong to the selected person.")
        allowed_partner_ids = allocation.authorized_partner_ids.ids + [allocation.partner_id.id]
        if partner.id not in allowed_partner_ids:
            return qr_failure("This person is not authorized for this locker.")
        if credential.access_method != "qr":
            return qr_failure("QR authentication is not configured for this credential.")

        self._reset_person_method_attempts(partner.id, "qr")
        self._set_pending_authentication(credential, partner, allocation)
        return {
            "success": True,
            "locked": False,
            "attempts_remaining": 3,
            "message": "QR code verified successfully. Please choose an authentication method.",
            "partner_name": partner.display_name,
            "has_otp": True,
        }

    # START FACE AUTHENTICATION

    @http.route("/locker/access/start_face", type="jsonrpc", auth="user", methods=["POST"])
    def start_face(self, partner_id=None, allocation_id=None):
        if not partner_id or not allocation_id:
            return {"success": False, "message": "Person and locker allocation are required."}
        Partner = request.env["res.partner"].sudo()
        Allocation = request.env["locker.allocation"].sudo()
        partner = Partner.browse(int(partner_id)).exists()
        allocation = Allocation.browse(int(allocation_id)).exists()
        if not partner:
            return {"success": False, "message": "Person not found."}
        if not allocation:
            return {"success": False, "message": "Locker allocation not found."}
        if allocation.state not in ACTIVE_ALLOCATION_STATES:
            return {"success": False, "message": "This locker is not currently allocated."}
        if not self._can_act_for(partner):
            return {"success": False, "message": "You can only access your own locker."}
        allowed_partner_ids = allocation.authorized_partner_ids.ids + [allocation.partner_id.id]
        if partner.id not in allowed_partner_ids:
            return {"success": False, "message": "This person is not authorized for this locker."}
        credential = self._get_credential(partner.id, allocation.id)
        if not credential:
            return {"success": False, "message": "No active access credential was found for this person."}
        face_auth_state = self._get_person_method_auth_state(
            partner.id,
            "face",
        )
        if face_auth_state["locked"]:
            locked_until = face_auth_state["locked_until"]
            return {
                "success": False,
                "locked": True,
                "locked_until": locked_until,
                "message": f"You have already used all 3 attempts. Please try again after {self._lock_wait_text(locked_until)}.",
            }
        self._set_pending_authentication(credential, partner, allocation)
        return {
            "success": True,
            "message": "Face authentication started.",
            "partner_name": partner.display_name,
        }

    # VERIFY FACE

    @http.route("/locker/access/verify_face", type="jsonrpc", auth="user", methods=["POST"])
    def verify_face(self, image=None):
        if not image:
            return {"success": False, "message": "Face image is required."}
        pending = self._get_pending_records()
        if not pending:
            return {"success": False, "message": "Face authentication session expired. Please select the person again."}
        partner = pending["partner"]
        allocation = pending["allocation"]
        credential = pending["credential"]
        face_auth_state = self._get_person_method_auth_state(
            partner.id,
            "face",
        )
        if face_auth_state["locked"]:
            locked_until = face_auth_state["locked_until"]
            return {
                "success": False,
                "locked": True,
                "locked_until": locked_until,
                "message": f"You have already used all 3 attempts. Please try again after {self._lock_wait_text(locked_until)}.",
            }
        if not partner.image_1920:
            return {"success": False, "message": "No profile photo is available for this person."}
        try:
            if "," in image:
                image = image.split(",", 1)[1]
            live_bytes = base64.b64decode(image, validate=True)
            reference_bytes = base64.b64decode(partner.image_1920)
        except Exception:
            return {"success": False, "message": "Invalid face image."}
        is_live, liveness_score, liveness_message = self._check_face_liveness(
            live_bytes
        )
        if not is_live:
            result = self._record_person_method_failure(
                partner.id,
                "face",
            )
            if result["locked"]:
                return {
                    "success": False,
                    "locked": True,
                    "locked_until": result["locked_until"],
                    "attempts_remaining": 0,
                    "liveness_score": liveness_score,
                    "message": (
                        "Face liveness verification failed. "
                        "You have used all 3 face attempts. "
                        f"Please try again after {self._lock_wait_text()}."
                    ),
                }
            return {
                "success": False,
                "locked": False,
                "attempts_remaining": result["remaining"],
                "liveness_score": liveness_score,
                "message": (
                    f"{liveness_message or 'Face liveness verification failed.'} "
                    f"{result['remaining']} attempts remaining."
                ),
            }

        matched, similarity, face_error = self._compare_faces(reference_bytes, live_bytes)
        if not matched:
            result = self._record_person_method_failure(partner.id, "face")
            if face_error:
                reason = self._FACE_ERROR_MESSAGES.get(face_error, "Face verification failed.")
                if result["locked"]:
                    return {
                        "success": False,
                        "locked": True,
                        "locked_until": result["locked_until"],
                        "message": f"{reason} You have used all 3 attempts. Please try again after {self._lock_wait_text()}.",
                    }
                return {
                    "success": False,
                    "locked": False,
                    "attempts_remaining": result["remaining"],
                    "message": f"{reason} {result['remaining']} attempts remaining.",
                }
            if result["locked"]:
                return {
                    "success": False,
                    "locked": True,
                    "locked_until": result["locked_until"],
                    "message": f"Face verification failed. You have used all 3 attempts. Please try again after {self._lock_wait_text()}.",
                }
            return {
                "success": False,
                "locked": False,
                "message": f"Face does not match. {result['remaining']} attempts remaining.",
                "attempts_remaining": result["remaining"],
            }
        self._reset_person_method_attempts(partner.id, "face")
        request.session.pop("locker_otp", None)
        self._clear_pending_authentication()
        return {
            "success": True,
            "locked": False,
            "message": "Face verified successfully.",
            "similarity": similarity,
            "liveness_score": liveness_score,
            "allocation": self._get_allocation_payload(
                allocation,
                partner,
                credential.access_method,
            ),
        }

    # SEND OTP

    @http.route("/locker/access/send_otp", type="jsonrpc", auth="user", methods=["POST"])
    def send_otp(self):
        pending = self._get_pending_records()
        if not pending:
            return {"success": False, "message": "QR authentication session expired. Please scan the QR code again."}
        partner = pending["partner"]
        credential = pending["credential"]
        auth_state = self._get_person_method_auth_state(partner.id, credential.access_method)
        if auth_state["locked"]:
            return {
                "success": False,
                "locked": True,
                "locked_until": auth_state["locked_until"],
                "message": f"You have already used all 3 attempts. Please try again after {self._lock_wait_text(auth_state["locked_until"])}.",
            }
        email = (partner.email or "").strip()
        if not email:
            return {"success": False, "message": "No email address is available for this person."}
        otp = str(secrets.randbelow(900000) + 100000)
        otp_hash = self._hash_otp(otp)
        request.session["locker_otp"] = {
            "credential_id": credential.id,
            "otp_hash": otp_hash,
            "expires_at": time.time() + 300,
        }
        try:
            mail_template = request.env.ref(
                "iPredict_locker_management.mail_template_locker_authentication_otp",
                raise_if_not_found=False,
            )
            if not mail_template:
                request.session.pop("locker_otp", None)
                return {"success": False, "message": "Locker OTP email template is not configured."}
            mail_template.sudo().with_context(otp=otp).send_mail(
                credential.id,
                email_values={
                    "email_to": email,
                    "email_from": request.env.company.email_formatted or request.env.user.email_formatted,
                },
                force_send=False,
            )
        except Exception:
            request.session.pop("locker_otp", None)
            return {"success": False, "message": "Unable to send OTP email. Please check the email configuration."}
        return {"success": True, "message": "OTP has been sent to your registered email address."}

    # VERIFY OTP

    @http.route("/locker/access/verify_otp", type="jsonrpc", auth="user", methods=["POST"])
    def verify_otp(self, otp=None):
        if not otp:
            return {"success": False, "message": "Please enter the OTP."}
        pending = self._get_pending_records()
        if not pending:
            return {"success": False, "message": "QR authentication session expired. Please scan the QR code again."}
        otp_data = request.session.get("locker_otp")
        if not otp_data:
            return {"success": False, "message": "No OTP request found. Please request a new OTP."}
        if int(otp_data.get("credential_id", 0)) != pending["credential"].id:
            request.session.pop("locker_otp", None)
            return {"success": False, "message": "Invalid OTP session."}
        current_time = time.time()
        partner = pending["partner"]
        credential = pending["credential"]
        auth_state = self._get_person_method_auth_state(partner.id, credential.access_method)
        if auth_state["locked"]:
            return {
                "success": False,
                "locked": True,
                "locked_until": auth_state["locked_until"],
                "message": f"You have already used all 3 attempts. Please try again after {self._lock_wait_text(auth_state["locked_until"])}.",
            }
        if current_time > float(otp_data.get("expires_at", 0)):
            request.session.pop("locker_otp", None)
            return {"success": False, "message": "OTP has expired. Please request a new OTP."}
        otp = str(otp).strip()
        if not otp.isdigit() or len(otp) != 6:
            result = self._record_person_method_failure(partner.id, credential.access_method)
            if result["locked"]:
                return {
                    "success": False,
                    "locked": True,
                    "locked_until": result["locked_until"],
                    "message": f"You have used all 3 attempts. Please try again after {self._lock_wait_text()}.",
                }
            return {
                "success": False,
                "locked": False,
                "message": f"OTP must contain exactly 6 digits. {result['remaining']} attempts remaining.",
            }
        entered_hash = self._hash_otp(otp)
        if not secrets.compare_digest(entered_hash, otp_data.get("otp_hash", "")):
            result = self._record_person_method_failure(partner.id, credential.access_method)
            if result["locked"]:
                return {
                    "success": False,
                    "locked": True,
                    "locked_until": result["locked_until"],
                    "message": f"You have used all 3 attempts. Please try again after {self._lock_wait_text()}.",
                }
            return {
                "success": False,
                "locked": False,
                "message": f"Invalid OTP. {result['remaining']} attempts remaining.",
            }
        self._reset_person_method_attempts(partner.id, credential.access_method)
        request.session.pop("locker_otp", None)
        allocation = pending["allocation"]
        partner = pending["partner"]
        credential = pending["credential"]
        self._clear_pending_authentication()
        return {
            "success": True,
            "locked": False,
            "message": "OTP verified successfully.",
            "allocation": self._get_allocation_payload(
                allocation,
                partner,
                credential.access_method,
            ),
        }

    # VERIFY PIN / RFID / BIOMETRIC / PHYSICAL KEY

    @http.route("/locker/access/authenticate", type="jsonrpc", auth="user", methods=["POST"])
    def authenticate(
        self,
        identity=None,
        partner_id=None,
        allocation_id=None,
    ):

        if not partner_id:
            return {
                "success": False,
                "message": "Please select a person first.",
            }

        if not allocation_id:
            return {
                "success": False,
                "message": "Locker allocation is required.",
            }

        try:
            partner_id = int(partner_id)
            allocation_id = int(allocation_id)
        except (TypeError, ValueError):
            return {
                "success": False,
                "message": "Invalid person or locker allocation.",
            }

        Partner = request.env["res.partner"].sudo()
        Allocation = request.env["locker.allocation"].sudo()
        Credential = request.env["locker.access.credential"].sudo()

        partner = Partner.browse(partner_id).exists()
        allocation = Allocation.browse(allocation_id).exists()

        if not partner:
            return {
                "success": False,
                "message": "Person not found.",
            }

        if not allocation:
            return {
                "success": False,
                "message": "Locker allocation not found.",
            }

        if allocation.state not in ACTIVE_ALLOCATION_STATES:
            return {
                "success": False,
                "message": "This locker is not currently allocated.",
            }

        if not self._can_act_for(partner):
            return {
                "success": False,
                "message": "You can only access your own locker.",
            }

        allowed_partner_ids = (
            allocation.authorized_partner_ids.ids
            + [allocation.partner_id.id]
        )

        if partner.id not in allowed_partner_ids:
            return {
                "success": False,
                "message": "This person is not authorized for this locker.",
            }

        access_method = str(allocation.access_method or "").strip().lower()

        if not access_method:
            return {
                "success": False,
                "message": "Access Method is not configured for this locker.",
            }

        credential = Credential.search(
            [
                ("allocation_id", "=", allocation.id),
                ("partner_id", "=", partner.id),
                ("active", "=", True),
            ],
            limit=1,
        )

        if not credential:
            return {
                "success": False,
                "message": "No active authentication credential found for this person.",
            }

        # PHYSICAL KEY
        if access_method == "physical_key":
            self._clear_pending_authentication()

            return {
                "success": True,
                "locked": False,
                "attempts_remaining": 3,
                "message": "Physical key authentication successful.",
                "allocation": self._get_allocation_payload(
                    allocation,
                    partner,
                    access_method,
                ),
            }

        # DIGITAL AUTHENTICATION LOCK
        auth_state = self._get_person_method_auth_state(
            partner.id,
            access_method,
        )

        if auth_state["locked"]:
            return {
                "success": False,
                "locked": True,
                "locked_until": auth_state["locked_until"],
                "attempts_remaining": 0,
                "message": (
                    "You have used all 3 attempts. "
                    f"Please try again after {self._lock_wait_text(auth_state['locked_until'])}."
                ),
            }

        # QR IS HANDLED BY verify_qr
        if access_method == "qr":
            return {
                "success": False,
                "message": (
                    "QR authentication must be performed by scanning "
                    "the QR code."
                ),
            }

        # BIOMETRIC
        if access_method == "biometric":
            entered_identity = str(identity or "").strip()
            credential_valid = bool(
                entered_identity
                and credential.biometric_id
                and secrets.compare_digest(
                    entered_identity,
                    str(credential.biometric_id).strip(),
                )
            )

        # PIN
        elif access_method == "pin":
            entered_identity = str(identity or "").strip()

            credential_valid = bool(
                entered_identity
                and credential.pin_code
                and secrets.compare_digest(
                    entered_identity,
                    str(credential.pin_code).strip(),
                )
            )

        # RFID
        elif access_method == "rfid":
            entered_identity = str(identity or "").strip()

            credential_valid = bool(
                entered_identity
                and credential.rfid_uid
                and secrets.compare_digest(
                    entered_identity,
                    str(credential.rfid_uid).strip(),
                )
            )

        else:
            return {
                "success": False,
                "message": (
                    f"Unsupported access method: {access_method}"
                ),
            }

        if not credential_valid:
            result = self._record_person_method_failure(
                partner.id,
                access_method,
            )

            if result["locked"]:
                return {
                    "success": False,
                    "locked": True,
                    "locked_until": result["locked_until"],
                    "attempts_remaining": 0,
                    "message": (
                        f"Invalid {access_method.upper()} credential. "
                        "You have used all 3 attempts. "
                        f"Please try again after {self._lock_wait_text()}."
                    ),
                }

            return {
                "success": False,
                "locked": False,
                "attempts": result["attempts"],
                "attempts_remaining": result["remaining"],
                "message": (
                    f"Invalid {access_method.upper()} credential. "
                    f"{result['remaining']} attempts remaining."
                ),
            }

        # SUCCESS
        self._reset_person_method_attempts(
            partner.id,
            access_method,
        )
        self._clear_pending_authentication()
        request.session.pop("locker_otp", None)

        return {
            "success": True,
            "locked": False,
            "attempts_remaining": 3,
            "message": "Identity verified successfully.",
            "allocation": self._get_allocation_payload(
                allocation,
                partner,
                access_method,
            ),
        }

    # CHECK IN / CHECK OUT

    @http.route("/locker/access/action", type="jsonrpc", auth="user", methods=["POST"])
    def access_action(self, allocation_id=None, action=None, authenticated_partner_id=None,companion_count=0):
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
        if allocation.state not in ACTIVE_ALLOCATION_STATES:
            return {"success": False, "message": "This locker is not currently allocated."}
        partner = request.env["res.partner"].browse(int(authenticated_partner_id)).exists()
        if not partner:
            return {"success": False, "message": "Authenticated person not found."}
        if not self._can_act_for(partner):
            return {"success": False, "message": "You can only access your own locker."}
        allowed_partner_ids = allocation.authorized_partner_ids.ids + [allocation.partner_id.id]
        if partner.id not in allowed_partner_ids:
            return {"success": False, "message": "This person is not authorized for this locker."}
        active_access = Access.search(
            [
                ("allocation_id", "=", allocation.id),
                ("authenticated_partner_id", "=", partner.id),
                ("state", "=", "checked_in"),
            ],
            limit=1,
            order="id desc",
        )
        if action == "check_in":
            if active_access:
                return {"success": False, "message": "This person is already checked in."}
            access = Access.create({
                "partner_id": allocation.partner_id.id,
                "authenticated_partner_id": partner.id,
                "allocation_id": allocation.id,
                "state": "checked_out",
                "companion_count": int(companion_count or 0),

            })
            access.action_check_in()           
            return {
                "success": True,
                "message": "Check In successful.",
                "allocation": self._get_allocation_payload(
                    allocation,
                    partner,
                    allocation.access_method,
                ),
            }
        if not active_access:
            return {"success": False, "message": "This person is not currently checked in."}
        active_access.action_check_out()
        return {
            "success": True,
            "message": "Check Out successful.",
            "allocation": self._get_allocation_payload(
                allocation,
                partner,
                allocation.access_method,
            ),
        }