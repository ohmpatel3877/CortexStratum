/**
 * opengeometry-shim.mjs — Node/ESM bridge for CortexStratum's geometry-module.py.
 *
 * Reads a JSON command from stdin: { "op": "...", "args": {...} }
 * Writes a JSON result to stdout: { "ok": true, "data": {...} } or { "ok": false, "error": "..." }
 *
 * OpenGeometry is a Rust/WASM CAD kernel (npm: opengeometry). The WASM must be initialized
 * via `await OpenGeometry.create({ wasmURL: <bytes> })` BEFORE constructing any kernel object.
 * This shim runs as ESM so top-level await works, and loads the local .wasm bytes directly
 * (Node has no browser fetch/base-URL to resolve it automatically).
 *
 * Real kernel-backed ops:
 *   primitive  -> make Cuboid/Cylinder/Sphere/Wedge -> B-rep (verts/edges/faces) + bounds
 *   brep       -> getBrepData() of a primitive -> full topology
 *   boolean    -> shape.subtract([operand]) / union / intersection -> B-rep of result
 *   transform  -> setPlacement translate/rotate/scale on a shape
 */
import * as og from "opengeometry";
import fs from "fs";
import path from "path";

function brepSummary(brep) {
  const verts = brep.vertices || [];
  const xs = [], ys = [], zs = [];
  for (const v of verts) {
    const p = v.position || v;
    xs.push(p.x ?? p[0]); ys.push(p.y ?? p[1]); zs.push(p.z ?? p[2]);
  }
  const mn = [Math.min(...xs), Math.min(...ys), Math.min(...zs)];
  const mx = [Math.max(...xs), Math.max(...ys), Math.max(...zs)];
  return {
    vertices: verts.length,
    edges: (brep.edges || []).length,
    faces: (brep.faces || []).length,
    bounds: { min: mn, max: mx, size: [mx[0]-mn[0], mx[1]-mn[1], mx[2]-mn[2]] },
  };
}

function makePrimitive(s) {
  const kind = (s.kind || "cuboid").toLowerCase();
  if (kind === "cuboid") return new og.Cuboid(s.width ?? 1, s.height ?? 1, s.depth ?? 1);
  if (kind === "cylinder") return new og.Cylinder(s.radius ?? 0.5, s.height ?? 1);
  if (kind === "sphere") return new og.Sphere(s.radius ?? 0.5);
  if (kind === "wedge") return new og.Wedge(s.width ?? 1, s.height ?? 1, s.depth ?? 1);
  throw new Error(`unknown primitive kind: ${kind}`);
}

function run(cmd) {
  const { op, args = {} } = cmd;
  switch (op) {
    case "primitive":
    case "brep": {
      const shape = makePrimitive(args);
      const brep = shape.getBrepData();
      return { kind: (args.kind || "cuboid").toLowerCase(), brep: brepSummary(brep), raw: op === "brep" ? brep : undefined };
    }
    case "boolean": {
      const mode = (args.mode || "subtraction").toLowerCase();
      const a = makePrimitive(args.a || { kind: "cuboid", width: 2, height: 2, depth: 2 });
      const b = makePrimitive(args.b || { kind: "cylinder", radius: 0.6, height: 2.2 });
      let result;
      try {
        if (mode === "union") result = a.union ? a.union([b]) : og.booleanUnion(a, b);
        else if (mode === "intersection") result = a.intersection ? a.intersection([b]) : og.booleanIntersection(a, b);
        else result = a.subtract([b]);
      } catch (e) { throw new Error(`boolean ${mode} failed: ${e.message}`); }
      if (!result || (result.error)) throw new Error(`boolean ${mode} failed: ${result?.error?.toString?.() || "empty result"}`);
      const brep = result.getBrepData ? result.getBrepData() : null;
      return { mode, brep: brep ? brepSummary(brep) : null };
    }
    case "transform": {
      const shape = makePrimitive(args.shape || { kind: "cuboid", width: 1, height: 1, depth: 1 });
      const pl = shape.getPlacement ? shape.getPlacement() : null;
      if (args.translate && pl && pl.translate) pl.translate(new og.Vector3(args.translate[0], args.translate[1], args.translate[2]));
      if (args.rotate && pl && pl.rotate) pl.rotate(new og.Vector3(args.rotate[0], args.rotate[1], args.rotate[2]));
      if (args.scale && pl && pl.scale) pl.scale(new og.Vector3(args.scale[0], args.scale[1], args.scale[2]));
      return { placed: true, brep: brepSummary(shape.getBrepData()) };
    }
    default:
      throw new Error(`unknown op: ${op}`);
  }
}

async function main() {
  let input = "";
  for await (const chunk of process.stdin) input += chunk;
  try {
    const wasmRel = path.resolve("node_modules/opengeometry/opengeometry_bg.wasm");
    const wasmBytes = fs.readFileSync(wasmRel);
    await og.OpenGeometry.create({ wasmURL: wasmBytes });
    const data = run(JSON.parse(input));
    process.stdout.write(JSON.stringify({ ok: true, data }));
  } catch (e) {
    process.stdout.write(JSON.stringify({ ok: false, error: String(e.message || e) }));
  }
}
main();
