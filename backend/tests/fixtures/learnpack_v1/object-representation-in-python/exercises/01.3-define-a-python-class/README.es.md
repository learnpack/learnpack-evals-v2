---
{}
---

# 01.3 Definir una Clase en Python

En esta lección, pondrás en práctica lo que has aprendido sobre las clases en Python definiendo tu propia clase **Guerrero**. Esta clase tendrá atributos para almacenar el nombre y la salud de un guerrero, y un método para reducir la salud cuando el guerrero recibe daño.

## Definiendo la Clase Guerrero

Aquí está el código completo para la clase Guerrero y cómo crear instancias e interactuar con ellas:

```python
class Guerrero:
    def __init__(self, nombre, salud):
        # Asignar los atributos nombre y salud a la instancia
        self.nombre = nombre
        self.salud = salud

    def recibir_daño(self, cantidad):
        # Reducir la salud de la instancia por la cantidad de daño
        self.salud -= cantidad

# Crear dos instancias de Guerrero con diferentes nombres y valores de salud
guerrero1 = Guerrero("Aragorn", 100)
guerrero2 = Guerrero("Legolas", 90)

# Aplicar daño al primer guerrero
guerrero1.recibir_daño(25)

# Imprimir el estado actual de cada guerrero
print(f"{guerrero1.nombre} tiene {guerrero1.salud} de salud")  # Salida: Aragorn tiene 75 de salud
print(f"{guerrero2.nombre} tiene {guerrero2.salud} de salud")  # Salida: Legolas tiene 90 de salud
```

### ¿Qué está pasando aquí?

- El método `__init__` configura cada nuevo Guerrero con un `nombre` y `salud`.
- El método `recibir_daño` disminuye la salud del guerrero por la cantidad especificada.
- Cada instancia de guerrero mantiene su propio estado independiente — cambiar uno no afecta al otro.

## ¿Por qué usar `self`?

El parámetro `self` en los métodos se refiere a la instancia específica de la clase. Permite que cada guerrero lleve un registro de sus propios atributos:

- `self.nombre` y `self.salud` pertenecen al guerrero individual.
- Cuando llamas a `guerrero1.recibir_daño(25)`, Python pasa automáticamente `guerrero1` como `self`.

## Sugerencia para practicar

Intenta crear un nuevo guerrero y llama a `recibir_daño` con diferentes valores. Observa cómo cada instancia mantiene su propio estado independiente.

## Ilustración conceptual

![/.learn/assets/1mnu2vi820th.png](/.learn/assets/1mnu2vi820th.png)

Esta imagen te ayuda a visualizar cómo el plano de la clase crea guerreros individuales, cada uno con sus propios datos y comportamientos.

---

Sigue experimentando con tu clase Guerrero añadiendo nuevos métodos como `curar` o `atacar` para profundizar tu comprensión de cómo el estado y el comportamiento trabajan juntos en las clases de Python!