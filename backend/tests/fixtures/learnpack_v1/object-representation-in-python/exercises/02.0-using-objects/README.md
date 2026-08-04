---
readingTime:
  minutes: 1.936
  words: 484
fkglResult: 6.95
---

# 02.0 Using Objects

Understanding how to create and work with objects is a fundamental step in applying Object-Oriented Programming in Python. Now that you've defined classes and their behaviors, it's time to see what happens when you bring those classes to life by creating instances.

## What is Instantiation?

**Instantiation** is the process of creating a specific object from a class blueprint. Think of a class as a cookie cutter and each object as a cookie made from that cutter. When you instantiate a class, Python:

- Creates a new object in memory.
- Calls the `__init__` method to initialize the object's attributes.
- Returns the new object so you can use it.

For example:

```python
warrior1 = Warrior("Aragorn", 100)
```

Here, `warrior1` is an **instance** of the `Warrior` class, with its own `name` and `health`.

## Independence of Instances

Each object you create is independent. This means:

- Changing one object's attributes does not affect another.
- Each instance maintains its own state.

Example:

```python
warrior2 = Warrior("Legolas", 90)

warrior1.take_damage(25)

print(warrior1.health)  # Outputs: 75
print(warrior2.health)  # Outputs: 90
```

Even though both are `Warrior` objects, `warrior1` and `warrior2` have separate health values.

## Working with Objects: Dot Notation

You interact with objects using **dot notation**:

- Access attributes: `object.attribute`
- Call methods: `object.method()`

Example:

```python
print(warrior1.name)       # Outputs: Aragorn
warrior1.take_damage(10)   # Calls method to reduce health
```

Be cautious when modifying attributes directly from outside the class, as it can bypass important logic inside methods.

## Why Does This Matter?

Understanding instantiation and object independence allows you to model real-world entities accurately and manage complex data structures effectively. This foundation prepares you for more advanced topics like collections of objects and nested objects.

## Quick Recap

- **Instantiation** creates a new object from a class.
- Each object is an independent **instance** with its own data.
- Use **dot notation** to access attributes and methods.

## Test Your Understanding

Select the correct answer for each question.

1. What does instantiation do in Python?

   - [ ] It defines a new class.
   - [x] It creates a new object from a class.
   - [ ] It deletes an object.

2. If you have two instances of the same class, changing one instance's attribute will:

   - [ ] Change the attribute in the other instance.
   - [x] Only affect the instance you changed.
   - [ ] Change the class definition.

3. How do you call a method named `attack` on an object `warrior`?

   - [ ] `attack.warrior()`
   - [ ] `warrior.attack`
   - [x] `warrior.attack()`

4. What is the risk of modifying an object's attribute directly from outside the class?

   - [ ] There is no risk; it's always safe.
   - [x] It can bypass validation or logic inside methods.
   - [ ] It deletes the attribute.

Keep experimenting with your classes and objects. The more you practice, the more natural these concepts will become!