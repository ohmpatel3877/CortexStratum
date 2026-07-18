#!/usr/bin/env python3
"""
fea_analyzer.py - Basic FEA structural analysis for 3D printed / laser-cut parts
CortexStratum cad-module
Provides: section property analysis, beam stress calc, safety factor estimation
"""
import math


def rect_beam_stress(force_N, length_mm, width_mm, height_mm, yield_MPa=40):
    """
    Calculate max bending stress on a rectangular beam.
    Default yield = 40MPa (PLA). Laser-cut acrylic = ~70MPa.
    
    Returns: (stress_MPa, safety_factor, deflection_mm)
    """
    F = force_N
    L = length_mm / 1000  # convert to m
    w = width_mm / 1000
    h = height_mm / 1000
    
    # Moment of inertia for rectangle
    I = (w * h**3) / 12
    
    # Max bending moment (simply supported, center load)
    M = F * L / 4
    
    # Distance from neutral axis to extreme fiber
    c = h / 2
    
    # Max stress: sigma = Mc/I
    if I == 0:
        return (float('inf'), 0, float('inf'))
    stress_Pa = M * c / I
    stress_MPa = stress_Pa / 1e6
    
    # Safety factor
    sf = yield_MPa / stress_MPa if stress_MPa > 0 else float('inf')
    
    # Deflection (simply supported, center load)  delta = FL^3/(48EI)
    E_PLA = 3.5e9  # Pa (PLA modulus)
    E_acrylic = 3.0e9  # Pa
    E = E_PLA if yield_MPa <= 50 else E_acrylic
    
    deflection_m = (F * L**3) / (48 * E * I)
    deflection_mm = deflection_m * 1000
    
    return (round(stress_MPa, 2), round(sf, 2), round(deflection_mm, 3))


def column_buckling(force_N, length_mm, width_mm, height_mm, E_MPa=3500):
    """
    Euler buckling analysis for a column.
    Returns: (critical_load_N, safety_factor)
    """
    L = length_mm / 1000
    w = width_mm / 1000
    h = height_mm / 1000
    E = E_MPa * 1e6  # convert to Pa
    
    I_min = min((w * h**3) / 12, (h * w**3) / 12)
    
    # Euler buckling load (pinned-pinned)
    P_cr = (math.pi**2 * E * I_min) / (L**2)
    
    sf = P_cr / force_N if force_N > 0 else float('inf')
    
    return (round(P_cr, 1), round(sf, 2))


def bolt_shear(force_N, bolt_d_mm, count=1, shear_MPa=200):
    """
    Bolt shear strength check.
    Default shear_MPa = 200 for stainless steel M3/M4 bolts.
    """
    area = count * math.pi * (bolt_d_mm / 2)**2 / 1e6  # m^2
    shear_Pa = force_N / area
    shear_MPa_calc = shear_Pa / 1e6
    
    sf = shear_MPa / shear_MPa_calc if shear_MPa_calc > 0 else float('inf')
    
    return (round(shear_MPa_calc, 2), round(sf, 2))


def servo_torque_check(load_N, arm_mm, servo_torque_Nm=1.5):
    """
    Check if servo can handle the load at given arm length.
    Default servo_torque: SM-S2309S ~1.5 Nm at 6V.
    """
    torque_required = load_N * (arm_mm / 1000)
    margin = servo_torque_Nm - torque_required
    sf = servo_torque_Nm / torque_required if torque_required > 0 else float('inf')
    
    return {
        'torque_required_Nm': round(torque_required, 3),
        'servo_torque_Nm': servo_torque_Nm,
        'margin_Nm': round(margin, 3),
        'safety_factor': round(sf, 2),
        'adequate': margin >= 0
    }


def analyze_bottle_flipper():
    """Run full FEA analysis on the Bottle Flipping System."""
    print('=' * 60)
    print('  FEA ANALYSIS - Bottle Flipping System')
    print('=' * 60)
    
    # Parameters from the design
    bottle_mass = 0.5  # kg (500mL water)
    gravity = 9.81
    bottle_weight = bottle_mass * gravity  # ~4.9N
    
    # Clamping arm analysis
    print('\n--- Clamping Arm (130mm, 22x8mm cross-section) ---')
    stress, sf, deflection = rect_beam_stress(bottle_weight, 130, 22, 8, 40)
    print(f'  Max bending stress: {stress} MPa')
    print(f'  Safety factor (PLA): {sf}')
    print(f'  Tip deflection: {deflection} mm')
    
    # Servo torque check
    print('\n--- Servo Torque (SM-S2309S) ---')
    torque = servo_torque_check(bottle_weight, 80, 1.5)
    print(f'  Required torque at 80mm arm: {torque["torque_required_Nm"]} Nm')
    print(f'  Servo rated torque: {torque["servo_torque_Nm"]} Nm')
    print(f'  Safety factor: {torque["safety_factor"]}')
    print(f'  Adequate: {torque["adequate"]}')
    
    # Base frame (acrylic)
    print('\n--- Base Frame (6mm acrylic, 220x200mm) ---')
    stress2, sf2, defl2 = rect_beam_stress(bottle_weight * 2, 200, 220, 6, 70)
    print(f'  Max bending stress: {stress2} MPa')
    print(f'  Safety factor (acrylic): {sf2}')
    print(f'  Max deflection: {defl2} mm')
    
    # Bolt shear
    print('\n--- M3 Bolt Shear Check ---')
    shear, sf3 = bolt_shear(bottle_weight * 3, 3, 4, 200)
    print(f'  Shear stress (4 bolts): {shear} MPa')
    print(f'  Safety factor: {sf3}')
    
    # Column buckling on support ribs
    print('\n--- Support Rib Buckling (8mm tall, 5mm thick) ---')
    buckling, sf4 = column_buckling(bottle_weight * 5, 8, 5, 200, 3500)
    print(f'  Critical load: {buckling} N')
    print(f'  Safety factor: {sf4}')
    
    print('\n' + '=' * 60)
    print('  VERDICT:', end=' ')
    all_pass = all([
        sf > 2, torque['adequate'], sf2 > 2, sf3 > 5, sf4 > 10
    ])
    if all_pass:
        print('ALL CHECKS PASS - Design is structurally adequate')
    else:
        print('SOME CHECKS FAIL - Review highlighted items')
    print('=' * 60)


if __name__ == '__main__':
    import sys
    if '--all' in sys.argv or '-a' in sys.argv:
        analyze_bottle_flipper()
    else:
        print('Usage: python fea_analyzer.py --all')
        print('       python fea_analyzer.py <force_N> <length_mm> <width_mm> <height_mm>')
        if len(sys.argv) >= 5:
            F = float(sys.argv[1])
            L = float(sys.argv[2])
            W = float(sys.argv[3])
            H = float(sys.argv[4])
            stress, sf, defl = rect_beam_stress(F, L, W, H)
            print(f'\nBeam analysis:')
            print(f'  Force: {F}N, Length: {L}mm, Section: {W}x{H}mm')
            print(f'  Stress: {stress} MPa')
            print(f'  Safety Factor: {sf}')
            print(f'  Deflection: {defl} mm')
        else:
            analyze_bottle_flipper()
