# Electrical Assembly Skill

Integrates the ai-memory-core electrical-module for circuit design, wiring diagrams, pin mapping, and power budgeting.

## When to use

Use when designing circuits, wiring diagrams, Arduino pin assignments, power budget calculations, or documenting electrical connections for mechatronic projects.

## Module Location

`C:\Users\ohmpa\github\ai-memory-core\electrical-module\`

## Tools

### circuit_designer.py
Complete circuit design system with:
- Component library (Arduino Uno, servo SM-S2309S, LCD 16x2 I2C, INA219, IR sensor)
- Connection validation and pin compatibility checking
- SVG wiring diagram generation
- Power budget calculator
- Arduino pin map generator

### Usage

```bash
python electrical-module/circuit_designer.py
```

Output: circuit validation, power budget, pin map, and SVG wiring diagram generated in Downloads.

## Example: Bottle Flipper

| Component | Arduino Pin | Function |
|---|---|---|
| Drive Servo | D9 (PWM) | Four-bar linkage rotation |
| Clamp Servo | D10 (PWM) | Bottle grip |
| IR Sensor | D2 | Bottle detect |
| LCD I2C | A4 (SDA), A5 (SCL) | Status display |
| INA219 | A4 (SDA), A5 (SCL) | Power measurement |

All I2C devices share the SDA/SCL bus at address 0x27 (LCD) and 0x40 (INA219).
