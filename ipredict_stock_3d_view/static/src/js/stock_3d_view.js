/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const actionRegistry = registry.category("actions");

const STATUS_COLORS = {
    inUse: "#22c55e",
    almostFull: "#f59e0b",
    overloaded: "#ef4444",
    noCapacity: "#3b82f6",
    empty: "#9ca3af",
};

const hexToInt = (hex, fallback) => {
    if (!hex) return fallback;
    try { return parseInt(String(hex).replace('#', ''), 16); }
    catch (e) { return fallback; }
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

        // ---- Fly-to state ----
        this._flyingTo = false;
        this._prevCameraPos = null;
        this._prevOrbitTarget = null;

        this._highlightedLabel = null;

        this.state = useState({
            searchQuery: "",
            heatmapEnabled: false,
            walkMode: false,
            selectedLocation: null,
            selectedProduct: null,
            locations: [],
            products: [],
            filteredLocations: [],
            flying: false,
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
        if (window.THREE) {
            await this.loadGLTFLoader();
            this.threeLoaded = true;
            return;
        }
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
                this.state.filteredLocations = this.state.locations;
            } else {
                this.notification.add("No 3D locations found.", { type: "warning" });
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

        const ambient = new THREE.AmbientLight(0xffffff, 0.85);
        this.scene.add(ambient);

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
    }

    renderScene() {
        if (!this.scene || !this.threeLoaded) return;

        this.rackMeshes.forEach(obj => { if (obj.parent) obj.parent.remove(obj); });
        this.rackMeshes = [];
        this.labelObjects.forEach(obj => { if (obj.parent) obj.parent.remove(obj); });
        this.labelObjects = [];
        this._highlightedLabel = null;

        this.drawFloor();

        const locations = this.state.searchQuery
            ? this.state.locations.filter(l =>
                (l.complete_name || l.name).toLowerCase()
                    .includes(this.state.searchQuery.toLowerCase()))
            : this.state.locations;

        this.state.filteredLocations = locations;

        locations.forEach(loc => this.drawRack(loc));

        if (!this.forklift) this.createForklift();
        if (!this.forkliftPath) this.createForkliftPath();

        this.fitCamera();
        this.animate();
    }

    drawFloor() {
        const gridHelper = new THREE.GridHelper(80, 40, 0x888888, 0xcccccc);
        gridHelper.position.y = -0.01;
        this.scene.add(gridHelper);
        this.rackMeshes.push(gridHelper);
    }

    drawRack(loc) {
        const group = new THREE.Group();

        const heatmapOn = this.state.heatmapEnabled;
        const status = this.getRackStatus(loc);

        let uprightHex, beamHex, slatHex;

        if (heatmapOn) {
            const baseHex = parseInt(status.color.replace('#', ''), 16);
            const baseColor = new THREE.Color(baseHex);

            const uColor = baseColor.clone().multiplyScalar(0.75);
            uprightHex = uColor.getHex();
            beamHex = baseHex;
            const sColor = baseColor.clone().lerp(new THREE.Color(0xffffff), 0.45);
            slatHex = sColor.getHex();
        } else {
            uprightHex = hexToInt(loc.color_upright, 0x4F6489);
            beamHex = hexToInt(loc.color_beam, 0xF4C842);
            slatHex = hexToInt(loc.color_slat, 0xD5D5D5);
        }

        const uprightMat = new THREE.MeshStandardMaterial({
            color: uprightHex, metalness: 0.15, roughness: 0.65,
        });
        const beamMat = new THREE.MeshStandardMaterial({
            color: beamHex, metalness: 0.1, roughness: 0.55,
        });
        const slatMat = new THREE.MeshStandardMaterial({
            color: slatHex, metalness: 0.05, roughness: 0.85,
        });

        const L = loc.rack_length || 3.0;
        const W = loc.rack_width || 1.2;
        const H = loc.rack_height || 3.0;
        const levels = Math.max(1, loc.shelf_levels || 5);
        const bins = Math.max(1, loc.bins_per_level || 3);
        const postW = loc.post_thickness || 0.09;
        const postD = postW * 0.8;
        const beamH = loc.beam_height || 0.16;
        const beamD = 0.05;
        const slatH = 0.025;
        const braceT = 0.035;

        // Uprights
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

        // X-bracing
        [-L / 2, L / 2].forEach(xPos => {
            const spanZ = W - postD * 2;
            const spanY = H - 0.2;
            const diagLen = Math.sqrt(spanZ * spanZ + spanY * spanY);
            const diagAngle = Math.atan2(spanZ, spanY);

            const d1 = new THREE.Mesh(new THREE.BoxGeometry(braceT, diagLen, braceT), uprightMat);
            d1.position.set(xPos, H / 2, 0);
            d1.rotation.x = diagAngle;
            group.add(d1);

            const d2 = new THREE.Mesh(new THREE.BoxGeometry(braceT, diagLen, braceT), uprightMat);
            d2.position.set(xPos, H / 2, 0);
            d2.rotation.x = -diagAngle;
            group.add(d2);
        });

        // Shelves
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
                transparent: true,
                opacity: 0.0,
                depthWrite: false,
            })
        );
        catcher.position.set(0, H / 2, 0);
        catcher.userData = {
            type: 'rack',
            locationId: loc.id,
            isClickCatcher: true,
        };
        catcher.renderOrder = -1;
        group.add(catcher);

        group.position.set(loc.pos_x, loc.pos_y, loc.pos_z);
        group.userData = { type: 'rack', locationId: loc.id };

        this.scene.add(group);
        this.rackMeshes.push(group);

        const labelY = loc.pos_y + H + 1.0;
        this.addLabel(loc, loc.pos_x, labelY, loc.pos_z, group);
    }


          // ==================== SLOT BOXES ====================
    renderSlotBoxes(rackGroup, loc, levelYs, L, W, bins, beamH) {
        const binWidth = L / bins;
        const boxW = Math.min(binWidth * 0.55, 0.42);
        const boxH = 0.20;
        const boxD = Math.min(W * 0.55, 0.45);
        const defaultColor = hexToInt(loc.color_box, 0xE8C89A);

        const slots = loc.slots || [];

        slots.forEach((slot) => {
            const lvl = slot.level;
            const bin = slot.bin;
            if (lvl == null || bin == null) return;
            if (lvl < 0 || lvl >= levelYs.length) return;
            if (bin < 0 || bin >= bins) return;

            const xPos = -L / 2 + binWidth * (bin + 0.5);

            const slotCenterY = levelYs[lvl] + beamH / 2 + boxH / 2 + 0.02;

            const products = slot.products || [];
            const displayName = slot.location_name || slot.complete_name || '';

            if (products.length > 0) {
                // ---- Box hoy — box + label upar ----
                let topBoxY = slotCenterY + boxH / 2;

                products.forEach((prod, pIdx) => {
                    const color = hexToInt(prod.color, defaultColor);
                    const box = new THREE.Mesh(
                        new THREE.BoxGeometry(boxW, boxH, boxD),
                        new THREE.MeshStandardMaterial({
                            color, roughness: 0.7, metalness: 0.05,
                        })
                    );
                    const yOffset = slotCenterY + pIdx * (boxH + 0.02);
                    box.position.set(xPos, yOffset, 0);
                    box.castShadow = true; box.receiveShadow = true;
                    box.userData = {
                        type: 'product',
                        productId: prod.id,
                        product_name: prod.name,
                        quantity: prod.qty,
                        locationId: slot.location_id,
                        location_name: slot.complete_name || displayName,
                    };
                    rackGroup.add(box);
                    topBoxY = yOffset + boxH / 2;
                });

                // Label ABOVE box
                const labelY = topBoxY + 0.13;
                this.addSlotLabel(
                    rackGroup, displayName,
                    xPos, labelY, 0,
                    binWidth, true
                );
            } else {
                this.addSlotLabel(
                    rackGroup, displayName,
                    xPos, slotCenterY, 0,
                    binWidth, false
                );
            }
        });
    }

    formatQty(qty) {
        const rounded = Math.round((qty || 0) * 100) / 100;
        return `${rounded} pcs`;
    }

    
    addSlotLabel(parentGroup, text, x, y, z, binWidth, occupied) {
        if (!this.threeLoaded || !window.THREE || !text) return null;

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = 320;
        canvas.height = 96;
        const w = canvas.width, h = canvas.height, r = 22;

        // Unified dark pill background for both states.
        ctx.fillStyle = 'rgba(15, 23, 42, 0.90)';
        ctx.beginPath();
        ctx.moveTo(r, 0);
        ctx.lineTo(w - r, 0); ctx.quadraticCurveTo(w, 0, w, r);
        ctx.lineTo(w, h - r); ctx.quadraticCurveTo(w, h, w - r, h);
        ctx.lineTo(r, h); ctx.quadraticCurveTo(0, h, 0, h - r);
        ctx.lineTo(0, r); ctx.quadraticCurveTo(0, 0, r, 0);
        ctx.closePath();
        ctx.fill();

        ctx.strokeStyle = occupied ? 'rgba(34,197,94,0.55)' : 'rgba(255,255,255,0.18)';
        ctx.lineWidth = 3;
        ctx.stroke();

        const dotX = 30, dotY = h / 2;
        ctx.beginPath();
        ctx.arc(dotX, dotY, 10, 0, Math.PI * 2);
        ctx.fillStyle = occupied ? '#22c55e' : '#9ca3af';
        if (occupied) {
            ctx.shadowColor = '#22c55e';
            ctx.shadowBlur = 12;
        }
        ctx.fill();
        ctx.shadowBlur = 0;

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
        if (ctx.measureText(displayText).width > maxTextWidth) {
            while (displayText.length > 3 && ctx.measureText(displayText + '…').width > maxTextWidth) {
                displayText = displayText.slice(0, -1);
            }
            displayText += '…';
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
        const targetHeight = targetWidth / aspect;
        sprite.scale.set(targetWidth, targetHeight, 1);
        sprite.userData.baseScale = { x: targetWidth, y: targetHeight };
        sprite.renderOrder = 2;

        parentGroup.add(sprite);
        this.labelObjects.push(sprite);
        return sprite;
    }

    addLabel(loc, x, y, z, parentGroup) {
        if (!this.threeLoaded || !window.THREE) return;

        const status = this.getRackStatus(loc);
        const codeText = loc.code_3d || loc.name;
        const hasCap = loc.capacity > 0 && loc.fill_percentage != null;
        const pctText = hasCap ? `${Math.round(loc.fill_percentage)}%` : "-";
        const mainText = `${codeText}  ${pctText}`;

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = 768;       
        canvas.height = 128;
        const w = canvas.width, h = canvas.height, r = 30;

        // Background
        ctx.fillStyle = 'rgba(0,0,0,0.80)';
        ctx.beginPath();
        ctx.moveTo(r, 0);
        ctx.lineTo(w - r, 0); ctx.quadraticCurveTo(w, 0, w, r);
        ctx.lineTo(w, h - r); ctx.quadraticCurveTo(w, h, w - r, h);
        ctx.lineTo(r, h); ctx.quadraticCurveTo(0, h, 0, h - r);
        ctx.lineTo(0, r); ctx.quadraticCurveTo(0, 0, r, 0);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,0.20)';
        ctx.lineWidth = 2; ctx.stroke();

        // Status dot
        ctx.beginPath();
        ctx.arc(40, h / 2, 14, 0, Math.PI * 2);
        ctx.fillStyle = status.color;
        ctx.shadowColor = status.color;
        ctx.shadowBlur = 12; ctx.fill(); ctx.shadowBlur = 0;

        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';

        const maxWidth = w - 70 - 25;
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
        this.scene.add(sprite);
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
                if (!map[p.id]) {
                    map[p.id] = { id: p.id, name: p.name, qty: 0, color: p.color };
                }
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
            new THREE.Vector3(-8, 0.2, -8),
            new THREE.Vector3(-4, 0.2, -4),
            new THREE.Vector3(0, 0.2, 0),
            new THREE.Vector3(4, 0.2, -4),
            new THREE.Vector3(8, 0.2, -8),
            new THREE.Vector3(4, 0.2, -10),
            new THREE.Vector3(-4, 0.2, -10),
            new THREE.Vector3(-8, 0.2, -8),
        ];
        this.forkliftPath = new THREE.CatmullRomCurve3(points);
    }

    // ==================== CAMERA ====================
    computeSceneBounds() {
        let minX = Infinity, maxX = -Infinity;
        let minZ = Infinity, maxZ = -Infinity;
        let maxY = 0;

        this.state.locations.forEach(loc => {
            const L = loc.rack_length || 3;
            const W = loc.rack_width || 1.2;
            const H = loc.rack_height || 3;
            minX = Math.min(minX, loc.pos_x - L / 2);
            maxX = Math.max(maxX, loc.pos_x + L / 2);
            minZ = Math.min(minZ, loc.pos_z - W / 2);
            maxZ = Math.max(maxZ, loc.pos_z + W / 2);
            maxY = Math.max(maxY, loc.pos_y + H);
        });

        if (!isFinite(minX)) {
            return { centerX: 0, centerZ: 0, sizeX: 10, sizeZ: 10, maxY: 2 };
        }
        return {
            centerX: (minX + maxX) / 2,
            centerZ: (minZ + maxZ) / 2,
            sizeX: Math.max(maxX - minX, 4),
            sizeZ: Math.max(maxZ - minZ, 4),
            maxY,
        };
    }

    fitCamera() {
        if (!this.camera || !this.state.locations.length) return;
        const b = this.computeSceneBounds();
        const dist = Math.max(Math.max(b.sizeX, b.sizeZ) * 1.4, 15);
        this.orbitTarget.set(b.centerX, Math.min(b.maxY / 2, 3), b.centerZ);
        this.camera.position.set(b.centerX + dist, dist * 0.55, b.centerZ + dist);
        this.camera.lookAt(this.orbitTarget);
    }

    // ==================== ANIMATION ====================
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

    onMouseDown(e) {
        if (e.button !== 0) return;
        const pos = this.getMousePos(e);
        this.mouse.x = pos.x;
        this.mouse.y = pos.y;

        this.raycaster.setFromCamera(this.mouse, this.camera);
        const hits = this.raycaster.intersectObjects(this.rackMeshes, true);

        if (hits.length) {
            let productData = null;
            let rackData = null;

            for (const h of hits) {
                let obj = h.object;
                while (obj) {
                    if (obj.userData && obj.userData.type) {
                        if (obj.userData.type === 'product' && !productData) {
                            productData = obj.userData;
                        } else if (obj.userData.type === 'rack' && !rackData) {
                            rackData = obj.userData;
                        }
                        break;
                    }
                    obj = obj.parent;
                }
                if (productData) break;
            }

            if (productData) {
                this.state.selectedProduct = {
                    id: productData.productId,
                    name: productData.product_name,
                    quantity: productData.quantity,
                    location_name: productData.location_name,
                };
                this.state.selectedLocation = null;
                this.highlightSlotLabel(productData.labelSprite);
                return;
            }

            if (rackData) {
                const loc = this.state.locations.find(l => l.id === rackData.locationId);
                if (loc) {
                    const allProducts = this.collectProducts(loc);
                    this.state.selectedLocation = {
                        ...loc,
                        products_info: allProducts,
                    };
                    this.state.selectedProduct = null;
                    if (this._flyingTo) {
                        this._flyingTo = false;
                        this.state.flying = false;
                    }
                    return;
                }
            }
        }

        this.state.selectedProduct = null;
        this.state.selectedLocation = null;
        this.highlightSlotLabel(null);
        this.isOrbiting = true;
        this.lastX = e.clientX;
        this.lastY = e.clientY;

        if (this._flyingTo) {
            this._flyingTo = false;
            this.state.flying = false;
        }
    }

    highlightSlotLabel(sprite) {
        if (this._highlightedLabel && this._highlightedLabel !== sprite) {
            const base = this._highlightedLabel.userData.baseScale;
            if (base) this._highlightedLabel.scale.set(base.x, base.y, 1);
        }
        if (sprite) {
            const base = sprite.userData.baseScale;
            if (base) sprite.scale.set(base.x * 1.25, base.y * 1.25, 1);
            sprite.renderOrder = 5;
        }
        this._highlightedLabel = sprite || null;
    }

    onMouseMove(e) {
        if (this.isOrbiting) {
            const dx = (e.clientX - this.lastX) * 0.005;
            const dy = (e.clientY - this.lastY) * 0.005;
            this.lastX = e.clientX;
            this.lastY = e.clientY;

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

    onMouseUp() { this.isOrbiting = false; }

    onWheel(e) {
        e.preventDefault();
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

    // ==================== UI ACTIONS ====================
    clearSearch() {
        this.state.searchQuery = "";
        this.renderScene();
    }

    toggleHeatmap() {
        this.state.heatmapEnabled = !this.state.heatmapEnabled;
        this.renderScene();
    }

    toggleWalkMode() {
        this.state.walkMode = !this.state.walkMode;
        this.camera.position.set(
            this.camera.position.x,
            this.state.walkMode ? 1.6 : 5,
            this.camera.position.z
        );
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
        const target = new THREE.Vector3(
            loc.pos_x,
            loc.pos_y + (loc.rack_height || 3) / 2,
            loc.pos_z
        );
        this.orbitTarget.copy(target);
        this.camera.position.set(
            target.x + 5,
            target.y + 2,
            target.z + 6
        );
        this.camera.lookAt(target);

        this._flyingTo = true;
        this.state.flying = true;
    }

    closeDetail() {
        this.state.selectedLocation = null;
        if (this._flyingTo) {
            this._flyingTo = false;
            this.state.flying = false;
        }
    }

    closeProductDetail() {
        this.state.selectedProduct = null;
        this.highlightSlotLabel(null);
    }
}

Stock3DView.template = "ipredict_stock_3d_view.Stock3DView";
actionRegistry.add("stock_3d_view", Stock3DView);