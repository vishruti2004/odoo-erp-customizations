/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const actionRegistry = registry.category("actions");

const STATUS_COLORS = {
    inUse: "#22c55e", almostFull: "#f59e0b", overloaded: "#ef4444",
    noCapacity: "#3b82f6", empty: "#9ca3af",
};

const hexToInt = (hex, fallback) => {
    if (!hex) return fallback;
    try { return parseInt(String(hex).replace('#', ''), 16); }
    catch (e) { return fallback; }
};

const DEFAULT_NEW_RACK = {
    locationId: '',
    rack_length: 3.0,
    rack_width: 1.2,
    rack_height: 3.0,
    shelf_levels: 3,
    bins_per_level: 5,
    capacity: 1000,
    pos_x: 0,
    pos_z: 0,
    rotation_y: 0,
};

export class Stock3DView extends Component {
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
        this.rackMeshes = [];
        this.labelObjects = [];
        this.threeLoaded = false;

        this.forklift = null;
        this.forkliftPath = null;
        this.forkliftProgress = 0;
        this.forkliftSpeed = 0.002;

        this._flyingTo = false;
        this._prevCameraPos = null;
        this._prevOrbitTarget = null;

        this.isDraggingBox = false;
        this.draggedBox = null;
        this.dragPlane = null;
        this.dragOffset = null;
        this.dragStartPos = { x: 0, y: 0 };
        this.hasMoved = false;
        this.pendingBoxMove = null;
        this._ghostSlot = null;

        this.isDraggingRack = false;
        this.draggedRackGroup = null;
        this.draggedRackLoc = null;
        this.dragRackPlane = null;
        this.dragRackOffset = null;

        this.pendingRackMoves = {};
        this.pendingBoxMoves = [];

        this._warehouseOffsets = {};

        this.state = useState({
            searchQuery: "", heatmapEnabled: false, walkMode: false,
            selectedLocation: null, selectedProduct: null,
            locations: [], products: [], filteredLocations: [],
            productsExpanded: false,
            flying: false,
            addPanelOpen: false,
            editMode: false,
            editRackId: null,
            availableLocations: [],
            availableLocationsGrouped: [],
            newRack: { ...DEFAULT_NEW_RACK },
            editRackMode: false,
            hasUnsavedChanges: false,
            warehouses: [],
            selectedWarehouse: '',
        });

        this.isOrbiting = false;
        this.lastX = 0;
        this.lastY = 0;
        this.orbitTarget = null;

        this.resizeHandler = this.onResize.bind(this);
        this.boundOnMouseDown = this.onMouseDown.bind(this);
        this.boundOnMouseMove = this.onMouseMove.bind(this);
        this.boundOnMouseUp = this.onMouseUp.bind(this);
        this.boundOnWheel = this.onWheel.bind(this);

        onWillStart(async () => {
            await this.loadThreeJS();
            await this.loadData();
        });

        onMounted(() => {
            this.initScene();
            this.renderScene();
            window.addEventListener("resize", this.resizeHandler);
            this.renderer.domElement.addEventListener("mousedown", this.boundOnMouseDown);
            window.addEventListener("mousemove", this.boundOnMouseMove);
            window.addEventListener("mouseup", this.boundOnMouseUp);
            this.renderer.domElement.addEventListener("wheel", this.boundOnWheel, { passive: false });
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
        if (window.THREE) { await this.loadGLTFLoader(); this.threeLoaded = true; return; }
        return new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";
            script.onload = async () => {
                await this.loadGLTFLoader();
                this.threeLoaded = true;
                resolve();
            };
            script.onerror = () => reject(new Error("Failed to load Three.js"));
            document.head.appendChild(script);
        });
    }

    async loadGLTFLoader() {
        if (window.THREE && window.THREE.GLTFLoader) return;
        return new Promise((resolve) => {
            const script = document.createElement("script");
            script.src = "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js";
            script.onload = () => resolve();
            script.onerror = () => resolve();
            document.head.appendChild(script);
        });
    }

    async loadData() {
        try {
            const result = await this.orm.call("stock.location", "get_3d_data", [[]]);
            if (result && result.locations) {
                this.state.locations = result.locations;
                this.state.products = result.products || [];
                this.state.warehouses = result.warehouses || [];
                this.state.filteredLocations = this.state.locations;
            }
        } catch (e) {
            console.error("3D data load error:", e);
            this.notification.add("Failed to load warehouse data.", { type: "danger" });
        }
    }

    initScene() {
        if (!this.threeLoaded || !window.THREE) return;
        const container = this.canvasRef.el;
        if (!container) return;

        const width = container.clientWidth || window.innerWidth;
        const height = container.clientHeight || window.innerHeight;

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xf0f2f5);

        this.camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 10000);
        this.camera.position.set(10, 8, 15);

        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        container.appendChild(this.renderer.domElement);

        this.scene.add(new THREE.AmbientLight(0xffffff, 0.85));

        const dirLight = new THREE.DirectionalLight(0xffffff, 0.7);
        dirLight.position.set(20, 30, 20);
        dirLight.castShadow = true;
        dirLight.shadow.mapSize.width = 2048;
        dirLight.shadow.mapSize.height = 2048;
        dirLight.shadow.camera.left = -40;
        dirLight.shadow.camera.right = 40;
        dirLight.shadow.camera.top = 40;
        dirLight.shadow.camera.bottom = -40;
        this.scene.add(dirLight);

        const dirLight2 = new THREE.DirectionalLight(0xffffff, 0.4);
        dirLight2.position.set(-20, 10, -20);
        this.scene.add(dirLight2);

        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        this.orbitTarget = new THREE.Vector3(0, 0, 0);

        this.dragPlane = new THREE.Plane();
        this.dragOffset = new THREE.Vector3();

        this.dragRackPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
        this.dragRackOffset = new THREE.Vector3();
    }

    renderScene() {
        if (!this.scene || !this.threeLoaded) return;

        this.rackMeshes.forEach(obj => { if (obj.parent) obj.parent.remove(obj); });
        this.rackMeshes = [];
        this.labelObjects.forEach(obj => { if (obj.parent) obj.parent.remove(obj); });
        this.labelObjects = [];
        this._ghostSlot = null;

        this.drawFloor();

        const q = (this.state.searchQuery || "").toLowerCase().trim();
        const whFilter = this.state.selectedWarehouse
            ? parseInt(this.state.selectedWarehouse, 10)
            : null;

        const filtered = this.state.locations.filter(loc => {
            if (whFilter !== null) {
                const locWh = loc.warehouse_id || 0;
                if (locWh !== whFilter) return false;
            }
            return true;
        });

        const locations = filtered.map(loc => {
            let labelMatch = false;
            if (q) {
                const locName = (loc.name || '').toLowerCase();
                const code = (loc.code_3d || '').toLowerCase();
                const complete = (loc.complete_name || '').toLowerCase();
                const whName = (loc.warehouse_name || '').toLowerCase();

                if (locName.includes(q) || code.includes(q)
                    || complete.includes(q) || whName.includes(q)) {
                    labelMatch = true;
                }
            }
            return Object.assign({}, loc, { _searchMatch: labelMatch });
        });

        const groups = {};
        locations.forEach(loc => {
            const wid = loc.warehouse_id || 0;
            if (!groups[wid]) {
                groups[wid] = {
                    wid: wid,
                    name: loc.warehouse_name || 'Unassigned',
                    racks: [],
                };
            }
            groups[wid].racks.push(loc);
        });

        this._warehouseOffsets = this._computeWarehouseOffsets(groups);

        Object.entries(groups).forEach(([wid, group]) => {
            const off = this._warehouseOffsets[wid] || { dx: 0, dz: 0 };
            this.drawWarehouseBox(group.racks, group.name, off);
            group.racks.forEach(loc => this.drawRack(loc, off));
        });

        this.state.filteredLocations = locations;
        this.fitCamera();
        this.animate();
    }

    _computeWarehouseOffsets(groups) {
        const entries = Object.entries(groups);
        const out = {};

        if (entries.length <= 1) {
            entries.forEach(([wid]) => out[wid] = { dx: 0, dz: 0 });
            return out;
        }

        const items = entries.map(([wid, group]) => {
            let minX = Infinity, maxX = -Infinity;
            let minZ = Infinity, maxZ = -Infinity;
            group.racks.forEach(loc => {
                const L = loc.rack_length || 3;
                const W = loc.rack_width || 1.2;
                const px = (this.pendingRackMoves[loc.id] || {}).pos_x ?? loc.pos_x;
                const pz = (this.pendingRackMoves[loc.id] || {}).pos_z ?? loc.pos_z;
                minX = Math.min(minX, px - L / 2);
                maxX = Math.max(maxX, px + L / 2);
                minZ = Math.min(minZ, pz - W / 2);
                maxZ = Math.max(maxZ, pz + W / 2);
            });
            return { wid, minX, maxX, minZ, maxZ };
        });

        items.sort((a, b) => a.minX - b.minX);

        const GAP = 4.0;
        let cursorX = null;

        items.forEach(item => {
            if (cursorX === null) {
                out[item.wid] = { dx: 0, dz: 0 };
                cursorX = item.maxX + GAP;
            } else {
                if (item.minX < cursorX) {
                    const shift = cursorX - item.minX;
                    out[item.wid] = { dx: shift, dz: 0 };
                    cursorX = item.maxX + shift + GAP;
                } else {
                    out[item.wid] = { dx: 0, dz: 0 };
                    cursorX = item.maxX + GAP;
                }
            }
        });

        return out;
    }

    drawFloor() {
        return;
    }

    drawWarehouseBox(racks, name, offset = { dx: 0, dz: 0 }) {
        if (!racks || racks.length === 0) return;

        const ox = offset.dx || 0;
        const oz = offset.dz || 0;

        let minX = Infinity, maxX = -Infinity;
        let minZ = Infinity, maxZ = -Infinity;

        racks.forEach(loc => {
            const L = loc.rack_length || 3;
            const W = loc.rack_width || 1.2;
            const px = ((this.pendingRackMoves[loc.id] || {}).pos_x ?? loc.pos_x) + ox;
            const pz = ((this.pendingRackMoves[loc.id] || {}).pos_z ?? loc.pos_z) + oz;
            minX = Math.min(minX, px - L / 2);
            maxX = Math.max(maxX, px + L / 2);
            minZ = Math.min(minZ, pz - W / 2);
            maxZ = Math.max(maxZ, pz + W / 2);
        });

        const pad = 1.8;
        minX -= pad; maxX += pad;
        minZ -= pad; maxZ += pad;

        const w = maxX - minX;
        const d = maxZ - minZ;
        const cx = (minX + maxX) / 2;
        const cz = (minZ + maxZ) / 2;

        const floorGeo = new THREE.PlaneGeometry(w, d);
        const floorMat = new THREE.MeshBasicMaterial({
            color: 0xffffff,
            transparent: true,
            opacity: 0.75,
            side: THREE.DoubleSide,
            depthWrite: false,
        });
        const floor = new THREE.Mesh(floorGeo, floorMat);
        floor.rotation.x = -Math.PI / 2;
        floor.position.set(cx, 0.01, cz);
        floor.renderOrder = -10;
        this.scene.add(floor);
        this.rackMeshes.push(floor);

        this.addWarehouseLabel(name, cx, 4.8, cz);
    }

    addWarehouseLabel(text, x, y, z) {
        if (!this.threeLoaded || !window.THREE) return;

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = 640;
        canvas.height = 96;
        const w = canvas.width, h = canvas.height, r = 22;

        const grad = ctx.createLinearGradient(0, 0, w, 0);
        grad.addColorStop(0, 'rgba(124, 58, 237, 0.95)');
        grad.addColorStop(1, 'rgba(37, 99, 235, 0.95)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(r, 0); ctx.lineTo(w - r, 0);
        ctx.quadraticCurveTo(w, 0, w, r);
        ctx.lineTo(w, h - r); ctx.quadraticCurveTo(w, h, w - r, h);
        ctx.lineTo(r, h); ctx.quadraticCurveTo(0, h, 0, h - r);
        ctx.lineTo(0, r); ctx.quadraticCurveTo(0, 0, r, 0);
        ctx.closePath(); ctx.fill();

        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        let fontSize = 44;
        ctx.font = `bold ${fontSize}px Arial, sans-serif`;
        while (ctx.measureText(text).width > w - 40 && fontSize > 16) {
            fontSize -= 2;
            ctx.font = `bold ${fontSize}px Arial, sans-serif`;
        }

        let displayText = text;
        if (ctx.measureText(displayText).width > w - 40) {
            while (displayText.length > 3
                   && ctx.measureText(displayText + '...').width > w - 40) {
                displayText = displayText.slice(0, -1);
            }
            displayText += '...';
        }

        ctx.fillText(displayText, w / 2, h / 2 + 2);

        const tex = new THREE.CanvasTexture(canvas);
        tex.needsUpdate = true;
        const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
            map: tex, transparent: true, depthTest: false, depthWrite: false,
        }));
        sprite.position.set(x, y, z);

        const aspect = canvas.width / canvas.height;
        sprite.scale.set(0.55 * aspect, 0.55, 1);
        sprite.renderOrder = 20;
        this.scene.add(sprite);
        this.labelObjects.push(sprite);
    }

    async onWarehouseChange(ev) {
        this.state.selectedWarehouse = ev.target.value || "";
        this.renderScene();

        if (this.state.addPanelOpen && !this.state.editMode) {
            await this._reloadAvailableLocations();
        }
    }

    async _reloadAvailableLocations() {
        try {
            const locations = await this.orm.call(
                "stock.location", "get_available_locations_for_3d", []
            );

            const selWh = this.state.selectedWarehouse
                ? parseInt(this.state.selectedWarehouse, 10)
                : null;
            const available = (locations || []).filter(l => {
                if (l.show_in_3d) return false;
                if (selWh !== null && (l.warehouse_id || 0) !== selWh) return false;
                return true;
            });
            this.state.availableLocations = available;

            const groups = {};
            available.forEach(loc => {
                const wid = loc.warehouse_id || 0;
                const wname = loc.warehouse_name || 'Unassigned';
                if (!groups[wid]) {
                    groups[wid] = { wid: wid, name: wname, locations: [] };
                }
                groups[wid].locations.push(loc);
            });
            this.state.availableLocationsGrouped = Object.values(groups);

            // Jo selected location have list ma nathi, to reset karo
            const currentId = parseInt(this.state.newRack.locationId, 10);
            if (currentId && !available.some(l => l.id === currentId)) {
                this.state.newRack.locationId = '';
            }
        } catch (e) {
            console.error("Reload locations error:", e);
        }
    }

    drawRack(loc, offset = { dx: 0, dz: 0 }) {
        const group = new THREE.Group();
        const heatmapOn = this.state.heatmapEnabled;
        const status = this.getRackStatus(loc);

        let uprightHex, beamHex, slatHex;
        if (heatmapOn) {
            const baseHex = parseInt(status.color.replace('#', ''), 16);
            const baseColor = new THREE.Color(baseHex);
            uprightHex = baseColor.clone().multiplyScalar(0.75).getHex();
            beamHex = baseHex;
            slatHex = baseColor.clone().lerp(new THREE.Color(0xffffff), 0.45).getHex();
        } else {
            uprightHex = hexToInt(loc.color_upright, 0x4F6489);
            beamHex = hexToInt(loc.color_beam, 0xF4C842);
            slatHex = hexToInt(loc.color_slat, 0xD5D5D5);
        }

        const uprightMat = new THREE.MeshStandardMaterial({
            color: uprightHex, metalness: 0.15, roughness: 0.65 });
        const beamMat = new THREE.MeshStandardMaterial({
            color: beamHex, metalness: 0.1, roughness: 0.55 });
        const slatMat = new THREE.MeshStandardMaterial({
            color: slatHex, metalness: 0.05, roughness: 0.85 });

        const L = loc.rack_length || 3.0;
        const W = loc.rack_width || 1.2;
        const H = loc.rack_height || 3.0;
        const levels = Math.max(1, loc.shelf_levels || 5);
        const bins = Math.max(1, loc.bins_per_level || 3);
        const postW = 0.09;
        const postD = postW * 0.8;
        const beamH = loc.beam_height || 0.16;
        const beamD = 0.05;
        const slatH = 0.025;
        const braceT = 0.035;

        const frameCount = bins + 1;
        const frameSpacing = L / bins;
        for (let i = 0; i < frameCount; i++) {
            const xPos = -L / 2 + i * frameSpacing;
            const fp = new THREE.Mesh(new THREE.BoxGeometry(postW, H, postD), uprightMat);
            fp.position.set(xPos, H / 2, W / 2 - postD / 2);
            fp.castShadow = true; fp.receiveShadow = true;
            group.add(fp);

            const bp = new THREE.Mesh(new THREE.BoxGeometry(postW, H, postD), uprightMat);
            bp.position.set(xPos, H / 2, -W / 2 + postD / 2);
            bp.castShadow = true; bp.receiveShadow = true;
            group.add(bp);

            [0.06, H - 0.06].forEach(y => {
                const tie = new THREE.Mesh(
                    new THREE.BoxGeometry(postW * 0.7, braceT, W - postD),
                    uprightMat
                );
                tie.position.set(xPos, y, 0);
                group.add(tie);
            });
        }

        [-L / 2, L / 2].forEach(xPos => {
            const spanZ = W - postD * 2;
            const spanY = H - 0.2;
            const diagLen = Math.sqrt(spanZ * spanZ + spanY * spanY);
            const diagAngle = Math.atan2(spanZ, spanY);
            const d1 = new THREE.Mesh(new THREE.BoxGeometry(braceT, diagLen, braceT), uprightMat);
            d1.position.set(xPos, H / 2, 0); d1.rotation.x = diagAngle;
            group.add(d1);
            const d2 = new THREE.Mesh(new THREE.BoxGeometry(braceT, diagLen, braceT), uprightMat);
            d2.position.set(xPos, H / 2, 0); d2.rotation.x = -diagAngle;
            group.add(d2);
        });

        const levelYs = [];
        const bottomY = 0.15 + beamH / 2;
        const topY = H - 0.15 - beamH / 2;
        const usable = topY - bottomY;
        const step = levels > 1 ? usable / (levels - 1) : 0;

        for (let i = 0; i < levels; i++) {
            const y = bottomY + i * step;
            levelYs.push(y);

            [W / 2 - beamD / 2 - postD / 2 + 0.02,
             -W / 2 + beamD / 2 + postD / 2 - 0.02].forEach(z => {
                const beam = new THREE.Mesh(new THREE.BoxGeometry(L, beamH, beamD), beamMat);
                beam.position.set(0, y, z);
                beam.castShadow = true; beam.receiveShadow = true;
                group.add(beam);
            });

            const innerW = W - 2 * postD - beamD;
            if (innerW > 0.05) {
                const slatCount = Math.max(8, Math.floor(L * 7));
                const slatSpacing = L / slatCount;
                const slatWidth = slatSpacing * 0.5;
                for (let s = 0; s < slatCount; s++) {
                    const sx = -L / 2 + slatSpacing * (s + 0.5);
                    const slat = new THREE.Mesh(
                        new THREE.BoxGeometry(slatWidth, slatH, innerW),
                        slatMat
                    );
                    slat.position.set(sx, y + beamH / 2 - slatH / 2 - 0.001, 0);
                    slat.castShadow = true; slat.receiveShadow = true;
                    group.add(slat);
                }
            }
        }

        this.renderSlotBoxes(group, loc, levelYs, L, W, bins, beamH);

        const catcher = new THREE.Mesh(
            new THREE.BoxGeometry(L + 0.1, H + 0.1, W + 0.1),
            new THREE.MeshBasicMaterial({
                transparent: true, opacity: 0.0, depthWrite: false,
            })
        );
        catcher.position.set(0, H / 2, 0);
        catcher.userData = {
            type: 'rack', locationId: loc.id, isClickCatcher: true,
        };
        catcher.renderOrder = -1;
        group.add(catcher);

        const pending = this.pendingRackMoves[loc.id];
        const px = pending ? pending.pos_x : loc.pos_x;
        const pz = pending ? pending.pos_z : loc.pos_z;

        const ox = offset.dx || 0;
        const oz = offset.dz || 0;

        group.position.set(px + ox, loc.pos_y, pz + oz);
        group.rotation.y = (loc.rotation_y || 0) * (Math.PI / 180);
        group.userData = { type: 'rack', locationId: loc.id };

        this.scene.add(group);
        this.rackMeshes.push(group);

        this.addLabel(loc, 0, H + 1.0, 0, group, !!loc._searchMatch);
    }

    renderSlotBoxes(rackGroup, loc, levelYs, L, W, bins, beamH) {
        const binWidth = L / bins;
        const boxW = Math.min(binWidth * 0.55, 0.42);
        const boxH = 0.20;
        const boxD = Math.min(W * 0.55, 0.45);
        const boxGap = 0.02;
        const defaultColor = hexToInt(loc.color_box, 0xE8C89A);

        const slots = loc.slots || [];
        const searchQ = (this.state.searchQuery || "").toLowerCase().trim();

        const seenQids = new Set();
        const allProducts = [];

        slots.forEach(s => {
            (s.products || []).forEach(p => {
                const qid = p.quant_id || `p-${p.id}`;
                if (seenQids.has(qid)) return;
                seenQids.add(qid);
                allProducts.push({
                    ...p,
                    srcLevel: s.level ?? 0,
                    srcBin: s.bin ?? 0,
                    srcName: s.location_name || s.complete_name || loc.name,
                });
            });
        });

        (loc.products || []).forEach(p => {
            const qid = p.quant_id || `p-${p.id}`;
            if (seenQids.has(qid)) return;
            seenQids.add(qid);
            allProducts.push({
                ...p,
                srcLevel: 0,
                srcBin: 0,
                srcName: loc.code_3d || loc.name,
            });
        });

        if (allProducts.length === 0) return;

        const totalLevels = levelYs.length;
        const step = totalLevels > 1
            ? (levelYs[totalLevels - 1] - levelYs[0]) / (totalLevels - 1)
            : (loc.rack_height || 3.0);
        const maxStackPerLevel = {};
        for (let lvl = 0; lvl < totalLevels; lvl++) {
            const space = step - beamH - 0.04;
            maxStackPerLevel[lvl] = Math.max(
                1, Math.floor(space / (boxH + boxGap))
            );
        }

        const filledCells = new Set();
        const fillOrder = [];
        for (let lvl = 0; lvl < totalLevels; lvl++) {
            for (let b = 0; b < bins; b++) {
                fillOrder.push({ level: lvl, bin: b });
            }
        }

        const bySource = new Map();
        allProducts.forEach(p => {
            const key = `${p.srcLevel},${p.srcBin}`;
            if (!bySource.has(key)) bySource.set(key, []);
            bySource.get(key).push(p);
        });

        bySource.forEach((products, key) => {
            const [srcLvl, srcBin] = key.split(',').map(Number);

            let idx = fillOrder.findIndex(f => f.level === srcLvl && f.bin === srcBin);
            if (idx < 0) idx = 0;

            let p = 0;
            while (p < products.length && idx < fillOrder.length) {
                const { level, bin } = fillOrder[idx];
                const cellKey = `${level},${bin}`;
                idx++;

                if (filledCells.has(cellKey)) continue;

                const maxS = maxStackPerLevel[level];
                const batch = products.slice(p, p + maxS);
                p += batch.length;

                if (batch.length === 0) continue;
                filledCells.add(cellKey);

                const xPos = -L / 2 + binWidth * (bin + 0.5);
                const yBase = levelYs[level] + beamH / 2 + boxH / 2 + 0.02;

                let topMostBox = null;
                let topMostY = -Infinity;
                let labelName = batch[0].srcName || loc.name;

                batch.forEach((prod, pIdx) => {
                    const color = hexToInt(prod.color, defaultColor);
                    const isMatch = searchQ && (prod.name || "").toLowerCase().includes(searchQ);
                    const size = isMatch ? 1.18 : 1.0;
                    const boxMat = isMatch
                        ? new THREE.MeshStandardMaterial({
                            color: 0xffd700, emissive: 0xffa500, emissiveIntensity: 0.85,
                            roughness: 0.35, metalness: 0.4,
                        })
                        : new THREE.MeshStandardMaterial({
                            color, roughness: 0.7, metalness: 0.05,
                        });

                    const box = new THREE.Mesh(
                        new THREE.BoxGeometry(boxW * size, boxH * size, boxD * size),
                        boxMat
                    );
                    const yOffset = yBase + pIdx * (boxH + boxGap);
                    box.position.set(xPos, yOffset, 0);
                    box.castShadow = true; box.receiveShadow = true;
                    box.userData = {
                        type: 'product',
                        productId: prod.id,
                        quantId: prod.quant_id,
                        product_name: prod.name,
                        quantity: prod.qty,
                        locationId: loc.id,
                        location_name: prod.srcName || loc.name,
                        slotLevel: level,
                        slotBin: bin,
                        rackId: loc.id,
                        rackGroup: rackGroup,
                        boxW, boxH, boxD, binWidth,
                        isMatch: isMatch,
                        initialPos: box.position.clone(),
                    };
                    rackGroup.add(box);

                    if (yOffset > topMostY) {
                        topMostY = yOffset;
                        topMostBox = box;
                        labelName = prod.srcName || labelName;
                    }
                });

                if (topMostBox) {
                    const labelSprite = this.addSlotLabelToBox(topMostBox, labelName, boxH);
                    if (labelSprite) topMostBox.userData.labelSprite = labelSprite;
                }
            }
        });
    }

    addSlotLabel(parentGroup, text, x, y, z, binWidth, occupied) {
        if (!this.threeLoaded || !window.THREE || !text) return null;
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = 320; canvas.height = 96;
        const w = canvas.width, h = canvas.height, r = 22;

        ctx.fillStyle = 'rgba(15, 23, 42, 0.90)';
        ctx.beginPath();
        ctx.moveTo(r, 0); ctx.lineTo(w - r, 0);
        ctx.quadraticCurveTo(w, 0, w, r);
        ctx.lineTo(w, h - r); ctx.quadraticCurveTo(w, h, w - r, h);
        ctx.lineTo(r, h); ctx.quadraticCurveTo(0, h, 0, h - r);
        ctx.lineTo(0, r); ctx.quadraticCurveTo(0, 0, r, 0);
        ctx.closePath(); ctx.fill();

        ctx.strokeStyle = occupied ? 'rgba(34,197,94,0.55)' : 'rgba(255,255,255,0.18)';
        ctx.lineWidth = 3; ctx.stroke();

        ctx.beginPath();
        ctx.arc(30, h / 2, 10, 0, Math.PI * 2);
        ctx.fillStyle = occupied ? '#22c55e' : '#9ca3af';
        if (occupied) { ctx.shadowColor = '#22c55e'; ctx.shadowBlur = 12; }
        ctx.fill(); ctx.shadowBlur = 0;

        const maxTextWidth = w - 58;
        let fontSize = 34;
        ctx.textBaseline = 'middle';
        ctx.fillStyle = '#ffffff';
        let displayText = text;
        ctx.font = `600 ${fontSize}px Arial, sans-serif`;
        while (ctx.measureText(displayText).width > maxTextWidth && fontSize > 18) {
            fontSize -= 2;
            ctx.font = `600 ${fontSize}px Arial, sans-serif`;
        }
        ctx.fillText(displayText, 54, h / 2 + 1);

        const tex = new THREE.CanvasTexture(canvas);
        tex.needsUpdate = true;
        const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
            map: tex, transparent: true, depthTest: false, depthWrite: false,
        }));
        sprite.position.set(x, y, z);
        const aspect = canvas.width / canvas.height;
        const targetWidth = Math.min(binWidth * 0.60, 0.70);
        sprite.scale.set(targetWidth, targetWidth / aspect, 1);
        sprite.renderOrder = 2;
        parentGroup.add(sprite);
        this.labelObjects.push(sprite);
        return sprite;
    }

    addSlotLabelToBox(boxMesh, text, boxH) {
        if (!this.threeLoaded || !window.THREE || !text) return null;
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = 320; canvas.height = 96;
        const w = canvas.width, h = canvas.height, r = 22;

        ctx.fillStyle = 'rgba(15, 23, 42, 0.90)';
        ctx.beginPath();
        ctx.moveTo(r, 0); ctx.lineTo(w - r, 0);
        ctx.quadraticCurveTo(w, 0, w, r);
        ctx.lineTo(w, h - r); ctx.quadraticCurveTo(w, h, w - r, h);
        ctx.lineTo(r, h); ctx.quadraticCurveTo(0, h, 0, h - r);
        ctx.lineTo(0, r); ctx.quadraticCurveTo(0, 0, r, 0);
        ctx.closePath(); ctx.fill();
        ctx.strokeStyle = 'rgba(34,197,94,0.55)';
        ctx.lineWidth = 3; ctx.stroke();

        ctx.beginPath();
        ctx.arc(30, h / 2, 10, 0, Math.PI * 2);
        ctx.fillStyle = '#22c55e';
        ctx.shadowColor = '#22c55e';
        ctx.shadowBlur = 12;
        ctx.fill(); ctx.shadowBlur = 0;

        const maxTextWidth = w - 58;
        let fontSize = 34;
        ctx.textBaseline = 'middle';
        ctx.fillStyle = '#ffffff';
        let displayText = text;
        ctx.font = `600 ${fontSize}px Arial, sans-serif`;
        while (ctx.measureText(displayText).width > maxTextWidth && fontSize > 18) {
            fontSize -= 2;
            ctx.font = `600 ${fontSize}px Arial, sans-serif`;
        }
        ctx.fillText(displayText, 54, h / 2 + 1);

        const tex = new THREE.CanvasTexture(canvas);
        tex.needsUpdate = true;
        const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
            map: tex, transparent: true, depthTest: false, depthWrite: false,
        }));
        sprite.position.set(0, boxH / 2 + 0.14, 0);
        const aspect = canvas.width / canvas.height;
        const targetWidth = 0.50;
        sprite.scale.set(targetWidth, targetWidth / aspect, 1);
        sprite.renderOrder = 10;
        boxMesh.add(sprite);
        this.labelObjects.push(sprite);
        return sprite;
    }

    addLabel(loc, x, y, z, parentGroup, isMatch = false) {
        if (!this.threeLoaded || !window.THREE) return;
        const status = this.getRackStatus(loc);
        const codeText = loc.code_3d || loc.name;
        const hasCap = loc.capacity > 0 && loc.fill_percentage != null;
        const pctText = hasCap ? `${Math.round(loc.fill_percentage)}%` : "-";
        const mainText = `${codeText}  ${pctText}`;

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = 768; canvas.height = 128;
        const w = canvas.width, h = canvas.height, r = 30;

        ctx.fillStyle = isMatch ? 'rgba(255, 196, 0, 0.95)' : 'rgba(0,0,0,0.80)';
        ctx.beginPath();
        ctx.moveTo(r, 0); ctx.lineTo(w - r, 0);
        ctx.quadraticCurveTo(w, 0, w, r);
        ctx.lineTo(w, h - r); ctx.quadraticCurveTo(w, h, w - r, h);
        ctx.lineTo(r, h); ctx.quadraticCurveTo(0, h, 0, h - r);
        ctx.lineTo(0, r); ctx.quadraticCurveTo(0, 0, r, 0);
        ctx.closePath(); ctx.fill();

        if (isMatch) {
            ctx.strokeStyle = '#ff8a00';
            ctx.lineWidth = 5;
            ctx.stroke();
        }

        ctx.beginPath();
        ctx.arc(40, h / 2, 14, 0, Math.PI * 2);
        ctx.fillStyle = status.color;
        ctx.shadowColor = status.color;
        ctx.shadowBlur = 12; ctx.fill(); ctx.shadowBlur = 0;

        ctx.fillStyle = isMatch ? '#1a1a1a' : '#ffffff';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        const maxWidth = w - 95;
        let fontSize = 46;
        ctx.font = `bold ${fontSize}px Arial, sans-serif`;
        while (ctx.measureText(mainText).width > maxWidth && fontSize > 22) {
            fontSize -= 2;
            ctx.font = `bold ${fontSize}px Arial, sans-serif`;
        }
        ctx.fillText(mainText, 70, h / 2 + 2);

        const tex = new THREE.CanvasTexture(canvas);
        tex.needsUpdate = true;
        const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
            map: tex, transparent: true, depthTest: false, depthWrite: false,
        }));
        sprite.position.set(x, y, z);
        const aspect = canvas.width / canvas.height;
        sprite.scale.set(0.55 * aspect, 0.55, 1);

        if (parentGroup) {
            parentGroup.add(sprite);
        } else {
            this.scene.add(sprite);
        }
        this.labelObjects.push(sprite);
    }

    getRackStatus(loc) {
        const cap = loc.capacity, pct = loc.fill_percentage;
        if (!cap || cap <= 0 || pct == null) return { color: STATUS_COLORS.noCapacity };
        if (pct <= 0) return { color: STATUS_COLORS.empty };
        if (pct >= 100) return { color: STATUS_COLORS.overloaded };
        if (pct >= 80) return { color: STATUS_COLORS.almostFull };
        return { color: STATUS_COLORS.inUse };
    }

    collectProducts(node) {
        const map = {};
        const walk = (n) => {
            (n.products || []).forEach(p => {
                if (!map[p.id]) map[p.id] = { id: p.id, name: p.name, qty: 0, color: p.color };
                map[p.id].qty += (p.qty || 0);
            });
            (n.children || []).forEach(walk);
        };
        walk(node);
        return Object.values(map);
    }

    createForklift() {
        if (!window.THREE || !window.THREE.GLTFLoader) return;
        const loader = new THREE.GLTFLoader();
        loader.load('/ipredict_stock_3d_view/static/src/models/Gabelstapler.glb', (gltf) => {
            this.forklift = gltf.scene;
            this.forklift.scale.set(0.12, 0.12, 0.12);
            this.forklift.position.set(0, 0.2, 0);
            this.scene.add(this.forklift);
        }, undefined, () => {});
    }

    createForkliftPath() {
        const points = [
            new THREE.Vector3(-8, 0.2, -8), new THREE.Vector3(-4, 0.2, -4),
            new THREE.Vector3(0, 0.2, 0), new THREE.Vector3(4, 0.2, -4),
            new THREE.Vector3(8, 0.2, -8), new THREE.Vector3(4, 0.2, -10),
            new THREE.Vector3(-4, 0.2, -10), new THREE.Vector3(-8, 0.2, -8),
        ];
        this.forkliftPath = new THREE.CatmullRomCurve3(points);
    }

    computeSceneBounds() {
        let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity, maxY = 0;
        const src = this.state.filteredLocations || this.state.locations;
        src.forEach(loc => {
            const L = loc.rack_length || 3, W = loc.rack_width || 1.2, H = loc.rack_height || 3;
            const off = this._warehouseOffsets[loc.warehouse_id || 0] || { dx: 0, dz: 0 };
            const px = ((this.pendingRackMoves[loc.id] || {}).pos_x ?? loc.pos_x) + (off.dx || 0);
            const pz = ((this.pendingRackMoves[loc.id] || {}).pos_z ?? loc.pos_z) + (off.dz || 0);
            minX = Math.min(minX, px - L / 2);
            maxX = Math.max(maxX, px + L / 2);
            minZ = Math.min(minZ, pz - W / 2);
            maxZ = Math.max(maxZ, pz + W / 2);
            maxY = Math.max(maxY, loc.pos_y + H);
        });
        if (!isFinite(minX)) return { centerX: 0, centerZ: 0, sizeX: 10, sizeZ: 10, maxY: 2 };
        return {
            centerX: (minX + maxX) / 2, centerZ: (minZ + maxZ) / 2,
            sizeX: Math.max(maxX - minX, 4), sizeZ: Math.max(maxZ - minZ, 4), maxY,
        };
    }

    fitCamera() {
        if (!this.camera) return;
        const b = this.computeSceneBounds();
        const dist = Math.max(Math.max(b.sizeX, b.sizeZ) * 1.4, 15);
        this.orbitTarget.set(b.centerX, Math.min(b.maxY / 2, 3), b.centerZ);
        this.camera.position.set(b.centerX + dist, dist * 0.55, b.centerZ + dist);
        this.camera.lookAt(this.orbitTarget);
    }

    animate() {
        this.animationFrame = requestAnimationFrame(() => this.animate());
        if (this.forklift && this.forkliftPath) {
            this.forkliftProgress += this.forkliftSpeed;
            if (this.forkliftProgress > 1) this.forkliftProgress = 0;
            const p = this.forkliftPath.getPoint(this.forkliftProgress);
            this.forklift.position.copy(p);
            const t = this.forkliftPath.getTangent(this.forkliftProgress);
            this.forklift.lookAt(p.clone().add(t));
        }
        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    }

    getMousePos(e) {
        const r = this.renderer.domElement.getBoundingClientRect();
        return {
            x: ((e.clientX - r.left) / r.width) * 2 - 1,
            y: -((e.clientY - r.top) / r.height) * 2 + 1,
        };
    }

    toggleEditRackMode() {
        if (this.state.editRackMode) {
            if (this.state.hasUnsavedChanges) {
                this.cancelLayoutChanges();
            }
            this.state.editRackMode = false;
        } else {
            this.state.editRackMode = true;
            this.state.addPanelOpen = false;
            this.state.selectedLocation = null;
            this.state.selectedProduct = null;
            this.notification.add(
                "Edit mode active — drag racks or boxes to reposition them.",
                { type: "info" }
            );
        }
        this.renderScene();
    }

    async saveLayoutChanges() {
        const rackEntries = Object.entries(this.pendingRackMoves);
        const boxMoves = this.pendingBoxMoves;
        const totalChanges = rackEntries.length + boxMoves.length;

        if (totalChanges === 0) {
            this.state.editRackMode = false;
            this.state.hasUnsavedChanges = false;
            this.notification.add("No pending changes to save.", { type: "info" });
            return;
        }

        try {
            for (const [rackId, move] of rackEntries) {
                await this.orm.call("stock.location", "action_move_rack_3d",
                    [parseInt(rackId, 10), move.pos_x, move.pos_z]);
            }
            for (const m of boxMoves) {
                await this.orm.call("stock.location", "action_move_box_3d",
                    [m.rackId, m.quantId, m.fromLevel, m.fromBin, m.toLevel, m.toBin]);
            }

            this.pendingRackMoves = {};
            this.pendingBoxMoves = [];
            this.state.hasUnsavedChanges = false;
            this.state.editRackMode = false;

            this.notification.add(
                `Layout saved successfully — ${totalChanges} change${totalChanges > 1 ? 's' : ''} applied.`,
                { type: "success" }
            );

            await this.loadData();
            this.renderScene();
        } catch (e) {
            console.error("Save layout error:", e);
            this.notification.add(
                e.message || "Could not save layout. Please try again.",
                { type: "danger" }
            );
        }
    }

    async cancelLayoutChanges() {
        this.pendingRackMoves = {};
        this.pendingBoxMoves = [];
        this.state.hasUnsavedChanges = false;
        this.notification.add("Layout changes discarded.", { type: "info" });
        await this.loadData();
        this.renderScene();
    }

    onMouseDown(e) {
        if (e.button !== 0) return;
        const pos = this.getMousePos(e);
        this.mouse.x = pos.x; this.mouse.y = pos.y;
        this.dragStartPos = { x: e.clientX, y: e.clientY };
        this.hasMoved = false;

        this.raycaster.setFromCamera(this.mouse, this.camera);
        const hits = this.raycaster.intersectObjects(this.rackMeshes, true);

        if (hits.length) {
            let productMesh = null;
            let rackData = null;

            for (const h of hits) {
                let obj = h.object;
                while (obj) {
                    if (obj.userData && obj.userData.type === 'product'
                        && obj.userData.slotLevel !== undefined) {
                        productMesh = obj;
                        break;
                    }
                    if (obj.userData && obj.userData.type === 'rack') {
                        rackData = obj.userData;
                    }
                    obj = obj.parent;
                }
                if (productMesh) break;
            }

            if (this.state.editRackMode) {
                if (productMesh) {
                    this._startBoxDrag(productMesh, e);
                    return;
                }
                if (rackData) {
                    this._startRackDrag(rackData, e);
                    return;
                }
            }

            if (productMesh) {
                const ud = productMesh.userData;
                this.state.selectedProduct = {
                    id: ud.productId,
                    name: ud.product_name,
                    quantity: ud.quantity,
                    location_name: ud.location_name,
                    slotLevel: ud.slotLevel,
                    slotBin: ud.slotBin,
                };
                this.state.selectedLocation = null;
                return;
            }

            if (rackData) {
                const loc = this.state.locations.find(l => l.id === rackData.locationId);
                if (loc) {
                    const allProducts = this.collectProducts(loc);
                    this.state.selectedLocation = { ...loc, products_info: allProducts };
                    this.state.selectedProduct = null;
                    this.state.productsExpanded = false;  
                    if (this._flyingTo) { this._flyingTo = false; this.state.flying = false; }
                    return;
                }
            }
        }

        this.state.selectedProduct = null;
        this.state.selectedLocation = null;
        this.isOrbiting = true;
        this.lastX = e.clientX;
        this.lastY = e.clientY;
    }

    _startBoxDrag(productMesh, e) {
        const ud = productMesh.userData;
        const rackLoc = this.state.locations.find(l => l.id === ud.rackId);
        if (!rackLoc) return;

        this.isDraggingBox = true;
        this.isOrbiting = false;
        this.draggedBox = productMesh;

        const camDir = new THREE.Vector3();
        this.camera.getWorldDirection(camDir);

        const boxWorldPos = new THREE.Vector3();
        productMesh.getWorldPosition(boxWorldPos);

        this.dragPlane.setFromNormalAndCoplanarPoint(camDir, boxWorldPos);

        const hitPoint = new THREE.Vector3();
        if (this.raycaster.ray.intersectPlane(this.dragPlane, hitPoint)) {
            this.dragOffset.set(
                boxWorldPos.x - hitPoint.x,
                boxWorldPos.y - hitPoint.y,
                boxWorldPos.z - hitPoint.z
            );
        } else {
            this.dragOffset.set(0, 0, 0);
        }

        productMesh.material.emissive = new THREE.Color(0x4444ff);
        productMesh.material.emissiveIntensity = 0.5;
        this.renderer.domElement.style.cursor = 'grabbing';

        e.preventDefault();
        e.stopPropagation();
    }

    _startRackDrag(rackData, e) {
        const loc = this.state.locations.find(l => l.id === rackData.locationId);
        if (!loc) return;

        let rackGroup = null;
        for (const obj of this.rackMeshes) {
            if (obj.userData && obj.userData.type === 'rack'
                && obj.userData.locationId === loc.id) {
                rackGroup = obj;
                break;
            }
        }
        if (!rackGroup) return;

        this.isDraggingRack = true;
        this.isOrbiting = false;
        this.draggedRackGroup = rackGroup;
        this.draggedRackLoc = loc;

        if (!this.dragRackOffset) this.dragRackOffset = new THREE.Vector3();
        const hitPoint = new THREE.Vector3();
        if (this.raycaster.ray.intersectPlane(this.dragRackPlane, hitPoint)) {
            this.dragRackOffset.set(
                hitPoint.x - rackGroup.position.x,
                0,
                hitPoint.z - rackGroup.position.z
            );
        } else {
            this.dragRackOffset.set(0, 0, 0);
        }
        this.renderer.domElement.style.cursor = 'move';
    }

    onMouseMove(e) {
        if (Math.hypot(e.clientX - this.dragStartPos.x,
                       e.clientY - this.dragStartPos.y) > 5) {
            this.hasMoved = true;
        }

        if (this.isDraggingRack && this.draggedRackGroup) {
            if (!this.dragRackOffset) this.dragRackOffset = new THREE.Vector3();
            const pos = this.getMousePos(e);
            this.mouse.x = pos.x; this.mouse.y = pos.y;
            this.raycaster.setFromCamera(this.mouse, this.camera);

            const hitPoint = new THREE.Vector3();
            if (this.raycaster.ray.intersectPlane(this.dragRackPlane, hitPoint)) {
                const newX = hitPoint.x - this.dragRackOffset.x;
                const newZ = hitPoint.z - this.dragRackOffset.z;
                this.draggedRackGroup.position.x = newX;
                this.draggedRackGroup.position.z = newZ;
            }
            e.preventDefault();
            return;
        }

        if (this.isDraggingBox && this.draggedBox && this.draggedBox.position) {
            const pos = this.getMousePos(e);
            this.mouse.x = pos.x; this.mouse.y = pos.y;
            this.raycaster.setFromCamera(this.mouse, this.camera);

            const ud = this.draggedBox.userData;
            const rackLoc = this.state.locations.find(l => l.id === ud.rackId);
            if (!rackLoc) return;

            const hitPoint = new THREE.Vector3();
            if (this.raycaster.ray.intersectPlane(this.dragPlane, hitPoint)) {
                const newWorldX = hitPoint.x + this.dragOffset.x;
                const newWorldY = hitPoint.y + this.dragOffset.y;

                const off = this._warehouseOffsets[rackLoc.warehouse_id || 0] || { dx: 0, dz: 0 };
                const localX = newWorldX - (rackLoc.pos_x + (off.dx || 0));
                const localY = newWorldY - rackLoc.pos_y;

                this.draggedBox.position.x = localX;
                this.draggedBox.position.y = localY;

                const L = rackLoc.rack_length || 3;
                const H = rackLoc.rack_height || 3;
                const bins = rackLoc.bins_per_level || 3;
                const levels = rackLoc.shelf_levels || 3;
                const binWidth = L / bins;
                const beamH = rackLoc.beam_height || 0.16;

                let nearestBin = Math.round((localX + L / 2 - binWidth / 2) / binWidth);
                nearestBin = Math.max(0, Math.min(bins - 1, nearestBin));

                const bottomY = 0.15 + beamH / 2;
                const topY = H - 0.15 - beamH / 2;
                const levelStep = levels > 1 ? (topY - bottomY) / (levels - 1) : 0;
                let nearestLevel = Math.round((localY - bottomY) / levelStep);
                nearestLevel = Math.max(0, Math.min(levels - 1, nearestLevel));

                const snapX = -L / 2 + binWidth * (nearestBin + 0.5);
                const snapY = bottomY + nearestLevel * levelStep + beamH / 2 + ud.boxH / 2 + 0.02;
                this._updateGhostSlot(ud.rackGroup, snapX, snapY, ud);

                this.pendingBoxMove = {
                    rackId: ud.rackId,
                    quantId: ud.quantId,
                    fromLevel: ud.slotLevel,
                    fromBin: ud.slotBin,
                    toLevel: nearestLevel,
                    toBin: nearestBin,
                    displayName: ud.location_name,
                    locationId: ud.locationId,
                };
            }
            e.preventDefault();
            return;
        }

        if (this.isOrbiting) {
            const dx = (e.clientX - this.lastX) * 0.005;
            const dy = (e.clientY - this.lastY) * 0.005;
            this.lastX = e.clientX; this.lastY = e.clientY;

            const t = this.orbitTarget;
            const radius = this.camera.position.distanceTo(t);
            const theta = Math.atan2(this.camera.position.x - t.x, this.camera.position.z - t.z) + dx;
            let phi = Math.acos((this.camera.position.y - t.y) / radius) + dy;
            phi = Math.max(0.1, Math.min(Math.PI / 2 - 0.05, phi));

            this.camera.position.x = t.x + radius * Math.sin(phi) * Math.sin(theta);
            this.camera.position.y = t.y + radius * Math.cos(phi);
            this.camera.position.z = t.z + radius * Math.sin(phi) * Math.cos(theta);
            this.camera.lookAt(t);
        }
    }

    _updateGhostSlot(rackGroup, x, y, ud) {
        if (!this._ghostSlot) {
            const geo = new THREE.BoxGeometry(ud.boxW * 1.15, ud.boxH * 1.15, ud.boxD * 1.15);
            const mat = new THREE.MeshBasicMaterial({
                color: 0xf59e0b, transparent: true, opacity: 0.55, depthWrite: false,
            });
            this._ghostSlot = new THREE.Mesh(geo, mat);
            this._ghostSlot.renderOrder = 5;
        }
        this._ghostSlot.position.set(x, y, 0);
        if (!this._ghostSlot.parent) rackGroup.add(this._ghostSlot);
    }

    onMouseUp() {
        if (this.isDraggingRack && this.draggedRackGroup) {
            const group = this.draggedRackGroup;
            const loc = this.draggedRackLoc;
            const moved = this.hasMoved;

            this.isDraggingRack = false;
            this.draggedRackGroup = null;
            this.draggedRackLoc = null;
            this.renderer.domElement.style.cursor = 'grab';
            this.hasMoved = false;

            if (!moved || !loc) {
                if (loc) {
                    const allProducts = this.collectProducts(loc);
                    this.state.selectedLocation = { ...loc, products_info: allProducts };
                    this.state.selectedProduct = null;
                    this.state.productsExpanded = false;   
                }
                return;
            }
            const off = this._warehouseOffsets[loc.warehouse_id || 0] || { dx: 0, dz: 0 };
            const newX = Number((group.position.x - (off.dx || 0)).toFixed(3));
            const newZ = Number((group.position.z - (off.dz || 0)).toFixed(3));

            this.pendingRackMoves[loc.id] = { pos_x: newX, pos_z: newZ };
            this.state.hasUnsavedChanges = true;

            this.notification.add(
                `Rack "${loc.name}" repositioned to X:${newX.toFixed(1)} · Z:${newZ.toFixed(1)}`,
                { type: "info" }
            );
            return;
        }

        if (this.isDraggingBox && this.draggedBox) {
            const boxMesh = this.draggedBox;
            const move = this.pendingBoxMove;
            const ud = { ...boxMesh.userData };
            const rackLoc = this.state.locations.find(l => l.id === ud.rackId);

            if (boxMesh.material) {
                boxMesh.material.emissive = new THREE.Color(0x000000);
                boxMesh.material.emissiveIntensity = 0;
            }
            this.renderer.domElement.style.cursor = 'grab';

            if (this._ghostSlot && this._ghostSlot.parent) {
                this._ghostSlot.parent.remove(this._ghostSlot);
            }
            this._ghostSlot = null;

            this.draggedBox = null;
            this.isDraggingBox = false;
            this.pendingBoxMove = null;

            if (!this.hasMoved) {
                this.hasMoved = false;
                if (boxMesh && boxMesh.position) {
                    boxMesh.position.copy(ud.initialPos);
                }
                return;
            }

            this.hasMoved = false;

            if (!move || !rackLoc
                || (move.fromLevel === move.toLevel && move.fromBin === move.toBin)) {
                if (boxMesh && boxMesh.position) {
                    boxMesh.position.copy(ud.initialPos);
                }
                return;
            }

            const L = rackLoc.rack_length || 3;
            const H = rackLoc.rack_height || 3;
            const bins = rackLoc.bins_per_level || 3;
            const levels = rackLoc.shelf_levels || 3;
            const binWidth = L / bins;
            const beamH = rackLoc.beam_height || 0.16;
            const bottomY = 0.15 + beamH / 2;
            const topY = H - 0.15 - beamH / 2;
            const levelStep = levels > 1 ? (topY - bottomY) / (levels - 1) : 0;

            if (boxMesh && boxMesh.position) {
                boxMesh.position.x = -L / 2 + binWidth * (move.toBin + 0.5);
                boxMesh.position.y = bottomY + move.toLevel * levelStep + beamH / 2 + ud.boxH / 2 + 0.02;
            }

            this.pendingBoxMoves.push({
                rackId: move.rackId,
                quantId: move.quantId,
                fromLevel: move.fromLevel,
                fromBin: move.fromBin,
                toLevel: move.toLevel,
                toBin: move.toBin,
                locationId: move.locationId,
                displayName: move.displayName,
            });
            this.state.hasUnsavedChanges = true;

            this.notification.add(
                `"${move.displayName}" relocated to Level ${move.toLevel + 1} · Bin ${move.toBin + 1}`,
                { type: "info" }
            );
            return;
        }

        this.isOrbiting = false;
        this.hasMoved = false;
    }

    onWheel(e) {
        e.preventDefault();
        if (this.isDraggingBox || this.isDraggingRack) return;
        const t = this.orbitTarget;
        const r = this.camera.position.distanceTo(t);
        const nr = Math.max(2, Math.min(100, r + (e.deltaY > 0 ? 1 : -1)));
        const dir = this.camera.position.clone().sub(t).normalize();
        this.camera.position.copy(t).add(dir.multiplyScalar(nr));
        this.camera.lookAt(t);
    }

    onResize() {
        if (!this.camera || !this.renderer) return;
        const c = this.canvasRef.el;
        const w = c.clientWidth || window.innerWidth;
        const h = c.clientHeight || window.innerHeight;
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(w, h);
    }

    async toggleAddPanel() {
        this.state.addPanelOpen = !this.state.addPanelOpen;

        if (this.state.addPanelOpen) {
            if (!this.state.editMode) {
                this.state.selectedLocation = null;
                this.state.selectedProduct = null;
                this.state.newRack = { ...DEFAULT_NEW_RACK };

                await this._reloadAvailableLocations();

                if (this.state.availableLocations.length === 0) {
                    this.notification.add(
                        "No locations available for this warehouse.",
                        { type: "warning" }
                    );
                }
            }
        } else {
            this.state.editMode = false;
            this.state.editRackId = null;
            this.state.newRack = { ...DEFAULT_NEW_RACK };
        }
    }

    openEditPanel() {
        const loc = this.state.selectedLocation;
        if (!loc) {
            this.notification.add("No rack selected.", { type: "warning" });
            return;
        }

        this.state.editMode = true;
        this.state.editRackId = loc.id;
        this.state.addPanelOpen = true;

        this.state.newRack = {
            locationId: loc.id,
            rack_length: loc.rack_length || 3.0,
            rack_width: loc.rack_width || 1.2,
            rack_height: loc.rack_height || 3.0,
            shelf_levels: loc.shelf_levels || 3,
            bins_per_level: loc.bins_per_level || 5,
            capacity: loc.capacity || 1000,
            pos_x: loc.pos_x || 0,
            pos_z: loc.pos_z || 0,
            rotation_y: loc.rotation_y || 0,
        };

        this.state.availableLocations = [{
            id: loc.id,
            name: loc.name,
            complete_name: loc.complete_name,
        }];
        this.state.availableLocationsGrouped = [{
            wid: loc.warehouse_id || 0,
            name: loc.warehouse_name || 'Unassigned',
            locations: [{
                id: loc.id,
                name: loc.name,
                complete_name: loc.complete_name,
            }],
        }];

        this.state.selectedLocation = null;
        this.state.selectedProduct = null;
    }

    async deleteRack() {
        const loc = this.state.selectedLocation;
        if (!loc) {
            this.notification.add("No rack selected.", { type: "warning" });
            return;
        }

        try {
            const result = await this.orm.call(
                "stock.location", "delete_rack_from_3d", [[loc.id]]
            );

            if (result && result.error) {
                this.notification.add(result.error, { type: "danger" });
                return;
            }

            this.notification.add(
                ` Rack "${loc.complete_name}" deleted`,
                { type: "success" }
            );

            this.state.selectedLocation = null;
            this.state.selectedProduct = null;
            if (this._flyingTo) {
                this._flyingTo = false;
                this.state.flying = false;
            }

            await this.loadData();
            this.renderScene();
        } catch (err) {
            console.error("Delete rack error:", err);
            this.notification.add(
                err.message || "Could not delete rack.",
                { type: "danger" }
            );
        }
    }

    async createRackFromPanel() {
        const locId = parseInt(this.state.newRack.locationId, 10);
        if (!locId) {
            this.notification.add("Please select a location.", { type: "warning" });
            return;
        }

        const params = {
            pos_x: Number(this.state.newRack.pos_x) || 0,
            pos_z: Number(this.state.newRack.pos_z) || 0,
            rotation_y: Number(this.state.newRack.rotation_y) || 0,
            rack_length: Number(this.state.newRack.rack_length) || 3,
            rack_width: Number(this.state.newRack.rack_width) || 1.2,
            rack_height: Number(this.state.newRack.rack_height) || 3,
            shelf_levels: Number(this.state.newRack.shelf_levels) || 3,
            bins_per_level: Number(this.state.newRack.bins_per_level) || 5,
        };

        const isEdit = this.state.editMode;
        const rackId = this.state.editRackId || locId;

        try {
            const result = await this.orm.call(
                "stock.location", "setup_rack_3d", [rackId, params]
            );
            if (result && result.error) {
                this.notification.add(result.error, { type: "danger" });
                return;
            }

            this.notification.add(
                isEdit
                    ? `Rack "${result.name}" updated`
                    : ` "${result.name}" added to 3D view`,
                { type: "success" }
            );

            this.state.addPanelOpen = false;
            this.state.editMode = false;
            this.state.editRackId = null;
            this.state.newRack = { ...DEFAULT_NEW_RACK };

            await this.loadData();
            this.renderScene();
        } catch (e) {
            this.notification.add(
                e.message || (isEdit ? "Failed to update rack." : "Failed to create rack."),
                { type: "danger" }
            );
        }
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value || "";
        this.renderScene();
    }

    clearSearch() { this.state.searchQuery = ""; this.renderScene(); }
    toggleHeatmap() { this.state.heatmapEnabled = !this.state.heatmapEnabled; this.renderScene(); }
    toggleWalkMode() {
        this.state.walkMode = !this.state.walkMode;
        this.camera.position.set(this.camera.position.x,
            this.state.walkMode ? 1.6 : 5, this.camera.position.z);
    }
    flyToSelected() {
        if (!this.state.selectedLocation) return;
        if (this._flyingTo) {
            if (this._prevCameraPos && this._prevOrbitTarget) {
                this.camera.position.copy(this._prevCameraPos);
                this.orbitTarget.copy(this._prevOrbitTarget);
                this.camera.lookAt(this.orbitTarget);
            }
            this._flyingTo = false;
            this.state.flying = false;
            return;
        }
        this._prevCameraPos = this.camera.position.clone();
        this._prevOrbitTarget = this.orbitTarget.clone();
        const loc = this.state.selectedLocation;
        const off = this._warehouseOffsets[loc.warehouse_id || 0] || { dx: 0, dz: 0 };
        const target = new THREE.Vector3(
            loc.pos_x + (off.dx || 0),
            loc.pos_y + (loc.rack_height || 3) / 2,
            loc.pos_z + (off.dz || 0)
        );
        this.orbitTarget.copy(target);
        this.camera.position.set(target.x + 5, target.y + 2, target.z + 6);
        this.camera.lookAt(target);
        this._flyingTo = true;
        this.state.flying = true;
    }

    toggleProductsExpanded() {
        this.state.productsExpanded = !this.state.productsExpanded;
    }

   
    closeDetail() {
        this.state.selectedLocation = null;
        if (this._flyingTo) { this._flyingTo = false; this.state.flying = false; }
    }
    closeProductDetail() {
        this.state.selectedProduct = null;
    }
}

Stock3DView.template = "ipredict_stock_3d_view.Stock3DView";
actionRegistry.add("stock_3d_view", Stock3DView);