/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const actionRegistry = registry.category("actions");

// ---- CONSTANTS ----
const STOCK_BOX_COLOR = 0xf3ce8a;
const STATUS_COLORS = {
    inUse: "#22c55e",
    almostFull: "#f59e0b",
    overloaded: "#ef4444",
    noCapacity: "#3b82f6",
    empty: "#9ca3af",
};

export class Stock3DView extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.canvasRef = useRef("canvas");

        // ---- THREE.JS OBJECTS ----
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.labelRenderer = null;
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

        // ---- STATE ----
        this.state = useState({
            searchQuery: "",
            heatmapEnabled: false,
            walkMode: false,
            selectedLocation: null,   
            selectedProduct: null,    
            locations: [],
            products: [],
            filteredLocations: [],
        });

        this.isOrbiting = false;
        this.lastX = 0;
        this.lastY = 0;
        this.orbitTarget = null;

        // ---- EVENT HANDLERS ----
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
            if (this.labelRenderer) {
                this.labelRenderer.domElement.remove();
            }
        });
    }

    // ====================================================================
    //  LOAD LIBRARIES
    // ====================================================================

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
                console.log("✅ Three.js loaded from CDN");
                await this.loadGLTFLoader();
                this.threeLoaded = true;
                resolve();
            };
            script.onerror = () => {
                reject(new Error("Failed to load Three.js from CDN"));
            };
            document.head.appendChild(script);
        });
    }

    async loadGLTFLoader() {
        if (window.THREE && window.THREE.GLTFLoader) return;
        return new Promise((resolve) => {
            const script = document.createElement("script");
            script.src = "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js";
            script.onload = () => {
                console.log("✅ GLTFLoader loaded:", !!window.THREE.GLTFLoader);
                resolve();
            };
            script.onerror = () => {
                console.warn("⚠️ GLTFLoader load failed");
                resolve();
            };
            document.head.appendChild(script);
        });
    }

    // ====================================================================
    //  LOAD DATA FROM ODOO
    // ====================================================================

    async loadData() {
        try {
            const result = await this.orm.call("stock.location", "get_3d_data", [[]]);
            if (result && result.locations) {
                this.state.locations = result.locations;
                this.state.products = result.products || [];
                this.state.filteredLocations = this.state.locations;
                console.log("✅ Loaded locations:", this.state.locations.length);
            } else {
                this.notification.add("No 3D locations found. Please configure locations.", { type: "warning" });
            }
        } catch (e) {
            console.error("❌ 3D data load error:", e);
            this.notification.add("Failed to load warehouse data.", { type: "danger" });
        }
    }

    // ====================================================================
    //  INIT THREE.JS SCENE
    // ====================================================================

    initScene() {
        if (!this.threeLoaded || !window.THREE) {
            console.error("❌ Three.js not loaded yet");
            return;
        }

        const container = this.canvasRef.el;
        if (!container) return;

        const width = container.clientWidth || window.innerWidth;
        const height = container.clientHeight || window.innerHeight;

        // ---- MAIN RENDERER ----
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

        // ---- CSS2D RENDERER (optional) ----
        if (window.THREE.CSS2DRenderer) {
            this.labelRenderer = new THREE.CSS2DRenderer();
            this.labelRenderer.setSize(width, height);
            this.labelRenderer.domElement.style.position = 'absolute';
            this.labelRenderer.domElement.style.top = '0px';
            this.labelRenderer.domElement.style.left = '0px';
            this.labelRenderer.domElement.style.pointerEvents = 'none';
            container.style.position = 'relative';
            container.appendChild(this.labelRenderer.domElement);
            console.log("✅ CSS2DRenderer initialized");
        } else {
            console.warn("⚠️ CSS2DRenderer not available, labels will use Sprites");
        }

        // ---- LIGHTING ----
        const ambient = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambient);

        const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(20, 30, 20);
        dirLight.castShadow = true;
        this.scene.add(dirLight);

        const dirLight2 = new THREE.DirectionalLight(0xffffff, 0.3);
        dirLight2.position.set(-20, 10, -20);
        this.scene.add(dirLight2);

        // ---- RAYCASTER ----
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        this.orbitTarget = new THREE.Vector3(0, 0, 0);
    }

    // ====================================================================
    //  RENDER SCENE
    // ====================================================================

    renderScene() {
        console.log("🔵 renderScene called, locations:", this.state.locations.length);

        if (!this.scene || !this.threeLoaded) return;

        // Clear previous objects
        this.rackMeshes.forEach(obj => this.scene.remove(obj));
        this.rackMeshes = [];
        this.labelObjects.forEach(obj => {
            if (obj.parent) obj.parent.remove(obj);
        });
        this.labelObjects = [];

        this.drawFloor();
        this.drawRacks();

        // Create forklift and path (if not already created)
        if (!this.forklift) {
            this.createForklift();
        }
        if (!this.forkliftPath) {
            this.createForkliftPath();
        }

        this.fitCamera();
        this.animate();
    }

    // ---- FLOOR ----
    drawFloor() {
        const gridHelper = new THREE.GridHelper(60, 20, 0x888888, 0xcccccc);
        gridHelper.position.y = -0.01;
        this.scene.add(gridHelper);
        this.rackMeshes.push(gridHelper);
    }

    // ---- DRAW RACKS ----
    drawRacks() {
        console.log("🟢 drawRacks called, locations:", this.state.locations.length);

        const locations = this.state.searchQuery
            ? this.state.locations.filter(l =>
                (l.complete_name || l.name).toLowerCase().includes(this.state.searchQuery.toLowerCase())
              )
            : this.state.locations;

        this.state.filteredLocations = locations;

        locations.forEach((loc) => {
            this.drawRack(loc);
        });
    }

    // ---- DRAW RACK (GLB + Stock Boxes) ----
    drawRack(loc) {
        console.log("🟡 Drawing rack:", loc.complete_name);

        if (!window.THREE.GLTFLoader) {
            console.warn("⚠️ GLTFLoader not available, skipping rack:", loc.complete_name);
            return;
        }

        const cx = loc.pos_x;
        const cz = loc.pos_z;
        const floorY = loc.pos_y;

        const loader = new THREE.GLTFLoader();
        const modelPath = '/ipredict_stock_3d_view/static/src/models/rack+de+pallet.glb';

        loader.load(modelPath, (gltf) => {
            const rack = gltf.scene;
            rack.scale.set(0.5, 0.5, 0.5);

            // ---- Get actual GLB dimensions ----
            const box = new THREE.Box3().setFromObject(rack);
            const size = new THREE.Vector3();
            box.getSize(size);
            const boxCenter = new THREE.Vector3();
            box.getCenter(boxCenter);
            const minY = box.min.y;

            // ---- Center the GLB ----
            rack.position.x += (cx - boxCenter.x);
            rack.position.z += (cz - boxCenter.z);
            rack.position.y += (floorY - minY);

            // ---- Heatmap (optional) ----
            if (this.state.heatmapEnabled) {
                const color = new THREE.Color().setHSL(0.3 - (loc.fill_percentage / 100) * 0.3, 1, 0.5);
                rack.traverse((child) => {
                    if (child.isMesh && child.material) {
                        child.material = child.material.clone();
                        child.material.color.set(color);
                    }
                });
            }

            rack.userData = { locationId: loc.id, type: 'rack' };

            this.scene.add(rack);
            this.rackMeshes.push(rack);

            // ---- ADD STOCK BOXES (1 Product = 1 Box) ----
            this.addStockBoxes(loc, cx, floorY, cz, size);

            // ---- LABEL ----
            const labelY = floorY + size.y + 0.35;
            this.addLabel(loc, cx, labelY, cz);

        }, undefined, (error) => {
            console.warn("⚠️ GLB rack not loaded for:", loc.complete_name, error);
        });
    }

    addStockBoxes(loc, cx, floorY, cz, rackSize) {
        const rack_length = rackSize.x;
        const rack_width = rackSize.z;
        const rack_height = rackSize.y;

        let shelf_levels = loc.shelf_levels > 0 ? loc.shelf_levels : 5;
        let bins_per_level = loc.bins_per_level > 0 ? loc.bins_per_level : 2;

        const MAX_SHELF_LEVELS = 10;
        if (shelf_levels > MAX_SHELF_LEVELS) {
            console.warn(`⚠️ shelf_levels (${shelf_levels}) capped to ${MAX_SHELF_LEVELS} for visibility.`);
            shelf_levels = MAX_SHELF_LEVELS;
        }
        if (bins_per_level < 1) bins_per_level = 2;

        let productIds = loc.product_ids || [];
        let productCount = productIds.length;

        if (productCount === 0) return;

        const shelfHeight = rack_height / (shelf_levels + 1);
        const widthPerBin = rack_length / bins_per_level;
        const boxSize = Math.min(widthPerBin - 0.1, 0.4);
        const totalSlots = shelf_levels * bins_per_level;

        for (let i = 0; i < productCount; i++) {
            const slotIndex = i % totalSlots;
            const stackLevel = Math.floor(i / totalSlots);

            const level = Math.floor(slotIndex / bins_per_level);
            const bin = slotIndex % bins_per_level;

            const xOff = bin * widthPerBin + widthPerBin / 2 - rack_length / 2 + 0.1;
            const yOff = floorY + (level + 0.5) * shelfHeight + 0.05 + stackLevel * 0.22;

            const prodGeo = new THREE.BoxGeometry(boxSize, 0.2, boxSize);
            const prodMat = new THREE.MeshStandardMaterial({
                color: STOCK_BOX_COLOR,
                roughness: 0.6,
                metalness: 0.0,
            });
            const prod = new THREE.Mesh(prodGeo, prodMat);
            prod.position.set(cx + xOff, yOff, cz);
            prod.castShadow = true;
            prod.receiveShadow = true;

            const productId = productIds[i];
            prod.userData = {
                productId: productId,
                type: 'product',
                locationId: loc.id,
            };

            this.scene.add(prod);
            this.rackMeshes.push(prod);
        }
    }

    // ---- LABEL (Sprite) ----
    addLabel(loc, x, y, z) {
        if (!this.threeLoaded || !window.THREE) {
            console.warn("⚠️ Three.js not loaded, label skipped for:", loc.name);
            return;
        }

        const status = this.getRackStatus(loc);
        const codeText = loc.code_3d || loc.complete_name || loc.name;
        const hasCapacity = loc.capacity_3d > 0 && loc.fill_percentage !== null && loc.fill_percentage !== undefined;
        const pctText = hasCapacity ? `${Math.round(loc.fill_percentage)}%` : "-";
        const mainText = `${codeText}  ${pctText}`;

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = 512;
        canvas.height = 128;

        // Background (rounded pill)
        ctx.fillStyle = 'rgba(0, 0, 0, 0.80)';
        const radius = 30;
        const w = canvas.width;
        const h = canvas.height;
        ctx.beginPath();
        ctx.moveTo(radius, 0);
        ctx.lineTo(w - radius, 0);
        ctx.quadraticCurveTo(w, 0, w, radius);
        ctx.lineTo(w, h - radius);
        ctx.quadraticCurveTo(w, h, w - radius, h);
        ctx.lineTo(radius, h);
        ctx.quadraticCurveTo(0, h, 0, h - radius);
        ctx.lineTo(0, radius);
        ctx.quadraticCurveTo(0, 0, radius, 0);
        ctx.closePath();
        ctx.fill();

        ctx.strokeStyle = 'rgba(255,255,255,0.20)';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Status Dot
        const dotX = 40;
        const dotY = h / 2;
        const dotRadius = 14;
        ctx.beginPath();
        ctx.arc(dotX, dotY, dotRadius, 0, Math.PI * 2);
        ctx.fillStyle = status.color;
        ctx.shadowColor = status.color;
        ctx.shadowBlur = 12;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Text
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 42px Arial, sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText(mainText, dotX + dotRadius + 16, dotY + 2);

        const texture = new THREE.CanvasTexture(canvas);
        texture.needsUpdate = true;
        const material = new THREE.SpriteMaterial({
            map: texture,
            transparent: true,
            depthTest: false,
            depthWrite: false,
        });
        const sprite = new THREE.Sprite(material);

        // ---- Position ----
        sprite.position.set(x, y, z);

        // ---- Scale ----
        const aspect = canvas.width / canvas.height;
        const labelHeight = 0.55;
        sprite.scale.set(labelHeight * aspect, labelHeight, 1);

        this.scene.add(sprite);
        this.labelObjects.push(sprite);
        console.log(`🏷️ Label added for: ${loc.name} at (${x.toFixed(2)}, ${y.toFixed(2)}, ${z.toFixed(2)})`);
    }

    // ---- STATUS ----
    getRackStatus(loc) {
        const capacity = loc.capacity_3d;
        const pct = loc.fill_percentage;

        if (!capacity || capacity <= 0 || pct === null || pct === undefined) {
            return { color: STATUS_COLORS.noCapacity, label: "No capacity" };
        }
        if (pct <= 0) {
            return { color: STATUS_COLORS.empty, label: "Empty" };
        }
        if (pct >= 100) {
            return { color: STATUS_COLORS.overloaded, label: "Overloaded" };
        }
        if (pct >= 80) {
            return { color: STATUS_COLORS.almostFull, label: "Almost full" };
        }
        return { color: STATUS_COLORS.inUse, label: "In use" };
    }

    // ====================================================================
    //  FORKLIFT 
    // ====================================================================

    createForklift() {
        if (!window.THREE || !window.THREE.GLTFLoader) {
            console.warn("⚠️ GLTFLoader not available, using fallback forklift");
            this.createFallbackForklift();
            return;
        }

        const loader = new THREE.GLTFLoader();
        const modelPath = '/ipredict_stock_3d_view/static/src/models/Gabelstapler.glb';

        loader.load(modelPath, (gltf) => {
            this.forklift = gltf.scene;
            this.forklift.scale.set(0.12, 0.12, 0.12);
            this.forklift.position.set(0, 0.2, 0);
            this.scene.add(this.forklift);
            console.log("✅ Forklift GLB loaded successfully!");
        }, undefined, (error) => {
            console.warn("⚠️ Forklift GLB load failed, using fallback:", error);
            this.createFallbackForklift();
        });
    }

    createFallbackForklift() {
        const group = new THREE.Group();

        const bodyGeo = new THREE.BoxGeometry(0.8, 0.3, 1.5);
        const bodyMat = new THREE.MeshStandardMaterial({ color: 0xff5722 });
        const body = new THREE.Mesh(bodyGeo, bodyMat);
        body.position.y = 0.15;
        group.add(body);

        const cabinGeo = new THREE.BoxGeometry(0.6, 0.3, 0.6);
        const cabinMat = new THREE.MeshStandardMaterial({ color: 0x2196f3 });
        const cabin = new THREE.Mesh(cabinGeo, cabinMat);
        cabin.position.set(0, 0.45, -0.3);
        group.add(cabin);

        const wheelGeo = new THREE.CylinderGeometry(0.1, 0.1, 0.05, 8);
        const wheelMat = new THREE.MeshStandardMaterial({ color: 0x333333 });
        const wheelPositions = [
            [-0.3, 0.05, 0.5],
            [0.3, 0.05, 0.5],
            [-0.3, 0.05, -0.5],
            [0.3, 0.05, -0.5]
        ];
        wheelPositions.forEach(pos => {
            const wheel = new THREE.Mesh(wheelGeo, wheelMat);
            wheel.rotation.x = Math.PI / 2;
            wheel.position.set(pos[0], pos[1], pos[2]);
            group.add(wheel);
        });

        const forkGeo = new THREE.BoxGeometry(0.05, 0.02, 0.5);
        const forkMat = new THREE.MeshStandardMaterial({ color: 0x888888, metalness: 0.8 });
        const forkPositions = [
            [-0.2, 0.05, 0.8],
            [0.2, 0.05, 0.8]
        ];
        forkPositions.forEach(pos => {
            const fork = new THREE.Mesh(forkGeo, forkMat);
            fork.position.set(pos[0], pos[1], pos[2]);
            group.add(fork);
        });

        group.scale.set(0.3, 0.3, 0.3);
        this.scene.add(group);
        this.forklift = group;
        console.log("🟡 Fallback forklift created");
    }

    createForkliftPath() {
        const points = [
            new THREE.Vector3(-6, 0.2, -6),
            new THREE.Vector3(-4, 0.2, -3),
            new THREE.Vector3(-2, 0.2, 0),
            new THREE.Vector3(2, 0.2, 0),
            new THREE.Vector3(4, 0.2, -3),
            new THREE.Vector3(6, 0.2, -6),
            new THREE.Vector3(4, 0.2, -8),
            new THREE.Vector3(-4, 0.2, -8),
            new THREE.Vector3(-6, 0.2, -6)
        ];

        this.forkliftPath = new THREE.CatmullRomCurve3(points);

        const curvePoints = this.forkliftPath.getPoints(50);
        const geometry = new THREE.BufferGeometry().setFromPoints(curvePoints);
        const material = new THREE.LineBasicMaterial({ color: 0x00ff00 });
        const curveLine = new THREE.Line(geometry, material);
        this.scene.add(curveLine);
        this.rackMeshes.push(curveLine);
        console.log("🟢 Forklift path created (far from racks)");
    }

    // ====================================================================
    //  CAMERA
    // ====================================================================

    computeSceneBounds() {
        let minX = Infinity, maxX = -Infinity;
        let minZ = Infinity, maxZ = -Infinity;
        let maxY = 0;

        this.state.locations.forEach((loc) => {
            const rackWidth = 1.0;
            const rackDepth = 1.0;

            minX = Math.min(minX, loc.pos_x);
            maxX = Math.max(maxX, loc.pos_x + rackWidth);
            minZ = Math.min(minZ, loc.pos_z);
            maxZ = Math.max(maxZ, loc.pos_z + rackDepth);
            maxY = Math.max(maxY, loc.pos_y + 2.0);
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

        const bounds = this.computeSceneBounds();
        const footprint = Math.max(bounds.sizeX, bounds.sizeZ);
        const distance = Math.max(footprint * 1.4, 15);

        this.orbitTarget.set(bounds.centerX, Math.min(bounds.maxY / 2, 3), bounds.centerZ);

        this.camera.position.set(
            bounds.centerX + distance,
            distance * 0.55,
            bounds.centerZ + distance
        );
        this.camera.lookAt(this.orbitTarget);

        console.log("📷 Camera position:", this.camera.position);
    }

    // ====================================================================
    //  ANIMATION LOOP
    // ====================================================================

    animate() {
        this.animationFrame = requestAnimationFrame(() => this.animate());

        if (this.forklift && this.forkliftPath) {
            this.forkliftProgress += this.forkliftSpeed;
            if (this.forkliftProgress > 1) {
                this.forkliftProgress = 0;
            }

            const position = this.forkliftPath.getPoint(this.forkliftProgress);
            this.forklift.position.copy(position);

            const tangent = this.forkliftPath.getTangent(this.forkliftProgress);
            this.forklift.lookAt(position.clone().add(tangent));
        }

        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
        if (this.labelRenderer && this.scene && this.camera) {
            this.labelRenderer.render(this.scene, this.camera);
        }
    }

    // ====================================================================
    //  MOUSE EVENTS (Box Click → Product Details, Rack Click → Rack Details)
    // ====================================================================

    getMousePos(e) {
        const rect = this.renderer.domElement.getBoundingClientRect();
        return {
            x: ((e.clientX - rect.left) / rect.width) * 2 - 1,
            y: -((e.clientY - rect.top) / rect.height) * 2 + 1
        };
    }

    onMouseDown(e) {
        if (e.button !== 0) return;
        const pos = this.getMousePos(e);
        this.mouse.x = pos.x;
        this.mouse.y = pos.y;

        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.rackMeshes, true);

        if (intersects.length) {
            let hit = intersects[0].object;
            let targetType = null;
            let targetId = null;
            let locationId = null;

            while (hit) {
                if (hit.userData && hit.userData.type) {
                    targetType = hit.userData.type;
                    if (targetType === 'product') {
                        targetId = hit.userData.productId;
                        locationId = hit.userData.locationId;
                    } else if (targetType === 'rack') {
                        targetId = hit.userData.locationId;
                    }
                    break;
                }
                hit = hit.parent;
            }

            // ---- BOX (Product) CLICK: Show Product Detail Panel ----
            if (targetType === 'product' && targetId) {
                const product = (this.state.products || []).find(p => p.id === targetId);
                const loc = this.state.locations.find(l => l.id === locationId);
                let quantity = 0;
                if (loc && loc.product_quantities) {
                    quantity = loc.product_quantities[targetId] || 0;
                }
                this.state.selectedProduct = {
                    id: targetId,
                    name: product ? product.name : `Product ${targetId}`,
                    quantity: quantity,
                    location_name: loc ? loc.complete_name : '',
                };
                return;
            }

            // ---- RACK CLICK: Show Rack Detail Panel ----
            if (targetType === 'rack' && targetId) {
                const loc = this.state.locations.find(l => l.id === targetId);
                if (loc) {
                    this.state.selectedLocation = loc;
                    this.state.heatmapEnabled = false;
                    return;
                }
            }
        }

        // ---- Click on empty space: clear both panels ----
        this.state.selectedProduct = null;
        this.state.selectedLocation = null;

        // ---- Orbit start ----
        this.isOrbiting = true;
        this.lastX = e.clientX;
        this.lastY = e.clientY;
    }

    onMouseMove(e) {
        if (this.isOrbiting) {
            const dx = (e.clientX - this.lastX) * 0.005;
            const dy = (e.clientY - this.lastY) * 0.005;
            this.lastX = e.clientX;
            this.lastY = e.clientY;

            const target = this.orbitTarget;
            const radius = this.camera.position.distanceTo(target);
            const theta = Math.atan2(this.camera.position.x - target.x, this.camera.position.z - target.z) + dx;
            let phi = Math.acos((this.camera.position.y - target.y) / radius) + dy;
            phi = Math.max(0.1, Math.min(Math.PI / 2 - 0.05, phi));

            this.camera.position.x = target.x + radius * Math.sin(phi) * Math.sin(theta);
            this.camera.position.y = target.y + radius * Math.cos(phi);
            this.camera.position.z = target.z + radius * Math.sin(phi) * Math.cos(theta);
            this.camera.lookAt(target);
        }
    }

    onMouseUp() {
        this.isOrbiting = false;
    }

    onWheel(e) {
        e.preventDefault();
        const target = this.orbitTarget;
        const radius = this.camera.position.distanceTo(target);
        const newRadius = Math.max(2, Math.min(80, radius + (e.deltaY > 0 ? 1 : -1)));
        const dir = this.camera.position.clone().sub(target).normalize();
        this.camera.position.copy(target).add(dir.multiplyScalar(newRadius));
        this.camera.lookAt(target);
    }

    onResize() {
        if (!this.camera || !this.renderer) return;
        const container = this.canvasRef.el;
        const w = container.clientWidth || window.innerWidth;
        const h = container.clientHeight || window.innerHeight;
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(w, h);
        if (this.labelRenderer) {
            this.labelRenderer.setSize(w, h);
        }
    }

    // ====================================================================
    //  UI ACTIONS
    // ====================================================================

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
        if (this.state.walkMode) {
            this.camera.position.set(this.camera.position.x, 1.6, this.camera.position.z);
        } else {
            this.camera.position.set(this.camera.position.x, 5, this.camera.position.z);
        }
    }

    flyToSelected() {
        if (!this.state.selectedLocation) return;
        const loc = this.state.selectedLocation;
        const target = new THREE.Vector3(
            loc.pos_x,
            loc.pos_y + 1.5,
            loc.pos_z
        );
        this.orbitTarget.copy(target);
        this.camera.position.set(target.x + 5, target.y + 3, target.z + 8);
        this.camera.lookAt(target);
    }

    closeDetail() {
        this.state.selectedLocation = null;
    }

    closeProductDetail() {
        this.state.selectedProduct = null;
    }
}

Stock3DView.template = "ipredict_stock_3d_view.Stock3DView";

actionRegistry.add("stock_3d_view", Stock3DView);