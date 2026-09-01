import fs from 'fs';
import path from 'path';
import * as THREE from 'three';
import { OBJExporter } from 'three/examples/jsm/exporters/OBJExporter.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { pathToFileURL } from 'url';

// Full part-structure export for a Three.js scene.
//   part_meshes/<part_name>/<mesh_name>.obj  -> one OBJ per individual mesh
//   links/<part_name>.obj                    -> one merged OBJ per part
//
// A "part" (link) is any NAMED THREE.Group. Each mesh belongs to its NEAREST
// named-group ancestor; nested named groups are separate parts (their meshes are
// NOT merged into an ancestor). Parts with no owned meshes are skipped.
//
// Usage:
//   node export_structure.mjs [--input <scene.js>] \
//        [--part-mesh-dir <dir>] [--link-dir <dir>]
// Defaults match the standard task layout (/root/data/object.js, /root/output/...).

const args = process.argv.slice(2);
const getArg = (flag, fallback) => {
    const idx = args.indexOf(flag);
    if (idx === -1 || idx + 1 >= args.length) return fallback;
    return args[idx + 1];
};

const INPUT_PATH = getArg('--input', '/root/data/object.js');
const PART_MESH_DIR = getArg('--part-mesh-dir', '/root/output/part_meshes');
const LINK_DIR = getArg('--link-dir', '/root/output/links');

const sceneModuleURL = pathToFileURL(INPUT_PATH).href;
const sceneModule = await import(sceneModuleURL);
const root = typeof sceneModule.createScene === 'function'
    ? sceneModule.createScene()
    : sceneModule.sceneObject;

if (!root) {
    throw new Error('Scene module must export createScene() or sceneObject.');
}

root.updateMatrixWorld(true);

fs.rmSync(PART_MESH_DIR, { recursive: true, force: true });
fs.rmSync(LINK_DIR, { recursive: true, force: true });
fs.mkdirSync(PART_MESH_DIR, { recursive: true });
fs.mkdirSync(LINK_DIR, { recursive: true });

// Every named group is a candidate part/link (including the root if it owns meshes).
const linkMeshMap = {};
root.traverse((obj) => {
    if (obj instanceof THREE.Group && obj.name) {
        linkMeshMap[obj.name] = { group: obj, meshes: [] };
    }
});

// Assign each mesh to its nearest named-group ancestor.
root.traverse((obj) => {
    if (!(obj instanceof THREE.Mesh)) return;
    let parent = obj.parent;
    let parentLink = null;
    while (parent) {
        if (parent instanceof THREE.Group && parent.name) {
            parentLink = parent;
            break;
        }
        parent = parent.parent;
    }
    if (parentLink && linkMeshMap[parentLink.name]) {
        linkMeshMap[parentLink.name].meshes.push(obj);
    }
});

const exporter = new OBJExporter();

// Bake world transform into a standalone geometry. toNonIndexed() is REQUIRED:
// primitive geometries are indexed, and the verifier compares raw vertex clouds,
// so indexed vs non-indexed produces a different vertex set and fails matching.
const bake = (mesh) => {
    let geom = mesh.geometry.clone();
    geom.applyMatrix4(mesh.matrixWorld);
    if (geom.index) {
        geom = geom.toNonIndexed();
    }
    if (!geom.attributes.normal) {
        geom.computeVertexNormals();
    }
    return geom;
};

const exportMesh = (geom, filepath, name) => {
    const tempMesh = new THREE.Mesh(geom);
    tempMesh.name = name;
    fs.writeFileSync(filepath, exporter.parse(tempMesh));
};

let unnamedIndex = 0;
let meshFileCount = 0;
let linkFileCount = 0;

for (const [linkName, linkData] of Object.entries(linkMeshMap)) {
    if (linkData.meshes.length === 0) continue; // skip parts with no owned meshes

    const linkDir = path.join(PART_MESH_DIR, linkName);
    fs.mkdirSync(linkDir, { recursive: true });

    const geometries = [];
    for (const mesh of linkData.meshes) {
        const geom = bake(mesh);
        geometries.push(geom);

        const meshName = mesh.name || `unnamed_mesh_${unnamedIndex++}`;
        exportMesh(geom, path.join(linkDir, `${meshName}.obj`), meshName);
        meshFileCount += 1;
    }

    const merged = mergeGeometries(geometries, false);
    if (merged) {
        const mergedMesh = new THREE.Mesh(merged);
        mergedMesh.name = linkName;
        fs.writeFileSync(path.join(LINK_DIR, `${linkName}.obj`), exporter.parse(mergedMesh));
        linkFileCount += 1;
    }
}

console.log(`Wrote ${meshFileCount} mesh OBJ files under ${PART_MESH_DIR}`);
console.log(`Wrote ${linkFileCount} link OBJ files under ${LINK_DIR}`);
