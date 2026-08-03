/** @odoo-module **/

import { Component, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import * as THREE from "../lib/three.module.js";

export class Locker3DView extends Component {
    setup() {
        this.canvasRef = useRef("canvas");
        onMounted(() => {
            this.startScene();
        });
    }

    startScene() {
        const container = this.canvasRef.el;

        // Scene
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x2c2c2c);

        // Camera
        const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
        camera.position.set(0, 3, 18);
        camera.lookAt(0, 0, 0);

        // Renderer
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
        container.appendChild(renderer.domElement);

        // Lights
        scene.add(new THREE.AmbientLight(0xffffff, 2));
        const light = new THREE.DirectionalLight(0xffffff, 3);
        light.position.set(10, 20, 20);
        scene.add(light);

        // Floor
        const floor = new THREE.Mesh(
            new THREE.PlaneGeometry(50, 50),
            new THREE.MeshStandardMaterial({ color: 0x555555, side: THREE.DoubleSide })
        );
        floor.rotation.x = -Math.PI / 2;
        floor.position.y = -5;
        scene.add(floor);

        // Locker Group
        const lockerGroup = new THREE.Group();
        const rows = 4;
        const cols = 6;
        const width = 1;
        const height = 2;
        const depth = 0.8;
        const gapX = 0.25;
        const gapY = 0.25;

        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                // Body
                const body = new THREE.Mesh(
                    new THREE.BoxGeometry(width, height, depth),
                    new THREE.MeshStandardMaterial({ color: 0xbcbcbc, metalness: 0.4, roughness: 0.5 })
                );
                body.position.x = (c - (cols - 1) / 2) * (width + gapX);
                body.position.y = ((rows - 1) / 2 - r) * (height + gapY);

                // Door
                const door = new THREE.Mesh(
                    new THREE.BoxGeometry(width * 0.95, height * 0.95, 0.05),
                    new THREE.MeshStandardMaterial({ color: 0x9e9e9e })
                );
                door.position.z = depth / 2 + 0.03;
                body.add(door);

                // Handle
                const handle = new THREE.Mesh(
                    new THREE.SphereGeometry(0.05, 16, 16),
                    new THREE.MeshStandardMaterial({ color: 0x111111 })
                );
                handle.position.set(width / 2 - 0.12, 0, depth / 2 + 0.08);
                body.add(handle);

                lockerGroup.add(body);
            }
        }
        scene.add(lockerGroup);

        // Animation
        const animate = () => {
            requestAnimationFrame(animate);
            // lockerGroup.rotation.y += 0.002;
            renderer.render(scene, camera);
        };
        animate();

        // Resize
        window.addEventListener("resize", () => {
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        });
    }
}

Locker3DView.template = "iPredict_locker_management.Locker3DView";
registry.category("actions").add("locker_3d_view", Locker3DView);