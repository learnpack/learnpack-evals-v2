---
readingTime:
  minutes: 1.56
  words: 390
fkglResult: 9.79
---

# 01.3 Define a Python Class

In this lesson, you'll put into practice what you've learned about Python classes by defining your own **Warrior** class. This class will have attributes to store a warrior's name and health, and a method to reduce health when the warrior takes damage.

## Defining the Warrior Class

Here's the complete code for the Warrior class and how to create instances and interact with them:

```python
class Warrior:
    def __init__(self, name, health):
        # Assign the name and health attributes to the instance
        self.name = name
        self.health = health

    def take_damage(self, amount):
        # Reduce the instance's health by the damage amount
        self.health -= amount

# Create two Warrior instances with different names and health values
warrior1 = Warrior("Aragorn", 100)
warrior2 = Warrior("Legolas", 90)

# Apply damage to the first warrior
warrior1.take_damage(25)

# Print the current state of each warrior
print(f"{warrior1.name} has {warrior1.health} health")  # Output: Aragorn has 75 health
print(f"{warrior2.name} has {warrior2.health} health")  # Output: Legolas has 90 health
```

### What’s Happening Here?

- The `__init__` method sets up each new Warrior with a `name` and `health`.
- The `take_damage` method decreases the warrior's health by the specified amount.
- Each warrior instance maintains its own independent state — changing one does not affect the other.

## Why Use `self`?

The `self` parameter in methods refers to the specific instance of the class. It allows each warrior to keep track of its own attributes:

- `self.name` and `self.health` belong to the individual warrior.
- When you call `warrior1.take_damage(25)`, Python automatically passes `warrior1` as `self`.

## Practice Suggestion

Try creating a new warrior and call `take_damage` with different values. Observe how each instance maintains its own independent state.

## Conceptual Illustration

![GENERATING: Create a clear, modern educational illustration for a chapter titled “Define a Python Class”.
In the center, show a large, clean diagram of a Python class definition, using a simple example like a  Warrior  class. The diagram should highlight the key parts of a class: the  class  keyword, the class name (e.g.  Warrior ), the  __init__  constructor, parameters like  self ,  name , and  health , and a couple of basic methods. Visually emphasize the structure and indentation so beginners can see how all the pieces fit together.
Around the main class diagram, add small annotations or labels with short phrases like “class name”, “constructor”, “attributes”, and “methods”, using arrows or callouts that point to the corresponding lines of code. Optionally, show one or two tiny instance examples (like  warrior1 = Warrior("Aragorn", 100) ) near the bottom, to hint that defining a class is what enables creating objects.
Use a flat or semi-flat illustration style with a calm, educational color palette (soft blues and purples with warm accent colors), lots of white space, and legible monospace-style text for the code. The overall look should feel like a polished slide or textbook header for a beginner-friendly Python OOP course.
Aspect ratio 16:9, suitable as a section cover for “01.3 Define a Python Class
](/.learn/assets/1mnu2vi820th)

This image helps you visualize how the class blueprint creates individual warriors, each with their own data and behavior.

---

Keep experimenting with your Warrior class by adding new methods like `heal` or `attack` to deepen your understanding of how state and behavior work together in Python classes!