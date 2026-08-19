/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { useRef,useState,useExternalListener} from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { isIosApp } from "@web/core/browser/feature_detection";
patch(ActivityMenu.prototype, {
    setup() {
        super.setup();
        useExternalListener(window, "click", (ev) => {
            const attendanceMenu = ev.target.closest(".o-dropdown--menu");
            if (attendanceMenu) {
                return;
            }
            if (!this.isSigningAction) {
                this.closeCamera();
            }
        });
        this.videoPreviewRef = useRef("videoPreview");  
        this.stream = null;
        this.orm = useService("orm");
        this.state = useState({
            isImageCaptureEnabled: false,
            permissionStatus: null,
            isFaceRecognitionEnabled: false,
            isCameraRequired: false,
            isFaceMatched: false,
        });
    },
    async openCamera() {
        try {
            const employeeConfig = await this.orm.searchRead("hr.employee", [["id", "=", this.employee.id]], ["allow_without_image_capture"]);
            this.state.allowWithoutImage = employeeConfig[0].allow_without_image_capture;
            const records = await this.orm.searchRead("res.company", [], ["attendance_image_capture","face_recognition","face_recognition_backend"]);
            this.state.isImageCaptureEnabled = records[0].attendance_image_capture;
            this.state.isFaceRecognitionEnabled = records[0].face_recognition && records[0].face_recognition_backend;
            const Status = await navigator.permissions.query({ name: 'camera' });
            this.state.permissionStatus = Status.state;
            if ((this.state.isImageCaptureEnabled || this.state.isFaceRecognitionEnabled) && !this.state.allowWithoutImage) {
                if (this.state.permissionStatus == 'granted') {
                    this.stream = await navigator.mediaDevices.getUserMedia({ video: true });
                    this.videoPreviewRef.el.srcObject = this.stream;
                }
            }
        } catch (err) {
            console.error("Camera access denied:", err);
        }
    },
    async addImage(photo) {
        if (this.state.isImageCaptureEnabled) {   
            if (this.state.permissionStatus == 'granted') {
                let imgBase64 = null;
                imgBase64 = await this.blobToBase64(photo);
                await rpc("/hr_attendance/store_captured_photo", {
                    photo: imgBase64,
                    action_type: this.state.checkedIn ? 'check_in' : 'check_out',
                });
            }
        }
    },
    async signInOut() {
        this.isSigningAction = true
        this.dropdown.close();
        let latitude = null;
        let longitude = null;

        if (navigator.geolocation && !isIosApp()) {
            try {
                const pos = await new Promise((resolve, reject) => {
                    navigator.geolocation.getCurrentPosition(resolve, reject);
                });
                latitude = pos.coords.latitude;
                longitude = pos.coords.longitude;
                const result = await rpc('/face_attendance/check_location', {
                    latitude: latitude,
                    longitude: longitude,
                });
                if (!result.success) {
                    this.notification.add(result.msg, {
                        title: _t("Location Validation"),
                        type: "danger",
                        sticky: true,
                    });
                return;
                    return;
                }
            } catch (err) {
                this.notification.add(_t("Location access denied"), {
                    type: "warning",
                });
            }
        }
        const isImageEnabled = this.state.isImageCaptureEnabled;
        const isFaceRecognitionEnabled = this.state.isFaceRecognitionEnabled;
        const isPermissionGranted = this.state.permissionStatus === 'granted';
        const employeeConfig = await this.orm.searchRead("hr.employee", [["id", "=", this.employee.id]], ["allow_without_image_capture"]);
        const allowWithoutImage = employeeConfig[0].allow_without_image_capture;

        if ((isImageEnabled || isFaceRecognitionEnabled) && !allowWithoutImage && !isPermissionGranted) {
            this.notification.add(_t("Camera permission is required"), {
                type: "danger",
            });
            return;
        }

        let photo = null;
        if ((isImageEnabled || isFaceRecognitionEnabled) && isPermissionGranted && !allowWithoutImage) {
            try {
                const track = this.stream.getVideoTracks()[0];
                const imageCapture = new ImageCapture(track);
                photo = await imageCapture.takePhoto();
            } catch (err) {
                console.error("Image capture failed:", err);
            }
        }

        try {
            if (photo && !allowWithoutImage) {
                await this.uploadImageToSession(photo);
            }
            if (isFaceRecognitionEnabled && !allowWithoutImage) {
                const faceResponse = await rpc("/hr_attendance/face_recognition_check", {});
                this.state.isFaceMatched = faceResponse.success;
                if (!faceResponse.success) {
                    this.notification.add(faceResponse.msg || "Face not recognized", {
                        title: "❌ Face Recognition Failed",
                        type: "danger",
                    });
                    this.closeCamera();
                    return;
                }
            }

            const response = await rpc("/hr_attendance/systray_check_in_out", {
                latitude: latitude,
                longitude: longitude,
            });

            if (response.attendance_state) {
                if (this.employee) {
                    this.employee.attendance_state = response.attendance_state;
                }

               const details = [
                    response.employee_name || '',
                    `📍 ${response.geo_ip.location || 'Location not available'}`,
                    `⏰ ${response.attendance_state || 'attendance'} completed`
                ].join('\n');

                const fullMessage = `${response.msg || "Attendance updated"}\n\n${details}`;

                this.notification.add(fullMessage, {
                    title: "✅ Success",
                    type: "success",
                    sticky: false,
                    className: 'my-preline',
                });
                this._searchReadEmployeeFill();
                if (!document.getElementById('my-preline-style')) {
                    const style = document.createElement('style');
                    style.id = 'my-preline-style';
                    style.innerHTML = `
                        .my-preline {
                            white-space: pre-line !important;
                        }
                    `;
                    document.head.appendChild(style);
                }
                if (this.state.isFaceMatched && !allowWithoutImage){
                    if (photo) {
                        await this.addImage(photo);
                    }
                }
                else if (!isFaceRecognitionEnabled && !allowWithoutImage) {
                    if (photo) {
                        await this.addImage(photo);
                    }
                }

            } else {
                this.notification.add(response.msg || "Attendance failed", {
                    title: "❌ Failed",
                    type: "danger",
                });
            }

        } catch (error) {
            console.error(error);
            this.notification.add(_t("Something went wrong"), {
                type: "danger",
            });
        }

        this.closeCamera();
    },
    blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    },
    async uploadImageToSession(photo) {
        const formData = new FormData();
        formData.append("image", photo);

        await fetch("/hr_attendance/store_image_session", {
            method: "POST",
            body: formData,
        });
    },
    async closeCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach((track) => track.stop());
            this.stream = null;
        }
    },
  
});