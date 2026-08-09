---
readingTime:
  minutes: 1.98
  words: 495
fkglResult: 7.96
---

# 01.0 Escribir Clases en Python

Entender cómo escribir clases en Python es el siguiente paso para convertir tu conocimiento de programación orientada a objetos en código real y funcional. En esta lección, aprenderás la estructura básica de una clase en Python, el papel especial del método `__init__` como constructor, y por qué `self` es esencial para referirse a cada instancia individual del objeto.

## La Anatomía de una Clase en Python

Una clase en Python es como un plano para crear objetos. Define los atributos (datos) y métodos (comportamiento) que tendrán los objetos creados a partir de ella.

Aquí está la estructura mínima de una clase en Python:

```python
class ClassName:
    def __init__(self, parameters):
        # Inicializa los atributos aquí
        self.attribute = value

    def method_name(self, other_parameters):
        # Define el comportamiento aquí
        pass
```

### Componentes Clave:

- **class ClassName:** Esta línea declara una nueva clase llamada `ClassName`.
- **método `__init__`:** Este método especial se llama automáticamente cuando creas un nuevo objeto (una instancia) de la clase. Configura el estado inicial del objeto.
- **parámetro `self`:** Es una referencia a la instancia actual de la clase. Te permite acceder a los atributos y métodos del objeto.

## Por Qué Importan `__init__` y `self`

- El método `__init__` actúa como un constructor. Cuando escribes `obj = ClassName(args)`, Python crea un nuevo objeto y llama a `__init__` para inicializarlo.
- El parámetro `self` no es una palabra clave de Python, sino una convención fuerte de la comunidad. Debe ser el primer parámetro de cualquier método de instancia.
- Usando `self`, asignas valores a los atributos del objeto, asegurando que cada instancia tenga sus propios datos independientes.

## Ejemplo: Definiendo una Clase Simple Guerrero

Definamos una clase `Warrior` que tiene un atributo `name` y `health`.

```python
class Warrior:
    def __init__(self, name, health):
        self.name = name      # Asigna el atributo name
        self.health = health  # Asigna el atributo health
```

Creando instancias:

```python
warrior1 = Warrior("Aragorn", 100)
warrior2 = Warrior("Legolas", 90)

print(warrior1.name)  # Salida: Aragorn
print(warrior2.health)  # Salida: 90
```

Cada objeto `Warrior` tiene su propio `name` y `health` independiente de los demás.

## Resumen

- Usa la palabra clave `class` para definir una nueva clase.
- El método `__init__` inicializa nuevos objetos.
- `self` se refiere a la instancia y se usa para establecer o acceder a atributos.
- Cada objeto creado a partir de una clase tiene sus propios atributos independientes.

## Próximos Pasos

En la próxima lección, aprenderás cómo agregar comportamiento a tus clases definiendo métodos que operan sobre los datos de la instancia.

---
