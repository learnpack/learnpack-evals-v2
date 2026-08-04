---
readingTime:
  minutes: 1.644
  words: 411
fkglResult: 12.16
---

# 02.1 Dot Notation

Interacting with objects in Python is done primarily through **dot notation**. This simple syntax lets you access and modify an object's attributes and call its methods.

## Accessing Attributes

To read an attribute's value, use:

```python
object.attribute
```

For example, consider a `User` class representing an Instagram user:

```python
class User:
    def __init__(self, username, bio):
        self.username = username
        self.bio = bio

user = User("jane_doe", "Traveler and photographer")
print(user.username)  # Outputs: jane_doe
```

Here, `user.username` accesses the `username` attribute of the `user` instance.

## Modifying Attributes

You can also update an attribute directly:

```python
user.bio = "Loves photography"
print(user.bio)  # Outputs: Loves photography
```

However, modifying attributes directly from outside the class can be risky. It bypasses any validation or logic you might want to enforce, such as limiting the length of a bio or sanitizing input.

## Using Methods to Modify Attributes

A better practice is to provide methods that encapsulate attribute changes. For example:

```python
class User:
    def __init__(self, username, bio):
        self.username = username
        self.bio = bio
    
    def update_bio(self, new_bio):
        # Here you could add validation logic
        self.bio = new_bio

user = User("jane_doe", "Traveler and photographer")
user.update_bio("Loves photography")
print(user.bio)  # Outputs: Loves photography
```

Calling a method uses dot notation followed by parentheses:

```python
user.update_bio("New bio")
```

## Why Prefer Methods?

- **Encapsulation:** Methods control how attributes change.
- **Validation:** You can add checks inside methods.
- **Maintainability:** Changes to attribute logic happen in one place.

## Summary

- Use **dot notation** to access attributes: `object.attribute`
- Use **dot notation with parentheses** to call methods: `object.method()`
- Avoid modifying attributes directly from outside the class when possible.
- Encapsulate attribute changes inside methods for safer, cleaner code.

## Try It Yourself

Experiment by creating a class with attributes and methods to update them. Try modifying attributes directly and via methods to observe the differences.

