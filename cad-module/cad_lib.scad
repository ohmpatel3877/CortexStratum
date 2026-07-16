// ============================================================
// CAD LIBRARY - Reusable mechanical components
// ai-memory-core cad-module
// Bottle Flipping System - ENGR18922D
// ============================================================
// Include this in any SCAD file with: use <cad_lib.scad>
// ============================================================

// ---------- STANDARD PROFILES ----------

module rectangle_profile(w, d, h, center=false) {
    // Rectangular bar
    cube([w, d, h], center=center);
}

module round_bar(d, h, center=false) {
    // Round bar / dowel
    cylinder(h=h, r=d/2, center=center, $fn=24);
}

module c_channel(w, h, t, length) {
    // C-channel profile
    difference() {
        cube([w, h, length]);
        translate([t, t, -0.5])
            cube([w-2*t, h-2*t, length+1]);
    }
}

// ---------- FASTENERS ----------

module screw_hole(r, length, head_r=0, head_depth=0) {
    // Clearance hole for screw with optional countersink
    if (head_r > 0) {
        translate([0, 0, -0.5])
            cylinder(h=head_depth+0.5, r=head_r, $fn=16);
    }
    translate([0, 0, -0.5])
        cylinder(h=length+1, r=r, $fn=12);
}

module nut_trap(flat_to_flat, thickness, depth) {
    // Hexagonal nut trap for 3D printing
    r = flat_to_flat / 2 / cos(30);
    translate([0, 0, -0.5])
        cylinder(h=min(thickness, depth), r=r, $fn=6);
}

// ---------- MECHANICAL JOINTS ----------

module pin_joint(plate_thick, pin_d, shoulder_d, shoulder_h) {
    // Shoulder pin joint for linkages
    union() {
        // Shoulder
        cylinder(h=shoulder_h, r=shoulder_d/2, $fn=24);
        // Pin
        translate([0, 0, shoulder_h])
            cylinder(h=plate_thick, r=pin_d/2, $fn=18);
    }
}

module clevis(width, thickness, hole_d, hole_offset) {
    // Clevis bracket (U-shaped)
    difference() {
        union() {
            cube([thickness, width, hole_offset * 2]);
            translate([0, 0, hole_offset * 2])
                cube([thickness, width, thickness]);
        }
        translate([-0.5, width/2, hole_offset])
            rotate([0, 90, 0])
                cylinder(h=thickness+1, r=hole_d/2, $fn=18);
    }
}

// ---------- COUPLINGS ----------

module shaft_collar(shaft_d, od, length) {
    // Simple shaft collar with set screw
    difference() {
        cylinder(h=length, r=od/2, $fn=24);
        translate([0, 0, -0.5])
            cylinder(h=length+1, r=shaft_d/2, $fn=18);
        // Set screw
        translate([od/3, 0, length/2])
            rotate([0, 90, 0])
                cylinder(h=od, r=1.5, $fn=12);
    }
}

// ---------- STRUCTURAL ----------

module lightening_pocket(w, d, depth, corner_r=3) {
    // Lightening pocket with rounded corners
    linear_extrude(height=depth)
        offset(r=corner_r)
            square([w-2*corner_r, d-2*corner_r], center=true);
}

module fillet_chamfer(size) {
    // Simple edge chamfer for 3D printing
    // Apply at edges: translate([0,0,h]) cube([size, size, 0.5]);
    cube([size, size, 0.5]);
}

echo("CAD Library loaded - Bottle Flipper System");
echo("Available modules: rectangle_profile, round_bar, c_channel, screw_hole, nut_trap, pin_joint, clevis, shaft_collar, lightening_pocket, fillet_chamfer");
