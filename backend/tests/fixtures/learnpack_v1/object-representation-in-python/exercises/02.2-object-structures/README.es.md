---
{}
---

# 02.2 Estructuras de Objetos

En Python, los objetos pueden ser más que simples contenedores de datos. Pueden contener otros objetos como atributos, y puedes gestionar colecciones de estos objetos usando listas. Esta capacidad te permite modelar sistemas complejos del mundo real de una manera natural y organizada.

## Objetos que Contienen Otros Objetos

Imagina un **Coche** que tiene **Ruedas**. Cada rueda es un objeto con sus propias propiedades, como la presión. El objeto coche contiene una lista de estos objetos rueda como uno de sus atributos.

```python
class Wheel:
    def __init__(self, pressure):
        self.pressure = pressure  # presión en PSI

class Car:
    def __init__(self, brand):
        self.brand = brand
        self.wheels = [Wheel(32), Wheel(32), Wheel(30), Wheel(31)]

car = Car("Toyota")
print(f"Presión de la primera rueda: {car.wheels[0].pressure} PSI")

# Modificar la presión de la segunda rueda
car.wheels[1].pressure = 33
print(f"Nueva presión de la segunda rueda: {car.wheels[1].pressure} PSI")
```

Aquí, `car.wheels` es una lista de objetos `Wheel`. Puedes acceder a cada rueda y sus atributos usando la **notación de punto** combinada con el índice de la lista.

## Gestionando Listas de Instancias de Objetos

También puedes crear listas que contengan múltiples instancias de una clase, como usuarios en una aplicación.

```python
class User:
    def __init__(self, username):
        self.username = username

users = [User("Ana"), User("Luis"), User("Marta")]

for user in users:
    print(f"Usuario: {user.username}")
```

Este patrón es común en aplicaciones del mundo real, donde puedes gestionar colecciones de publicaciones, productos o cualquier entidad.

## Añadiendo Comportamiento a Colecciones de Objetos

Puedes añadir métodos a tus clases que operen sobre estas colecciones. Por ejemplo, una clase `Car` podría verificar si la presión de alguna rueda está por debajo de un umbral seguro.

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
print(car.check_wheel_pressure(31))  # Salida: True porque una rueda tiene 30 PSI
```

## ¿Por qué Usar Objetos Dentro de Objetos?

- **Modularidad:** Cada clase maneja sus propios datos y comportamientos.
- **Claridad:** Los sistemas complejos se dividen en partes manejables.
- **Reutilización:** Puedes reutilizar clases como `Wheel` en diferentes contextos.

## Resumen

- Los objetos pueden contener otros objetos como atributos.
- Las listas pueden contener múltiples instancias de objetos.
- Los métodos pueden manipular estos objetos anidados y colecciones.
- Esta estructura modela relaciones del mundo real de forma natural.

![/.learn/assets/zfz8ebjpqbo.png](/.learn/assets/zfz8ebjpqbo.png)

---