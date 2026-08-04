---
readingTime:
  minutes: 2.02
  words: 505
fkglResult: 7.04
---

# 03.0 What You Know Now

Test your understanding of Python classes and object-oriented programming with this quiz. Each question focuses on key concepts you've learned about class syntax, instance creation, attributes, methods, and dot notation. Choose the best answer for each.

### Put your knowledge to the test!

Select the correct answer for each question.

1. Where should instance attributes always be defined?

   - [ ] Outside the class, as global variables
   - [x] In the __init__ method
   - [ ] In whichever method first uses them
   - [ ] In a separate setup() method

2. What is **self** in a Python class method?

   - [ ] A Python keyword with special reserved meaning
   - [ ] A reference to the class itself
   - [x] A reference to the current instance of the class
   - [ ] A placeholder that Python replaces with the method name

3. You see this code written outside the class: `player.score += 10`. What is the risk?

   - [ ] It throws a Python AttributeError
   - [ ] It creates a brand-new attribute unrelated to the class
   - [x] It bypasses any validation or control logic the class might add later
   - [ ] It works fine — Python encourages direct attribute access

4. A class named `MathUtils` has three methods (`add`, `subtract`, `multiply`), none of which use **self**. What is the problem?

   - [ ] Python requires all methods to use self
   - [ ] This is valid OOP — grouping functions in a class is the point
   - [x] This is the static class anti-pattern — it is function grouping, not OOP
   - [ ] The methods should use @staticmethod and then it is fine

5. You want a `Library` that contains `Book` objects. Which approach correctly models "objects within objects"?

   - [ ] Store book titles as a list of strings inside `Library`
   - [x] Create `Book` instances and store them in a list attribute on `Library`
   - [ ] Inherit `Library` from `Book`
   - [ ] Use a global dictionary with book names as keys

6. You have `car = Car("Toyota")` and `Car` stores four `Wheel` objects in `self.wheels`. How do you access the pressure of the first wheel?

   - [ ] `car[0].pressure`
   - [x] `car.wheels[0].pressure`
   - [ ] `car.Wheel.pressure`
   - [ ] `Wheel(car).pressure`

7. What does calling `Warrior("Aragorn", 100)` do?

   - [ ] Defines a new class named `Warrior`
   - [x] Creates a new object and calls __init__ with the given arguments
   - [ ] Updates an existing `Warrior` instance with new values
   - [ ] Imports the `Warrior` class from the standard library

8. You have a list `products = [Product("Laptop", 999), Product("Mouse", 25)]`. How do you print the name of the second product?

   - [ ] `print(products.name[1])`
   - [ ] `print(Product[1].name)`
   - [x] `print(products[1].name)`
   - [ ] `print(products[1]["name"])`

---

This quiz confirms your readiness to move forward with more advanced Python programming topics. Review any questions you found challenging and revisit the relevant lessons to strengthen your understanding. Keep coding and exploring!