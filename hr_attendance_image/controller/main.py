# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import base64
import re
import logging
from odoo.addons.hr_attendance.controllers.main import HrAttendance
import numpy as np
import face_recognition
from io import BytesIO
from PIL import Image
import math
import os
import cv2
import onnxruntime as ort

_logger = logging.getLogger(__name__)

class HrAttendanceController(HrAttendance):

    def _crop_face_with_scale(self, image_bgr, bbox, scale=2.7, out_size=80):
        """Crop the face region with extra context/padding around it (scaled
        by `scale`) before resizing to out_size x out_size. Matches the
        official Silent-Face-Anti-Spoofing preprocessing.
        """
        h, w = image_bgr.shape[:2]
        top, right, bottom, left = bbox
        box_w, box_h = right - left, bottom - top
        cx, cy = left + box_w / 2.0, top + box_h / 2.0

        # clamp scale to image boundaries (matches official _get_new_box)
        scale = min((h - 1) / box_h, min((w - 1) / box_w, scale))

        side_w = box_w * scale
        side_h = box_h * scale
        x1, y1 = cx - side_w / 2, cy - side_h / 2
        x2, y2 = cx + side_w / 2, cy + side_h / 2

        if x1 < 0:
            x2 -= x1
            x1 = 0
        if y1 < 0:
            y2 -= y1
            y1 = 0
        if x2 > w - 1:
            x1 -= (x2 - w + 1)
            x2 = w - 1
        if y2 > h - 1:
            y1 -= (y2 - h + 1)
            y2 = h - 1

        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        crop = image_bgr[y1:y2 + 1, x1:x2 + 1]

        if crop is None or crop.size == 0:
            return None

        return cv2.resize(crop, (out_size, out_size), interpolation=cv2.INTER_LINEAR)

    def _check_anti_spoof(self, image):
        """Check the captured image for a live face before normal face recognition.
        Model: MiniFASNetV2 (2.7_80x80) from Silent-Face-Anti-Spoofing."""
      
        try:
            model_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "lib",
                "MiniFASNetV2.onnx",
            )

            if not os.path.exists(model_path):
                _logger.warning("Anti-spoof model not found: %s", model_path)
                return True, ""

            image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            locations = face_recognition.face_locations(image)

            if not locations:
                return True, ""

            face_crop = self._crop_face_with_scale(
                image_bgr, locations[0], scale=2.7, out_size=80
            )

            if face_crop is None or face_crop.size == 0:
                return True, ""

            session = ort.InferenceSession(
                model_path,
                providers=["CPUExecutionProvider"],
            )
            input_name = session.get_inputs()[0].name
            output_name = session.get_outputs()[0].name

            face = face_crop.astype(np.float32)
            tensor = np.transpose(face, (2, 0, 1))
            tensor = np.expand_dims(tensor, axis=0)
            tensor = np.ascontiguousarray(tensor)

            output = session.run([output_name], {input_name: tensor})[0]
            scores = np.asarray(output, dtype=np.float32).reshape(-1)

            if scores.size != 3 or not np.all(np.isfinite(scores)):
                _logger.warning("Anti-spoof model returned unexpected output shape/values")
                return True, ""

            s = scores - np.max(scores)
            exp_s = np.exp(s)
            scores = exp_s / np.sum(exp_s)

            # index 1 = real face
            live_score = float(scores[1])

            _logger.info(
                "ANTI-SPOOF: live=%.4f (scores=[paper=%.4f, real=%.4f, screen=%.4f])",
                live_score, scores[0], scores[1], scores[2],
            )

            if live_score < 0.50:
                return False, "Spoof detected. Please use your real face."

            return True, ""

        except Exception:
            _logger.exception("Anti-spoof check failed")
            return True, ""

    @http.route('/hr_attendance/store_image_session', type='http', auth='user', methods=['POST'], csrf=False)
    def store_image_session(self, **post):
        file = request.httprequest.files.get('image')

        if not file:
            return "No file"

        image_data = base64.b64encode(file.read()).decode('utf-8')
        request.session['attendance_image'] = image_data

        return "ok"

    @http.route('/hr_attendance/systray_check_in_out', type="jsonrpc", auth="user")
    def systray_attendance(self, latitude=False, longitude=False):
        response = super().systray_attendance(latitude=latitude, longitude=longitude)

        employee = request.env.user.employee_id

        geo_ip_response = self._get_geoip_response(
            mode='systray',
            latitude=latitude,
            longitude=longitude,
            device_tracking_enabled=employee.company_id.attendance_device_tracking
        )

        response.update({
            "geo_ip": geo_ip_response
        })

        return response

    def _process_face_recognition(self, image_data):
        try:
            user = request.env.user
            emp = user.employee_id

            if not emp or not emp.face_encoding:
                return {"success": False, "msg": "No face data found for user"}

            try:
                if isinstance(image_data, bytes):
                    image_data = image_data.decode('utf-8')

                img_bytes = base64.b64decode(image_data)
                img = np.array(Image.open(BytesIO(img_bytes)))

            except Exception:
                return {"success": False, "msg": "Image decode failed"}

            anti_spoof_ok, anti_spoof_msg = self._check_anti_spoof(img)
            if not anti_spoof_ok:
                return {"success": False, "msg": anti_spoof_msg}

            encodings = face_recognition.face_encodings(img)
            if not encodings:
                return {"success": False, "msg": "No face detected"}

            captured_encoding = encodings[0]

            try:
                emp_encoding = np.frombuffer(
                    base64.b64decode(emp.face_encoding),
                    dtype=np.float64
                )
            except Exception:
                return {"success": False, "msg": "Stored face encoding invalid"}

            distance = face_recognition.face_distance(
                [emp_encoding], captured_encoding
            )[0]

            _logger.info(f"Face distance: {distance}")

            if distance > 0.5:
                return {"success": False, "msg": "Face not recognized"}

            return {
                "success": True,
                "employee_name": emp.name,
            }

        except Exception:
            _logger.exception("Face recognition error")
            return {"success": False, "msg": "Face recognition failed"}

    @http.route('/hr_attendance/face_recognition_check', type='jsonrpc', auth='user')
    def face_recognition_check(self):
        employee = request.env.user.employee_id
        company = employee.company_id

        if not company.face_recognition:
            return {"success": True, "msg": "Face recognition not enabled"}

        image_data = request.session.get('attendance_image')

        if not image_data:
            return {"success": False, "msg": "Image required"}

        result = self._process_face_recognition(image_data)

        return result

    @http.route('/hr_attendance/store_captured_photo', type='jsonrpc', auth='user')
    def store_captured_photo(self, photo=None,action_type=None):
        if photo:
            img_data = re.sub('^data:image/.+;base64,', '', photo)
            binary_data = base64.b64decode(img_data)

        attendance = request.env['hr.attendance'].sudo().search(
            [('employee_id', '=', request.env.user.employee_id.id)],
            order="id desc", limit=1)
        if action_type == 'check_in':
            attach_type = 'check_in_image'
        elif action_type == 'check_out':
            attach_type = 'check_out_image'
        request.env['ir.attachment'].sudo().create({
            'name': f'{attach_type}_{attendance.id}.png',
            'type': 'binary',
            'res_model': 'hr.attendance',
            'res_id': attendance.id,
            'mimetype': 'image/png',
            'datas': base64.b64encode(binary_data),
        })

        return {'status': 'photo_saved'}

    @http.route('/hr_attendance/face_recognition_check/kiosk', type='jsonrpc',  auth="public")
    def face_recognition_check_kiosk(self,image,token,latitude=None, longitude=None):
        employee = request.env.user.employee_id
        company = employee.company_id
    

        if not image:
            return {"success": False, "msg": "Image required"}

        result = self._process_face_recognition_kiosk(image,token,latitude,longitude)
        return result

    #  @http.route('/hr_attendance/face_recognition_check/kiosk', type='json', auth='public', csrf=False)
    def _process_face_recognition_kiosk(self, image=None,token=None,latitude=None, longitude=None):
        try:
            company = self._get_company(token)
            allowed_locations = company.multi_location_ids

            if allowed_locations:
                if not latitude or not longitude:
                    return {
                        "success": False,
                        "msg": "❌ Location (latitude & longitude) is required"
                    }

                location_valid = False
                closest_distance = float('inf')
                closest_name = ""

                for loc in allowed_locations:
                    dist = self.calculate_distance_meters(
                        loc.face_attendance_latitude,
                        loc.face_attendance_longitude,
                        latitude,
                        longitude
                    )

                    if dist is not None and dist <= loc.face_attendance_radius:
                        location_valid = True
                        break

                    # Keep track of closest for better error message
                    if dist is not None and dist < closest_distance:
                        closest_distance = dist
                        closest_name = loc.name

                if not location_valid:
                    msg = "❌ You are not within any allowed attendance area."
                    if closest_distance != float('inf'):
                        msg += f"\nClosest location: {closest_name} ({closest_distance:.0f}m away)"
                    print("MESSAGE+++++++++++++",msg)
                    return {"success": False, "msg": msg}

            if not image:
                return {"success": False, "msg": "No image provided"}

            try:
                if isinstance(image, bytes):
                    image = image.decode('utf-8')

                img_bytes = base64.b64decode(image.split(",")[1] if "," in image else image)
                img = np.array(Image.open(BytesIO(img_bytes)))

            except Exception:
                return {"success": False, "msg": "Image decode failed"}

            anti_spoof_ok, anti_spoof_msg = self._check_anti_spoof(img)
            if not anti_spoof_ok:
                return {"success": False, "msg": anti_spoof_msg}

            encodings = face_recognition.face_encodings(img)
            if not encodings:
                return {"success": False, "msg": "No face detected"}

            captured_encoding = encodings[0]

            employees = request.env['hr.employee'].sudo().search([
                ('face_encoding', '!=', False),
                ('company_id', '=', company.id)
            ])

            print("employees",employees)
            if not employees:
                return {"success": False, "msg": "No registered faces"}

            best_match = None
            best_distance = 1.0

            for emp in employees:
                try:
                    emp_encoding = np.frombuffer(
                        base64.b64decode(emp.face_encoding),
                        dtype=np.float64
                    )

                    distance = face_recognition.face_distance(
                        [emp_encoding], captured_encoding
                    )[0]

                    _logger.info(f"{emp.name} distance: {distance}")

                    if distance < best_distance:
                        best_distance = distance
                        best_match = emp

                except Exception:
                    continue

            print("best_match",best_match.name)
            if best_match and best_distance < 0.5:
                if best_match:
                    best_match._attendance_action_change(self._get_geoip_response('kiosk',latitude=latitude,longitude=longitude,device_tracking_enabled=company.attendance_device_tracking))
                    data =  self._get_employee_info_response(best_match)
                    return {"success": True, "msg": "Face recognition failed","data":data}
                return {}
            return {"success": False, "msg": "Face not recognized"}

        except Exception:
            _logger.exception("Kiosk face recognition error")
            return {"success": False, "msg": "Face recognition failed"}

    def calculate_distance_meters(self, lat1, lon1, lat2, lon2):
        """Calculate the Haversine distance between two points in meters.

        :param lat1: Latitude of first point
        :param lon1: Longitude of first point
        :param lat2: Latitude of second point
        :param lon2: Longitude of second point
        :return: Distance in meters
        """
        if not all([lat1, lon1, lat2, lon2]):
            return None

        R = 6371000  # Radius of Earth in meters
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) * math.sin(dlat / 2) +
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
            math.sin(dlon / 2) * math.sin(dlon / 2)
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        return distance

    def _validate_location(self, latitude, longitude):
        company = request.env.user.company_id.sudo()
        allowed_locations = company.multi_location_ids

        if not allowed_locations:
            return {"valid": True}

        if not latitude or not longitude:
            return {
                "valid": False,
                "msg": "❌ Location (latitude & longitude) is required when geofencing is enabled"
            }

        location_valid = False
        closest_distance = float('inf')
        closest_name = ""

        for loc in allowed_locations:
            dist = self.calculate_distance_meters(
                loc.face_attendance_latitude,
                loc.face_attendance_longitude,
                latitude,
                longitude
            )

            if dist is not None and dist <= loc.face_attendance_radius:
                location_valid = True
                break

            if dist is not None and dist < closest_distance:
                closest_distance = dist
                closest_name = loc.name

        if not location_valid:
            msg = "❌ You are not within any allowed attendance area."
            if closest_distance != float('inf'):
                msg += f"\nClosest location: {closest_name} ({closest_distance:.0f}m away)"

            return {"valid": False, "msg": msg}

        return {"valid": True}

    @http.route('/hr_attendance/get_company_by_token', type='jsonrpc', auth='public')
    def get_company_by_token(self, token):
        company = self._get_company(token)

        if not company:
            return {}

        return {
            "id": company.id,
            "name": company.name,
            "face_recognition": company.face_recognition,
            "face_recognition_kiosk": company.face_recognition_kiosk,
            "attendance_image_capture":company.attendance_image_capture,
        }

    @http.route('/hr_attendance/store_captured_photo_kiosk', type='jsonrpc', auth='public')
    def store_captured_photo_kiosk(self, photo=None, action_type=None, employee_id=None):
        if not photo or not employee_id:
            return {'status': 'error', 'message': 'Missing data'}

        img_data = re.sub('^data:image/.+;base64,', '', photo)
        binary_data = base64.b64decode(img_data)

        attendance = request.env['hr.attendance'].sudo().search(
            [('employee_id', '=', employee_id)],
            order="id desc", limit=1
        )

        if not attendance:
            return {'status': 'error', 'message': 'No attendance found'}

        if action_type == 'checked_in':
            attach_type = 'check_in_image'
        elif action_type == 'checked_out':
            attach_type = 'check_out_image'
        else:
            attach_type = 'kiosk_image'

        request.env['ir.attachment'].sudo().create({
            'name': f'{attach_type}_{attendance.id}.png',
            'type': 'binary',
            'res_model': 'hr.attendance',
            'res_id': attendance.id,
            'mimetype': 'image/png',
            'datas': base64.b64encode(binary_data),
        })

        return {'status': 'photo_saved'}

    @http.route('/face_attendance/check_location', type='jsonrpc', auth='public')
    def check_location(self, latitude=None, longitude=None):

        # attendance_obj = request.env['hr.attendance'].sudo()

        try:
            # company = attendance_obj._get_company(token)
            company = self.env.company
            allowed_locations = company.multi_location_ids

            if not allowed_locations:
                return {
                    "success": True,
                    "msg": "No location restriction configured."
                }

            if not latitude or not longitude:
                return {
                    "success": False,
                    "msg": "❌ Location (latitude & longitude) is required"
                }

            location_valid = False
            closest_distance = float('inf')
            closest_name = ""

            latitude = float(latitude)
            longitude = float(longitude)

            for loc in allowed_locations:
                dist = self.calculate_distance_meters(
                    loc.face_attendance_latitude,
                    loc.face_attendance_longitude,
                    latitude,
                    longitude
                )

                if dist is not None and dist <= loc.face_attendance_radius:
                    location_valid = True
                    return {
                        "success": True,
                        "msg": f"✅ Location verified ({loc.name})",
                        "location": loc.name,
                    }

                if dist is not None and dist < closest_distance:
                    closest_distance = dist
                    closest_name = loc.name

            msg = "❌ You are not within any allowed attendance area."
            if closest_distance != float('inf'):
                msg += f"\nClosest location: {closest_name} ({closest_distance:.0f}m away)"

            return {
                "success": False,
                "msg": msg,
            }

        except Exception as e:
            return {
                "success": False,
                "msg": str(e),
            }