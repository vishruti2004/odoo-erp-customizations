/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import kioskModule from "@hr_attendance/public_kiosk/public_kiosk_app";
const { kioskAttendanceApp } = kioskModule; 
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";
import  { FaceRecognitionButton }  from "./faceRecognizationButton/faceRecognizationButton";
import { rpc } from "@web/core/network/rpc";
patch(kioskAttendanceApp, {
    components: {
        ...kioskAttendanceApp.components,
        FaceRecognitionButton,
    },

});
    
patch(kioskAttendanceApp.prototype, {
    setup() {
        super.setup();

        Object.assign(this.state, {
            isFaceRecognitionEnabled: false,
            isImageCaptureEnabled:false
        });

        onWillStart(async () => {
            try {
                const token = this.props.token;

                const result = await rpc("/hr_attendance/get_company_by_token", {
                    token: token,
                });

                console.log("Company from token:", result);

                if (result && result.id) {
                    this.state.isFaceRecognitionEnabled = result.face_recognition && result.face_recognition_kiosk;
                    this.state.isImageCaptureEnabled = result.attendance_image_capture
                }
            } catch (e) {
                console.error("Error fetching company via token:", e);
            }
        });
    },
});