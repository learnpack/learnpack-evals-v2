---
readingTime:
  minutes: 2.412
  words: 603
fkglResult: 10.01
---

# 03.1 De Prompt a Tokens

Cuando escribes un prompt en una IA, no procesa tus palabras como oraciones completas como lo hace un humano. En cambio, divide tu entrada en piezas más pequeñas llamadas **tokens**—piensa en ellos como ladrillos LEGO que construyen tu oración. Un token puede ser una palabra completa como "gato", una parte de una palabra como "in" en "increíble", o incluso puntuación como un punto.

> Como regla general, un token equivale aproximadamente a una palabra promedio. Sin embargo, palabras largas o compuestas pueden dividirse en múltiples tokens, mientras que palabras cortas y comunes típicamente permanecen como tokens individuales.

Por ejemplo, la frase "Mantequilla de maní y..." podría dividirse en tokens como ["Mantequilla", " de", " maní", " y"]. La IA entonces predice qué token es más probable que venga después, como "mermelada".

Porque la IA funciona prediciendo el siguiente token basado en la secuencia que ha visto hasta ahora, incluso pequeños cambios en la redacción pueden llevar a diferentes secuencias de tokens y por lo tanto a diferentes respuestas de la IA. Por ejemplo, "Explica blockchain" y "Explica la blockchain" se tokenizan de manera diferente, empujando a la IA hacia patrones de respuesta distintos.

## La Ventana de Contexto: La Memoria a Corto Plazo de la IA

Cada modelo de IA tiene un límite en la cantidad de tokens que puede considerar a la vez. Este límite se llama **ventana de contexto**. Puedes pensar en ella como la memoria a corto plazo de la IA.

Si tu prompt más la respuesta generada por la IA exceden este límite de tokens, las partes más antiguas pueden ser "olvidadas" o ignoradas. Por eso, conversaciones o documentos muy largos a veces pierden detalles anteriores.

Entender la ventana de contexto te ayuda a crear prompts que encajen dentro de la memoria de la IA, asegurando que se enfoque en la información más relevante.

## Por Qué Esto Importa para Tus Prompts

- **Precisión en la redacción** guía a la IA hacia los patrones que quieres que continúe.
- **Gestionar la longitud del prompt** asegura que la IA recuerde el contexto importante.
- Al resumir o analizar textos largos, incluir solo las partes más relevantes dentro del límite de tokens mejora la calidad de la respuesta.

Dominar la tokenización y las ventanas de contexto te permite comunicarte con la IA con mayor precisión, reduciendo malentendidos y mejorando la calidad de las respuestas.

![/.learn/assets/tokenization.png](/.learn/assets/tokenization.png)

### Reflexiona y Explica

Con tus propias palabras, explica por qué es importante entender los tokens y la ventana de contexto al interactuar con IA generativa.

```question eval="La respuesta debe mencionar que los tokens son las piezas que la IA usa para procesar el lenguaje, y la ventana de contexto limita cuánto texto puede considerar la IA a la vez, afectando cómo se entienden los prompts y se generan las respuestas. Las respuestas que demuestren comprensión de la tokenización y los límites de memoria son correctas."
CORRECTO: Los tokens son las pequeñas piezas en las que la IA divide el texto, y la ventana de contexto es el límite de cuántos tokens puede procesar la IA a la vez, así que saber esto me ayuda a escribir prompts que encajen y obtener mejores respuestas.
CORRECTO: Entender los tokens y la ventana de contexto es importante porque la IA solo ve el texto en partes y solo puede recordar una cantidad limitada, por lo que necesito ser preciso y conciso.
INCORRECTO: Los tokens son las palabras que la IA conoce, y la ventana de contexto es qué tan rápido responde la IA.
INCORRECTO: No es importante porque la IA entiende todo lo que escribo completamente.
CORRECTO: Porque la IA procesa el texto como tokens y tiene una ventana de contexto limitada, debo gestionar la longitud y redacción del prompt para asegurar que se incluya y entienda la información relevante.
```