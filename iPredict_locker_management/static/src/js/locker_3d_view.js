/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const actionRegistry = registry.category("actions");

class Locker3DView extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.canvasRef = useRef("canvas");

        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.animationFrame = null;
        this.raycaster = null;
        this.mouse = null;
        this.lockerMeshes = [];
        this.siteObjects = [];

        this.isOrbiting = false;
        this.lastX = 0;
        this.lastY = 0;
        this.orbitTarget = null;
        this.draggedObject = null;
        this.dragPlane = null;
        this.planeNormal = null;
        this.planeIntersection = null;
        this.dragOffset = null;
        this.isDraggingLocker = false;
        this.dragStartPos = { x: 0, y: 0 };
        this.hasMoved = false;

        this.resizeHandler = this.onWindowResize.bind(this);
        this.boundOnMouseMove = this.onMouseMove.bind(this);
        this.boundOnMouseUp = this.onMouseUp.bind(this);
        this.boundOnMouseDown = this.onMouseDown.bind(this);
        this.boundOnWheel = this.onWheel.bind(this);

        this.state = useState({
            companies: [],
            lockerLocations: [],
            selectedCompanyId: null,
            selectedLockerLocationId: null,
            lockers: [],
            filteredLockers: [],
            allSites: [],       
            sites: [],          
            profilesList: [],
            searchQuery: "",
            activeStatusFilter: null,
            activeProfileFilter: null,
            selectedLocker: null,
            isAdmin: false,
            hasLockers: false,
            isEditMode: false,
            statusColors: {
                available: "#198754",
                allocated: "#dc3545",
                reserved: "#ffc107"
            },
            statusColorsByCompany: {}
        });

        this.pendingPositionChanges = new Map();
        this.originalPositions = new Map();
        this.cameraInitialized = false;

        onWillStart(async () => {
            try {
                await this.loadThreeJS();
                this.orbitTarget = new THREE.Vector3(0, 0, 0);
                this.dragPlane = new THREE.Plane();
                this.planeNormal = new THREE.Vector3(0, 1, 0);
                this.planeIntersection = new THREE.Vector3();
                this.dragOffset = new THREE.Vector3();
                await this.loadInitialData();
            } catch (error) {
                console.error("3D init error:", error);
            }
        });

        onMounted(async () => {
            await this.renderScene();
            window.addEventListener("resize", this.resizeHandler);
            if (this.renderer) {
                this.renderer.domElement.addEventListener("mousedown", this.boundOnMouseDown);
                window.addEventListener("mousemove", this.boundOnMouseMove);
                window.addEventListener("mouseup", this.boundOnMouseUp);
                this.renderer.domElement.addEventListener("wheel", this.boundOnWheel, { passive: false });
            }
        });

        onWillUnmount(() => {
            if (this.animationFrame) cancelAnimationFrame(this.animationFrame);
            window.removeEventListener("resize", this.resizeHandler);
            window.removeEventListener("mousemove", this.boundOnMouseMove);
            window.removeEventListener("mouseup", this.boundOnMouseUp);
            if (this.renderer) {
                this.renderer.domElement.removeEventListener("mousedown", this.boundOnMouseDown);
                this.renderer.domElement.removeEventListener("wheel", this.boundOnWheel);
                this.renderer.dispose();
            }
        });
    }

    async loadThreeJS() {
        if (window.THREE) return;
        await new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
        if (!window.THREE) throw new Error("THREE library failed to load");
    }

    async loadInitialData() {
        try {
            const data = await this.orm.call("locker.locker", "get_3d_data", []);
            if (!data) return;

            this.state.companies = data.companies || [];
            this.state.lockerLocations = data.locker_locations || [];
            this.state.lockers = data.lockers || [];
            this.state.allSites = data.sites || [];
            this.state.profilesList = data.profiles || [];
            this.state.isAdmin = data.is_admin || false;
            this.state.statusColorsByCompany = data.status_colors || {};
            this.state.hasLockers = this.state.lockers.length > 0;

            const actionContext = (this.props.action && this.props.action.context) || {};
            const defaultLocationId = Number(actionContext.default_location_id) || null;
            const defaultCompanyId = Number(actionContext.default_company_id)
                || Number(data.current_company_id)
                || null;
            const defaultLocation = defaultLocationId
                ? this.state.lockerLocations.find((loc) => loc.id === defaultLocationId)
                : null;

            if (defaultLocation) {
                this.state.selectedLockerLocationId = defaultLocation.id;
                this.state.selectedCompanyId = defaultLocation.company_id || defaultCompanyId;
            } else {
                const defaultCompany = defaultCompanyId
                    ? this.state.companies.find((company) => company.id === defaultCompanyId)
                    : null;
                if (defaultCompany) {
                    this.state.selectedCompanyId = defaultCompany.id;
                } else if (this.state.companies.length) {
                    this.state.selectedCompanyId = this.state.companies[0].id;
                }
                const companyLocations = this.state.lockerLocations.filter(
                    (loc) => !this.state.selectedCompanyId || loc.company_id === this.state.selectedCompanyId
                );
                if (companyLocations.length) {
                    this.state.selectedLockerLocationId = companyLocations[0].id;
                }
            }

            this.updateStatusColors();
            this.refreshFilteredSites();
            this.apply3DFilters();
        } catch (error) {
            console.error("loadInitialData error:", error);
        }
    }


    get visibleLocations() {
        return (this.state.lockerLocations || []).filter(
            (loc) => !this.state.selectedCompanyId || loc.company_id === this.state.selectedCompanyId
        );
    }

    getStatusColors(companyId) {
        const defaults = { available: "#198754", allocated: "#dc3545", reserved: "#ffc107" };
        const configured = (this.state.statusColorsByCompany || {})[companyId] || {};
        return {
            available: configured.available || defaults.available,
            allocated: configured.allocated || defaults.allocated,
            reserved: configured.reserved || defaults.reserved,
        };
    }

    updateStatusColors() {
        const companyId = this.state.selectedCompanyId
            || (this.state.companies.length ? this.state.companies[0].id : null);
        this.state.statusColors = this.getStatusColors(companyId);
    }

    refreshFilteredSites() {
        let sites = [...this.state.allSites];

        if (this.state.selectedCompanyId) {
            sites = sites.filter(
                (s) => s.company_id === this.state.selectedCompanyId
            );
        }

        if (this.state.selectedLockerLocationId) {
            sites = sites.filter(
                (s) => s.locker_location_id === this.state.selectedLockerLocationId
            );
        }

        this.state.sites = this.prepareSites(sites);
    }

    prepareSites(sites) {
        return (sites || [])
            .filter(site => site.active !== false)
            .map(site => ({
                id: site.id,
                name: site.name || `Site ${site.id}`,
                x: Number(site.pos_x) || 0,
                y: Number(site.pos_y) || 0,
                z: Number(site.pos_z) || 0,
                width: Math.max(Number(site.width) || 1, 1),
                height: Math.max(Number(site.height) || 1, 1),
                depth: Math.max(Number(site.depth) || 1, 1)
            }));
    }

   
    getLockerBounds() {
        const lockers = this.state.filteredLockers;

        if (!lockers || !lockers.length) {
            return this.getSiteBounds();
        }

        let minX = Infinity, maxX = -Infinity;
        let minZ = Infinity, maxZ = -Infinity;
        let maxHeight = 0;

        lockers.forEach((locker) => {
            const w = Math.max(parseFloat(locker.w ?? locker.width) || 1, 0.01);
            const d = Math.max(parseFloat(locker.d ?? locker.depth) || 1, 0.01);
            const h = Math.max(parseFloat(locker.h ?? locker.height) || 1, 0.01);

            const x = Number(locker.pos_x) || 0;
            const z = Number(locker.pos_z) || 0;
            const y = Number(locker.pos_y) || 0;

            minX = Math.min(minX, x);
            maxX = Math.max(maxX, x + w);
            minZ = Math.min(minZ, z);
            maxZ = Math.max(maxZ, z + d);
            maxHeight = Math.max(maxHeight, y + h);
        });

        const pad = 5;
        return {
            minX: minX - pad,
            maxX: maxX + pad,
            minZ: minZ - pad,
            maxZ: maxZ + pad,
            maxHeight,
        };
    }

    getSiteBounds() {
        if (!this.state.sites.length) {
            return { minX: -50, maxX: 50, minZ: -50, maxZ: 50, maxHeight: 0 };
        }
        let minX = Infinity, maxX = -Infinity;
        let minZ = Infinity, maxZ = -Infinity;
        this.state.sites.forEach(site => {
            const hw = site.width / 2;
            const hd = site.depth / 2;
            minX = Math.min(minX, site.x - hw);
            maxX = Math.max(maxX, site.x + hw);
            minZ = Math.min(minZ, site.z - hd);
            maxZ = Math.max(maxZ, site.z + hd);
        });
        const pad = 5;
        return { minX: minX - pad, maxX: maxX + pad, minZ: minZ - pad, maxZ: maxZ + pad, maxHeight: 0 };
    }

    clampLockerToSite(mesh, posX, posZ) {
        const lockerData = mesh.userData.lockerData;
        if (!lockerData) return { x: posX, z: posZ };
        const site = this.state.sites.find(s => s.id === lockerData.site_id);
        if (!site) return { x: posX, z: posZ };

        const w = parseFloat(lockerData.w ?? lockerData.width) || 1;
        const d = parseFloat(lockerData.d ?? lockerData.depth) || 1;
        const halfW = w / 2;
        const halfD = d / 2;

        const siteMinX = site.x - site.width / 2;
        const siteMaxX = site.x + site.width / 2;
        const siteMinZ = site.z - site.depth / 2;
        const siteMaxZ = site.z + site.depth / 2;

        const minLockerCenterX = siteMinX + halfW;
        const maxLockerCenterX = siteMaxX - halfW;
        const minLockerCenterZ = siteMinZ + halfD;
        const maxLockerCenterZ = siteMaxZ - halfD;

        const clampedX = Math.max(minLockerCenterX, Math.min(posX, maxLockerCenterX));
        const clampedZ = Math.max(minLockerCenterZ, Math.min(posZ, maxLockerCenterZ));

        return { x: clampedX, z: clampedZ };
    }

    clampLockerToSiteXY(mesh, posX, posY) {
        const lockerData = mesh.userData.lockerData;
        if (!lockerData) return { x: posX, y: posY };
        const site = this.state.sites.find(s => s.id === lockerData.site_id);
        if (!site) return { x: posX, y: posY };

        const w = parseFloat(lockerData.w ?? lockerData.width) || 1;
        const h = parseFloat(lockerData.h ?? lockerData.height) || 1;
        const halfW = w / 2;
        const halfH = h / 2;

        const siteMinX = site.x - site.width / 2;
        const siteMaxX = site.x + site.width / 2;
        const siteMinY = site.y;
        const siteMaxY = site.y + site.height;

        const minLockerCenterX = siteMinX + halfW;
        const maxLockerCenterX = siteMaxX - halfW;
        const minLockerCenterY = siteMinY + halfH;
        const maxLockerCenterY = siteMaxY - halfH;

        const clampedX = Math.max(minLockerCenterX, Math.min(posX, maxLockerCenterX));
        const clampedY = Math.max(minLockerCenterY, Math.min(posY, maxLockerCenterY));

        return { x: clampedX, y: clampedY };
    }

    async renderScene() {
        const container = this.canvasRef.el;
        if (!container) return;
        container.innerHTML = "";

        const width = container.clientWidth || window.innerWidth;
        const height = container.clientHeight || window.innerHeight;

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xf5f5f5);

        this.camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 10000);

        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        container.appendChild(this.renderer.domElement);

        const ambient = new THREE.AmbientLight(0xffffff, 0.8);
        this.scene.add(ambient);
        const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
        dirLight.position.set(100, 200, 100);
        this.scene.add(dirLight);

        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();

        this.drawFloor();
        this.drawSites();
        this.drawLockers();
        this.fitCameraToScene();
        this.animate();
    }

    drawFloor() {
        return;
    }

    drawSites() {
        this.clearSites();
        this.state.sites.forEach(site => this.drawSingleSite(site));
    }

    drawSingleSite(site) {
       
        return; 
    }

    addSiteLabel(text, x, y, z) {
        const canvas = document.createElement("canvas");
        canvas.width = 512;
        canvas.height = 128;
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.font = "bold 52px Arial";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "#333333";
        ctx.fillText(text, canvas.width / 2, canvas.height / 2);
        const texture = new THREE.CanvasTexture(canvas);
        const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
        const sprite = new THREE.Sprite(material);
        sprite.position.set(x, y, z);
        const site = this.state.sites.find(s => s.name === text);
        const labelSize = Math.max(8, Math.min(18, Math.min(
            site?.width || 18,
            site?.depth || 18
        ) * 0.5));
        sprite.scale.set(labelSize * 2.5, labelSize * 0.6, 1);
        sprite.userData = { type: "site_label" };
        this.scene.add(sprite);
        this.siteObjects.push(sprite);
    }

    clearSites() {
        this.siteObjects.forEach(obj => {
            if (obj.parent) obj.parent.remove(obj);
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) {
                if (obj.material.map) obj.material.map.dispose();
                obj.material.dispose();
            }
        });
        this.siteObjects = [];
    }

    drawLockers() {
            this.lockerMeshes = [];
            if (!this.state.filteredLockers) return;

            this.state.filteredLockers.forEach(locker => {
                this.drawLocker(locker);
            });
        }

        drawLocker(locker) {
    const w = Math.max(parseFloat(locker.w ?? locker.width) || 1, 0.01);
    const h = Math.max(parseFloat(locker.h ?? locker.height) || 1, 0.01);
    const d = Math.max(parseFloat(locker.d ?? locker.depth) || 1, 0.01);
    const side = locker.side || "side_1";

    const rawX = Number(locker.renderX ?? locker.pos_x ?? 0);
    const rawY = Number(locker.renderY ?? locker.pos_y ?? 0);
    const rawZ = Number(locker.renderZ ?? locker.pos_z ?? 0);

    const site = this.state.sites.find(s => s.id === locker.site_id);

    let vertical = false;

    if (site) {
        const sites = this.state.sites || [];
        if (sites.length > 1) {
            const centerX = (Math.min(...sites.map(s => s.x)) + Math.max(...sites.map(s => s.x))) / 2;
            const centerZ = (Math.min(...sites.map(s => s.z)) + Math.max(...sites.map(s => s.z))) / 2;
            const dx = Math.abs(site.x - centerX);
            const dz = Math.abs(site.z - centerZ);
            vertical = dx >= dz;
        }
    }

    const centerX = rawX + w / 2;
    const centerY = rawY + h / 2;
    const centerZ = rawZ + d / 2;

    const boxGeo = new THREE.BoxGeometry(w, h, d);

    const lockerStatusColors = this.getStatusColors(locker.company_id);
const statusColor = lockerStatusColors[locker.status] || lockerStatusColors.available;
const bodyColorHex = this.getProfileColorHex(statusColor);
const doorColorHex = this.getProfileColorHex(locker.profile_color);

const body = new THREE.Mesh(
    boxGeo,
    new THREE.MeshStandardMaterial({
        color: bodyColorHex,
        roughness: 0.4,
        metalness: 0.1,
        polygonOffset: true,
        polygonOffsetFactor: 1,
        polygonOffsetUnits: 1
    })
);

    body.position.set(centerX, centerY, centerZ);

    const edgesGeo = new THREE.EdgesGeometry(boxGeo);
    const borderMat = new THREE.LineBasicMaterial({
    color: 0x000000,
    linewidth: 1
});

    body.add(new THREE.LineSegments(edgesGeo, borderMat));

    const doorWidth = vertical ? d * 0.88 : w * 0.88;
    const doorHeight = h * 0.88;

    const door = new THREE.Mesh(
        new THREE.PlaneGeometry(doorWidth, doorHeight),
        new THREE.MeshStandardMaterial({
            color: doorColorHex,
            roughness: 0.3,
            side: THREE.DoubleSide
        })
    );

    if (vertical) {
        door.rotation.y = side === "side_1" ? -Math.PI / 2 : Math.PI / 2;

        door.position.set(
            side === "side_1" ? -(w / 2) - 0.01 : (w / 2) + 0.01,
            0,
            0
        );
    } else {
        door.rotation.y = side === "side_1" ? Math.PI : 0;

        door.position.set(
            0,
            0,
            side === "side_1" ? -(d / 2) - 0.01 : (d / 2) + 0.01
        );
    }

    body.add(door);

    const handle = new THREE.Mesh(
        new THREE.CylinderGeometry(
            Math.max(Math.min(w, h) * 0.03, 0.015),
            Math.max(Math.min(w, h) * 0.03, 0.015),
            Math.max(h * 0.1, 0.05),
            8
        ),
        new THREE.MeshStandardMaterial({
            color: 0x222222,
            metalness: 0.8,
            roughness: 0.25
        })
    );

    if (vertical) {
        handle.rotation.z = Math.PI / 2;

        handle.position.set(
            side === "side_1" ? -(w / 2) - 0.03 : (w / 2) + 0.03,
            0,
            d * 0.35
        );
    } else {
        handle.rotation.x = Math.PI / 2;

        handle.position.set(
            w * 0.35,
            0,
            side === "side_1" ? -(d / 2) - 0.03 : (d / 2) + 0.03
        );
    }

    body.add(handle);

    body.userData = {
        type: "locker",
        locker: locker,
        lockerData: locker,
        lockerId: locker.id,
        initialPos: body.position.clone()
    };

    body.castShadow = true;
    body.receiveShadow = true;

    this.scene.add(body);
    this.lockerMeshes.push(body);

    locker.pos_x = rawX;
    locker.pos_y = rawY;
    locker.pos_z = rawZ;

    }

    fitCameraToScene() {
        if (!this.camera) return;
        const bounds = this.getLockerBounds();
        const centerX = (bounds.minX + bounds.maxX) / 2;
        const centerZ = (bounds.minZ + bounds.maxZ) / 2;
        const size = Math.max(bounds.maxX - bounds.minX, bounds.maxZ - bounds.minZ, 10);
        this.orbitTarget.set(centerX, (bounds.maxHeight || 0) * 0.5, centerZ);
        if (this.cameraInitialized) {
            this.camera.lookAt(this.orbitTarget);
            return;
        }
        this.camera.position.set(
            centerX + size * 0.75,
            (bounds.maxHeight || 0) + size * 0.6,
            centerZ + size * 1.1
        );
        this.camera.lookAt(this.orbitTarget);
        this.cameraInitialized = true;
    }

    animate() {
        this.animationFrame = requestAnimationFrame(() => this.animate());
        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    }

    onWindowResize() {
        if (!this.camera || !this.renderer) return;
        const container = this.canvasRef.el;
        const w = container.clientWidth || window.innerWidth;
        const h = container.clientHeight || window.innerHeight;
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(w, h);
    }

    apply3DFilters() {
        try {
            let lockers = [...this.state.lockers];
            if (this.state.selectedCompanyId)
                lockers = lockers.filter(l => l.company_id === this.state.selectedCompanyId);
            if (this.state.selectedLockerLocationId)
                lockers = lockers.filter(l => l.locker_location_id === this.state.selectedLockerLocationId);
            if (this.state.searchQuery) {
                const q = this.state.searchQuery.toLowerCase().trim();
                lockers = lockers.filter(l => String(l.name || "").toLowerCase().includes(q));
            }
            if (this.state.activeStatusFilter)
                lockers = lockers.filter(l => l.status === this.state.activeStatusFilter);
            if (this.state.activeProfileFilter)
                lockers = lockers.filter(l => l.profile_id === this.state.activeProfileFilter);

            this.state.filteredLockers = lockers;
            this.state.hasLockers = this.state.lockers.some(l =>
                (!this.state.selectedCompanyId || l.company_id === this.state.selectedCompanyId) &&
                (!this.state.selectedLockerLocationId || l.locker_location_id === this.state.selectedLockerLocationId)
            );
            this.updateStatusColors();

            this.refreshFilteredSites();

            if (this.scene) {
                this.removeLockerObjects();
                this.drawFloor();
                this.drawSites();
                this.drawLockers();
                this.fitCameraToScene();
            }
        } catch (err) {
            console.error("DEBUG: apply3DFilters threw an error:", err);
        }
    }

    removeLockerObjects() {
        if (!this.scene) return;
        const toRemove = [];
        this.scene.traverse(obj => {
            if (obj.userData && (obj.userData.type === "locker" || obj.userData.type === "locker_border"))
                toRemove.push(obj);
        });
        toRemove.forEach(obj => {
            this.scene.remove(obj);
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) {
                if (obj.material.map) obj.material.map.dispose();
                obj.material.dispose();
            }
        });
    }

    async onCompanyChange(event) {
        this.state.selectedCompanyId = event.target.value ? Number(event.target.value) : null;
        const companyLocations = this.visibleLocations;
        this.state.selectedLockerLocationId = companyLocations.length ? companyLocations[0].id : null;
        await this.reload3DData();
    }

    async onLockerLocationChange(event) {
        this.state.selectedLockerLocationId = event.target.value ? Number(event.target.value) : null;
        await this.reload3DData();
    }

    async reload3DData() {
        try {
            const data = await this.orm.call("locker.locker", "get_3d_data", []);
            if (!data) return;
            this.state.lockers = data.lockers || [];
            this.state.allSites = data.sites || [];
            this.state.profilesList = data.profiles || [];
            this.state.statusColorsByCompany = data.status_colors || {};
            this.apply3DFilters();
        } catch (e) { console.error("reload error:", e); }
    }

    clearSearch() { this.state.searchQuery = ""; this.apply3DFilters(); }

    toggleStatusFilter(status) {
        console.log("DEBUG: toggleStatusFilter called with:", status, "| current activeStatusFilter:", this.state.activeStatusFilter);
        this.state.activeStatusFilter = (this.state.activeStatusFilter === status) ? null : status;
        console.log("DEBUG: activeStatusFilter is now:", this.state.activeStatusFilter);
        this.apply3DFilters();
        console.log("DEBUG: filteredLockers count after filter:", this.state.filteredLockers.length);
    }

    toggleProfileFilter(profileId) {
        console.log("DEBUG: toggleProfileFilter called with:", profileId, "(type:", typeof profileId, ") | current activeProfileFilter:", this.state.activeProfileFilter, "(type:", typeof this.state.activeProfileFilter, ")");

        const profileIdCounts = {};
        this.state.lockers.forEach(l => {
            const key = `${l.profile_id} (type: ${typeof l.profile_id})`;
            profileIdCounts[key] = (profileIdCounts[key] || 0) + 1;
        });
        console.log("DEBUG: all lockers loaded:", this.state.lockers.length);
        console.log("DEBUG: profile_id distribution across ALL loaded lockers:", profileIdCounts);

        console.log("DEBUG: selectedCompanyId:", this.state.selectedCompanyId, "| selectedLockerLocationId:", this.state.selectedLockerLocationId);
        const afterCompanyLocationFilter = this.state.lockers.filter(l =>
            (!this.state.selectedCompanyId || l.company_id === this.state.selectedCompanyId) &&
            (!this.state.selectedLockerLocationId || l.locker_location_id === this.state.selectedLockerLocationId)
        );
        console.log("DEBUG: lockers matching current company+location (before profile filter):", afterCompanyLocationFilter.length);
        const profileIdsInScope = {};
        afterCompanyLocationFilter.forEach(l => {
            const key = `${l.profile_id} (type: ${typeof l.profile_id})`;
            profileIdsInScope[key] = (profileIdsInScope[key] || 0) + 1;
        });
        console.log("DEBUG: profile_id distribution WITHIN current company+location:", profileIdsInScope);

        this.state.activeProfileFilter = (this.state.activeProfileFilter === profileId) ? null : profileId;
        console.log("DEBUG: activeProfileFilter is now:", this.state.activeProfileFilter);
        this.apply3DFilters();
        console.log("DEBUG: filteredLockers count after filter:", this.state.filteredLockers.length);
    }

    toggleEditMode() {
        if (!this.state.isEditMode) {
            // Enter edit mode: store original positions, clear pending
            this.state.isEditMode = true;
            this.pendingPositionChanges.clear();
            this.originalPositions.clear();
            this.lockerMeshes.forEach(mesh => {
                const lockerId = mesh.userData.lockerId;
                this.originalPositions.set(lockerId, mesh.position.clone());
                mesh.userData.initialPos = mesh.position.clone();
            });
            this.notification.add("3D edit mode enabled.", { type: "info" });
        } else {
            this.saveLayout();
        }
    }

    setObjectOpacity(object, opacity) {
        object.traverse(child => {
            if (child.isMesh && child.material) {
                child.material.transparent = opacity < 1.0;
                child.material.opacity = opacity;
            }
        });
    }

    async saveLayout() {
        if (!this.pendingPositionChanges.size) {
            this.notification.add("No changes to save.", { type: "info" });
            this.state.isEditMode = false;
            this.originalPositions.clear();
            this.lockerMeshes.forEach(m => this.setObjectOpacity(m, 1));
            return;
        }

        try {
            const changes = Array.from(this.pendingPositionChanges.values());

            for (const change of changes) {
                await this.orm.call("locker.locker", "update_locker_position", [
                    change.id,
                    change.pos_x,
                    change.pos_y,
                    change.pos_z,
                    change.side,
                    change.site_id
                ]);
            }

            for (const change of changes) {
                const locker = this.state.lockers.find(l => l.id === change.id);
                if (locker) {
                    locker.pos_x = change.pos_x;
                    locker.pos_y = change.pos_y;
                    locker.pos_z = change.pos_z;
                    locker.side = change.side;
                    locker.site_id = change.site_id;
                }
            }

            this.lockerMeshes.forEach(mesh => {
                const lockerId = mesh.userData.lockerId;
                const change = this.pendingPositionChanges.get(lockerId);
                if (change) {
                    mesh.userData.initialPos = mesh.position.clone();
                    this.originalPositions.set(lockerId, mesh.position.clone());
                }
            });

            this.pendingPositionChanges.clear();
            this.originalPositions.clear();
            this.state.isEditMode = false;
            this.lockerMeshes.forEach(m => this.setObjectOpacity(m, 1));
            this.notification.add("3D layout saved successfully.", { type: "success" });
        } catch (error) {
            console.error("Save layout error:", error);
            this.notification.add("Unable to save 3D layout.", { type: "danger" });
        }
    }

    getCanvasMousePos(e) {
        if (!this.renderer || !this.renderer.domElement) return { x: 0, y: 0 };
        const rect = this.renderer.domElement.getBoundingClientRect();
        return {
            x: ((e.clientX - rect.left) / rect.width) * 2 - 1,
            y: -((e.clientY - rect.top) / rect.height) * 2 + 1
        };
    }

    onMouseDown(e) {
        if (e.button !== 0) return;
        const pos = this.getCanvasMousePos(e);
        this.mouse.x = pos.x;
        this.mouse.y = pos.y;
        this.dragStartPos = { x: e.clientX, y: e.clientY };
        this.hasMoved = false;

        this.raycaster.setFromCamera(this.mouse, this.camera);
        const visible = this.lockerMeshes.filter(
            m => m.visible && m.userData.lockerData && m.userData.lockerData.is_mine !== false
        );
        const intersects = this.raycaster.intersectObjects(visible, true);

        if (intersects.length) {
            let hit = intersects[0].object;
            while (hit && (!hit.userData || !hit.userData.lockerId)) {
                hit = hit.parent;
            }
            if (hit && hit.userData && hit.userData.lockerId) {
                if (this.state.isEditMode) {
                    this.isDraggingLocker = true;
                    this.isOrbiting = false;
                    this.draggedObject = hit;
                    hit.userData.initialPos = hit.position.clone();

                   const lockerSite = this.state.sites.find(
                            s => s.id === hit.userData.lockerData.site_id
                        );
                        const sceneSites = this.state.sites || [];
                        let isVerticalSite = false;
                        if (lockerSite && sceneSites.length > 1) {
                            const centerX =
                                (Math.min(...sceneSites.map(s => s.x)) +
                                Math.max(...sceneSites.map(s => s.x))) / 2;
                            const centerZ =
                                (Math.min(...sceneSites.map(s => s.z)) +
                                Math.max(...sceneSites.map(s => s.z))) / 2;
                            isVerticalSite =
                                Math.abs(lockerSite.x - centerX) >=
                                Math.abs(lockerSite.z - centerZ);
                        }
                        this.planeNormal.set(
                            isVerticalSite ? 1 : 0,
                            0,
                            isVerticalSite ? 0 : 1
                        );
                        this.dragPlane.setFromNormalAndCoplanarPoint(
                            this.planeNormal,
                            this.draggedObject.position
                        );
                    if (this.raycaster.ray.intersectPlane(this.dragPlane, this.planeIntersection)) {
                        this.dragOffset.copy(this.draggedObject.position).sub(this.planeIntersection);
                    } else {
                        this.dragOffset.set(0, 0, 0);
                    }
                    this.setObjectOpacity(hit, 0.6);
                    e.preventDefault();
                    e.stopPropagation();
                } else {
                    this.state.selectedLocker = hit.userData.lockerData;
                }
                return;
            }
        }

        this.isOrbiting = true;
        this.isDraggingLocker = false;
        this.lastX = e.clientX;
        this.lastY = e.clientY;
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
        let newPos = this.planeIntersection.clone().add(this.dragOffset);
        const lockerSite = this.state.sites.find(
            s => s.id === this.draggedObject.userData.lockerData.site_id
        );
        const sceneSites = this.state.sites || [];
        let isVerticalSite = false;
        if (lockerSite && sceneSites.length > 1) {
            const centerX =
                (Math.min(...sceneSites.map(s => s.x)) +
                Math.max(...sceneSites.map(s => s.x))) / 2;
            const centerZ =
                (Math.min(...sceneSites.map(s => s.z)) +
                Math.max(...sceneSites.map(s => s.z))) / 2;
            isVerticalSite =
                Math.abs(lockerSite.x - centerX) >=
                Math.abs(lockerSite.z - centerZ);
        }
        if (isVerticalSite) {
            this.draggedObject.position.z = newPos.z;
        } else {
            this.draggedObject.position.x = newPos.x;
        }
        this.draggedObject.position.y = newPos.y;
    }
    e.preventDefault();
    return;
}

        if (this.isOrbiting) {
            const dx = (e.clientX - this.lastX) * 0.01;
            const dy = (e.clientY - this.lastY) * 0.01;
            this.lastX = e.clientX;
            this.lastY = e.clientY;
            const target = this.orbitTarget;
            const radius = this.camera.position.distanceTo(target);
            const theta = Math.atan2(this.camera.position.x - target.x, this.camera.position.z - target.z) - dx;
            let phi = Math.acos((this.camera.position.y - target.y) / radius) - dy;
            phi = Math.max(0.1, Math.min(Math.PI / 2 - 0.05, phi));
            this.camera.position.x = target.x + radius * Math.sin(phi) * Math.sin(theta);
            this.camera.position.y = target.y + radius * Math.cos(phi);
            this.camera.position.z = target.z + radius * Math.sin(phi) * Math.cos(theta);
            this.camera.lookAt(target);
        }
    }

    onWheel(e) {
        e.preventDefault();
        if (this.isDraggingLocker) return;
        const target = this.orbitTarget;
        const radius = this.camera.position.distanceTo(target);
        const newRadius = Math.max(5, Math.min(200, radius + (e.deltaY > 0 ? 2 : -2)));
        const dir = this.camera.position.clone().sub(target).normalize();
        this.camera.position.copy(target).add(dir.multiplyScalar(newRadius));
        this.camera.lookAt(target);
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
        }
        this.draggedObject = null;
        this.isDraggingLocker = false;
        this.isOrbiting = false;
        this.hasMoved = false;
    }

    async onDrop(draggedLockerMesh) {
        const draggedLockerId = draggedLockerMesh.userData.lockerId;
        const draggedData = draggedLockerMesh.userData.lockerData;
        const initialPos = draggedLockerMesh.userData.initialPos.clone();

        const w = parseFloat(draggedData.w ?? draggedData.width) || 1;
        const h = parseFloat(draggedData.h ?? draggedData.height) || 1;
        const d = parseFloat(draggedData.d ?? draggedData.depth) || 1;

        const dropX = draggedLockerMesh.position.x;
        const dropY = draggedLockerMesh.position.y;
        const dropZ = draggedLockerMesh.position.z;

        let targetMesh = null;
        let minDist = Infinity;
        const draggedSide = draggedData.side || "side_1";

        for (const mesh of this.lockerMeshes) {
            if (mesh === draggedLockerMesh || !mesh.visible) continue;
            const otherData = mesh.userData.lockerData;
            const otherSide = otherData.side || "side_1";
            if (draggedSide !== otherSide) continue;

            const ow = parseFloat(otherData.w ?? otherData.width) || 1;
            const oh = parseFloat(otherData.h ?? otherData.height) || 1;
            const od = parseFloat(otherData.d ?? otherData.depth) || 1;

            if (Math.abs(mesh.position.z - dropZ) > Math.max(d, od) * 0.45) continue;

            const dist = Math.hypot(mesh.position.x - dropX, mesh.position.y - dropY);
            const swapRadius = Math.max(w, ow) * 0.55;
            if (dist < swapRadius && dist < minDist) {
                minDist = dist;
                targetMesh = mesh;
            }
        }

        if (targetMesh) {
            const targetData = targetMesh.userData.lockerData;
            const targetW = parseFloat(targetData.w ?? targetData.width) || 1;
            const targetH = parseFloat(targetData.h ?? targetData.height) || 1;
            const targetD = parseFloat(targetData.d ?? targetData.depth) || 1;

            if (targetW >= w && targetH >= h && targetD >= d) {
                const targetPos = targetMesh.position.clone();
                draggedLockerMesh.position.set(targetPos.x, targetPos.y, targetPos.z);
                targetMesh.position.set(initialPos.x, initialPos.y, initialPos.z);

                const draggedPosX = targetPos.x - w / 2;
                const draggedPosY = targetPos.y - h / 2;
                const draggedPosZ = targetPos.z - d / 2;
                const targetPosX = initialPos.x - targetW / 2;
                const targetPosY = initialPos.y - targetH / 2;
                const targetPosZ = initialPos.z - targetD / 2;

                this.pendingPositionChanges.set(draggedLockerId, {
                    id: draggedLockerId,
                    pos_x: draggedPosX,
                    pos_y: draggedPosY,
                    pos_z: draggedPosZ,
                    side: draggedData.side,
                    site_id: targetData.site_id
                });
                this.pendingPositionChanges.set(targetMesh.userData.lockerId, {
                    id: targetMesh.userData.lockerId,
                    pos_x: targetPosX,
                    pos_y: targetPosY,
                    pos_z: targetPosZ,
                    side: targetData.side,
                    site_id: draggedData.site_id
                });
            } else {
                draggedLockerMesh.position.copy(initialPos);
                this.notification.add("Cannot swap: target locker is smaller.", { type: "warning" });
            }
            return;
        }

        const posX = dropX - w / 2;
        const posY = dropY - h / 2;
        const posZ = dropZ - d / 2;

        this.pendingPositionChanges.set(draggedLockerId, {
            id: draggedLockerId,
            pos_x: posX,
            pos_y: posY,
            pos_z: posZ,
            side: draggedData.side,
            site_id: draggedData.site_id
        });
    }

    closePopup() { this.state.selectedLocker = null; }

    getProfileColorHex(colorValue) {
        const ODOO_COLORS = {
            0: 0x8f8f8f, 1: 0xF05365, 2: 0xFABC2A, 3: 0xECE133,
            4: 0x27AE60, 5: 0x1ABC9C, 6: 0x3498DB, 7: 0x2980B9,
            8: 0x9B59B6, 9: 0xE84393, 10: 0x7F8C8D, 11: 0x34495E
        };
        if (typeof colorValue === "number" && ODOO_COLORS[colorValue] !== undefined)
            return ODOO_COLORS[colorValue];
        if (typeof colorValue === "string" && colorValue.trim().startsWith("#"))
            return parseInt(colorValue.trim().replace("#", "0x"), 16);
        return 0x8f8f8f;
    }
}

Locker3DView.template = "iPredict_locker_management.Locker3DView";
Locker3DView.props = { "*": true };

actionRegistry.add("locker_3d_view", Locker3DView);