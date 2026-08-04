---
readingTime:
  minutes: 2.172
  words: 543
fkglResult: 10.06
---

# 01.2 Adding Behavior with Methods

In Python classes, **methods** are functions defined inside a class that operate on the data contained in each instance. These methods allow objects to have **behavior** — actions they can perform or respond to — which is essential for modeling real-world entities.

## Defining Methods with `self`

Every instance method must include `self` as its first parameter. This parameter is a reference to the specific object instance calling the method. Through `self`, methods can access and modify the instance's attributes.

Consider this example:

```python
class Warrior:
    def __init__(self, name, health):
        self.name = name
        self.health = health

    def take_damage(self, amount):
        self.health -= amount  # modifies this instance's health
```

Here, `take_damage` is a method that reduces the warrior's health by the given amount. When you call:

```python
warrior = Warrior("Aragorn", 100)
warrior.take_damage(25)
print(warrior.health)  # Output: 75
```

Python automatically passes the `warrior` instance as `self` to the method, so you only provide the damage amount.

## Why Use Methods to Change Attributes?

- **Encapsulation:** Methods control how an object's data changes, allowing validation or side effects.
- **Maintainability:** If you later add rules (e.g., health cannot go below zero), you only update the method.
- **Clarity:** Calling `warrior.take_damage(25)` clearly expresses intent, better than directly modifying attributes.

## The Static Class Anti-Pattern

Avoid defining methods inside classes that do not use `self`. Such methods behave like standalone functions grouped under a class name but do not leverage object-oriented benefits like encapsulation or instance-specific behavior.

Example of an anti-pattern:

```python
class MathUtils:
    def add(x, y):  # no 'self' parameter
        return x + y
```

This is better written as a standalone function or, if grouping is needed, as a static method with the `@staticmethod` decorator.

## Best Practices

- Always include `self` as the first parameter in instance methods.
- Use methods to modify attributes rather than changing them directly from outside the class.
- Keep state (attributes) and behavior (methods) together in the class.

## Conceptual Illustration

![GENERATING: Create a clean, modern educational illustration that explains “adding behavior with methods” in Python classes.
In the center, show a simplified Python class called  Warrior  represented as a card or diagram, clearly divided into two parts: the upper part for attributes (for example  name ,  health ,  strength ) and the lower part for methods (for example  take_damage() ,  heal() ,  attack() ). Make it visually obvious that methods represent actions or behaviors the object can perform.
Around the main class card, depict a couple of Warrior instances (for example  warrior1 ,  warrior2 ) as smaller character cards or icons. Use small, dynamic arrows or motion lines showing these objects “using” their methods, such as  warrior1.take_damage(20)  reducing its health, or  warrior2.attack(warrior1)  to suggest interaction between objects. This should clearly convey that methods operate on the object’s own state.
Add small, clear labels like “class”, “attributes (state)”, “methods (behavior)”, and “instance” near the relevant elements to reinforce the learning concept. The style should be flat or semi-flat, friendly and beginner-focused, with a soft color palette (blues, violets, and warm accents) and good use of white space, as if it were a slide or chapter header in a Python OOP course.
Aspect ratio 16:9, suitable for a course section cover titled “Adding Behavior with Methods”
](/.learn/assets/gdaavpgh3w)

## Summary

- Methods define behaviors that operate on an object's own data.
- The `self` parameter is essential to access instance attributes inside methods.
- Encapsulation through methods helps maintain control over how data changes.
- Avoid static classes that do not use `self` as they do not represent true objects.

## Next Steps

Try extending the Warrior class by adding a `heal` method that increases health. Create instances and call both `take_damage` and `heal` to observe how the object's state changes through methods.

