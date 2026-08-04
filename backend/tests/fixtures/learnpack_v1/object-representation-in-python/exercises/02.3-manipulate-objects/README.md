---
readingTime:
  minutes: 1.556
  words: 389
fkglResult: 8.99
---

# 02.3 Manipulate Objects

In this lesson, you'll apply your knowledge of Python classes and object manipulation by working with a list of **Product** instances. You'll learn how to create multiple objects, store them in a list, and find the product with the highest price using Python's built-in functions.

## Defining the Product Class

First, let's define a simple `Product` class with two attributes: `name` and `price`. These attributes will be set when we create each product instance.

```python
class Product:
    def __init__(self, name, price):
        self.name = name
        self.price = price
```

## Creating a List of Products

Next, we'll create a list called `products` that contains several `Product` instances. Each product has a unique name and price.

```python
products = [
    Product("Laptop", 999),
    Product("Mouse", 25),
    Product("Monitor", 350),
]
```

## Finding the Most Expensive Product

To find the product with the highest price, we use Python's `max()` function combined with a `lambda` function that extracts the `price` attribute from each product.

```python
most_expensive = max(products, key=lambda p: p.price)
print(f"{most_expensive.name}: ${most_expensive.price}")
```

This code prints the name and price of the most expensive product in the list.

## Try It Yourself!

- Add more products to the `products` list with different names and prices.
- Use the `min()` function with a similar lambda to find the cheapest product.

Example:

```python
cheapest = min(products, key=lambda p: p.price)
print(f"{cheapest.name}: ${cheapest.price}")
```

## Why This Matters

- **Instantiation:** You create multiple independent objects from the same class.
- **Collections:** Lists can hold many objects, allowing you to manage groups of related data.
- **Functional Tools:** Functions like `max()` and `min()` combined with lambdas let you easily query object collections.

This pattern is common in real-world applications, such as e-commerce platforms where you might need to find the most expensive or cheapest item in a catalog.

## Visualizing the Concept

![GENERATING: Create a clear, modern educational illustration for a chapter titled “Manipulate Objects” in a Python OOP course.
Show a central scene with several Python objects actively being used. Use a concrete example like  Product  objects in a small shop or inventory. Represent a few  Product  cards or boxes with attributes such as  name ,  price , and  stock , and visualize operations being performed on them: increasing or decreasing stock, changing prices, and selecting the most expensive product.
Next to these objects, depict a Python list as a horizontal row or container holding multiple  Product  instances, labeled something like  products = ... . Add subtle visual hints of operations: an arrow or funnel selecting the object with the highest price (e.g. “max by price”), another arrow showing filtering (e.g. only products in stock), and perhaps a small code snippet snippet area with lines like  max(products, key=lambda p: p.price)  to suggest using built-in functions to manipulate collections of objects.
Use small labels such as “objects”, “list of objects”, “manipulating state”, and “finding values in collections” near the relevant elements. The style should be flat or semi-flat, friendly and beginner-oriented, with soft blues and greens plus warm accent colors, clean typography, and plenty of white space so it feels like a polished course slide or chapter header. Aspect ratio 16:9, suitable for a section titled “02.3 Manipulate Objects](/.learn/assets/pw82l77emzr)

Keep experimenting with creating and manipulating lists of objects to strengthen your understanding of Python's object-oriented capabilities!