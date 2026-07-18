#!/usr/bin/env python3
"""
circuit_designer.py - Circuit schematic generator & wiring diagram creator
CortexStratum electrical-module
Generates SVG wiring diagrams, validates connections, produces pin maps
"""
import json
import math
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Component:
    name: str
    type: str
    pins: dict  # pin_name -> (x_offset, y_offset, electrical_role)
    package: str = ""
    datasheet: str = ""


@dataclass
class Connection:
    from_comp: str
    from_pin: str
    to_comp: str
    to_pin: str
    wire_type: str = "signal"  # signal, power, gnd


@dataclass
class Circuit:
    name: str
    components: dict = field(default_factory=dict)
    connections: list = field(default_factory=list)
    power_rails: dict = field(default_factory=lambda: {"VCC": "5V", "GND": "0V"})


# ---- Component Library ----
COMPONENT_LIBRARY = {
    "arduino_uno": Component(
        name="Arduino Uno R3",
        type="microcontroller",
        pins={
            "D2": (20, 40, "GPIO"), "D3": (20, 50, "GPIO_PWM"),
            "D4": (20, 60, "GPIO"), "D5": (20, 70, "GPIO_PWM"),
            "D6": (20, 80, "GPIO_PWM"), "D7": (20, 90, "GPIO"),
            "D8": (20, 100, "GPIO"), "D9": (20, 110, "GPIO_PWM"),
            "D10": (20, 120, "GPIO_PWM"), "D11": (20, 130, "GPIO_PWM"),
            "D12": (20, 140, "GPIO"), "D13": (20, 150, "GPIO_LED"),
            "A0": (20, 170, "ANALOG"), "A1": (20, 180, "ANALOG"),
            "A2": (20, 190, "ANALOG"), "A3": (20, 200, "ANALOG"),
            "A4": (20, 210, "ANALOG_I2C"), "A5": (20, 220, "ANALOG_I2C"),
            "5V": (0, 40, "POWER"), "3V3": (0, 50, "POWER"),
            "GND": (0, 60, "GROUND"), "VIN": (0, 70, "POWER_IN"),
            "RESET": (0, 30, "INPUT"),
        },
        package="DIP",
        datasheet="https://docs.arduino.cc/hardware/uno-rev3"
    ),
    "sm_s2309s": Component(
        name="SM-S2309S Servo",
        type="servo",
        pins={
            "PWM": (30, 0, "SIGNAL"),
            "VCC": (15, 0, "POWER_5V"),
            "GND": (0, 0, "GROUND"),
        },
        package="standard",
        datasheet="https://www.servocity.com/sm-s2309s"
    ),
    "lcd_16x2_i2c": Component(
        name="16x2 LCD I2C",
        type="display",
        pins={
            "VCC": (0, 10, "POWER_5V"),
            "GND": (0, 20, "GROUND"),
            "SDA": (0, 30, "I2C_DATA"),
            "SCL": (0, 40, "I2C_CLOCK"),
        },
        package="module",
        datasheet="Standard HD44780 + I2C backpack"
    ),
    "ina219": Component(
        name="INA219 Power Monitor",
        type="sensor",
        pins={
            "VCC": (0, 10, "POWER_5V"),
            "GND": (0, 20, "GROUND"),
            "SDA": (0, 30, "I2C_DATA"),
            "SCL": (0, 40, "I2C_CLOCK"),
            "VIN+": (20, 10, "SENSE"),
            "VIN-": (20, 20, "SENSE"),
        },
        package="module",
        datasheet="Texas Instruments SBOS448G"
    ),
    "ir_sensor": Component(
        name="IR Proximity Sensor E18-D80NK",
        type="sensor",
        pins={
            "VCC": (0, 10, "POWER_5V"),
            "GND": (0, 20, "GROUND"),
            "OUT": (0, 30, "DIGITAL_OUT"),
        },
        package="module",
        datasheet="E18-D80NK datasheet"
    ),
    "battery": Component(
        name="5V Power Supply",
        type="power",
        pins={
            "VCC": (10, 0, "POWER_5V"),
            "GND": (0, 0, "GROUND"),
        },
        package="bench supply"
    ),
}


class CircuitDesigner:
    """Generates circuit schematics, wiring diagrams, and validates connections."""

    def __init__(self, name="Bottle Flipper Circuit"):
        self.circuit = Circuit(name=name)
        self._placed = {}

    def add_component(self, name: str, comp_type: str, custom_pins: dict = None):
        """Add a component from library or with custom pinout."""
        lib_key = comp_type.lower().replace(" ", "_")
        if lib_key in COMPONENT_LIBRARY:
            base = COMPONENT_LIBRARY[lib_key]
            comp = Component(
                name=name,
                type=base.type,
                pins=custom_pins or base.pins,
                package=base.package,
                datasheet=base.datasheet
            )
        else:
            comp = Component(name=name, type=comp_type, pins=custom_pins or {})
        self.circuit.components[name] = comp
        return comp

    def connect(self, from_comp: str, from_pin: str, to_comp: str, to_pin: str, wire_type="signal"):
        """Add a wire connection between two component pins."""
        for c_name in [from_comp, to_comp]:
            if c_name not in self.circuit.components:
                raise ValueError(f"Component '{c_name}' not in circuit")
        conn = Connection(from_comp, from_pin, to_comp, to_pin, wire_type)
        self.circuit.connections.append(conn)
        return conn

    def validate(self):
        """Validate the circuit: check all connections go to valid pins."""
        issues = []
        for conn in self.circuit.connections:
            src = self.circuit.components[conn.from_comp]
            dst = self.circuit.components[conn.to_comp]
            if conn.from_pin not in src.pins:
                issues.append(f"Pin {conn.from_pin} not on {conn.from_comp}")
            if conn.to_pin not in dst.pins:
                issues.append(f"Pin {conn.to_pin} not on {conn.to_comp}")
            # Check electrical compatibility
            src_role = src.pins.get(conn.from_pin, ("", "", ""))[2] if len(src.pins.get(conn.from_pin, (0,0,""))) > 2 else ""
            dst_role = dst.pins.get(conn.to_pin, ("", "", ""))[2] if len(dst.pins.get(conn.to_pin, (0,0,""))) > 2 else ""
            if "POWER" in src_role and "GROUND" in dst_role:
                issues.append(f"WARN: {conn.from_comp}.{conn.from_pin} (power) to {conn.to_comp}.{conn.to_pin} (gnd)")
            if "GROUND" in src_role and "POWER" in dst_role:
                issues.append(f"OK: Ground reference established")
        return issues

    def power_budget(self):
        """Calculate total power consumption."""
        loads = {
            "servo": {"count": 2, "current_A": 0.75, "voltage_V": 5.0},  # stall current
            "arduino": {"count": 1, "current_A": 0.05, "voltage_V": 5.0},
            "lcd": {"count": 1, "current_A": 0.02, "voltage_V": 5.0},
            "ina219": {"count": 1, "current_A": 0.001, "voltage_V": 5.0},
            "ir_sensor": {"count": 1, "current_A": 0.01, "voltage_V": 5.0},
        }
        total_current = sum(v["count"] * v["current_A"] for v in loads.values())
        total_power = total_current * 5.0
        
        return {
            "total_current_A": round(total_current, 3),
            "total_power_W": round(total_power, 3),
            "components": loads,
            "power_supply_recommended": f"{round(total_current * 1.5, 1)}A at 5V (50% headroom)"
        }

    def generate_pin_map(self):
        """Generate a complete Arduino pin assignment table."""
        pins = []
        for conn in self.circuit.connections:
            if "arduino" in conn.from_comp.lower():
                pins.append((conn.from_pin, conn.to_comp, conn.to_pin, conn.wire_type))
            elif "arduino" in conn.to_comp.lower():
                pins.append((conn.to_pin, conn.from_comp, conn.from_pin, conn.wire_type))
        return pins

    def to_wiring_svg(self, output_path=None):
        """Generate an SVG wiring diagram."""
        svg_parts = []
        x_offset = 50
        y_offset = 50
        spacing = 120

        svg_parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" width="800" height="600">
  <rect width="800" height="600" fill="#f8f9fa" rx="8"/>
  <text x="400" y="30" text-anchor="middle" font-family="Arial" font-size="18" font-weight="bold" fill="#1a1a2e">{self.circuit.name} - Wiring Diagram</text>
''')

        # Draw components as boxes
        for i, (cname, comp) in enumerate(self.circuit.components.items()):
            cx = x_offset + (i % 3) * 250
            cy = y_offset + (i // 3) * 180
            self._placed[cname] = (cx, cy)
            
            w = 140
            h = len(comp.pins) * 18 + 30
            svg_parts.append(f'  <rect x="{cx}" y="{cy}" width="{w}" height="{h}" rx="6" fill="#e8e8e8" stroke="#555" stroke-width="1.5"/>')
            svg_parts.append(f'  <text x="{cx + w/2}" y="{cy + 18}" text-anchor="middle" font-family="Arial" font-size="10" font-weight="bold" fill="#333">{cname}</text>')
            svg_parts.append(f'  <text x="{cx + w/2}" y="{cy + 30}" text-anchor="middle" font-family="Arial" font-size="8" fill="#666">{comp.type}</text>')
            
            for j, (pname, (px, py, role)) in enumerate(comp.pins.items()):
                pin_y = cy + 35 + j * 18
                color = {"POWER": "#e74c3c", "GROUND": "#333", "SIGNAL": "#3498db", "GPIO": "#27ae60", "ANALOG": "#f39c12", "I2C": "#8e44ad"}.get(role.split("_")[0], "#555")
                svg_parts.append(f'  <circle cx="{cx + 10}" cy="{pin_y}" r="3" fill="{color}"/>')
                svg_parts.append(f'  <text x="{cx + 18}" y="{pin_y + 4}" font-family="monospace" font-size="8" fill="{color}">{pname}</text>')

        # Draw connections as lines
        for conn in self.circuit.connections:
            if conn.from_comp in self._placed and conn.to_comp in self._placed:
                x1, y1 = self._placed[conn.from_comp]
                x2, y2 = self._placed[conn.to_comp]
                # Find specific pin positions
                src_pins = self.circuit.components[conn.from_comp].pins
                dst_pins = self.circuit.components[conn.to_comp].pins
                
                pin_idx_src = list(src_pins.keys()).index(conn.from_pin) if conn.from_pin in src_pins else 0
                pin_idx_dst = list(dst_pins.keys()).index(conn.to_pin) if conn.to_pin in dst_pins else 0
                
                y1 += 35 + pin_idx_src * 18
                y2 += 35 + pin_idx_dst * 18
                
                color = {"signal": "#3498db", "power": "#e74c3c", "gnd": "#333"}.get(conn.wire_type, "#3498db")
                svg_parts.append(f'  <line x1="{x1 + 10}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.5" stroke-dasharray="4,2" opacity="0.7"/>')

        svg_parts.append('</svg>')
        
        svg_content = '\n'.join(svg_parts)
        if output_path:
            Path(output_path).write_text(svg_content)
        return svg_content


def design_bottle_flipper_circuit():
    """Create the complete Bottle Flipper circuit."""
    cd = CircuitDesigner("Bottle Flipping System - Circuit")
    
    # Add components
    cd.add_component("Arduino Uno", "arduino_uno")
    cd.add_component("Drive Servo", "sm_s2309s")
    cd.add_component("Clamp Servo", "sm_s2309s")
    cd.add_component("LCD Display", "lcd_16x2_i2c")
    cd.add_component("Power Monitor", "ina219")
    cd.add_component("IR Sensor", "ir_sensor")
    cd.add_component("Power Supply", "battery")
    
    # Power connections
    cd.connect("Power Supply", "VCC", "Arduino Uno", "VIN", "power")
    cd.connect("Power Supply", "GND", "Arduino Uno", "GND", "gnd")
    
    # Drive servo (pin 9 - PWM capable)
    cd.connect("Arduino Uno", "D9", "Drive Servo", "PWM", "signal")
    cd.connect("Arduino Uno", "5V", "Drive Servo", "VCC", "power")
    cd.connect("Arduino Uno", "GND", "Drive Servo", "GND", "gnd")
    
    # Clamp servo (pin 10 - PWM capable)
    cd.connect("Arduino Uno", "D10", "Clamp Servo", "PWM", "signal")
    cd.connect("Arduino Uno", "5V", "Clamp Servo", "VCC", "power")
    cd.connect("Arduino Uno", "GND", "Clamp Servo", "GND", "gnd")
    
    # LCD (I2C - pins A4/A5)
    cd.connect("Arduino Uno", "A4", "LCD Display", "SDA", "signal")
    cd.connect("Arduino Uno", "A5", "LCD Display", "SCL", "signal")
    cd.connect("Arduino Uno", "5V", "LCD Display", "VCC", "power")
    cd.connect("Arduino Uno", "GND", "LCD Display", "GND", "gnd")
    
    # INA219 (I2C - shared bus)
    cd.connect("Arduino Uno", "A4", "Power Monitor", "SDA", "signal")
    cd.connect("Arduino Uno", "A5", "Power Monitor", "SCL", "signal")
    cd.connect("Arduino Uno", "5V", "Power Monitor", "VCC", "power")
    cd.connect("Arduino Uno", "GND", "Power Monitor", "GND", "gnd")
    
    # INA219 in series with drive servo for power measurement
    cd.connect("Power Monitor", "VIN+", "Drive Servo", "VCC", "power")
    
    # IR Sensor
    cd.connect("Arduino Uno", "D2", "IR Sensor", "OUT", "signal")
    cd.connect("Arduino Uno", "5V", "IR Sensor", "VCC", "power")
    cd.connect("Arduino Uno", "GND", "IR Sensor", "GND", "gnd")
    
    return cd


if __name__ == '__main__':
    cd = design_bottle_flipper_circuit()
    
    print('=' * 60)
    print('  CIRCUIT DESIGN - Bottle Flipping System')
    print('=' * 60)
    
    print(f'\nComponents: {len(cd.circuit.components)}')
    for name, comp in cd.circuit.components.items():
        print(f'  {name}: {comp.type} ({len(comp.pins)} pins)')
    
    print(f'\nConnections: {len(cd.circuit.connections)}')
    for conn in cd.circuit.connections:
        print(f'  {conn.from_comp}.{conn.from_pin} -> {conn.to_comp}.{conn.to_pin} [{conn.wire_type}]')
    
    print(f'\nValidation:')
    issues = cd.validate()
    for i in issues:
        print(f'  {i}')
    
    print(f'\nPower Budget:')
    budget = cd.power_budget()
    print(f'  Total current: {budget["total_current_A"]}A')
    print(f'  Total power: {budget["total_power_W"]}W')
    print(f'  Recommended supply: {budget["power_supply_recommended"]}')
    
    print(f'\nArduino Pin Map:')
    pin_map = cd.generate_pin_map()
    for pin, comp, comp_pin, wtype in sorted(pin_map):
        print(f'  {pin:5s} -> {comp:15s} {comp_pin:8s} ({wtype})')
    
    # Generate wiring SVG (already done)
    svg = cd.to_wiring_svg()
    print(f'\nWiring SVG generated: {len(svg)} chars')
    print('Done.')
