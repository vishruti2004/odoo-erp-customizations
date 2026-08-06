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

            selectedLocker: null,
            profilesList: [],
        });

        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.labelRenderer = null;
        this.target = new THREE.Vector3(0, 1, 0);

        this.lockerMeshes = [];
        this.draggedObject = null;
        this.dragPlane = new THREE.Plane();
        this.planeNormal = new THREE.Vector3();
        this.planeIntersection = new THREE.Vector3();
        this.dragOffset = new THREE.Vector3();
        this.isDraggingLocker = false;

        this.dragStartPos = { x: 0, y: 0 };
        this.hasMoved = false;

        this.lockerSlots = [];
        this.slotOfLocker = new Map();
        this.lockerAtSlot = [];

        onMounted(async () => {
            await this.loadAllProfiles();
            await this.loadCompanies();
            await this.renderScene();
        });
    }

    async loadAllProfiles() {
        try {
            const profiles = await this.orm.searchRead(
                "locker.profile", 
                [], 
                ["id", "name", "color"]
            );
            this.state.profilesList = profiles.map(p => ({
                id: p.id,
                name: p.name,
                color: this.getProfileColorCss(p.color)
            }));
        } catch (e) {
            console.error("Error loading profiles:", e);
        }
    }

    getProfileColorHex(colorValue) {
        const ODOO_COLORS = {
            0: 0x8f8f8f,
            1: 0xF05365,
            2: 0xFABC2A,
            3: 0xECE133,
            4: 0x27AE60,
            5: 0x1ABC9C,
            6: 0x3498DB,
            7: 0x2980B9,
            8: 0x9B59B6,
            9: 0xE84393,
            10: 0x7F8C8D,
            11: 0x34495E,
        };

        if (typeof colorValue === "number" && ODOO_COLORS[colorValue] !== undefined) {
            return ODOO_COLORS[colorValue];
        }
        if (typeof colorValue === "string" && colorValue.startsWith("#")) {
            return parseInt(colorValue.replace("#", "0x"), 16);
        }
        return 0x2e7d32;
    }

    getProfileColorCss(colorValue) {
        const hexNum = this.getProfileColorHex(colorValue);
        return "#" + hexNum.toString(16).padStart(6, '0');
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
        this.lockerMeshes = [];

        this.lockerSlots = [];
        this.slotOfLocker = new Map();
        this.lockerAtSlot = [];

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
            container.innerHTML = `<div style="padding:50px;color:#666;text-align:center;font-size:16px;margin-top:100px;">No lockers found.</div>`;
            return;
        }

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xd0d0d0);

        const width = container.clientWidth || 800;
        const height = container.clientHeight || 600;

        this.camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 1000);

        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setSize(width, height);
        this.renderer.shadowMap.enabled = true;
        this.renderer.domElement.style.position = "absolute";
        this.renderer.domElement.style.top = "0px";
        this.renderer.domElement.style.left = "0px";
        container.appendChild(this.renderer.domElement);

        this.labelRenderer = new CSS2DRenderer();
        this.labelRenderer.setSize(width, height);
        this.labelRenderer.domElement.style.position = "absolute";
        this.labelRenderer.domElement.style.top = "0px";
        this.labelRenderer.domElement.style.left = "0px";
        this.labelRenderer.domElement.style.pointerEvents = "none";
        container.appendChild(this.labelRenderer.domElement);

        this.scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.2));
        const mainLight = new THREE.DirectionalLight(0xffffff, 1.5);
        mainLight.position.set(30, 50, 40);
        mainLight.castShadow = true;
        this.scene.add(mainLight);

        const floor = new THREE.Mesh(
            new THREE.PlaneGeometry(400, 400),
            new THREE.MeshStandardMaterial({ color: 0xb0b0b0, roughness: 0.9 })
        );
        floor.rotation.x = -Math.PI / 2;
        floor.position.y = 0;
        floor.receiveShadow = true;
        this.scene.add(floor);

        const groups = this.buildGroups(locations);
        this.buildLockerSlots(groups);

        for (const key in groups) {
            const group = groups[key];
            for (const locker of group.lockers) {
                this.drawLocker(locker);
            }
            this.drawSignboard(group);
        }

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
            const locType = loc.location_type || loc.type || "Standard";

            if (!groups[locKey]) {
                groups[locKey] = {
                    id: locKey,
                    name: locName,
                    type: locType,
                    lockers: [],
                    profiles: {},
                    topOfStack: 0,
                    offsetX: locationIndex * LOCATION_GAP,
                };
                locationIndex++;
            }

            for (const locker of loc.lockers) {
                if (locker.w <= 0 || locker.h <= 0 || locker.d <= 0) continue;

                locker.location_type = locType;
                locker.renderX = groups[locKey].offsetX + (locker.pos_x || 0);
                locker.renderY = locker.pos_y || 0;
                locker.renderZ = locker.pos_z || 0;
                locker.rotationY = 0;

                groups[locKey].lockers.push(locker);

                const top = locker.renderY + (locker.h || 3.0);
                if (top > groups[locKey].topOfStack) {
                    groups[locKey].topOfStack = top;
                }
            }
        }
        return groups;
    }

    buildLockerSlots(groups) {
        let slotIndex = 0;
        for (const key in groups) {
            for (const locker of groups[key].lockers) {
                const w = locker.w || 2.2;
                const h = locker.h || 3.2;
                const d = locker.d || 2.2;

                this.lockerSlots.push({
                    x: locker.renderX + w / 2,
                    y: locker.renderY + h / 2,
                    z: locker.renderZ + d / 2,
                    w, h, d,
                });
                this.slotOfLocker.set(locker.id, slotIndex);
                this.lockerAtSlot.push(locker.id);
                slotIndex++;
            }
        }
    }

    drawLocker(locker) {
        const w = locker.w || 2.2;
        const h = locker.h || 3.2;
        const d = locker.d || 2.2;

        const profileColor = this.getProfileColorHex(locker.profile_color);
        const isAllocated = locker.status === "allocated";
        const borderColor = isAllocated ? 0xff0000 : 0x00ff00;

        const boxGeometry = new THREE.BoxGeometry(w, h, d);
        const body = new THREE.Mesh(
            boxGeometry,
            new THREE.MeshStandardMaterial({
                color: profileColor,
                roughness: 0.3,
                metalness: 0.1,
                polygonOffset: true,
                polygonOffsetFactor: 1,
                polygonOffsetUnits: 1,
            })
        );

        body.position.set(
            locker.renderX + w / 2,
            locker.renderY + h / 2,
            locker.renderZ + d / 2
        );

        if (locker.rotationY !== undefined) {
            body.rotation.y = locker.rotationY;
        }

        const edgesGeometry = new THREE.EdgesGeometry(boxGeometry);
        const borderMaterial = new THREE.LineBasicMaterial({
            color: borderColor,
            linewidth: 3,
        });
        const wireframeBorder = new THREE.LineSegments(edgesGeometry, borderMaterial);
        body.add(wireframeBorder);

        body.userData.lockerData = locker;
        body.userData.lockerId = locker.id;

        body.castShadow = true;
        body.receiveShadow = true;

        const door = new THREE.Mesh(
            new THREE.PlaneGeometry(w * 0.85, h * 0.85),
            new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.2 })
        );
        door.position.set(0, 0, d / 2 + 0.02);
        body.add(door);

        const handle = new THREE.Mesh(
            new THREE.CylinderGeometry(0.05, 0.05, 0.3, 8),
            new THREE.MeshStandardMaterial({ color: 0x222222, metalness: 0.8 })
        );
        handle.rotation.x = Math.PI / 2;
        handle.position.set(w * 0.3, 0, d / 2 + 0.08);
        body.add(handle);

        this.scene.add(body);
        this.lockerMeshes.push(body);
    }

    drawSignboard(group) {
        if (group.lockers.length === 0) return;

        let sumX = 0, sumZ = 0;
        for (const locker of group.lockers) {
            sumX += locker.renderX + (locker.w || 2.2) / 2;
            sumZ += locker.renderZ + (locker.d || 2.2) / 2;
        }
        const x = sumX / group.lockers.length;
        const z = sumZ / group.lockers.length;
        const y = group.topOfStack + 4.0;

        const titleDiv = document.createElement("div");
        titleDiv.className = "location-label";
        titleDiv.textContent = group.name;

        const titleLabel = new CSS2DObject(titleDiv);
        titleLabel.position.set(x, y, z);
        this.scene.add(titleLabel);
    }

    fitCamera(groups) {
        let minX = Infinity, maxX = -Infinity;
        let minZ = Infinity, maxZ = -Infinity;
        let maxHeight = 0;

        for (const key in groups) {
            const group = groups[key];
            for (const locker of group.lockers) {
                const w = locker.w || 2.2;
                const d = locker.d || 2.2;
                minX = Math.min(minX, locker.renderX);
                maxX = Math.max(maxX, locker.renderX + w);
                minZ = Math.min(minZ, locker.renderZ);
                maxZ = Math.max(maxZ, locker.renderZ + d);
                const h = locker.renderY + (locker.h || 3.2);
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

        const cameraDist = Math.max(maxDim * 1.2, 18);

        this.camera.position.set(
            centerX,
            maxHeight + cameraDist * 0.6,
            centerZ + cameraDist * 1.1
        );

        this.camera.lookAt(this.target);
    }

    async onDrop(draggedLockerMesh) {
        const draggedLockerId = draggedLockerMesh.userData.lockerId;
        const initialPos = draggedLockerMesh.userData.initialPos;

        const startSlotIndex = this.slotOfLocker.get(draggedLockerId);
        const startSlot = this.lockerSlots[startSlotIndex];

        if (startSlot === undefined) {
            draggedLockerMesh.position.copy(initialPos);
            return;
        }

        const dropX = draggedLockerMesh.position.x;
        const dropZ = draggedLockerMesh.position.z;

        let targetSlotIndex = -1;
        let minDistance = Infinity;
        const snapRadius = Math.max(startSlot.w, startSlot.d) * 1.5;

        for (let i = 0; i < this.lockerSlots.length; i++) {
            if (i === startSlotIndex) continue;
            const slot = this.lockerSlots[i];

            if (Math.abs(slot.z - startSlot.z) > startSlot.d * 0.6) continue;

            const distance = Math.hypot(slot.x - dropX, slot.z - dropZ);
            if (distance < snapRadius && distance < minDistance) {
                minDistance = distance;
                targetSlotIndex = i;
            }
        }

        try {
            if (targetSlotIndex !== -1) {
                const targetLockerId = this.lockerAtSlot[targetSlotIndex];
                const targetSlot = this.lockerSlots[targetSlotIndex];
                const targetMesh = this.lockerMeshes.find(
                    (m) => m.userData.lockerId === targetLockerId
                );

                draggedLockerMesh.position.set(targetSlot.x, targetSlot.y, targetSlot.z);
                if (targetMesh) {
                    targetMesh.position.set(startSlot.x, startSlot.y, startSlot.z);
                }

                this.lockerAtSlot[startSlotIndex] = targetLockerId;
                this.lockerAtSlot[targetSlotIndex] = draggedLockerId;
                this.slotOfLocker.set(draggedLockerId, targetSlotIndex);
                this.slotOfLocker.set(targetLockerId, startSlotIndex);

                await this.orm.call("locker.locker", "update_locker_position", [
                    draggedLockerId, targetSlot.x, targetSlot.y, targetSlot.z
                ]);
                await this.orm.call("locker.locker", "update_locker_position", [
                    targetLockerId, startSlot.x, startSlot.y, startSlot.z
                ]);
            } else {
                draggedLockerMesh.position.copy(initialPos);
            }
        } catch (err) {
            console.error("Error in onDrop:", err);
            draggedLockerMesh.position.copy(initialPos);
        }
    }

    setupControls() {
        const canvas = this.renderer.domElement;
        let isOrbiting = false;
        let lastX = 0, lastY = 0;

        const raycaster = new THREE.Raycaster();
        const mouse = new THREE.Vector2();

        const getMousePos = (e) => {
            const rect = canvas.getBoundingClientRect();
            mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
        };

        canvas.addEventListener("mousedown", (e) => {
            getMousePos(e);
            lastX = e.clientX;
            lastY = e.clientY;

            this.dragStartPos = { x: e.clientX, y: e.clientY };
            this.hasMoved = false;

            raycaster.setFromCamera(mouse, this.camera);
            const intersects = raycaster.intersectObjects(this.lockerMeshes, true);

            if (intersects.length > 0) {
                let hitObject = intersects[0].object;

                while (hitObject.parent && hitObject.parent.type !== "Scene") {
                    if (hitObject.userData && hitObject.userData.lockerId) {
                        break;
                    }
                    hitObject = hitObject.parent;
                }

                if (hitObject && hitObject.userData.lockerId) {
                    this.isDraggingLocker = true;
                    this.draggedObject = hitObject;

                    hitObject.userData.initialPos = hitObject.position.clone();

                    this.planeNormal.set(0, 1, 0);
                    this.dragPlane.setFromNormalAndCoplanarPoint(this.planeNormal, this.draggedObject.position);

                    if (raycaster.ray.intersectPlane(this.dragPlane, this.planeIntersection)) {
                        this.dragOffset.copy(this.draggedObject.position).sub(this.planeIntersection);
                    }

                    if (this.draggedObject.material) {
                        this.draggedObject.material.opacity = 0.6;
                        this.draggedObject.material.transparent = true;
                    }
                }
            } else {
                isOrbiting = true;
            }
        });

        window.addEventListener("mousemove", (e) => {
            const distMoved = Math.hypot(e.clientX - this.dragStartPos.x, e.clientY - this.dragStartPos.y);
            if (distMoved > 5) {
                this.hasMoved = true;
            }

            if (this.isDraggingLocker && this.draggedObject) {
                getMousePos(e);
                raycaster.setFromCamera(mouse, this.camera);

                if (raycaster.ray.intersectPlane(this.dragPlane, this.planeIntersection)) {
                    const newPos = this.planeIntersection.clone().add(this.dragOffset);
                    this.draggedObject.position.x = newPos.x;
                    this.draggedObject.position.z = newPos.z;
                }
                return;
            }

            if (isOrbiting) {
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
            }
        });

        window.addEventListener("mouseup", async () => {
            if (this.isDraggingLocker && this.draggedObject) {
                if (this.draggedObject.material) {
                    this.draggedObject.material.opacity = 1.0;
                    this.draggedObject.material.transparent = false;
                }

                if (this.hasMoved) {
                    await this.onDrop(this.draggedObject);
                } else {
                    this.state.selectedLocker = this.draggedObject.userData.lockerData;
                    this.draggedObject.position.copy(this.draggedObject.userData.initialPos);
                }
            }

            this.draggedObject = null;
            this.isDraggingLocker = false;
            isOrbiting = false;
        });

        canvas.addEventListener("wheel", (e) => {
            e.preventDefault();
            const radius = this.camera.position.distanceTo(this.target);
            const newRadius = Math.max(8, Math.min(150, radius + (e.deltaY > 0 ? 2 : -2)));

            const dir = this.camera.position.clone().sub(this.target).normalize();
            this.camera.position.copy(this.target).add(dir.multiplyScalar(newRadius));
            this.camera.lookAt(this.target);
        }, { passive: false });
    }
}

Locker3DView.template = "iPredict_locker_management.Locker3DView";
registry.category("actions").add("locker_3d_view", Locker3DView);