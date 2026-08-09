---
{}
---

# 01.1 Atributos y Valores

Entender cómo definir **atributos** y asignar **valores** en las clases de Python es esencial para crear objetos que representen con precisión entidades del mundo real. En esta lección, aprenderás por qué los atributos pertenecen dentro del método `__init__` y cómo cada objeto mantiene sus propios datos independientes.

## ¿Qué son los Atributos y Valores?

- Un **atributo** es como una etiqueta o una propiedad que pertenece a un objeto.
- Un **valor** es el dato real almacenado en ese atributo.

Por ejemplo, en una aplicación de redes sociales, un usuario podría tener un nombre de usuario y un número de seguidores:

```python
class User:
    def __init__(self, username, followers):
        self.username = username      # etiqueta del atributo: username
        self.followers = followers    # etiqueta del atributo: número de seguidores

# Creando dos instancias de User
user1 = User("alice123", 150)
user2 = User("bob_the_builder", 200)

print(user1.username)   # Salida: alice123
print(user2.followers)  # Salida: 200
```

Aquí, `self.username` y `self.followers` son **atributos** a los que se les asignan los valores pasados durante la creación del objeto.

## ¿Por qué definir atributos dentro de `__init__`?

- El método `__init__` se ejecuta automáticamente cuando creas un nuevo objeto.
- Definir atributos aquí asegura que cada objeto comience con su propio conjunto de datos.
- Esto garantiza **consistencia**: cada instancia tiene los mismos atributos inicializados.

## Independencia de los Atributos de los Objetos

Cada objeto tiene su propia copia de los atributos. Cambiar el atributo de un objeto no afecta al de otro:

```python
user1.followers += 10
print(user1.followers)  # 160
print(user2.followers)  # 200
```

Esta independencia es crucial para modelar entidades del mundo real donde cada instancia tiene datos únicos.

## Buenas Prácticas

- **Siempre** define los atributos de instancia dentro del método `__init__`.
- Evita establecer atributos fuera de `__init__` para prevenir datos faltantes o inconsistentes.

## Ilustración Conceptual

![/.learn/assets/ict9a4cfs.png](/.learn/assets/ict9a4cfs.png)

## Resumen

- Los atributos son etiquetas que contienen valores únicos para cada objeto.
- Define los atributos dentro del método `__init__` para asegurar que cada instancia esté correctamente inicializada.
- Cada objeto mantiene su propia copia independiente de los atributos.

## Próximos Pasos

En la próxima lección, aprenderás cómo agregar **comportamiento** a tus clases definiendo métodos que operen sobre estos atributos.