/** @odoo-module **/

import { renderToElement } from "@web/core/utils/render";
import { rpc } from "@web/core/network/rpc";

let qrScannerElement = null;
let qrStream = null;
let qrVideo = null;
let qrCanvas = null;
let qrContext = null;
let qrScanTimer = null;
let qrScanTimeout = null;
let qrScanning = false;
let qrScanInProgress = false;
let currentActionType = null;
let qrReturnUrl = null;

const QR_SCAN_INTERVAL = 100;
const QR_SCAN_TIMEOUT = 3000;
const QR_RETURN_DELAY = 2500;

async function startQRScanner(actionType) {
    if (qrScannerElement) {
        return;
    }

    qrReturnUrl = window.location.href;
    currentActionType = actionType;
    qrScanning = false;
    qrScanInProgress = false;

    if (typeof window.jsQR !== "function") {
        return;
    }

    if (
        !navigator.mediaDevices ||
        !navigator.mediaDevices.getUserMedia
    ) {
        return;
    }

    try {
        qrScannerElement = renderToElement(
            "iPredict_gym_portal.GymAttendanceQRScanner",
            {}
        );

        document.body.appendChild(qrScannerElement);

        const closeButton = qrScannerElement.querySelector(
            ".gym-qr-close"
        );

        if (closeButton) {
            closeButton.addEventListener(
                "click",
                closeQRScanner
            );
        }

        qrVideo = qrScannerElement.querySelector(
            ".gym-qr-video"
        );

        if (!qrVideo) {
            closeQRScanner();
            return;
        }

        qrCanvas = document.createElement("canvas");
        qrCanvas.width = 640;
        qrCanvas.height = 640;

        qrContext = qrCanvas.getContext("2d", {
            willReadFrequently: true,
        });

        if (!qrContext) {
            closeQRScanner();
            return;
        }

        qrStream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: {
                    ideal: "environment",
                },
                width: {
                    ideal: 1280,
                },
                height: {
                    ideal: 720,
                },
            },
            audio: false,
        });

        qrVideo.srcObject = qrStream;
        qrVideo.setAttribute("playsinline", "true");
        qrVideo.setAttribute("autoplay", "true");
        qrVideo.muted = true;

        await qrVideo.play();

        showMessage(
            "Position the QR code inside the frame.",
            "info"
        );

        startQRDetection();
    } catch (error) {
        console.error(
            "GYM QR: Scanner initialization error:",
            error
        );

        if (error?.name === "NotAllowedError") {
            showToast(
                "Camera permission was denied. Please allow camera access.",
                "danger"
            );
        } else if (error?.name === "NotFoundError") {
            showToast(
                "No camera was found on this device.",
                "danger"
            );
        } else if (error?.name === "NotReadableError") {
            showToast(
                "Camera is already being used by another application.",
                "danger"
            );
        } else {
            showToast(
                "Unable to start QR scanner. Please try again.",
                "danger"
            );
        }
    }
}

function startQRDetection() {
    if (
        !qrVideo ||
        !qrCanvas ||
        !qrContext ||
        qrScanning ||
        qrScanInProgress
    ) {
        return;
    }

    if (
        qrVideo.readyState <
        HTMLMediaElement.HAVE_CURRENT_DATA
    ) {
        setTimeout(() => {
            startQRDetection();
        }, 300);

        return;
    }

    qrScanning = true;
    qrScanInProgress = false;

    showScanningOverlay();

    showMessage(
        "Scanning QR code...",
        "info"
    );

    clearQRScanTimeout();

    qrScanTimeout = setTimeout(() => {
        if (
            !qrScanning ||
            qrScanInProgress
        ) {
            return;
        }

        qrScanning = false;

        clearQRScanTimer();

        hideScanningOverlay();

        showToast(
            "QR Code not detected. Please try again.",
            "danger"
        );

        setTimeout(() => {
            returnToGymScreen();
        }, QR_RETURN_DELAY);
    }, QR_SCAN_TIMEOUT);

    scanQRCode();
}

function scanQRCode() {
    if (
        !qrScanning ||
        qrScanInProgress ||
        !qrVideo ||
        !qrCanvas ||
        !qrContext
    ) {
        return;
    }

    try {
        if (
            qrVideo.readyState <
            HTMLMediaElement.HAVE_CURRENT_DATA
        ) {
            scheduleNextQRScan();
            return;
        }

        const videoWidth = qrVideo.videoWidth;
        const videoHeight = qrVideo.videoHeight;

        if (
            !videoWidth ||
            !videoHeight
        ) {
            scheduleNextQRScan();
            return;
        }

        const sourceSize = Math.min(
            videoWidth,
            videoHeight
        );

        const sourceX = Math.floor(
            (videoWidth - sourceSize) / 2
        );

        const sourceY = Math.floor(
            (videoHeight - sourceSize) / 2
        );

        const scanSize = 640;

        qrContext.drawImage(
            qrVideo,
            sourceX,
            sourceY,
            sourceSize,
            sourceSize,
            0,
            0,
            scanSize,
            scanSize
        );

        const imageData = qrContext.getImageData(
            0,
            0,
            scanSize,
            scanSize
        );

        const code = window.jsQR(
            imageData.data,
            scanSize,
            scanSize,
            {
                inversionAttempts: "attemptBoth",
            }
        );

        if (
            code &&
            code.data
        ) {
            const qrToken = code.data.trim();

            if (qrToken) {
                qrScanInProgress = true;
                qrScanning = false;

                clearQRScanTimer();
                clearQRScanTimeout();

                hideScanningOverlay();

                validateQRCode(qrToken);

                return;
            }
        }
    } catch (error) {
        console.warn(
            "GYM QR: QR frame could not be processed.",
            error
        );
    }

    scheduleNextQRScan();
}

function scheduleNextQRScan() {
    if (
        !qrScanning ||
        qrScanInProgress
    ) {
        return;
    }

    clearQRScanTimer();

    qrScanTimer = setTimeout(() => {
        scanQRCode();
    }, QR_SCAN_INTERVAL);
}

function clearQRScanTimer() {
    if (qrScanTimer) {
        clearTimeout(qrScanTimer);
        qrScanTimer = null;
    }
}

function clearQRScanTimeout() {
    if (qrScanTimeout) {
        clearTimeout(qrScanTimeout);
        qrScanTimeout = null;
    }
}

async function validateQRCode(qrToken) {
    if (!currentActionType) {
        stopCamera();

        showToast(
            "Invalid attendance action.",
            "danger"
        );

        setTimeout(() => {
            returnToGymScreen();
        }, QR_RETURN_DELAY);

        return;
    }

    showMessage(
        "QR code detected. Verifying...",
        "info"
    );

    try {
        const result = await rpc(
            "/my/gym/attendance/validate-qr",
            {
                qr_token: qrToken,
                action_type: currentActionType,
            }
        );

        if (
            !result ||
            !result.success
        ) {
            qrScanInProgress = true;
            qrScanning = false;

            stopCamera();
            hideScanningOverlay();

            showToast(
                result?.message ||
                "Invalid Gym QR Code.",
                "danger"
            );

            setTimeout(() => {
                returnToGymScreen();
            }, QR_RETURN_DELAY);

            return;
        }

        qrScanInProgress = true;
        qrScanning = false;

        stopCamera();
        hideScanningOverlay();

        showToast(
            result.message ||
            "Attendance updated successfully.",
            "success"
        );

        setTimeout(() => {
            closeQRScanner();
            window.location.href = "/my";
        }, 800);
    } catch (error) {
        console.error(
            "GYM QR: Backend validation error:",
            error
        );

        qrScanInProgress = true;
        qrScanning = false;

        stopCamera();
        hideScanningOverlay();

        showToast(
            "Unable to validate QR code. Please try again.",
            "danger"
        );

        setTimeout(() => {
            returnToGymScreen();
        }, QR_RETURN_DELAY);
    }
}

function stopCamera() {
    qrScanning = false;

    clearQRScanTimer();
    clearQRScanTimeout();

    if (qrStream) {
        qrStream.getTracks().forEach((track) => {
            track.stop();
        });

        qrStream = null;
    }

    if (qrVideo) {
        try {
            qrVideo.pause();
        } catch (error) {
            console.warn(
                "GYM QR: Unable to pause video.",
                error
            );
        }

        qrVideo.srcObject = null;
    }
}

function returnToGymScreen() {
    const returnUrl =
        qrReturnUrl ||
        window.location.href;

    closeQRScanner();

    if (
        window.location.href !==
        returnUrl
    ) {
        window.location.href =
            returnUrl;
    }
}

function closeQRScanner() {
    stopCamera();

    qrScanInProgress = false;
    currentActionType = null;

    if (qrScannerElement) {
        qrScannerElement.remove();
        qrScannerElement = null;
    }

    qrVideo = null;
    qrCanvas = null;
    qrContext = null;
    qrReturnUrl = null;
}

function showScanningOverlay() {
    if (!qrScannerElement) {
        return;
    }

    const overlay =
        qrScannerElement.querySelector(
            ".gym-qr-scanning-overlay"
        );

    if (overlay) {
        overlay.style.display = "flex";
    }
}

function hideScanningOverlay() {
    if (!qrScannerElement) {
        return;
    }

    const overlay =
        qrScannerElement.querySelector(
            ".gym-qr-scanning-overlay"
        );

    if (overlay) {
        overlay.style.display = "none";
    }
}

function showMessage(
    message,
    type = "info"
) {
    if (!qrScannerElement) {
        return;
    }

    const messageElement =
        qrScannerElement.querySelector(
            ".gym-qr-message"
        );

    if (!messageElement) {
        return;
    }

    messageElement.textContent =
        message;

    messageElement.className =
        `gym-qr-message ${type}`;
}

function showToast(
    message,
    type = "info"
) {
    if (!qrScannerElement) {
        return;
    }

    const toast =
        qrScannerElement.querySelector(
            ".gym-qr-toast"
        );

    if (!toast) {
        showMessage(
            message,
            type
        );

        return;
    }

    toast.textContent =
        message;

    toast.className =
        `gym-qr-toast ${type} show`;

    setTimeout(() => {
        if (toast) {
            toast.className =
                `gym-qr-toast ${type}`;
        }
    }, QR_RETURN_DELAY);
}

document.addEventListener(
    "click",
    (event) => {
        const button =
            event.target.closest(
                ".js_gym_attendance_qr"
            );

        if (!button) {
            return;
        }

        event.preventDefault();

        const actionType =
            button.dataset.actionType;

        if (!actionType) {
            return;
        }

        startQRScanner(
            actionType
        );
    }
);