/** @odoo-module **/

import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import * as THREE from "../lib/three.module.js";

export class Locker3DView extends Component {

    setup() {
        this.canvasRef = useRef("canvas");
        this.orm = useService("orm");
        // State that updates the UI cards automatically
        this.state = useState({
            companies: [],
            selectedCompanyId: false,
            overloadCount: 0,
            almostFullCount: 0,
            freeSpaceCount: 0,
            noLoadCount: 0,
        });

        // Three.js objects: scene, camera, renderer
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        // The center point the camera looks at
        this.target = new THREE.Vector3(0, 1, 0);

        // Max 5 lockers per row. Extra lockers go to a new row on top.
        this.ROW_SIZE = 5;

        // When the page loads, load companies then draw the 3D scene
        onMounted(async () => {
            await this.loadCompanies();
            await this.renderScene();
        });
    }

    // Load all companies from database for the dropdown
    async loadCompanies() {
        try {
            this.state.companies = await this.orm.searchRead("res.company", [], ["name"]);
            if (this.state.companies.length) {
                this.state.selectedCompanyId = this.state.companies[0].id;
            }
        } catch (e) {
            console.error("Companies load error:", e);
        }
    }

    // When user changes the company in dropdown, redraw the scene
    async onCompanyChange(ev) {
        this.state.selectedCompanyId = Number(ev.target.value);
        await this.renderScene();
    }

    // Creates a text label on a canvas 
    createLabelTexture(text, bg, fg, border) {
        // Make a temporary canvas to draw text
        const canvas = document.createElement("canvas");
        canvas.width = 512;
        canvas.height = 256;
        const ctx = canvas.getContext("2d");

        // Background color
        ctx.fillStyle = bg;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        // Border around the label
        ctx.strokeStyle = border;
        ctx.lineWidth = 6;
        ctx.strokeRect(0, 0, canvas.width, canvas.height);

        // Draw the text in center
        ctx.fillStyle = fg;
        ctx.font = "bold 72px Arial";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(text, canvas.width / 2, canvas.height / 2);

        const texture = new THREE.CanvasTexture(canvas);
        texture.needsUpdate = true;
        return texture;
    }

    async renderScene() {
        const container = this.canvasRef.el;
        container.innerHTML = "";

        // ---------- S Get lockers from database ----------
        let locations = [];
        try {
            locations = await this.orm.call("locker.locker", "get_3d_data", [this.state.selectedCompanyId]);
        } catch (e) {
            container.innerHTML = `<div style="padding:50px;color:red;text-align:center;">Error: ${e.message}</div>`;
            return;
        }

        // If no data, show a message
        if (!locations || locations.length === 0) {
            container.innerHTML = `<div style="padding:50px;color:#666;text-align:center;">No lockers found.</div>`;
            return;
        }

        console.log("DB Data:", locations);

        // ---------stats for the top cards ----------
        let overload = 0, almostFull = 0, freeSpace = 0, noLoad = 0;
        for (const loc of locations) {
            const total = loc.lockers.length;
            let allocated = 0;
            for (const locker of loc.lockers) {
                if (locker.status === "allocated") allocated++;
            }
            const percent = total > 0 ? (allocated / total) * 100 : 0;
            if (percent >= 80) overload++;
            else if (percent >= 50) almostFull++;
            else if (percent >= 20) freeSpace++;
            else noLoad++;
        }
        // Update UI cards
        this.state.overloadCount = overload;
        this.state.almostFullCount = almostFull;
        this.state.freeSpaceCount = freeSpace;
        this.state.noLoadCount = noLoad;

        // ---------- Set up the empty 3D scene ----------
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xe8ecf1); // Light grey background

        const width = container.clientWidth || 800;
        const height = container.clientHeight || 600;
        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);

        // Renderer: draws the 3D scene on the HTML canvas
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setSize(width, height);
        this.renderer.shadowMap.enabled = true;
        container.appendChild(this.renderer.domElement);

        // Add lights
        this.scene.add(new THREE.HemisphereLight(0xadd8e6, 0x3a3a3a, 0.8));
        const mainLight = new THREE.DirectionalLight(0xffffff, 1.8);
        mainLight.position.set(15, 30, 20);
        mainLight.castShadow = true;
        this.scene.add(mainLight);

        // Add a floor
        const floor = new THREE.Mesh(
            new THREE.PlaneGeometry(250, 250),
            new THREE.MeshStandardMaterial({ color: 0xd5dbe3, roughness: 0.9 })
        );
        floor.rotation.x = -Math.PI / 2;
        floor.position.y = -0.6;
        floor.receiveShadow = true;
        this.scene.add(floor);

        // ---------- Group lockers by location ----------
        // And calculate where each locker should be placed
        const groups = this.buildGroups(locations);

        // --Draw every locker box ----------
        for (const key in groups) {
            for (const locker of groups[key].lockers) {
                this.drawLocker(locker);
            }
        }

        for (const key in groups) {
            this.drawSignboard(groups[key]);
        }

        this.fitCamera(groups);

        this.setupControls();

        const animate = () => {
            requestAnimationFrame(animate);
            this.renderer.render(this.scene, this.camera);
        };
        animate();

        window.addEventListener("resize", () => {
            const w = container.clientWidth, h = container.clientHeight;
            if (w > 0 && h > 0) {
                this.camera.aspect = w / h;
                this.camera.updateProjectionMatrix();
                this.renderer.setSize(w, h);
            }
        });

    }


    buildGroups(locations) {
        const groups = {};

        // Put all lockers into their location groups
        for (const loc of locations) {
            const key = loc.location_id || loc.location;
            if (!groups[key]) groups[key] = { name: loc.location, lockers: [] };

            for (const locker of loc.lockers) {
                if (locker.w <= 0 || locker.h <= 0 || locker.d <= 0) continue; // bad size, skip
                groups[key].lockers.push(locker);
            }
        }

        for (const key in groups) {
            const group = groups[key];
            if (group.lockers.length === 0) continue;

            const anchorX = group.lockers[0].x;
            const anchorZ = group.lockers[0].z;
            const baseY = group.lockers[0].y || 0;
            let topY = baseY;

            for (let i = 0; i < group.lockers.length; i++) {
                const locker = group.lockers[i];
                const col = i % this.ROW_SIZE;         
                const row = Math.floor(i / this.ROW_SIZE); 

                locker.renderX = anchorX + col * (locker.w + 0.3);
                locker.renderZ = anchorZ;
                locker.renderY = baseY + row * (locker.h + 0.35);

                // Keep track of the highest point for signboard placement
                const top = locker.renderY + locker.h;
                if (top > topY) topY = top;
            }

            group.topOfStack = topY; 
        }

        return groups;
    }

    // Draws one locker box (body + door + handle + name label)
    drawLocker(locker) {
        const w = locker.w, h = locker.h, d = locker.d;
        const isAllocated = locker.status === "allocated";
        const color = isAllocated ? 0xdc3545 : 0x28a745; // Red if allocated, Green if available

        // The main box body
        const body = new THREE.Mesh(
            new THREE.BoxGeometry(w, h, d),
            new THREE.MeshStandardMaterial({ color, roughness: 0.5 })
        );
        body.position.set(locker.renderX, locker.renderY + h / 2, locker.renderZ);
        body.castShadow = true;
        body.receiveShadow = true;

        // Door (white panel on the front)
        const door = new THREE.Mesh(
            new THREE.BoxGeometry(w * 0.85, h * 0.85, 0.04),
            new THREE.MeshStandardMaterial({ color: 0xfcfcfc, roughness: 0.3 })
        );
        door.position.set(0, 0, d / 2 + 0.01);
        body.add(door);

        // Handle (small cylinder on the door)
        const handle = new THREE.Mesh(
            new THREE.CylinderGeometry(0.04, 0.04, 0.18, 8),
            new THREE.MeshStandardMaterial({ color: 0x444444, metalness: 0.9 })
        );
        handle.rotation.x = Math.PI / 2;
        handle.position.set(w * 0.3, -h * 0.2, d / 2 + 0.08);
        body.add(handle);

        // Locker name label on the door
        const labelTexture = this.createLabelTexture(locker.name, "#ffffff", "#222222", "#333333");
        const label = new THREE.Mesh(
            new THREE.PlaneGeometry(w * 0.7, h * 0.4),
            new THREE.MeshBasicMaterial({ map: labelTexture, side: THREE.DoubleSide })
        );
        label.position.set(0, h * 0.25, d / 2 + 0.03);
        body.add(label);

        this.scene.add(body);
    }

    // Draws the teal signboard with the location's name, above the group.
    drawSignboard(group) {
        if (group.lockers.length === 0) return;

        // Calculate the average X and Z of all lockers in this group
        let sumX = 0, sumZ = 0;
        for (const locker of group.lockers) {
            sumX += locker.renderX;
            sumZ += locker.renderZ;
        }
        const x = sumX / group.lockers.length;
        const z = sumZ / group.lockers.length;
        const y = group.topOfStack + 1.0; 

        // Pole 
        const pole = new THREE.Mesh(
            new THREE.CylinderGeometry(0.03, 0.05, y - 0.2, 6),
            new THREE.MeshStandardMaterial({ color: 0xaaaaaa, metalness: 0.3 })
        );
        pole.position.set(x, (y - 0.2) / 2, z);
        this.scene.add(pole);

        // Board 
        const boardDepth = 0.1;
        const board = new THREE.Mesh(
            new THREE.BoxGeometry(4.5, 0.9, boardDepth),
            new THREE.MeshStandardMaterial({ color: 0x017e84, roughness: 0.3 })
        );
        board.position.set(x, y, z);
        this.scene.add(board);

        // Text — placed  OUTSIDE the board front face so it's visible
        const textTexture = this.createLabelTexture(group.name, "#017e84", "#ffffff", "#01565c");
        const text = new THREE.Mesh(
            new THREE.PlaneGeometry(4.0, 0.6),
            new THREE.MeshBasicMaterial({ map: textTexture, transparent: true })
        );
        text.position.set(x, y, z + boardDepth / 2 + 0.01);
        this.scene.add(text);
    }

    // Positions the camera so every locker and every row is visible.
    fitCamera(groups) {
        let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity, tallest = 0;

        // Find the bounding box of all lockers
        for (const key in groups) {
            const group = groups[key];
            if (group.topOfStack > tallest) tallest = group.topOfStack;

            for (const locker of group.lockers) {
                if (locker.renderX < minX) minX = locker.renderX;
                if (locker.renderX > maxX) maxX = locker.renderX;
                if (locker.renderZ < minZ) minZ = locker.renderZ;
                if (locker.renderZ > maxZ) maxZ = locker.renderZ;
            }
        }

        // If no lockers, use default values
        if (!isFinite(minX)) { minX = -2; maxX = 2; minZ = -2; maxZ = 2; }

        const margin = 4;
        const centerX = (minX + maxX) / 2;
        const centerZ = (minZ + maxZ) / 2;
        const maxDim = Math.max(maxX - minX + margin * 2, maxZ - minZ + margin * 2, tallest * 1.5, 5);
        const dist = Math.max(maxDim * 1.5, 6) + 3;

        // Place the camera at an isometric angle
        this.target.set(centerX, 1.0, centerZ);
        this.camera.position.set(centerX + dist * 0.55, 1.0 + dist * 0.55, centerZ + dist * 0.75);
        this.camera.lookAt(this.target);
    }

    // Drag mouse to rotate the camera around the scene, scroll to zoom.
    setupControls() {
        const canvas = this.renderer.domElement;
        let dragging = false;
        let lastX = 0, lastY = 0;

        // When user presses mouse button, start dragging
        canvas.addEventListener("mousedown", (e) => {
            dragging = true;
            lastX = e.clientX;
            lastY = e.clientY;
        });

        // When user moves mouse, rotate the camera around the target
        window.addEventListener("mousemove", (e) => {
            if (!dragging) return;
            const dx = (e.clientX - lastX) * 0.005;
            const dy = (e.clientY - lastY) * 0.005;
            lastX = e.clientX;
            lastY = e.clientY;

            const radius = this.camera.position.distanceTo(this.target);
            const theta = Math.atan2(this.camera.position.x - this.target.x, this.camera.position.z - this.target.z) + dx;
            let phi = Math.acos((this.camera.position.y - this.target.y) / radius) + dy;
            phi = Math.max(0.1, Math.min(Math.PI - 0.1, phi));

            this.camera.position.x = this.target.x + radius * Math.sin(phi) * Math.sin(theta);
            this.camera.position.y = this.target.y + radius * Math.cos(phi);
            this.camera.position.z = this.target.z + radius * Math.sin(phi) * Math.cos(theta);
            this.camera.lookAt(this.target);
        });

        // When user releases mouse, stop dragging
        window.addEventListener("mouseup", () => { dragging = false; });

        // When user scrolls, zoom in/out
        canvas.addEventListener("wheel", (e) => {
            e.preventDefault();
            const radius = this.camera.position.distanceTo(this.target);
            const newRadius = Math.max(2, Math.min(80, radius + (e.deltaY > 0 ? 0.5 : -0.5)));
            const dir = this.camera.position.clone().sub(this.target).normalize();
            this.camera.position.copy(this.target).add(dir.multiplyScalar(newRadius));
            this.camera.lookAt(this.target);
        }, { passive: false });
    }
}

Locker3DView.template = "iPredict_locker_management.Locker3DView";
registry.category("actions").add("locker_3d_view", Locker3DView);