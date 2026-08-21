/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import {
    markup,
    useRef,
    useState,
    useExternalListener,
} from "@odoo/owl";
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
            locationPermissionStatus: null,
            isFaceRecognitionEnabled: false,
            isCameraRequired: false,
            isFaceMatched: false,
            attendanceDeviceTracking: false,
        });
    },


    async _fetchAllowWithoutImage() {
        const employeeConfig = await this.orm.searchRead(
            "hr.employee",
            [["id", "=", this.employee.id]],
            ["allow_without_image_capture"]
        );

        return employeeConfig[0]?.allow_without_image_capture || false;
    },

    _buildAlertMarkup(title, messageContent, wrapperStyle, headerStyle, messageStyle) {
        return markup(`
            <div style="${wrapperStyle}">
                <div style="${headerStyle}">
                    <i class="fa fa-exclamation-triangle"
                       style="
                           color:#DC3545;
                           font-size:20px;
                           width:24px;
                           min-width:24px;
                           text-align:center;
                           margin-right:4px;
                       ">
                    </i>

                    <span>${title}</span>
                </div>

                <div style="${messageStyle}">${messageContent}</div>
            </div>
        `);
    },

    // OPEN CAMERA
    async openCamera() {
        try {
            this.state.allowWithoutImage = await this._fetchAllowWithoutImage();

            const records = await this.orm.searchRead(
                "res.company",
                [],
                [
                    "attendance_image_capture",
                    "face_recognition",
                    "face_recognition_backend",
                    "attendance_device_tracking",
                ]
            );

            const company = records[0] || {};

            this.state.isImageCaptureEnabled =
                company.attendance_image_capture;

            this.state.isFaceRecognitionEnabled =
                company.face_recognition &&
                company.face_recognition_backend;

            this.state.attendanceDeviceTracking =
                company.attendance_device_tracking;

            // Check current camera permission.
            try {
                const cameraStatus = await navigator.permissions.query({
                    name: "camera",
                });

                this.state.permissionStatus = cameraStatus.state;

                cameraStatus.onchange = () => {
                    this.state.permissionStatus = cameraStatus.state;
                };
            } catch (err) {
                console.warn(
                    "Camera permission status unavailable:",
                    err
                );
            }

            // If permission is already granted, keep the existing
            // normal camera preview behaviour.
            if (
                (this.state.isImageCaptureEnabled ||
                    this.state.isFaceRecognitionEnabled) &&
                !this.state.allowWithoutImage &&
                this.state.permissionStatus === "granted"
            ) {
                if (!this.stream) {
                    this.stream =
                        await navigator.mediaDevices.getUserMedia({
                            video: true,
                        });
                }

                if (this.videoPreviewRef.el) {
                    this.videoPreviewRef.el.srcObject = this.stream;
                }
            }
        } catch (err) {
            console.error("Camera access denied:", err);
        }
    },

    // REQUEST CAMERA PERMISSION ONLY
    async requestCameraPermission() {
        try {
            const stream =
                await navigator.mediaDevices.getUserMedia({
                    video: true,
                });

            this.stream = stream;

            this.state.permissionStatus = "granted";

            if (this.videoPreviewRef.el) {
                this.videoPreviewRef.el.srcObject = this.stream;
            }

            return true;
        } catch (err) {
            console.error("Camera permission denied:", err);

            this.state.permissionStatus = "denied";

            return false;
        }
    },

    // REQUEST LOCATION PERMISSION ONLY
    async requestLocationPermission() {
        if (!navigator.geolocation || isIosApp()) {
            return true;
        }

        try {
            const position = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(
                    resolve,
                    reject,
                    {
                        enableHighAccuracy: true,
                        timeout: 10000,
                        maximumAge: 0,
                    }
                );
            });

            this.state.locationPermissionStatus = "granted";

            return {
                success: true,
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
            };
        } catch (err) {
            console.error("Location permission denied:", err);

            this.state.locationPermissionStatus = "denied";

            return {
                success: false,
                latitude: null,
                longitude: null,
            };
        }
    },

    // STORE CAPTURED IMAGE
    async addImage(photo) {
        if (this.state.isImageCaptureEnabled) {
            if (this.state.permissionStatus === "granted") {
                const imgBase64 = await this.blobToBase64(photo);

                await rpc("/hr_attendance/store_captured_photo", {
                    photo: imgBase64,
                    action_type: this.state.checkedIn
                        ? "check_in"
                        : "check_out",
                });
            }
        }
    },

    // CHECK IN / CHECK OUT
    async signInOut() {
        this.isSigningAction = true;

        try {
            const isImageEnabled = this.state.isImageCaptureEnabled;
            const isFaceRecognitionEnabled = this.state.isFaceRecognitionEnabled;

            const allowWithoutImage = await this._fetchAllowWithoutImage();

            if (
                (isImageEnabled || isFaceRecognitionEnabled) &&
                !allowWithoutImage
            ) {
                let cameraPermission = this.state.permissionStatus;

                try {
                    const cameraStatus = await navigator.permissions.query({
                        name: "camera",
                    });

                    cameraPermission = cameraStatus.state;
                    this.state.permissionStatus = cameraStatus.state;
                } catch (err) {
                    console.warn(
                        "Unable to read camera permission:",
                        err
                    );
                }

                if (cameraPermission !== "granted") {
                    const granted = await this.requestCameraPermission();

                    if (!granted) {
                        this.notification.add(
                            _t("Camera permission is required."),
                            {
                                type: "danger",
                            }
                        );
                    }

                    if (this.state.attendanceDeviceTracking) {
                        await this.requestLocationPermission();
                    }

                    return;
                }
            }

            let latitude = null;
            let longitude = null;

            if (
                this.state.attendanceDeviceTracking &&
                navigator.geolocation &&
                !isIosApp()
            ) {
                let locationPermission = null;

                try {
                    const locationStatus = await navigator.permissions.query({
                        name: "geolocation",
                    });

                    locationPermission = locationStatus.state;
                    this.state.locationPermissionStatus = locationStatus.state;
                } catch (err) {
                    console.warn(
                        "Unable to read location permission:",
                        err
                    );
                }

                if (locationPermission !== "granted") {
                    const locationResult = await this.requestLocationPermission();

                    if (!locationResult.success) {
                        this.notification.add(
                            _t("Location permission is required."),
                            {
                                type: "danger",
                            }
                        );

                        return;
                    }

                    return;
                }

                try {
                    const pos = await new Promise((resolve, reject) => {
                        navigator.geolocation.getCurrentPosition(
                            resolve,
                            reject,
                            {
                                enableHighAccuracy: true,
                                timeout: 10000,
                                maximumAge: 0,
                            }
                        );
                    });

                    latitude = pos.coords.latitude;
                    longitude = pos.coords.longitude;
                } catch (err) {
                    console.error(
                        "Unable to get current location:",
                        err
                    );

                    this.notification.add(
                        _t("Unable to get your current location."),
                        {
                            type: "warning",
                        }
                    );

                    return;
                }
            }

            // CHECK LOCATION
            // This happens ONLY after location permission is
            // already granted.
    
            if (latitude !== null && longitude !== null) {
                const result = await rpc(
                    "/face_attendance/check_location",
                    {
                        latitude: latitude,
                        longitude: longitude,
                    }
                );

                if (!result.success) {
                    const message =
                        result.msg || "You are not within allowed attendance area.";

                    // Close attendance dropdown
                    this.dropdown.close();

                    this.notification.add(
                        this._buildAlertMarkup(
                            "Location Validation",
                            message.trim().replace(/\s+/g, " "),
                            "",
                            "display:flex;align-items:center;margin:0;padding:0;line-height:1.4;",
                            "margin:0 0 0 28px;padding:0;line-height:1.5;white-space:normal;"
                        ),
                        {
                            type: "danger",
                            sticky: false,
                        }
                    );

                    return;
                }
            }

            // CAMERA MUST ALREADY BE GRANTED

            const isPermissionGranted = this.state.permissionStatus === "granted";

            if (
                (isImageEnabled || isFaceRecognitionEnabled) &&
                !allowWithoutImage &&
                !isPermissionGranted
            ) {
                this.notification.add(
                    _t("Camera permission is required"),
                    {
                        type: "danger",
                    }
                );

                return;
            }

            let photo = null;

            if (
                (isImageEnabled || isFaceRecognitionEnabled) &&
                isPermissionGranted &&
                !allowWithoutImage
            ) {
                try {
                    if (!this.stream || !this.stream.active) {
                        this.stream = await navigator.mediaDevices.getUserMedia({
                            video: true,
                        });
                    }

                    const track = this.stream.getVideoTracks()[0];
                    const imageCapture = new ImageCapture(track);

                    photo = await imageCapture.takePhoto();
                } catch (err) {
                    console.error(
                        "Image capture failed:",
                        err
                    );
                }
            }

            // UPLOAD IMAGE TO SESSION

            if (photo && !allowWithoutImage) {
                await this.uploadImageToSession(photo);
            }

            // FACE RECOGNITION

            if (isFaceRecognitionEnabled && !allowWithoutImage) {
                const faceResponse = await rpc(
                    "/hr_attendance/face_recognition_check",
                    {}
                );

                this.state.isFaceMatched = faceResponse.success;

                if (!faceResponse.success) {
                    const message = faceResponse.msg || "Face not recognized";

                    this.notification.add(
                        this._buildAlertMarkup(
                            "Face Recognition Failed",
                            message,
                            "margin:0 !important;padding:0 !important;",
                            "display:flex;align-items:center;margin:0 !important;padding:0 !important;line-height:1.4 !important;",
                            "margin:0 0 0 28px !important;padding:0 !important;line-height:1.4 !important;white-space:pre-line !important;"
                        ),
                        {
                            type: "danger",
                            sticky: false,
                        }
                    );

                    this.closeCamera();

                    return;
                }
            }

            // ACTUAL ODOO ATTENDANCE

            const response = await rpc(
                "/hr_attendance/systray_check_in_out",
                {
                    latitude: latitude,
                    longitude: longitude,
                }
            );

            if (response.attendance_state) {
                if (this.employee) {
                    this.employee.attendance_state = response.attendance_state;
                }

                const location =
                    response.geo_ip?.location || "Location not available";

                const employeeName = response.employee_name || "";

                const attendanceState = (response.attendance_state || "").toLowerCase();

                const isCheckout =
                    attendanceState === "checked_out" ||
                    attendanceState === "check_out";

                const greeting = isCheckout ? "   Goodbye" : "    Welcome";
                const actionText = isCheckout ? "Checked out at" : "Checked in at";

                const now = new Date();

                const formattedDate = now.toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                });

                const formattedTime = now.toLocaleTimeString("en-US", {
                    hour: "numeric",
                    minute: "2-digit",
                    hour12: true,
                });

                const fullMessage = markup(`
                    <div>

                        <!-- Welcome / Goodbye -->
                        <div style="
                            display:flex;
                            align-items:center;
                            margin-bottom:6px;
                        ">
                            <i class="fa fa-check-circle"
                               style="
                                   color:#28A745;
                                   font-size:16px;
                                   width:24px;
                                   min-width:24px;
                                   text-align:center;
                                   margin-right:4px;
                               ">
                            </i>

                            <span>
                                ${greeting} ! ${employeeName}
                            </span>
                        </div>

                        <!-- Check In / Check Out -->
                        <div style="
                            display:flex;
                            align-items:center;
                            margin-bottom:6px;
                        ">
                            <i class="oi oi-activity-plus"
                               style="
                                   color:#714B67;
                                   font-size:20px;
                                   width:24px;
                                   min-width:24px;
                                   text-align:center;
                                   margin-right:4px;
                               ">
                            </i>

                            <span>
                                ${actionText} ${formattedDate}, ${formattedTime}
                            </span>
                        </div>

                        <!-- Location -->
                        <div style="
                            display:flex;
                            align-items:center;
                        ">
                            <i class="fa fa-map-marker"
                               style="
                                   color:#E83E8C;
                                   font-size:20px;
                                   width:24px;
                                   min-width:24px;
                                   text-align:center;
                                   margin-right:4px;
                               ">
                            </i>

                            <span>
                                ${location}
                            </span>
                        </div>

                    </div>
                `);

                this.notification.add(fullMessage, {
                    type: "success",
                    sticky: false,
                });

                // STEP 9: STORE PHOTO

                if (this.state.isFaceMatched && !allowWithoutImage) {
                    if (photo) {
                        await this.addImage(photo);
                    }
                } else if (!isFaceRecognitionEnabled && !allowWithoutImage) {
                    if (photo) {
                        await this.addImage(photo);
                    }
                }
            } else {
                this.notification.add(
                    response.msg || "Attendance failed",
                    {
                        title: " Failed",
                        type: "danger",
                    }
                );
            }
        } catch (error) {
            console.error(error);

            this.notification.add(
                _t("Something went wrong"),
                {
                    type: "danger",
                }
            );
        }

        this.closeCamera();
        this.isSigningAction = false;
    },


    blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();

            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;

            reader.readAsDataURL(blob);
        });
    },

    // UPLOAD IMAGE TO SESSION
    async uploadImageToSession(photo) {
        const formData = new FormData();

        formData.append("image", photo);

        await fetch("/hr_attendance/store_image_session", {
            method: "POST",
            body: formData,
        });
    },

    // CLOSE CAMERA
    async closeCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach((track) => track.stop());
            this.stream = null;
        }

        if (this.videoPreviewRef?.el) {
            this.videoPreviewRef.el.srcObject = null;
            this.videoPreviewRef.el.pause();
        }

        // Close the attendance dropdown/camera section
        if (this.dropdown) {
            this.dropdown.close();
        }

        this.isSigningAction = false;
    },
});