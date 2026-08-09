---
readingTime:
  minutes: 2.02
  words: 505
fkglResult: 7.04
---

# 03.0 Lo que sabes ahora

Pon a prueba tu comprensión de las clases de Python y la programación orientada a objetos con este cuestionario. Cada pregunta se centra en conceptos clave que has aprendido sobre la sintaxis de clases, creación de instancias, atributos, métodos y notación de puntos. Elige la mejor respuesta para cada una.

### ¡Pon a prueba tus conocimientos!

Selecciona la respuesta correcta para cada pregunta.

1. ¿Dónde deben definirse siempre los atributos de instancia?

   - [ ] Fuera de la clase, como variables globales
   - [x] En el método __init__
   - [ ] En el primer método que los use
   - [ ] En un método setup() separado

2. ¿Qué es **self** en un método de clase en Python?

   - [ ] Una palabra clave de Python con un significado especial reservado
   - [ ] Una referencia a la clase en sí
   - [x] Una referencia a la instancia actual de la clase
   - [ ] Un marcador de posición que Python reemplaza con el nombre del método

3. Ves este código escrito fuera de la clase: `player.score += 10`. ¿Cuál es el riesgo?

   - [ ] Lanza un AttributeError de Python
   - [ ] Crea un atributo completamente nuevo no relacionado con la clase
   - [x] Omite cualquier validación o lógica de control que la clase pueda añadir después
   - [ ] Funciona bien — Python fomenta el acceso directo a atributos

4. Una clase llamada `MathUtils` tiene tres métodos (`add`, `subtract`, `multiply`), ninguno usa **self**. ¿Cuál es el problema?

   - [ ] Python requiere que todos los métodos usen self
   - [ ] Esto es OOP válido — agrupar funciones en una clase es el objetivo
   - [x] Este es el antipatrón de clase estática — es agrupación de funciones, no OOP
   - [ ] Los métodos deberían usar @staticmethod y entonces estaría bien

5. Quieres una `Library` que contenga objetos `Book`. ¿Qué enfoque modela correctamente "objetos dentro de objetos"?

   - [ ] Almacenar títulos de libros como una lista de cadenas dentro de `Library`
   - [x] Crear instancias de `Book` y almacenarlas en un atributo lista en `Library`
   - [ ] Heredar `Library` de `Book`
   - [ ] Usar un diccionario global con nombres de libros como claves

6. Tienes `car = Car("Toyota")` y `Car` almacena cuatro objetos `Wheel` en `self.wheels`. ¿Cómo accedes a la presión de la primera rueda?

   - [ ] `car[0].pressure`
   - [x] `car.wheels[0].pressure`
   - [ ] `car.Wheel.pressure`
   - [ ] `Wheel(car).pressure`

7. ¿Qué hace llamar a `Warrior("Aragorn", 100)`?

   - [ ] Define una nueva clase llamada `Warrior`
   - [x] Crea un nuevo objeto y llama a __init__ con los argumentos dados
   - [ ] Actualiza una instancia existente de `Warrior` con nuevos valores
   - [ ] Importa la clase `Warrior` de la biblioteca estándar

8. Tienes una lista `products = [Product("Laptop", 999), Product("Mouse", 25)]`. ¿Cómo imprimes el nombre del segundo producto?

   - [ ] `print(products.name[1])`
   - [ ] `print(Product[1].name)`
   - [x] `print(products[1].name)`
   - [ ] `print(products[1]["name"])`

---

Este cuestionario confirma que estás listo para avanzar hacia temas más avanzados de programación en Python. Revisa cualquier pregunta que te haya resultado difícil y repasa las lecciones relevantes para fortalecer tu comprensión. ¡Sigue programando y explorando!