---
readingTime:
  minutes: 1.98
  words: 495
fkglResult: 7.96
---

# 01.0 Writing Python Classes

Understanding how to write Python classes is the next step in turning your object-oriented programming knowledge into real, working code. In this lesson, you'll learn the basic structure of a Python class, the special role of the `__init__` method as a constructor, and why `self` is essential for referring to each individual object instance.

## The Anatomy of a Python Class

A Python class is like a blueprint for creating objects. It defines the attributes (data) and methods (behavior) that the objects created from it will have.

Here's the minimal structure of a Python class:

```python
class ClassName:
    def __init__(self, parameters):
        # Initialize attributes here
        self.attribute = value

    def method_name(self, other_parameters):
        # Define behavior here
        pass
```

### Key Components:

- **class ClassName:** This line declares a new class named `ClassName`.
- **`__init__` method:** This special method is called automatically when you create a new object (an instance) of the class. It sets up the initial state of the object.
- **`self` parameter:** This is a reference to the current instance of the class. It allows you to access attributes and methods on the object.

## Why `__init__` and `self` Matter

- The `__init__` method acts as a constructor. When you write `obj = ClassName(args)`, Python creates a new object and calls `__init__` to initialize it.
- The `self` parameter is not a Python keyword but a strong community convention. It must be the first parameter of any instance method.
- Using `self`, you assign values to the object's attributes, ensuring each instance has its own independent data.

## Example: Defining a Simple Warrior Class

Let's define a class `Warrior` that has a `name` and `health` attribute.

```python
class Warrior:
    def __init__(self, name, health):
        self.name = name      # Assign the name attribute
        self.health = health  # Assign the health attribute
```

Creating instances:

```python
warrior1 = Warrior("Aragorn", 100)
warrior2 = Warrior("Legolas", 90)

print(warrior1.name)  # Output: Aragorn
print(warrior2.health)  # Output: 90
```

Each `Warrior` object has its own `name` and `health` independent of others.

## Summary

- Use the `class` keyword to define a new class.
- The `__init__` method initializes new objects.
- `self` refers to the instance and is used to set or access attributes.
- Each object created from a class has its own independent attributes.

## Next Steps

In the next lesson, you'll learn how to add behavior to your classes by defining methods that operate on the instance's data.

---

