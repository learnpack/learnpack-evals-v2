---
{}
---

# 01.2 Añadiendo Comportamiento con Métodos

En las clases de Python, los **métodos** son funciones definidas dentro de una clase que operan sobre los datos contenidos en cada instancia. Estos métodos permiten que los objetos tengan **comportamiento** — acciones que pueden realizar o a las que pueden responder — lo cual es esencial para modelar entidades del mundo real.

## Definiendo Métodos con `self`

Cada método de instancia debe incluir `self` como su primer parámetro. Este parámetro es una referencia al objeto específico que llama al método. A través de `self`, los métodos pueden acceder y modificar los atributos de la instancia.

Considera este ejemplo:

```python
class Guerrero:
    def __init__(self, nombre, salud):
        self.nombre = nombre
        self.salud = salud

    def recibir_daño(self, cantidad):
        self.salud -= cantidad  # modifica la salud de esta instancia
```

Aquí, `recibir_daño` es un método que reduce la salud del guerrero en la cantidad dada. Cuando llamas:

```python
guerrero = Guerrero("Aragorn", 100)
guerrero.recibir_daño(25)
print(guerrero.salud)  # Salida: 75
```

Python pasa automáticamente la instancia `guerrero` como `self` al método, por lo que solo proporcionas la cantidad de daño.

## ¿Por qué usar métodos para cambiar atributos?

- **Encapsulación:** Los métodos controlan cómo cambian los datos de un objeto, permitiendo validación o efectos secundarios.
- **Mantenibilidad:** Si luego agregas reglas (por ejemplo, que la salud no puede bajar de cero), solo actualizas el método.
- **Claridad:** Llamar a `guerrero.recibir_daño(25)` expresa claramente la intención, mejor que modificar atributos directamente.

## El Anti-Patrón de Clases Estáticas

Evita definir métodos dentro de clases que no usan `self`. Tales métodos se comportan como funciones independientes agrupadas bajo un nombre de clase, pero no aprovechan los beneficios de la orientación a objetos como la encapsulación o el comportamiento específico de la instancia.

Ejemplo de un anti-patrón:

```python
class UtilidadesMat:
    def sumar(x, y):  # sin parámetro 'self'
        return x + y
```

Esto es mejor escribirlo como una función independiente o, si se necesita agrupación, como un método estático con el decorador `@staticmethod`.

## Buenas Prácticas

- Siempre incluye `self` como primer parámetro en los métodos de instancia.
- Usa métodos para modificar atributos en lugar de cambiarlos directamente desde fuera de la clase.
- Mantén el estado (atributos) y el comportamiento (métodos) juntos en la clase.

## Ilustración Conceptual

![/.learn/assets/gdaavpgh3w.png](/.learn/assets/gdaavpgh3w.png)

## Resumen

- Los métodos definen comportamientos que operan sobre los propios datos de un objeto.
- El parámetro `self` es esencial para acceder a los atributos de la instancia dentro de los métodos.
- La encapsulación mediante métodos ayuda a mantener el control sobre cómo cambian los datos.
- Evita clases estáticas que no usan `self` ya que no representan verdaderos objetos.

## Próximos Pasos

Intenta extender la clase Guerrero añadiendo un método `curar` que aumente la salud. Crea instancias y llama tanto a `recibir_daño` como a `curar` para observar cómo cambia el estado del objeto a través de los métodos.