/** @odoo-module **/

import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import * as THREE from "@iPredict_locker_management/lib/three.module";
import { CSS2DRenderer, CSS2DObject } from "@iPredict_locker_management/lib/CSS2DRenderer";

export class Locker3DView extends Component {
    setup() {
        this.canvasRef = useRef("canvas");
        this.orm = useService("orm");

        this.state = useState({
            companies: [],
            selectedCompanyId: false,

            lockerLocations: [],
            selectedLockerLocationId: false,

            overloadCount: 0,
            almostFullCount: 0,
            freeSpaceCount: 0,
            noLoadCount: 0,

            selectedLocker: null,
        });

        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.labelRenderer = null;
        this.target = new THREE.Vector3(0, 1, 0);

        onMounted(async () => {
            await this.loadCompanies();
            await this.renderScene();
        });
    }

    closePopup() {
        this.state.selectedLocker = null;
    }

    async loadCompanies() {
        try {
            this.state.companies = await this.orm.searchRead("res.company", [], ["name"]);

            if (this.state.companies.length) {
                this.state.selectedCompanyId = this.state.companies[0].id;

                this.state.lockerLocations = await this.orm.call(
                    "locker.locker",
                    "get_locker_locations",
                    [this.state.selectedCompanyId]
                );

                if (this.state.lockerLocations.length) {
                    this.state.selectedLockerLocationId = this.state.lockerLocations[0].id;
                }
            }
        } catch (e) {
            console.error("ERROR loading companies:", e);
        }
    }

    async onCompanyChange(ev) {
        this.state.selectedCompanyId = Number(ev.target.value);
        this.closePopup();

        this.state.lockerLocations = await this.orm.call(
            "locker.locker",
            "get_locker_locations",
            [this.state.selectedCompanyId]
        );

        if (this.state.lockerLocations.length) {
            this.state.selectedLockerLocationId = this.state.lockerLocations[0].id;
        } else {
            this.state.selectedLockerLocationId = false;
        }

        await this.renderScene();
    }

    async onLockerLocationChange(ev) {
        this.state.selectedLockerLocationId = Number(ev.target.value);
        this.closePopup();
        await this.renderScene();
    }

    async renderScene() {
        this.state.selectedLocker = null;
        const container = this.canvasRef.el;
        if (!container) return;
        
        container.innerHTML = "";

        let locations = [];
        try {
            locations = await this.orm.call("locker.locker", "get_3d_data", [this.state.selectedCompanyId]);
            if (this.state.selectedLockerLocationId) {
                locations = locations.filter(
                    (loc) => loc.location_id === this.state.selectedLockerLocationId
                );
            }
        } catch (e) {
            container.innerHTML = `<div style="padding:50px;color:red;text-align:center;">Error: ${e.message}</div>`;
            return;
        }

        if (!locations || locations.length === 0) {
            container.innerHTML = `<div style="padding:50px;color:#666;text-align:center;">No lockers found.</div>`;
            return;
        }

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

        this.state.overloadCount = overload;
        this.state.almostFullCount = almostFull;
        this.state.freeSpaceCount = freeSpace;
        this.state.noLoadCount = noLoad;

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xf5f5f5);

        const width = container.clientWidth || 800;
        const height = container.clientHeight || 600;

        //Camera Perspective Setup
        this.camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 1000);

        // WebGL 3D Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setSize(width, height);
        this.renderer.shadowMap.enabled = true;
        this.renderer.domElement.style.position = "absolute";
        this.renderer.domElement.style.top = "0px";
        this.renderer.domElement.style.left = "0px";
        container.appendChild(this.renderer.domElement);

        // 🔹CSS 2D Label Renderer Setup
        this.labelRenderer = new CSS2DRenderer();
        this.labelRenderer.setSize(width, height);
        this.labelRenderer.domElement.style.position = "absolute";
        this.labelRenderer.domElement.style.top = "0px";
        this.labelRenderer.domElement.style.left = "0px";
        this.labelRenderer.domElement.style.pointerEvents = "none";
        container.appendChild(this.labelRenderer.domElement);

        // Lights
        this.scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.2));
        const mainLight = new THREE.DirectionalLight(0xffffff, 1.5);
        mainLight.position.set(30, 50, 40);
        mainLight.castShadow = true;
        this.scene.add(mainLight);

        // Floor Ground
        const floor = new THREE.Mesh(
            new THREE.PlaneGeometry(400, 400),
            new THREE.MeshStandardMaterial({ color: 0xe5e5e5, roughness: 0.9 })
        );
        floor.rotation.x = -Math.PI / 2;
        floor.position.y = 0;
        floor.receiveShadow = true;
        this.scene.add(floor);

        const groups = this.buildGroups(locations);

        for (const key in groups) {
            const group = groups[key];
            for (const locker of group.lockers) {
                this.drawLocker(locker);
            }
            this.drawSignboard(group);
            for (const profileId in group.profiles) {
                this.drawProfileSignboard(group.profiles[profileId]);
            }
        }

        // Fit Camera Properly with Zoom Distance Adjustment
        this.fitCamera(groups);
        this.setupControls();

        const animate = () => {
            requestAnimationFrame(animate);
            this.renderer.render(this.scene, this.camera);
            this.labelRenderer.render(this.scene, this.camera);
        };
        animate();

        window.addEventListener("resize", () => {
            const w = container.clientWidth, h = container.clientHeight;
            if (w > 0 && h > 0) {
                this.camera.aspect = w / h;
                this.camera.updateProjectionMatrix();
                this.renderer.setSize(w, h);
                this.labelRenderer.setSize(w, h);
            }
        });
    }

    buildGroups(locations) {
        const groups = {};
        const LOCATION_GAP = 80.0; 
        let locationIndex = 0;

        for (const loc of locations) {
            const locKey = loc.locker_location_id ?? loc.location_id ?? 0;
            const locName = loc.location || loc.location_name || "Ground Floor";

            if (!groups[locKey]) {
                groups[locKey] = {
                    id: locKey,
                    name: locName,
                    lockers: [],
                    profiles: {},
                    topOfStack: 0,
                    offsetX: locationIndex * LOCATION_GAP,
                };
                locationIndex++;
            }

            const profileMap = {};
            for (const locker of loc.lockers) {
                if (locker.w <= 0 || locker.h <= 0 || locker.d <= 0) continue;

                const profId = locker.profile_id || 0;
                if (!profileMap[profId]) {
                    profileMap[profId] = [];
                }
                profileMap[profId].push(locker);
            }

            let profileIndex = 0;
            const profileIds = Object.keys(profileMap);

            const roomWidth = 24.0;
            const roomDepth = 24.0;

            for (const profId of profileIds) {
                const profileLockers = profileMap[profId];
                const profName = profileLockers[0].profile || "General Profile";

                if (!groups[locKey].profiles[profId]) {
                    groups[locKey].profiles[profId] = {
                        id: profId,
                        name: profName,
                        lockers: [],
                        rotationY: 0,
                    };
                }

                let basePX = 0, basePZ = 0, rotY = 0;

                const wallType = profileIndex % 4;
                if (wallType === 0) {
                    basePX = 0; basePZ = -roomDepth / 2; rotY = 0; 
                } else if (wallType === 1) {
                    basePX = -roomWidth / 2; basePZ = 0; rotY = Math.PI / 2; 
                } else if (wallType === 2) {
                    basePX = roomWidth / 2; basePZ = 0; rotY = -Math.PI / 2; 
                } else {
                    basePX = 0; basePZ = roomDepth / 2; rotY = Math.PI; 
                }

                groups[locKey].profiles[profId].rotationY = rotY;

                const LOCKER_GAP = 3.8; 
                const startOffset = -((profileLockers.length - 1) * LOCKER_GAP) / 2;

                profileLockers.forEach((locker, idx) => {
                    let localX = 0, localZ = 0;

                    if (rotY === 0 || rotY === Math.PI) {
                        localX = startOffset + idx * LOCKER_GAP;
                    } else {
                        localZ = startOffset + idx * LOCKER_GAP;
                    }

                    locker.renderX = groups[locKey].offsetX + basePX + localX;
                    locker.renderY = 0;
                    locker.renderZ = basePZ + localZ;
                    locker.rotationY = rotY; 

                    groups[locKey].lockers.push(locker);
                    groups[locKey].profiles[profId].lockers.push(locker);

                    const top = locker.renderY + (locker.h || 3.0);
                    if (top > groups[locKey].topOfStack) {
                        groups[locKey].topOfStack = top;
                    }
                });

                profileIndex++;
            }
        }
        return groups;
    }

    drawLocker(locker) {
        // Standard Box size (Width, Height, Depth)
        const w = locker.w || 2.2;
        const h = locker.h || 3.2;
        const d = locker.d || 2.2;

        const isAllocated = locker.status === "allocated";
        const color = isAllocated ? 0xff4d4f : 0x52c41a;

        // 3D Locker Mesh
        const body = new THREE.Mesh(
            new THREE.BoxGeometry(w, h, d),
            new THREE.MeshStandardMaterial({ color, roughness: 0.3, metalness: 0.1 })
        );
        body.position.set(locker.renderX, locker.renderY + h / 2, locker.renderZ);
        
        if (locker.rotationY !== undefined) {
            body.rotation.y = locker.rotationY;
        }

        body.userData.lockerId = locker.id;
        body.castShadow = true;
        body.receiveShadow = true;

        // Door Panel Outline Accent
        const door = new THREE.Mesh(
            new THREE.PlaneGeometry(w * 0.85, h * 0.85),
            new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.2 })
        );
        door.position.set(0, 0, d / 2 + 0.02);
        body.add(door);

        // Handle Accent
        const handle = new THREE.Mesh(
            new THREE.CylinderGeometry(0.05, 0.05, 0.3, 8),
            new THREE.MeshStandardMaterial({ color: 0x222222, metalness: 0.8 })
        );
        handle.rotation.x = Math.PI / 2;
        handle.position.set(w * 0.3, 0, d / 2 + 0.08);
        body.add(handle);

        // 🔹 Uses your CSS class `.locker-label`
        const labelDiv = document.createElement("div");
        labelDiv.className = "locker-label";
        labelDiv.textContent = locker.name;

        const lockerLabel = new CSS2DObject(labelDiv);
        lockerLabel.position.set(0, h / 2 + 0.5, 0);
        body.add(lockerLabel);

        this.scene.add(body);
    }

    drawSignboard(group) {
        if (group.lockers.length === 0) return;

        let sumX = 0, sumZ = 0;
        for (const locker of group.lockers) {
            sumX += locker.renderX;
            sumZ += locker.renderZ;
        }
        const x = sumX / group.lockers.length;
        const z = sumZ / group.lockers.length;
        const y = group.topOfStack + 5.0; 

        //  Uses your CSS class `.location-label`
        const titleDiv = document.createElement("div");
        titleDiv.className = "location-label";
        titleDiv.textContent = group.name;

        const titleLabel = new CSS2DObject(titleDiv);
        titleLabel.position.set(x, y, z);
        this.scene.add(titleLabel);
    }

    drawProfileSignboard(profile) {
        if (!profile.lockers.length) return;

        let sumX = 0, sumZ = 0, maxH = 0;
        for (const locker of profile.lockers) {
            sumX += locker.renderX;
            sumZ += locker.renderZ;
            if ((locker.h || 3.2) > maxH) maxH = locker.h || 3.2;
        }

        const x = sumX / profile.lockers.length;
        const z = sumZ / profile.lockers.length;
        const y = maxH + 2.5;

        const profDiv = document.createElement("div");
        profDiv.textContent = profile.name;
        profDiv.style.cssText = `
            background: #1890ff;
            color: #ffffff;
            font-size: 11px;
            font-weight: bold;
            font-family: sans-serif;
            padding: 3px 8px;
            border-radius: 4px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.2);
            white-space: nowrap;
        `;

        const profileLabel = new CSS2DObject(profDiv);
        profileLabel.position.set(x, y, z);
        this.scene.add(profileLabel);
    }

    fitCamera(groups) {
        let minX = Infinity, maxX = -Infinity;
        let minZ = Infinity, maxZ = -Infinity;
        let maxHeight = 0;

        for (const key in groups) {
            const group = groups[key];
            for (const locker of group.lockers) {
                minX = Math.min(minX, locker.renderX);
                maxX = Math.max(maxX, locker.renderX);
                minZ = Math.min(minZ, locker.renderZ);
                maxZ = Math.max(maxZ, locker.renderZ);
                const h = locker.h || 3.2;
                if (h > maxHeight) maxHeight = h;
            }
        }

        if (!isFinite(minX)) {
            minX = -10; maxX = 10;
            minZ = -10; maxZ = 10;
        }

        const centerX = (minX + maxX) / 2;
        const centerZ = (minZ + maxZ) / 2;

        this.target.set(centerX, maxHeight * 0.5, centerZ);

        const sizeX = maxX - minX;
        const sizeZ = maxZ - minZ;
        const maxDim = Math.max(sizeX, sizeZ);

        const cameraDist = Math.max(maxDim * 0.75, 18);

        this.camera.position.set(
            centerX,
            maxHeight + cameraDist * 0.6,
            centerZ + cameraDist * 1.1
        );

        this.camera.lookAt(this.target);
    }

    setupControls() {
        const canvas = this.renderer.domElement;
        let dragging = false;
        let lastX = 0, lastY = 0;

        const raycaster = new THREE.Raycaster();
        const mouse = new THREE.Vector2();

        canvas.addEventListener("mousedown", (e) => {
            dragging = true;
            lastX = e.clientX;
            lastY = e.clientY;
        });

        window.addEventListener("mousemove", (e) => {
            if (!dragging) return;

            const dx = (e.clientX - lastX) * 0.005;
            const dy = (e.clientY - lastY) * 0.005;

            lastX = e.clientX;
            lastY = e.clientY;

            const radius = this.camera.position.distanceTo(this.target);
            const theta = Math.atan2(
                this.camera.position.x - this.target.x,
                this.camera.position.z - this.target.z
            ) + dx;

            let phi = Math.acos(
                (this.camera.position.y - this.target.y) / radius
            ) + dy;

            phi = Math.max(0.1, Math.min(Math.PI / 2 - 0.05, phi));

            this.camera.position.x = this.target.x + radius * Math.sin(phi) * Math.sin(theta);
            this.camera.position.y = this.target.y + radius * Math.cos(phi);
            this.camera.position.z = this.target.z + radius * Math.sin(phi) * Math.cos(theta);

            this.camera.lookAt(this.target);
        });

        window.addEventListener("mouseup", () => {
            dragging = false;
        });

        canvas.addEventListener("wheel", (e) => {
            e.preventDefault();
            const radius = this.camera.position.distanceTo(this.target);
            const newRadius = Math.max(8, Math.min(150, radius + (e.deltaY > 0 ? 2 : -2)));

            const dir = this.camera.position.clone().sub(this.target).normalize();
            this.camera.position.copy(this.target).add(dir.multiplyScalar(newRadius));
            this.camera.lookAt(this.target);
        }, { passive: false });

        canvas.addEventListener("click", async (event) => {
            const rect = canvas.getBoundingClientRect();
            mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
            mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

            raycaster.setFromCamera(mouse, this.camera);
            const intersects = raycaster.intersectObjects(this.scene.children, true);

            const hit = intersects.find(i => i.object.userData.lockerId);

            if (hit) {
                const details = await this.orm.call(
                    "locker.locker",
                    "get_locker_details",
                    [hit.object.userData.lockerId]
                );
                this.state.selectedLocker = details;
            }
        });
    }
}

Locker3DView.template = "iPredict_locker_management.Locker3DView";
registry.category("actions").add("locker_3d_view", Locker3DView);