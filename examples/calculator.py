"""
Example Python script demonstrating Mistode obfuscation

This simple calculator module shows how Mistode handles:
- Function definitions
- Parameter names
- Local variables
- Imported modules (preserved)
- Built-in functions (preserved)
"""

import math
from datetime import datetime


def calculate_area(radius):
    """Calculate the area of a circle given its radius"""
    pi_value = math.pi
    area = pi_value * radius**2
    return area


def calculate_volume(radius, height):
    """Calculate the volume of a cylinder"""
    base_area = calculate_area(radius)
    volume = base_area * height
    return volume


def format_result(value, unit="m²"):
    """Format a numerical result with units"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result_str = f"[{timestamp}] Result: {value:.2f} {unit}"
    return result_str


class Calculator:
    """A simple calculator class"""

    def __init__(self, precision=2):
        self.precision = precision
        self.history = []

    def add(self, a, b):
        """Add two numbers"""
        result = a + b
        self.history.append(("add", a, b, result))
        return round(result, self.precision)

    def multiply(self, a, b):
        """Multiply two numbers"""
        result = a * b
        self.history.append(("multiply", a, b, result))
        return round(result, self.precision)

    def get_history(self):
        """Return calculation history"""
        return self.history


if __name__ == "__main__":
    # Test the functions
    r = 5.0
    h = 10.0

    area = calculate_area(r)
    volume = calculate_volume(r, h)

    print(format_result(area, "m²"))
    print(format_result(volume, "m³"))

    # Test the calculator class
    calc = Calculator(precision=3)
    result1 = calc.add(10.5, 20.3)
    result2 = calc.multiply(3.14, 2.0)

    print(f"Addition result: {result1}")
    print(f"Multiplication result: {result2}")
    print(f"History: {calc.get_history()}")
