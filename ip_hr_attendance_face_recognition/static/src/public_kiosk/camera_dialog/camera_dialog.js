/** @odoo-module **/

import { Component, useRef, onMounted, onWillUnmount,useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { rpc } from "@web/core/network/rpc";
import { _t, appTranslateFn } from "@web/core/l10n/translation";
import { isIosApp } from "@web/core/browser/feature_detection";

export class CameraDialog extends Component {
    static template = "ip_hr_attendance_face_recognition.CameraDialog";
    static components = { Dialog };

    setup() {
        this.videoRef = useRef("videoPreview");
        this.stream = null;
        this.interval = null;

        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.state = useState({
            processing: false,
        });

        onMounted(async () => {
            await this.startCamera();
            this.startAutoRecognition();
        });

        onWillUnmount(() => {
            this.stopAll();
        });
    }

    async startCamera() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ video: true });
            this.videoRef.el.srcObject = this.stream;
        } catch (err) {
            console.error(err);
            this.notification.add("Camera access denied", { type: "danger" });
        }
    }

    startAutoRecognition() {
        this.interval = setInterval(() => {
            this.processFrame();
        }, 2000);
    }

    async processFrame() {
        if (this.state.processing) return;
        this.state.processing = true;
        let latitude = null;
        let longitude = null;
        try {
            if (navigator.geolocation) {
                try {
                    if (isIosApp()) {
                        const loc = await this.getLocationFromIP();
                        latitude = loc.latitude;
                        longitude = loc.longitude;
                    } else {
                        const pos = await new Promise((resolve, reject) => {
                            navigator.geolocation.getCurrentPosition(resolve, reject, {
                                enableHighAccuracy: true,
                                timeout: 10000,
                            });
                        });

                        latitude = pos.coords.latitude;
                        longitude = pos.coords.longitude;
                    }
                } catch (err) {
                    this.notification.add(_t("Location access denied"), {
                        type: "warning",
                    });
                }
            }

            const photo = await this.captureFrame();
            const base64 = await this.blobToBase64(photo);
            const result = await rpc("/hr_attendance/face_recognition_check/kiosk", {
                image: base64,
                token:this.props.token,
                latitude:latitude,
                longitude:longitude,
            }); 
            if (result.data && result.data.employee_name) {
                this.props.onSuccess?.(result.data);
                if (this.props.attendance_image_capture) {
                    await rpc("/hr_attendance/store_captured_photo_kiosk", {
                        photo: base64,
                        action_type: result.data.attendance_state,
                        employee_id: result.data.id,
                    });
                }
            } else {
                this.props.onFailure(result.msg)
            }
            this.stopAll();
            this.dialog.closeAll();
            return;

        } catch (err) {
            console.error(err);
        }

        this.state.processing = false;
    }

    async captureFrame() {
        const track = this.stream.getVideoTracks()[0];
        const imageCapture = new ImageCapture(track);
        return await imageCapture.takePhoto();
    }

    blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }

    stopAll() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }

        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
    }
}