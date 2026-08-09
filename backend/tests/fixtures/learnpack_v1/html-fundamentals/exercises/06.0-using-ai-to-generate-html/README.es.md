---
readingTime:
  minutes: 1.62
  words: 406
fkglResult: 9.5
---

# 06.0 Usar IA para generar HTML

Las herramientas de IA para programar pueden acelerar el desarrollo web de forma drástica — pero solo si te mantienes al mando. La meta es dejar que la IA se encargue de las partes repetitivas mientras tú aportas el criterio que mantiene el código limpio, semántico y accesible.

## Qué hace bien la IA y dónde se queda corta

La IA es excelente con el **código repetitivo y la estructura estándar**: armar el esqueleto de una página, generar un menú de navegación o redactar una lista de elementos a partir de una descripción clara. Ante un prompt como *"Crea HTML semántico para una entrada de blog con un header, navegación, un main con tres secciones y un footer"*, puede producir un buen punto de partida en segundos.

Donde tiene dificultades es en el criterio sutil y dependiente del contexto: puede saltarse un nivel de encabezado, escribir un texto alternativo vago o ausente, o elegir un `<div>` genérico donde corresponde un elemento semántico. El código puede verse correcto mientras falla en silencio en accesibilidad. Esa brecha es exactamente la razón por la que **la revisión humana es esencial** — y por la que entender HTML tú mismo es lo que te hace útil aquí.

## Escribir prompts efectivos

La calidad de la salida de la IA depende mucho del prompt. Sé específico: nombra los elementos semánticos que quieres, menciona cualquier necesidad de accesibilidad y pide código limpio y válido.

- **Prompt débil:** "Haz un sitio web."
- **Prompt fuerte:** "Genera una página HTML semántica con un header que contenga un logo y navegación, una sección main con un artículo y dos subsecciones, y un footer con información de contacto."

## Revisar y validar la salida

Trata cada respuesta de la IA como un primer borrador para inspeccionar, no como una respuesta terminada. Verifica que use etiquetas semánticas correctamente, que siga una jerarquía de encabezados lógica, que dé a las imágenes un texto alternativo con significado y que produzca un marcado válido — el [Validador HTML del W3C](https://validator.w3.org/) y las herramientas de desarrollo de tu navegador son perfectos para esto.

Una buena regla práctica: apóyate en la IA para el código repetitivo, las tareas mecánicas y los prototipos rápidos, y escribe código a mano cuando manejes decisiones semánticas únicas, accesibilidad delicada o — especialmente ahora — cuando estés aprendiendo los fundamentos. Usada así, la IA potencia tus habilidades en lugar de reemplazar el entendimiento que estás construyendo.
