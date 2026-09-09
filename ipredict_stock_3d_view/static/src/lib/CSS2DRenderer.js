/**
 * CSS2DRenderer / CSS2DObject
 * -----------------------------------------------------------------------
 * Converted from the official three.js ES module addon
 * (three/addons/renderers/CSS2DRenderer.js) into a PLAIN SCRIPT that
 * relies on the global `window.THREE` object (loaded via the r128 CDN
 * build). This file intentionally has NO import/export statements so
 * that Odoo's asset bundler treats it as a regular script, not an
 * owl/ES module.
 *
 * Do NOT add "/** @odoo-module **\/" to the top of this file.
 *
 * IMPORTANT - LOAD ORDER:
 * This file is part of the STATIC asset bundle and therefore executes
 * immediately at page load, BEFORE three.min.js (which is injected
 * dynamically at runtime by loadThreeJS() in stock_3d_view.js). So we
 * cannot touch `window.THREE` at the top level here - it doesn't exist
 * yet. Instead we expose a setup function, `window.registerCSS2DRenderer`,
 * that stock_3d_view.js calls AFTER three.min.js has finished loading.
 * -----------------------------------------------------------------------
 */
( function () {

    window.registerCSS2DRenderer = function () {

    if ( typeof THREE === 'undefined' ) {
        console.error( 'CSS2DRenderer.js: THREE is not defined. Make sure three.min.js (r128) is loaded before calling registerCSS2DRenderer().' );
        return;
    }

    if ( THREE.CSS2DRenderer ) {
        // Already registered (e.g. component re-mounted), skip.
        return;
    }

    const Matrix4 = THREE.Matrix4;
    const Object3D = THREE.Object3D;
    const Vector2 = THREE.Vector2;
    const Vector3 = THREE.Vector3;

    /**
     * The only type of 3D object that is supported by CSS2DRenderer.
     */
    class CSS2DObject extends Object3D {

        constructor( element = document.createElement( 'div' ) ) {

            super();

            this.isCSS2DObject = true;

            this.element = element;

            this.element.style.position = 'absolute';
            this.element.style.userSelect = 'none';

            this.element.setAttribute( 'draggable', false );

            this.center = new Vector2( 0.5, 0.5 );

            this.rotation2D = 0;

            this.addEventListener( 'removed', function () {

                this.traverse( function ( object ) {

                    if (
                        object.element &&
                        object.element instanceof object.element.ownerDocument.defaultView.Element &&
                        object.element.parentNode !== null
                    ) {

                        object.element.remove();

                    }

                } );

            } );

        }

        copy( source, recursive ) {

            super.copy( source, recursive );

            this.element = source.element.cloneNode( true );

            this.center = source.center;

            this.rotation2D = source.rotation2D;

            return this;

        }

    }

    //

    const _vector = new Vector3();
    const _viewMatrix = new Matrix4();
    const _viewProjectionMatrix = new Matrix4();
    const _a = new Vector3();
    const _b = new Vector3();

    /**
     * Simplified CSS renderer supporting translation and 2D rotation only.
     */
    class CSS2DRenderer {

        constructor( parameters = {} ) {

            const _this = this;

            let _width, _height;
            let _widthHalf, _heightHalf;

            const cache = {
                objects: new WeakMap()
            };

            const domElement = parameters.element !== undefined ? parameters.element : document.createElement( 'div' );

            domElement.style.overflow = 'hidden';

            this.domElement = domElement;

            this.sortObjects = true;

            this.getSize = function () {

                return {
                    width: _width,
                    height: _height
                };

            };

            this.render = function ( scene, camera ) {

                if ( scene.matrixWorldAutoUpdate === true ) scene.updateMatrixWorld();
                if ( camera.parent === null && camera.matrixWorldAutoUpdate === true ) camera.updateMatrixWorld();

                _viewMatrix.copy( camera.matrixWorldInverse );
                _viewProjectionMatrix.multiplyMatrices( camera.projectionMatrix, _viewMatrix );

                renderObject( scene, scene, camera );
                if ( this.sortObjects ) zOrder( scene );

            };

            this.setSize = function ( width, height ) {

                _width = width;
                _height = height;

                _widthHalf = _width / 2;
                _heightHalf = _height / 2;

                domElement.style.width = width + 'px';
                domElement.style.height = height + 'px';

            };

            function hideObject( object ) {

                if ( object.isCSS2DObject ) object.element.style.display = 'none';

                for ( let i = 0, l = object.children.length; i < l; i ++ ) {

                    hideObject( object.children[ i ] );

                }

            }

            function renderObject( object, scene, camera ) {

                if ( object.visible === false ) {

                    hideObject( object );

                    return;

                }

                if ( object.isCSS2DObject ) {

                    _vector.setFromMatrixPosition( object.matrixWorld );
                    _vector.applyMatrix4( _viewProjectionMatrix );

                    const visible = ( _vector.z >= - 1 && _vector.z <= 1 ) && ( object.layers.test( camera.layers ) === true );

                    const element = object.element;
                    element.style.display = visible === true ? '' : 'none';

                    if ( visible === true ) {

                        object.onBeforeRender( _this, scene, camera );

                        // pivot point
                        const cx = 100 * object.center.x;
                        const cy = 100 * object.center.y;
                        element.style.transformOrigin = `${cx}% ${cy}%`;

                        // angle of rotation, counter-clockwise convention
                        const angle = - object.rotation2D;

                        // coordinates
                        const tx = _vector.x * _widthHalf + _widthHalf;
                        const ty = - _vector.y * _heightHalf + _heightHalf;

                        // transform
                        element.style.transform = `translate(${- cx}%, ${- cy}%) translate(${tx}px, ${ty}px) rotate(${angle}rad)`;

                        if ( element.parentNode !== domElement ) {

                            domElement.appendChild( element );

                        }

                        object.onAfterRender( _this, scene, camera );

                    }

                    const objectData = {
                        distanceToCameraSquared: getDistanceToSquared( camera, object )
                    };

                    cache.objects.set( object, objectData );

                }

                for ( let i = 0, l = object.children.length; i < l; i ++ ) {

                    renderObject( object.children[ i ], scene, camera );

                }

            }

            function getDistanceToSquared( object1, object2 ) {

                _a.setFromMatrixPosition( object1.matrixWorld );
                _b.setFromMatrixPosition( object2.matrixWorld );

                return _a.distanceToSquared( _b );

            }

            function filterAndFlatten( scene ) {

                const result = [];

                scene.traverseVisible( function ( object ) {

                    if ( object.isCSS2DObject ) result.push( object );

                } );

                return result;

            }

            function zOrder( scene ) {

                const sorted = filterAndFlatten( scene ).sort( function ( a, b ) {

                    if ( a.renderOrder !== b.renderOrder ) {

                        return b.renderOrder - a.renderOrder;

                    }

                    const distanceA = cache.objects.get( a ).distanceToCameraSquared;
                    const distanceB = cache.objects.get( b ).distanceToCameraSquared;

                    return distanceA - distanceB;

                } );

                const zMax = sorted.length;

                for ( let i = 0, l = sorted.length; i < l; i ++ ) {

                    sorted[ i ].element.style.zIndex = zMax - i;

                }

            }

        }

    }

    // Expose globally on THREE (and window, for convenience) instead of
    // using ES `export`, since this is loaded as a plain script.
    THREE.CSS2DObject = CSS2DObject;
    THREE.CSS2DRenderer = CSS2DRenderer;
    window.CSS2DObject = CSS2DObject;
    window.CSS2DRenderer = CSS2DRenderer;

    }; // end of window.registerCSS2DRenderer

} )();