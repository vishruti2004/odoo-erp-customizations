/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";  // 🔥 Direct import
import * as THREE from "@iPredict_locker_management/lib/three.module";
import { CSS2DRenderer, CSS2DObject } from "@iPredict_locker_management/lib/CSS2DRenderer";

export class Locker3DView extends Component {
    setup() {
        this.canvasRef = useRef("canvas");
        this.orm = useService("orm");

        const actionContext = this.props.action?.context || {};
        const defaultLocationId = actionContext.default_location_id || false;
        const defaultCompanyId = actionContext.default_company_id || false;

        this.state = useState({
            companies: [],
            selectedCompanyId: defaultCompanyId || false,
            lockerLocations: [],
            selectedLockerLocationId: defaultLocationId || false,
            selectedLocker: null,
            profilesList: [],
            statusColors: {
                available: "#28A745",
                allocated: "#DC3545",
            },
            activeStatusFilter: 'all',
            activeProfileFilter: 'all',
            isEditMode: false,
            hasLockers: false,
            searchQuery: '',
            isAdmin: false,
        });

        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.labelRenderer = null;
        this.animationFrameId = null;
        this.target = new THREE.Vector3(0, 0, 0);

        this.lockerMeshes = [];
        this.draggedObject = null;
        this.dragPlane = new THREE.Plane();
        this.planeNormal = new THREE.Vector3(0, 1, 0);
        this.planeIntersection = new THREE.Vector3();
        this.dragOffset = new THREE.Vector3();
        this.isDraggingLocker = false;
        this.isOrbiting = false;

        this.dragStartPos = { x: 0, y: 0 };
        this.hasMoved = false;

        this.groupsCache = null;

        this.boundOnMouseMove = this.onMouseMove.bind(this);
        this.boundOnMouseUp = this.onMouseUp.bind(this);
        this.boundOnResize = this.onResize.bind(this);
        this.boundOnWheel = this.onWheel.bind(this);

        onMounted(async () => {
            // 🔥 Direct user object — no RPC, no undefined
            this.state.isAdmin = user.isAdmin || false;
            console.log("[Locker3DView] isAdmin (from user import):", this.state.isAdmin);

            await this.loadAllProfiles();
            await this.loadCompanies();
            await this.renderScene();
        });

        onWillUnmount(() => {
            if (this.animationFrameId) {
                cancelAnimationFrame(this.animationFrameId);
            }
            window.removeEventListener("mousemove", this.boundOnMouseMove);
            window.removeEventListener("mouseup", this.boundOnMouseUp);
            window.removeEventListener("resize", this.boundOnResize);
        });
    }

    // ========================== SEARCH ==========================
    clearSearch() {
        this.state.searchQuery = '';
        this.apply3DFilters();
    }

    focusOnLocker(mesh) {
        if (!mesh) return;
        const pos = mesh.position.clone();
        this.target.copy(pos);
        const dist = Math.max(15, this.lockerMeshes.length * 0.8);
        this.camera.position.set(pos.x + dist * 0.7, pos.y + dist * 0.5, pos.z + dist);
        this.camera.lookAt(this.target);
    }

    // ========================== EDIT MODE ==========================
    toggleEditMode() {
        this.state.isEditMode = !this.state.isEditMode;
        if (this.dragControls) {
            this.dragControls.enabled = this.state.isEditMode;
            if (!this.state.isEditMode) {
                this.lockerMeshes.forEach(mesh => this.setObjectOpacity(mesh, 1.0));
                this.draggedObject = null;
                this.isDraggingLocker = false;
            }
        }
    }

    setObjectOpacity(object, opacity) {
        object.traverse((child) => {
            if (child.isMesh && child.material) {
                child.material.transparent = opacity < 1.0;
                child.material.opacity = opacity;
            }
        });
    }

    getCanvasMousePos(e) {
        if (!this.renderer || !this.renderer.domElement) return { x: 0, y: 0 };
        const canvas = this.renderer.domElement;
        const rect = canvas.getBoundingClientRect();
        return {
            x: ((e.clientX - rect.left) / rect.width) * 2 - 1,
            y: -((e.clientY - rect.top) / rect.height) * 2 + 1
        };
    }

    toggleStatusFilter(status) {
        if (this.state.activeStatusFilter === status) {
            this.state.activeStatusFilter = 'all';
        } else {
            this.state.activeStatusFilter = status;
        }
        this.apply3DFilters();
    }

    toggleProfileFilter(profileId) {
        if (this.state.activeProfileFilter === profileId) {
            this.state.activeProfileFilter = 'all';
        } else {
            this.state.activeProfileFilter = profileId;
        }
        this.apply3DFilters();
    }

    apply3DFilters() {
        const { activeStatusFilter, activeProfileFilter, searchQuery } = this.state;
        let foundMesh = null;

        this.lockerMeshes.forEach((mesh) => {
            const locker = mesh.userData.lockerData;

            const matchesStatus =
                activeStatusFilter === 'all' ||
                (activeStatusFilter === 'available' && locker.status !== 'allocated') ||
                (activeStatusFilter === 'allocated' && locker.status === 'allocated');

            const matchesProfile =
                activeProfileFilter === 'all' ||
                locker.profile_id === activeProfileFilter ||
                locker.profile_id?.[0] === activeProfileFilter ||
                locker.profile === activeProfileFilter;

            let matchesSearch = true;
            if (searchQuery.trim() !== '') {
                matchesSearch = locker.name.toLowerCase().includes(searchQuery.toLowerCase().trim());
                if (matchesSearch) foundMesh = mesh;
            }

            mesh.visible = matchesStatus && matchesProfile && matchesSearch;
        });

        if (searchQuery.trim() !== '' && foundMesh) {
            this.focusOnLocker(foundMesh);
        } else if (searchQuery.trim() === '' && this.groupsCache) {
            this.fitCamera(this.groupsCache);
        }
    }

    async loadAllProfiles() {
        try {
            const profiles = await this.orm.searchRead("locker.profile", [], ["id", "name", "color"]);
            this.state.profilesList = profiles.map(p => ({
                id: p.id,
                name: p.name,
                color: this.getProfileColorCss(p.color)
            }));
        } catch (e) {
            console.error("[Locker3DView] Error loading profiles:", e);
        }
    }

    getProfileColorHex(colorValue) {
        const ODOO_COLORS = {
            0: 0x8f8f8f, 1: 0xF05365, 2: 0xFABC2A, 3: 0xECE133,
            4: 0x27AE60, 5: 0x1ABC9C, 6: 0x3498DB, 7: 0x2980B9,
            8: 0x9B59B6, 9: 0xE84393, 10: 0x7F8C8D, 11: 0x34495E,
        };
        if (typeof colorValue === "number" && ODOO_COLORS[colorValue] !== undefined) return ODOO_COLORS[colorValue];
        if (typeof colorValue === "string" && colorValue.startsWith("#")) return parseInt(colorValue.replace("#", "0x"), 16);
        return 0x8f8f8f;
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
                if (!this.state.selectedCompanyId) {
                    this.state.selectedCompanyId = this.state.companies[0].id;
                }

                this.state.lockerLocations = await this.orm.call("locker.locker", "get_locker_locations", [this.state.selectedCompanyId]);

                if (this.state.selectedLockerLocationId) {
                    const exists = this.state.lockerLocations.some(loc => loc.id === this.state.selectedLockerLocationId);
                    if (!exists) {
                        this.state.selectedLockerLocationId = this.state.lockerLocations.length ? this.state.lockerLocations[0].id : false;
                    }
                } else {
                    this.state.selectedLockerLocationId = this.state.lockerLocations.length ? this.state.lockerLocations[0].id : false;
                }
            }
        } catch (e) {
            console.error("[Locker3DView] ERROR loading companies:", e);
        }
    }

    async onCompanyChange(ev) {
        if (!this.state.isAdmin) return;
        this.state.selectedCompanyId = Number(ev.target.value);
        this.state.activeStatusFilter = 'all';
        this.state.activeProfileFilter = 'all';
        this.state.searchQuery = '';
        this.closePopup();

        this.state.lockerLocations = await this.orm.call("locker.locker", "get_locker_locations", [this.state.selectedCompanyId]);
        this.state.selectedLockerLocationId = this.state.lockerLocations.length ? this.state.lockerLocations[0].id : false;
        await this.renderScene();
    }

    async onLockerLocationChange(ev) {
        if (!this.state.isAdmin) return;
        this.state.selectedLockerLocationId = Number(ev.target.value);
        this.state.activeStatusFilter = 'all';
        this.state.activeProfileFilter = 'all';
        this.state.searchQuery = '';
        this.closePopup();
        await this.renderScene();
    }

    // ========================== RENDER ==========================
    async renderScene() {
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }

        this.state.selectedLocker = null;
        this.lockerMeshes = [];

        const container = this.canvasRef.el;
        if (!container) return;

        container.innerHTML = "";

        let locations = [];
        try {
            const data = await this.orm.call("locker.locker", "get_3d_data", [this.state.selectedCompanyId]);

            if (data && typeof data === "object" && !Array.isArray(data)) {
                locations = data.locations || [];
                if (data.status_colors) {
                    this.state.statusColors.available = data.status_colors.available || "#28A745";
                    this.state.statusColors.allocated = data.status_colors.allocated || "#DC3545";
                }
            } else {
                locations = data || [];
            }

            if (this.state.selectedLockerLocationId) {
                locations = locations.filter((loc) => loc.location_id === this.state.selectedLockerLocationId);
            }
        } catch (e) {
            container.innerHTML = `<div style="padding:50px;color:red;text-align:center;">Error: ${e.message}</div>`;
            return;
        }

        if (!locations || locations.length === 0) {
            this.state.hasLockers = false;
            container.innerHTML = `<div style="padding:50px;color:#666;text-align:center;font-size:16px;margin-top:100px;">No lockers found.</div>`;
            return;
        }

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xd0d0d0);

        const width = container.clientWidth || 800;
        const height = container.clientHeight || 600;

        this.camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 2000);

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

        const groups = this.buildGroups(locations);
        this.groupsCache = groups;

        for (const key in groups) {
            const group = groups[key];
            for (const locker of group.lockers) {
                this.drawLocker(locker);
            }
            this.drawSignboard(group);
        }

        this.state.hasLockers = this.lockerMeshes.length > 0;

        this.fitCamera(groups);
        this.setupControls();

        const animate = () => {
            this.animationFrameId = requestAnimationFrame(animate);
            this.renderer.render(this.scene, this.camera);
            this.labelRenderer.render(this.scene, this.camera);
        };
        animate();

        window.removeEventListener("resize", this.boundOnResize);
        window.addEventListener("resize", this.boundOnResize);

        this.apply3DFilters();
    }

    onResize() {
        const container = this.canvasRef.el;
        if (!container || !this.camera) return;
        const w = container.clientWidth, h = container.clientHeight;
        if (w > 0 && h > 0) {
            this.camera.aspect = w / h;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(w, h);
            this.labelRenderer.setSize(w, h);
        }
    }

    buildGroups(locations) {
        const groups = {};

        for (const loc of locations) {
            const locKey = loc.locker_location_id ?? loc.location_id ?? 0;
            const locName = loc.location || loc.location_name || "Locker Area";
            const locType = loc.location_type || loc.type || "Standard";

            if (!groups[locKey]) {
                groups[locKey] = {
                    id: locKey,
                    name: locName,
                    type: locType,
                    lockers: [],
                    profiles: {},
                    topOfStack: 0,
                };
            }

            for (const locker of loc.lockers) {
                if (!locker.w || !locker.h || !locker.d) continue;

                locker.location_type = locType;

                locker.renderX = parseFloat(locker.pos_x) || 0;
                locker.renderY = parseFloat(locker.pos_y) || 0;
                locker.renderZ = parseFloat(locker.pos_z) || 0;

                groups[locKey].lockers.push(locker);

                const top = locker.renderY + locker.h;
                if (top > groups[locKey].topOfStack) {
                    groups[locKey].topOfStack = top;
                }
            }
        }
        return groups;
    }

    drawLocker(locker) {
        const w = parseFloat(locker.w);
        const h = parseFloat(locker.h);
        const d = parseFloat(locker.d);

        const isAllocated = locker.status === "allocated";
        const statusHexStr = isAllocated
            ? this.state.statusColors.allocated
            : this.state.statusColors.available;
        const bodyColorHex = this.getProfileColorHex(statusHexStr);

        const boxGeometry = new THREE.BoxGeometry(w, h, d);
        const body = new THREE.Mesh(
            boxGeometry,
            new THREE.MeshStandardMaterial({
                color: bodyColorHex,
                roughness: 0.4,
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

        const edgesGeometry = new THREE.EdgesGeometry(boxGeometry);
        const borderMaterial = new THREE.LineBasicMaterial({
            color: bodyColorHex,
            linewidth: 2
        });
        body.add(new THREE.LineSegments(edgesGeometry, borderMaterial));

        body.userData.lockerData = locker;
        body.userData.lockerId = locker.id;
        body.castShadow = true;
        body.receiveShadow = true;

        const doorColorHex = this.getProfileColorHex(locker.profile_color);

        const door = new THREE.Mesh(
            new THREE.PlaneGeometry(w * 0.88, h * 0.88),
            new THREE.MeshStandardMaterial({
                color: doorColorHex,
                roughness: 0.3
            })
        );
        door.position.set(0, 0, d / 2 + 0.01);
        body.add(door);

        const handle = new THREE.Mesh(
            new THREE.CylinderGeometry(w * 0.03, w * 0.03, h * 0.1, 8),
            new THREE.MeshStandardMaterial({ color: 0x222222, metalness: 0.8 })
        );
        handle.rotation.x = Math.PI / 2;
        handle.position.set(w * 0.35, 0, d / 2 + 0.03);
        body.add(handle);

        this.scene.add(body);
        this.lockerMeshes.push(body);
    }

    drawSignboard(group) {
        if (group.lockers.length === 0) return;

        let sumX = 0, sumZ = 0;
        for (const locker of group.lockers) {
            sumX += locker.renderX + locker.w / 2;
            sumZ += locker.renderZ + locker.d / 2;
        }
        const x = sumX / group.lockers.length;
        const z = sumZ / group.lockers.length;
        const y = group.topOfStack + (group.topOfStack * 0.15 || 1.0);

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
                const w = parseFloat(locker.w);
                const d = parseFloat(locker.d);
                minX = Math.min(minX, locker.renderX);
                maxX = Math.max(maxX, locker.renderX + w);
                minZ = Math.min(minZ, locker.renderZ);
                maxZ = Math.max(maxZ, locker.renderZ + d);
                const h = locker.renderY + parseFloat(locker.h);
                if (h > maxHeight) maxHeight = h;
            }
        }

        if (!isFinite(minX)) {
            minX = 0; maxX = 10;
            minZ = 0; maxZ = 10;
        }

        const centerX = (minX + maxX) / 2;
        const centerZ = (minZ + maxZ) / 2;

        this.target.set(centerX, maxHeight * 0.5, centerZ);

        const sizeX = maxX - minX;
        const sizeZ = maxZ - minZ;
        const cameraDist = Math.max(Math.max(sizeX, sizeZ) * 1.2, 10);

        this.camera.position.set(
            centerX,
            maxHeight + cameraDist * 0.6,
            centerZ + cameraDist * 1.1
        );
        this.camera.lookAt(this.target);
    }

    // ========================== DRAG & DROP ==========================
    async onDrop(draggedLockerMesh) {
        const draggedLockerId = draggedLockerMesh.userData.lockerId;
        const draggedData = draggedLockerMesh.userData.lockerData;
        const initialPos = draggedLockerMesh.userData.initialPos;

        const w = parseFloat(draggedData.w);
        const h = parseFloat(draggedData.h);
        const d = parseFloat(draggedData.d);

        const dropX = draggedLockerMesh.position.x;
        const dropY = draggedLockerMesh.position.y; 
        const dropZ = draggedLockerMesh.position.z;

        let targetMesh = null;
        let minDistance = Infinity;

        for (const mesh of this.lockerMeshes) {
            if (mesh === draggedLockerMesh || !mesh.visible) continue;

            const otherData = mesh.userData.lockerData;
            const ow = parseFloat(otherData.w);
            const od = parseFloat(otherData.d);

            if (Math.abs(mesh.position.y - dropY) > h * 0.5) continue;

            const swapRadius = (Math.max(w, ow) + Math.max(d, od)) / 2 * 0.9;
            const distance = Math.hypot(mesh.position.x - dropX, mesh.position.z - dropZ);

            if (distance < swapRadius && distance < minDistance) {
                minDistance = distance;
                targetMesh = mesh;
            }
        }

        try {
            if (targetMesh) {
                const targetData = targetMesh.userData.lockerData;
                const tw = parseFloat(targetData.w);
                const th = parseFloat(targetData.h);
                const td = parseFloat(targetData.d);

                const targetPos = targetMesh.position.clone();

                draggedLockerMesh.position.set(targetPos.x, initialPos.y, targetPos.z);
                draggedLockerMesh.userData.initialPos = draggedLockerMesh.position.clone();

                targetMesh.position.copy(initialPos);
                targetMesh.userData.initialPos = targetMesh.position.clone();

                const draggedPosX = targetPos.x - w / 2;
                const draggedPosY = initialPos.y - h / 2;
                const draggedPosZ = targetPos.z - d / 2;

                const targetPosX = initialPos.x - tw / 2;
                const targetPosY = initialPos.y - th / 2;
                const targetPosZ = initialPos.z - td / 2;

                draggedData.pos_x = draggedPosX;
                draggedData.pos_y = draggedPosY;
                draggedData.pos_z = draggedPosZ;

                targetData.pos_x = targetPosX;
                targetData.pos_y = targetPosY;
                targetData.pos_z = targetPosZ;

                await Promise.all([
                    this.orm.call("locker.locker", "update_locker_position", [
                        draggedLockerId, draggedPosX, draggedPosY, draggedPosZ
                    ]),
                    this.orm.call("locker.locker", "update_locker_position", [
                        targetMesh.userData.lockerId, targetPosX, targetPosY, targetPosZ
                    ]),
                ]);

            } else {
                const posX = dropX - w / 2;
                const posY = dropY - h / 2;
                const posZ = dropZ - d / 2;

                draggedData.pos_x = posX;
                draggedData.pos_y = posY;
                draggedData.pos_z = posZ;

                draggedLockerMesh.userData.initialPos = draggedLockerMesh.position.clone();

                await this.orm.call("locker.locker", "update_locker_position", [
                    draggedLockerId, posX, posY, posZ
                ]);
            }
        } catch (err) {
            console.error("[Locker3DView] Error updating positions:", err);
            draggedLockerMesh.position.copy(initialPos);
        }
    }

    // ========================== CONTROLS ==========================
    setupControls() {
        const canvas = this.renderer.domElement;
        this.isOrbiting = false;
        this.lastX = 0;
        this.lastY = 0;

        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();

        canvas.addEventListener("mousedown", (e) => {
            if (e.button !== 0) return;

            const pos = this.getCanvasMousePos(e);
            this.mouse.x = pos.x;
            this.mouse.y = pos.y;

            this.lastX = e.clientX;
            this.lastY = e.clientY;
            this.dragStartPos = { x: e.clientX, y: e.clientY };
            this.hasMoved = false;

            this.raycaster.setFromCamera(this.mouse, this.camera);

            const visibleMeshes = this.lockerMeshes.filter(m => m.visible);
            const intersects = this.raycaster.intersectObjects(visibleMeshes, true);

            if (intersects.length > 0) {
                let hitObject = intersects[0].object;

                while (hitObject && (!hitObject.userData || !hitObject.userData.lockerId)) {
                    hitObject = hitObject.parent;
                }

                if (hitObject && hitObject.userData && hitObject.userData.lockerId) {
                    if (!this.state.isEditMode) {
                        this.isDraggingLocker = false;
                        this.isOrbiting = false;
                        this.draggedObject = hitObject;
                        hitObject.userData.initialPos = hitObject.position.clone();
                        return;
                    }

                    this.isDraggingLocker = true;
                    this.isOrbiting = false;
                    this.draggedObject = hitObject;
                    hitObject.userData.initialPos = hitObject.position.clone();

                    this.planeNormal.set(0, 1, 0);
                    this.dragPlane.setFromNormalAndCoplanarPoint(this.planeNormal, this.draggedObject.position);

                    if (this.raycaster.ray.intersectPlane(this.dragPlane, this.planeIntersection)) {
                        this.dragOffset.copy(this.draggedObject.position).sub(this.planeIntersection);
                    } else {
                        this.dragOffset.set(0, 0, 0);
                    }

                    this.setObjectOpacity(hitObject, 0.6);
                }
            } else {
                this.isOrbiting = true;
                this.isDraggingLocker = false;
            }
        });

        window.removeEventListener("mousemove", this.boundOnMouseMove);
        window.removeEventListener("mouseup", this.boundOnMouseUp);
        window.addEventListener("mousemove", this.boundOnMouseMove);
        window.addEventListener("mouseup", this.boundOnMouseUp);

        canvas.removeEventListener("wheel", this.boundOnWheel);
        canvas.addEventListener("wheel", this.boundOnWheel, { passive: false });
    }

    onWheel(e) {
        e.preventDefault();
        if (this.isDraggingLocker) return;

        const radius = this.camera.position.distanceTo(this.target);
        const newRadius = Math.max(5, Math.min(200, radius + (e.deltaY > 0 ? 2 : -2)));

        const dir = this.camera.position.clone().sub(this.target).normalize();
        this.camera.position.copy(this.target).add(dir.multiplyScalar(newRadius));
        this.camera.lookAt(this.target);
    }

    onMouseMove(e) {
        if (Math.hypot(e.clientX - this.dragStartPos.x, e.clientY - this.dragStartPos.y) > 5) {
            this.hasMoved = true;
        }

        const pos = this.getCanvasMousePos(e);
        this.mouse.x = pos.x;
        this.mouse.y = pos.y;

        if (this.isDraggingLocker && this.draggedObject) {
            this.raycaster.setFromCamera(this.mouse, this.camera);

            if (this.raycaster.ray.intersectPlane(this.dragPlane, this.planeIntersection)) {
                const newPos = this.planeIntersection.clone().add(this.dragOffset);
                this.draggedObject.position.x = newPos.x;
                this.draggedObject.position.z = newPos.z;
            }
            return;
        }

        if (this.isOrbiting) {
            const dx = (e.clientX - this.lastX) * 0.005;
            const dy = (e.clientY - this.lastY) * 0.005;

            this.lastX = e.clientX;
            this.lastY = e.clientY;

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
    }

    async onMouseUp() {
        if (this.isDraggingLocker && this.draggedObject) {
            this.setObjectOpacity(this.draggedObject, 1.0);

            if (this.hasMoved) {
                await this.onDrop(this.draggedObject);
            } else {
                this.state.selectedLocker = this.draggedObject.userData.lockerData;
                this.draggedObject.position.copy(this.draggedObject.userData.initialPos);
            }
        } else if (this.draggedObject && !this.hasMoved && !this.state.isEditMode) {
            this.state.selectedLocker = this.draggedObject.userData.lockerData;
            this.draggedObject.position.copy(this.draggedObject.userData.initialPos);
        }

        this.draggedObject = null;
        this.isDraggingLocker = false;
        this.isOrbiting = false;
    }
}

Locker3DView.template = "iPredict_locker_management.Locker3DView";
registry.category("actions").add("locker_3d_view", Locker3DView);