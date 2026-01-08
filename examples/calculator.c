/*
 * Example C program demonstrating Mistode obfuscation
 *
 * This simple calculator program shows how Mistode handles:
 * - Function declarations and definitions
 * - Variable names
 * - Comments
 * - Preprocessor directives (preserved)
 * - Standard library functions (preserved)
 */

#include <stdio.h>
#include <stdlib.h>

// Define constants
#define PI 3.14159265358979323846
#define MAX_OPERATIONS 100

// Structure to hold calculator state
struct Calculator {
  int operation_count;
  double last_result;
};

// Initialize calculator
void init_calculator(struct Calculator *calc) {
  calc->operation_count = 0;
  calc->last_result = 0.0;
}

// Calculate the area of a circle
double calculate_area(double radius) {
  double area = PI * radius * radius;
  return area;
}

// Calculate the volume of a cylinder
double calculate_volume(double radius, double height) {
  double base_area = calculate_area(radius);
  double volume = base_area * height;
  return volume;
}

// Perform addition
double add_numbers(struct Calculator *calc, double a, double b) {
  double result = a + b;
  calc->last_result = result;
  calc->operation_count++;
  return result;
}

// Perform multiplication
double multiply_numbers(struct Calculator *calc, double a, double b) {
  double result = a * b;
  calc->last_result = result;
  calc->operation_count++;
  return result;
}

// Print calculator statistics
void print_stats(struct Calculator *calc) {
  printf("Calculator Statistics:\n");
  printf("  Operations performed: %d\n", calc->operation_count);
  printf("  Last result: %.2f\n", calc->last_result);
}

int main() {
  struct Calculator calc;
  init_calculator(&calc);

  // Test geometric calculations
  double radius = 5.0;
  double height = 10.0;

  double area = calculate_area(radius);
  double volume = calculate_volume(radius, height);

  printf("Circle area (r=%.1f): %.2f\n", radius, area);
  printf("Cylinder volume (r=%.1f, h=%.1f): %.2f\n", radius, height, volume);

  // Test arithmetic operations
  double sum = add_numbers(&calc, 10.5, 20.3);
  double product = multiply_numbers(&calc, 3.14, 2.0);

  printf("\nArithmetic results:\n");
  printf("  10.5 + 20.3 = %.2f\n", sum);
  printf("  3.14 * 2.0 = %.2f\n", product);

  printf("\n");
  print_stats(&calc);

  return 0;
}
