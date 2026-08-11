/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

console.log("Locker Kiosk JS loaded");

export class LockerKiosk extends Component {
    static template = "iPredict_locker_management.LockerKiosk";

    setup() {
        this.state = useState({
            mode: "person_search",
            personSearch: "",
            persons: [],
            selectedPerson: null,
            authentication: "",
            allocation: null,
            message: "",
            messageType: "",
            loading: false,
            qrScanning: false,
            qrSupported: false,
            qrAuthOptions: false,
            qrHasOTP: false,
            otp: "",
            otpSent: false,
            lockedUntil: null,
            faceScanning: false,
            faceVerifying: false,
        });
        this.qrStream = null;
        this.qrVideo = null;
        this.qrCanvas = null;
        this.qrContext = null;
        this.qrAnimationFrame = null;
        this.qrScanInProgress = false;
        this.faceStream = null;
        this.faceVideo = null;
        this.faceCanvas = null;
        this.faceContext = null;
        this.selectPerson = this.selectPerson.bind(this);
        onMounted(() => { this.focusCurrentInput(); });
        onWillUnmount(() => { this.stopQRScanner(); this.stopFaceScanner(); });
    }

    focusCurrentInput() {
        setTimeout(() => {
            let selector = null;
            if (this.state.mode === "person_search") {
                selector = ".locker-person-search-input";
            } else if (this.state.mode === "credential" && this.state.selectedPerson?.access_method !== "qr" && this.state.selectedPerson?.access_method !== "biometric") {
                selector = ".locker-authentication-input";
            } else if (this.state.mode === "otp") {
                selector = ".locker-otp-input";
            }
            if (!selector) return;
            const input = document.querySelector(selector);
            if (input) { input.focus(); input.select(); }
        }, 100);
    }

    showMessage(message, type) {
        this.state.message = message;
        this.state.messageType = type;
    }

    clearMessage() {
        this.state.message = "";
        this.state.messageType = "";
    }

    resetQRAuthenticationState() {
        this.state.qrAuthOptions = false;
        this.state.qrHasOTP = false;
        this.state.otp = "";
        this.state.otpSent = false;
        this.state.lockedUntil = null;
    }

    resetFaceAuthenticationState() {
        this.state.faceScanning = false;
        this.state.faceVerifying = false;
        this.stopFaceScanner();
    }

    onPersonSearchChange(ev) {
        this.state.personSearch = ev.target.value;
        this.clearMessage();
    }

    async findPerson() {
        const value = this.state.personSearch.trim();
        if (!value) {
            this.showMessage("Please enter name, email or phone number.", "danger");
            return;
        }
        this.state.loading = true;
        this.clearMessage();
        this.state.persons = [];
        this.state.selectedPerson = null;
        this.state.authentication = "";
        this.state.allocation = null;
        this.resetQRAuthenticationState();
        this.resetFaceAuthenticationState();
        this.stopQRScanner();
        try {
            const result = await rpc("/locker/access/find_person", { identity: value });
            if (!result.success) {
                this.showMessage(result.message || "No person found.", "danger");
                return;
            }
            this.state.persons = result.persons || [];
            if (!this.state.persons.length) {
                this.showMessage("No authorized person found.", "danger");
                return;
            }
            this.state.mode = "person_selection";
        } catch (error) {
            console.error("Locker person search error:", error);
            this.showMessage("Unable to find person. Please try again.", "danger");
        } finally {
            this.state.loading = false;
        }
    }

    selectPerson(person) {
        if (!person) {
            console.error("No person received in selectPerson()");
            return;
        }
        console.log("Selected Person:", person);
        console.log("Access Method:", person.access_method);
        this.stopQRScanner();
        this.stopFaceScanner();
        this.state.selectedPerson = person;
        this.state.authentication = "";
        this.state.allocation = null;
        this.clearMessage();
        this.resetQRAuthenticationState();
        if (person.otp_locked) {
            this.state.lockedUntil = person.otp_locked_until || null;
            this.state.mode = "locked";
            this.showMessage("You have already used all 3 authentication attempts. Please try again after 10 minutes.", "danger");
            return;
        }
        this.state.mode = "credential";
        if (person.access_method === "pin") {
            setTimeout(() => this.focusCurrentInput(), 200);
            return;
        }
        if (person.access_method === "rfid") {
            setTimeout(() => this.focusCurrentInput(), 200);
            return;
        }
        if (person.access_method === "qr") {
            setTimeout(() => this.startQRScanner(), 500);
            return;
        }
        if (person.access_method === "biometric") {
            setTimeout(() => this.startFaceScanner(), 500);
            return;
        }
        setTimeout(() => this.focusCurrentInput(), 200);
    }

    backToPersonSearch() {
        this.stopQRScanner();
        this.stopFaceScanner();
        this.state.mode = "person_search";
        this.state.personSearch = "";
        this.state.persons = [];
        this.state.selectedPerson = null;
        this.state.authentication = "";
        this.state.allocation = null;
        this.resetQRAuthenticationState();
        this.clearMessage();
        this.state.loading = false;
        this.focusCurrentInput();
    }

    onInputChange(ev) {
        this.state.authentication = ev.target.value;
        this.clearMessage();
    }

    async authenticate() {
        const value = this.state.authentication.trim();
        if (!value) {
            this.showMessage("Please enter or scan your authentication credential.", "danger");
            return;
        }
        if (!this.state.selectedPerson) {
            this.showMessage("Please select a person first.", "danger");
            return;
        }
        if (this.state.selectedPerson.access_method === "qr") {
            this.showMessage("Please scan the QR code first.", "danger");
            return;
        }
        if (this.state.selectedPerson.access_method === "biometric") {
            this.showMessage("Please use face recognition.", "danger");
            return;
        }
        this.state.loading = true;
        this.clearMessage();
        this.state.allocation = null;
        try {
            const result = await rpc("/locker/access/authenticate", {
                identity: value,
                partner_id: this.state.selectedPerson.partner_id,
                allocation_id: this.state.selectedPerson.allocation_id,
            });
            if (!result.success) {
                this.showMessage(result.message || "Authentication failed.", "danger");
                return;
            }
            this.state.allocation = result.allocation;
            this.state.mode = "result";
            this.showMessage("Identity verified successfully.", "success");
        } catch (error) {
            console.error("Locker authentication error:", error);
            this.showMessage("Unable to authenticate. Please try again.", "danger");
        } finally {
            this.state.loading = false;
        }
    }

    async startFaceScanner() {
        if (!this.state.selectedPerson || this.state.selectedPerson.access_method !== "biometric") return;
        this.stopFaceScanner();
        this.clearMessage();
        this.state.faceScanning = false;
        this.state.faceVerifying = false;
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.showMessage("Camera access is not supported by this browser.", "danger");
            return;
        }
        try {
            const pendingResult = await rpc("/locker/access/start_face", {
                partner_id: this.state.selectedPerson.partner_id,
                allocation_id: this.state.selectedPerson.allocation_id,
            });
            if (!pendingResult.success) {
                if (pendingResult.locked) {
                    this.state.lockedUntil = pendingResult.locked_until || null;
                    this.state.mode = "locked";
                }
                this.showMessage(pendingResult.message || "Unable to start face authentication.", "danger");
                return;
            }
            const video = document.querySelector(".locker-face-video");
            if (!video) {
                console.error("Face video element not found.");
                this.showMessage("Unable to initialize face camera.", "danger");
                return;
            }
            this.faceVideo = video;
            this.faceCanvas = document.createElement("canvas");
            this.faceContext = this.faceCanvas.getContext("2d");
            if (!this.faceContext) {
                this.showMessage("Unable to initialize face camera.", "danger");
                return;
            }
            this.faceStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: "user" }, width: { ideal: 1280 }, height: { ideal: 720 } },
                audio: false,
            });
            this.faceVideo.srcObject = this.faceStream;
            this.faceVideo.setAttribute("playsinline", "true");
            this.faceVideo.setAttribute("autoplay", "true");
            this.faceVideo.muted = true;
            await this.faceVideo.play();
            this.state.faceScanning = true;
        } catch (error) {
            console.error("Face scanner initialization error:", error);
            this.state.faceScanning = false;
            if (error.name === "NotAllowedError") {
                this.showMessage("Camera permission was denied. Please allow camera access.", "danger");
            } else if (error.name === "NotFoundError") {
                this.showMessage("No camera was found on this device.", "danger");
            } else if (error.name === "NotReadableError") {
                this.showMessage("Camera is already being used by another application.", "danger");
            } else {
                this.showMessage("Unable to start face camera. Please try again.", "danger");
            }
        }
    }

    async verifyFace() {
        if (!this.state.selectedPerson || !this.faceVideo || !this.state.faceScanning) {
            this.showMessage("Please start the camera first.", "danger");
            return;
        }
        if (this.state.faceVerifying) return;
        const video = this.faceVideo;
        if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
            this.showMessage("Camera is not ready yet. Please wait.", "danger");
            return;
        }
        const videoWidth = video.videoWidth;
        const videoHeight = video.videoHeight;
        if (!videoWidth || !videoHeight) {
            this.showMessage("Unable to capture the camera image. Please try again.", "danger");
            return;
        }
        this.faceCanvas.width = videoWidth;
        this.faceCanvas.height = videoHeight;
        this.faceContext.drawImage(video, 0, 0, videoWidth, videoHeight);
        const image = this.faceCanvas.toDataURL("image/jpeg", 0.85);
        this.state.faceVerifying = true;
        this.state.loading = true;
        this.clearMessage();
        try {
            const result = await rpc("/locker/access/verify_face", { image: image });
            if (!result.success) {
                if (result.locked) {
                    this.state.lockedUntil = result.locked_until || null;
                    this.state.mode = "locked";
                    this.stopFaceScanner();
                    this.showMessage(result.message || "Too many incorrect authentication attempts.", "danger");
                    return;
                }
                this.showMessage(result.message || "Face verification failed.", "danger");
                return;
            }
            this.state.allocation = result.allocation;
            this.state.mode = "result";
            this.stopFaceScanner();
            this.showMessage(result.message || "Face verified successfully.", "success");
        } catch (error) {
            console.error("Face verification error:", error);
            this.showMessage("Unable to verify face. Please try again.", "danger");
        } finally {
            this.state.faceVerifying = false;
            this.state.loading = false;
        }
    }

    stopFaceScanner() {
        this.state.faceScanning = false;
        this.state.faceVerifying = false;
        if (this.faceStream) {
            this.faceStream.getTracks().forEach((track) => { track.stop(); });
            this.faceStream = null;
        }
        if (this.faceVideo) {
            try { this.faceVideo.pause(); } catch (error) { console.warn("Unable to pause face video:", error); }
            this.faceVideo.srcObject = null;
            this.faceVideo = null;
        }
        this.faceCanvas = null;
        this.faceContext = null;
    }

    async startQRScanner() {
        if (!this.state.selectedPerson || this.state.selectedPerson.access_method !== "qr") return;
        this.stopQRScanner();
        this.clearMessage();
        this.state.qrScanning = false;
        this.state.qrSupported = false;
        this.qrScanInProgress = false;
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.showMessage("Camera access is not supported by this browser.", "danger");
            return;
        }
        if (typeof window.jsQR !== "function") {
            console.error("jsQR library is not loaded.");
            this.showMessage("QR scanner library is not loaded. Please refresh the page.", "danger");
            return;
        }
        this.state.qrSupported = true;
        try {
            const video = document.querySelector(".locker-qr-video");
            if (!video) {
                console.error("QR video element not found.");
                this.showMessage("Unable to initialize QR scanner.", "danger");
                return;
            }
            this.qrVideo = video;
            this.qrCanvas = document.createElement("canvas");
            this.qrCanvas.width = 640;
            this.qrCanvas.height = 480;
            this.qrContext = this.qrCanvas.getContext("2d", { willReadFrequently: true });
            if (!this.qrContext) {
                this.showMessage("Unable to initialize QR scanner.", "danger");
                return;
            }
            this.qrStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
                audio: false,
            });
            this.qrVideo.srcObject = this.qrStream;
            this.qrVideo.setAttribute("playsinline", "true");
            this.qrVideo.setAttribute("autoplay", "true");
            this.qrVideo.muted = true;
            await this.qrVideo.play();
            this.state.qrScanning = true;
            this.scanQRCode();
        } catch (error) {
            console.error("QR scanner initialization error:", error);
            this.state.qrScanning = false;
            if (error.name === "NotAllowedError") {
                this.showMessage("Camera permission was denied. Please allow camera access.", "danger");
            } else if (error.name === "NotFoundError") {
                this.showMessage("No camera was found on this device.", "danger");
            } else if (error.name === "NotReadableError") {
                this.showMessage("Camera is already being used by another application.", "danger");
            } else {
                this.showMessage("Unable to start QR scanner. Please try again.", "danger");
            }
        }
    }

    async scanQRCode() {
        if (!this.state.qrScanning || !this.qrVideo || !this.qrCanvas || !this.qrContext) return;
        if (this.qrScanInProgress) return;
        try {
            const video = this.qrVideo;
            if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
                this.scheduleNextQRScan();
                return;
            }
            const videoWidth = video.videoWidth;
            const videoHeight = video.videoHeight;
            if (!videoWidth || !videoHeight) {
                this.scheduleNextQRScan();
                return;
            }
            if (this.qrCanvas.width !== videoWidth || this.qrCanvas.height !== videoHeight) {
                this.qrCanvas.width = videoWidth;
                this.qrCanvas.height = videoHeight;
            }
            this.qrContext.drawImage(video, 0, 0, videoWidth, videoHeight);
            const imageData = this.qrContext.getImageData(0, 0, videoWidth, videoHeight);
            const code = window.jsQR(imageData.data, imageData.width, imageData.height, { inversionAttempts: "attemptBoth" });
            if (code && code.data) {
                const qrValue = code.data.trim();
                if (qrValue) {
                    console.log("QR CODE DETECTED:", qrValue);
                    this.qrScanInProgress = true;
                    this.state.authentication = qrValue;
                    this.stopQRScanner();
                    await this.verifyQRCode(qrValue);
                    return;
                }
            }
        } catch (error) {
            console.error("QR scanning error:", error);
        }
        this.scheduleNextQRScan();
    }

    async verifyQRCode(qrToken) {
        if (!this.state.selectedPerson) {
            this.showMessage("Please select a person first.", "danger");
            return;
        }
        this.state.loading = true;
        this.clearMessage();
        try {
            const result = await rpc("/locker/access/verify_qr", {
                qr_token: qrToken,
                partner_id: this.state.selectedPerson.partner_id,
                allocation_id: this.state.selectedPerson.allocation_id,
            });
            if (!result.success) {
                this.showMessage(result.message || "Invalid QR code.", "danger");
                this.qrScanInProgress = false;
                return;
            }
            this.state.qrHasOTP = !!result.has_otp;
            this.state.qrAuthOptions = true;
            this.state.mode = "qr_verification";
            if (this.state.qrHasOTP) {
                this.showMessage("QR code verified. Please continue with OTP authentication.", "success");
            } else {
                this.showMessage("OTP authentication is not available for this person.", "danger");
            }
        } catch (error) {
            console.error("QR verification error:", error);
            this.showMessage("Unable to verify QR code. Please try again.", "danger");
        } finally {
            this.state.loading = false;
            this.qrScanInProgress = false;
        }
    }

    async chooseOTP() {
        if (!this.state.qrHasOTP) {
            this.showMessage("OTP authentication is not available for this person.", "danger");
            return;
        }
        this.state.loading = true;
        this.clearMessage();
        try {
            const result = await rpc("/locker/access/send_otp", {});
            if (!result.success) {
                if (result.locked) {
                    this.state.lockedUntil = result.locked_until || null;
                    this.state.mode = "locked";
                }
                this.showMessage(result.message || "Unable to send OTP.", "danger");
                return;
            }
            this.state.otp = "";
            this.state.otpSent = true;
            this.state.mode = "otp";
            this.showMessage(result.message || "OTP has been sent to the registered email address.", "success");
            setTimeout(() => { this.focusCurrentInput(); }, 200);
        } catch (error) {
            console.error("Send OTP error:", error);
            this.showMessage("Unable to send OTP. Please try again.", "danger");
        } finally {
            this.state.loading = false;
        }
    }

    onOTPChange(ev) {
        this.state.otp = ev.target.value.replace(/\D/g, "").slice(0, 6);
        this.clearMessage();
    }

    async verifyOTP() {
        const otp = this.state.otp.trim();
        if (!otp) {
            this.showMessage("Please enter the OTP.", "danger");
            return;
        }
        if (otp.length !== 6) {
            this.showMessage("OTP must contain exactly 6 digits.", "danger");
            return;
        }
        this.state.loading = true;
        this.clearMessage();
        try {
            const result = await rpc("/locker/access/verify_otp", { otp: otp });
            if (!result.success) {
                if (result.locked) {
                    this.state.otp = "";
                    this.state.otpSent = false;
                    this.state.lockedUntil = result.locked_until || null;
                    this.state.mode = "locked";
                    this.showMessage(result.message || "Too many incorrect attempts.", "danger");
                    return;
                }
                this.showMessage(result.message || "Invalid OTP.", "danger");
                return;
            }
            this.state.allocation = result.allocation;
            this.state.mode = "result";
            this.state.otp = "";
            this.state.otpSent = false;
            this.showMessage(result.message || "OTP verified successfully.", "success");
        } catch (error) {
            console.error("OTP verification error:", error);
            this.showMessage("Unable to verify OTP. Please try again.", "danger");
        } finally {
            this.state.loading = false;
        }
    }

    backToQRAuthentication() {
        this.state.otp = "";
        this.state.otpSent = false;
        this.clearMessage();
        this.state.mode = "qr_verification";
    }

    scheduleNextQRScan() {
        if (!this.state.qrScanning) return;
        this.qrAnimationFrame = requestAnimationFrame(() => { this.scanQRCode(); });
    }

    stopQRScanner() {
        this.state.qrScanning = false;
        this.qrScanInProgress = false;
        if (this.qrAnimationFrame) {
            cancelAnimationFrame(this.qrAnimationFrame);
            this.qrAnimationFrame = null;
        }
        if (this.qrStream) {
            this.qrStream.getTracks().forEach((track) => { track.stop(); });
            this.qrStream = null;
        }
        if (this.qrVideo) {
            try { this.qrVideo.pause(); } catch (error) { console.warn("Unable to pause QR video:", error); }
            this.qrVideo.srcObject = null;
            this.qrVideo = null;
        }
        this.qrCanvas = null;
        this.qrContext = null;
    }

    startRFIDInput() {
        setTimeout(() => {
            const input = document.querySelector(".locker-rfid-input") || document.querySelector(".locker-authentication-input");
            if (input) { input.focus(); input.select(); }
        }, 100);
    }

    async checkIn() {
        if (!this.state.allocation) return;
        await this.performAccess("check_in");
    }

    async checkOut() {
        if (!this.state.allocation) return;
        await this.performAccess("check_out");
    }

    async performAccess(action) {
        if (!this.state.allocation) return;
        this.state.loading = true;
        this.clearMessage();
        try {
            const result = await rpc("/locker/access/action", {
                allocation_id: this.state.allocation.id,
                action: action,
                authenticated_partner_id: this.state.allocation.authenticated_partner_id,
            });
            if (!result.success) {
                this.showMessage(result.message || "Unable to perform action.", "danger");
                return;
            }
            this.state.allocation = result.allocation;
            this.showMessage(result.message, "success");
        } catch (error) {
            console.error("Locker access action error:", error);
            this.showMessage("Something went wrong. Please try again.", "danger");
        } finally {
            this.state.loading = false;
        }
    }

    resetScreen() {
        this.stopQRScanner();
        this.stopFaceScanner();
        this.state.mode = "person_search";
        this.state.personSearch = "";
        this.state.persons = [];
        this.state.selectedPerson = null;
        this.state.authentication = "";
        this.state.allocation = null;
        this.resetQRAuthenticationState();
        this.clearMessage();
        this.state.loading = false;
        this.state.qrScanning = false;
        this.state.qrSupported = false;
        this.state.faceScanning = false;
        this.state.faceVerifying = false;
        this.focusCurrentInput();
    }
}

registry.category("actions").add("locker_kiosk_action", LockerKiosk);