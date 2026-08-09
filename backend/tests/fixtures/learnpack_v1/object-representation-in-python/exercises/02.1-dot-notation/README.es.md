# 02.1 Notación de Punto

Interactuar con objetos en Python se realiza principalmente a través de la **notación de punto**. Esta sintaxis simple te permite acceder y modificar los atributos de un objeto y llamar a sus métodos.

## Accediendo a Atributos

Para leer el valor de un atributo, usa:

```python
objeto.atributo
```

Por ejemplo, considera una clase `User` que representa a un usuario de Instagram:

```python
class User:
    def __init__(self, username, bio):
        self.username = username
        self.bio = bio

user = User("jane_doe", "Viajera y fotógrafa")
print(user.username)  # Muestra: jane_doe
```

Aquí, `user.username` accede al atributo `username` de la instancia `user`.

## Modificando Atributos

También puedes actualizar un atributo directamente:

```python
user.bio = "Ama la fotografía"
print(user.bio)  # Muestra: Ama la fotografía
```

Sin embargo, modificar atributos directamente desde fuera de la clase puede ser riesgoso. Se omite cualquier validación o lógica que quieras aplicar, como limitar la longitud de una biografía o sanitizar la entrada.

## Usando Métodos para Modificar Atributos

Una mejor práctica es proveer métodos que encapsulen los cambios de atributos. Por ejemplo:

```python
class User:
    def __init__(self, username, bio):
        self.username = username
        self.bio = bio
    
    def update_bio(self, new_bio):
        # Aquí podrías agregar lógica de validación
        self.bio = new_bio

user = User("jane_doe", "Viajera y fotógrafa")
user.update_bio("Ama la fotografía")
print(user.bio)  # Muestra: Ama la fotografía
```

Llamar a un método usa la notación de punto seguida de paréntesis:

```python
user.update_bio("Nueva biografía")
```

## ¿Por qué Preferir Métodos?

- **Encapsulación:** Los métodos controlan cómo cambian los atributos.
- **Validación:** Puedes agregar verificaciones dentro de los métodos.
- **Mantenibilidad:** Los cambios en la lógica de atributos ocurren en un solo lugar.

## Resumen

- Usa **notación de punto** para acceder a atributos: `objeto.atributo`
- Usa **notación de punto con paréntesis** para llamar métodos: `objeto.metodo()`
- Evita modificar atributos directamente desde fuera de la clase cuando sea posible.
- Encapsula los cambios de atributos dentro de métodos para un código más seguro y limpio.

## Pruébalo Tú Mismo

Experimenta creando una clase con atributos y métodos para actualizarlos. Intenta modificar atributos directamente y mediante métodos para observar las diferencias.
