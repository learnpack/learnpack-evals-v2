---
readingTime:
  minutes: 1.936
  words: 484
fkglResult: 6.95
---

# 02.0 Uso de Objetos

Entender cómo crear y trabajar con objetos es un paso fundamental para aplicar la Programación Orientada a Objetos en Python. Ahora que has definido clases y sus comportamientos, es momento de ver qué sucede cuando das vida a esas clases creando instancias.

## ¿Qué es la Instanciación?

**Instanciación** es el proceso de crear un objeto específico a partir de un plano de clase. Piensa en una clase como un cortador de galletas y cada objeto como una galleta hecha con ese cortador. Cuando instancias una clase, Python:

- Crea un nuevo objeto en memoria.
- Llama al método `__init__` para inicializar los atributos del objeto.
- Devuelve el nuevo objeto para que puedas usarlo.

Por ejemplo:

```python
warrior1 = Warrior("Aragorn", 100)
```

Aquí, `warrior1` es una **instancia** de la clase `Warrior`, con su propio `name` y `health`.

## Independencia de las Instancias

Cada objeto que creas es independiente. Esto significa:

- Cambiar los atributos de un objeto no afecta a otro.
- Cada instancia mantiene su propio estado.

Ejemplo:

```python
warrior2 = Warrior("Legolas", 90)

warrior1.take_damage(25)

print(warrior1.health)  # Muestra: 75
print(warrior2.health)  # Muestra: 90
```

Aunque ambos son objetos `Warrior`, `warrior1` y `warrior2` tienen valores de salud separados.

## Trabajando con Objetos: Notación de Punto

Interactúas con objetos usando **notación de punto**:

- Acceder a atributos: `objeto.atributo`
- Llamar métodos: `objeto.método()`

Ejemplo:

```python
print(warrior1.name)       # Muestra: Aragorn
warrior1.take_damage(10)   # Llama al método para reducir la salud
```

Ten cuidado al modificar atributos directamente desde fuera de la clase, ya que puede omitir lógica importante dentro de los métodos.

## ¿Por qué es Importante?

Entender la instanciación y la independencia de objetos te permite modelar entidades del mundo real con precisión y manejar estructuras de datos complejas de manera efectiva. Esta base te prepara para temas más avanzados como colecciones de objetos y objetos anidados.

## Resumen Rápido

- La **instanciación** crea un nuevo objeto a partir de una clase.
- Cada objeto es una **instancia** independiente con sus propios datos.
- Usa la **notación de punto** para acceder a atributos y métodos.

## Pon a Prueba tu Comprensión

Selecciona la respuesta correcta para cada pregunta.

1. ¿Qué hace la instanciación en Python?

   - [ ] Define una nueva clase.
   - [x] Crea un nuevo objeto a partir de una clase.
   - [ ] Elimina un objeto.

2. Si tienes dos instancias de la misma clase, cambiar el atributo de una instancia:

   - [ ] Cambia el atributo en la otra instancia.
   - [x] Solo afecta a la instancia que cambiaste.
   - [ ] Cambia la definición de la clase.

3. ¿Cómo llamas a un método llamado `attack` en un objeto `warrior`?

   - [ ] `attack.warrior()`
   - [ ] `warrior.attack`
   - [x] `warrior.attack()`

4. ¿Cuál es el riesgo de modificar un atributo de un objeto directamente desde fuera de la clase?

   - [ ] No hay riesgo; siempre es seguro.
   - [x] Puede omitir validaciones o lógica dentro de los métodos.
   - [ ] Elimina el atributo.

Sigue experimentando con tus clases y objetos. Cuanto más practiques, más naturales serán estos conceptos para ti!