---
readingTime:
  minutes: 1.888
  words: 472
fkglResult: 10.66
---

# 01.1 Attributes and Values

Understanding how to define **attributes** and assign **values** in Python classes is essential for creating objects that accurately represent real-world entities. In this lesson, you'll learn why attributes belong inside the `__init__` method and how each object maintains its own independent data.

## What Are Attributes and Values?

- An **attribute** is like a label or a property that belongs to an object.
- A **value** is the actual data stored in that attribute.

For example, in a social media app, a user might have a username and a number of followers:

```python
class User:
    def __init__(self, username, followers):
        self.username = username      # attribute label: username
        self.followers = followers    # attribute label: followers count

# Creating two User instances
user1 = User("alice123", 150)
user2 = User("bob_the_builder", 200)

print(user1.username)   # Output: alice123
print(user2.followers)  # Output: 200
```

Here, `self.username` and `self.followers` are **attributes** assigned the values passed during object creation.

## Why Define Attributes Inside `__init__`?

- The `__init__` method runs automatically when you create a new object.
- Defining attributes here ensures every object starts with its own set of data.
- This guarantees **consistency**: every instance has the same attributes initialized.

## Independence of Object Attributes

Each object has its own copy of attributes. Changing one object's attribute does not affect another's:

```python
user1.followers += 10
print(user1.followers)  # 160
print(user2.followers)  # 200
```

This independence is crucial for modeling real-world entities where each instance has unique data.

## Best Practices

- **Always** define instance attributes inside the `__init__` method.
- Avoid setting attributes outside `__init__` to prevent missing or inconsistent data.

## Conceptual Illustration

![GENERATING: Create a clean, modern educational illustration that explains “attributes and values” in Python object-oriented programming.
Show a large, friendly Python class diagram in the center with a simplified class called  Warrior . Around it, visually separate the attributes (for example  name ,  health ,  strength ) from their values (for example  "Aragorn" ,  100 ,  75 ) using labels, icons, or colored tags, so that it is visually obvious that attributes are like “empty slots” or “labels” and values are the concrete data stored inside.
Depict a couple of Warrior instances as character cards or rounded boxes (for example  warrior1 ,  warrior2 ), each showing the same attribute names but different values, to reinforce the idea that each object has its own values for the same attributes. Use subtle connecting lines or arrows between the class and the instances to indicate that they share the same structure.
The style should be flat or semi-flat, with a soft, approachable color palette (blues, greens, and warm accents), clear typography, and minimal clutter. The overall mood should feel like a clear, beginner-friendly visualization in a programming course. Add small text labels such as “class”, “attribute”, “value”, and “instance” near the corresponding visual elements.
Aspect ratio 16:9, suitable for a course slide or chapter header.
](/.learn/assets/ict9a4cfs)

## Summary

- Attributes are labels that hold values unique to each object.
- Define attributes inside the `__init__` method to ensure every instance is properly initialized.
- Each object maintains its own independent copy of attributes.

## Next Steps

In the next lesson, you'll learn how to add **behavior** to your classes by defining methods that operate on these attributes.