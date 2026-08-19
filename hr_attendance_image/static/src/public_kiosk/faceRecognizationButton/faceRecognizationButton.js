/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { CameraDialog } from "../camera_dialog/camera_dialog";
import {registry} from "@web/core/registry";
export class FaceRecognitionButton extends Component {
    static template = "hr_attendance_image.FaceRecognitionButton";

    setup() {
        this.dialog = useService("dialog");
    }

    openCamera() {
        this.dialog.add(CameraDialog, {
            title: "Face Recognition",
            token: this.props.token,
            
            attendance_image_capture: this.props.attendance_image_capture,
            onSuccess: (result) => {
                if (this.props.onSuccess) {
                    this.props.onSuccess(result);
                }
            },

            onFailure: (result) => {
                if (this.props.onFailure) {
                    this.props.onFailure(result);
                }
            },
        });
    }
}
// registry.category("components").add("FaceRecognitionButton", FaceRecognitionButton);