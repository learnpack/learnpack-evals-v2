---
readingTime:
  minutes: 2.264
  words: 566
fkglResult: 7.7
---

# 02.2 Object Structures

In Python, objects can be more than just simple containers of data. They can hold other objects as attributes, and you can manage collections of these objects using lists. This ability allows you to model complex real-world systems in a natural and organized way.

## Objects Containing Other Objects

Imagine a **Car** that has **Wheels**. Each wheel is an object with its own properties, like pressure. The car object contains a list of these wheel objects as one of its attributes.

```python
class Wheel:
    def __init__(self, pressure):
        self.pressure = pressure  # pressure in PSI

class Car:
    def __init__(self, brand):
        self.brand = brand
        self.wheels = [Wheel(32), Wheel(32), Wheel(30), Wheel(31)]

car = Car("Toyota")
print(f"First wheel pressure: {car.wheels[0].pressure} PSI")

# Modify the pressure of the second wheel
car.wheels[1].pressure = 33
print(f"Second wheel new pressure: {car.wheels[1].pressure} PSI")
```

Here, `car.wheels` is a list of `Wheel` objects. You can access each wheel and its attributes using **dot notation** combined with list indexing.

## Managing Lists of Object Instances

You can also create lists that hold multiple instances of a class, such as users in an application.

```python
class User:
    def __init__(self, username):
        self.username = username

users = [User("Ana"), User("Luis"), User("Marta")]

for user in users:
    print(f"User: {user.username}")
```

This pattern is common in real-world applications, where you might manage collections of posts, products, or any entities.

## Adding Behavior to Object Collections

You can add methods to your classes that operate on these collections. For example, a `Car` class might check if any wheel's pressure is below a safe threshold.

```python
class Car:
    def __init__(self, brand):
        self.brand = brand
        self.wheels = [Wheel(32), Wheel(32), Wheel(30), Wheel(31)]

    def check_wheel_pressure(self, min_pressure):
        for wheel in self.wheels:
            if wheel.pressure < min_pressure:
                return True
        return False

car = Car("Honda")
print(car.check_wheel_pressure(31))  # Outputs: True because one wheel is 30 PSI
```

## Why Use Objects Within Objects?

- **Modularity:** Each class handles its own data and behavior.
- **Clarity:** Complex systems are broken down into manageable parts.
- **Reusability:** You can reuse classes like `Wheel` in different contexts.

## Summary

- Objects can contain other objects as attributes.
- Lists can hold multiple instances of objects.
- Methods can manipulate these nested objects and collections.
- This structure models real-world relationships naturally.

![GENERATING: Create a clear, modern educational illustration for a chapter titled “Object Structures” in a Python OOP course.
Visually explain how Python objects can contain other objects and collections of objects. At the center, show a main object, such as a  Team  or  Party  object, represented as a large container or card. Inside it, depict multiple smaller  Warrior  objects as distinct character cards or icons, each with its own attributes like  name  and  health , to convey that the main object “holds” other objects.
Next to this, show a horizontal list or array-like structure (for example a row of boxes) labeled as a Python  list , containing several  Warrior  instances, to represent managing collections of objects. Use lines or arrows to connect the list and the container object, making it clear that the  Team  object has an attribute that is a list of other objects.
Add small labels such as “object”, “attribute”, “object attribute”, and “collection of objects (list)” near the corresponding visual elements. The style should be flat or semi-flat, with a friendly, beginner-focused mood, soft blues and greens with warm accent colors, legible typography, and plenty of white space, as if it were a slide or chapter cover in a Python OOP course. Aspect ratio 16:9, suitable for a section titled “02.2 Object Structures
](/.learn/assets/zfz8ebjpqbo)

---