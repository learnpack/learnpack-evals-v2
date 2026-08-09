---
readingTime:
  minutes: 0.63
  words: 158
fkglResult: 6.5
---

# 04.1 Refactoriza una página a HTML semántico

`app.html` contiene una página funcional construida enteramente con elementos `<div>` y nombres de clase genéricos. Se renderiza bien, pero no les dice nada a los navegadores ni a la tecnología de asistencia sobre qué *es* cada parte. Tu trabajo es darle significado.

**Tu tarea:** refactoriza `app.html` para que su estructura use elementos semánticos en lugar de contenedores genéricos.

- Reemplaza el `<div class="site-header">` por un `<header>`.
- Reemplaza el `<div class="navigation">` por un `<nav>`.
- Reemplaza el `<div class="content">` por un `<main>`.
- Reemplaza el `<div class="site-footer">` por un `<footer>`.
- Mantén todo el texto y los elementos anidados exactamente como están, y elimina los nombres de clase que ya no se necesitan.

**Resultado esperado:** la página se ve idéntica en el navegador, pero su marcado ahora usa `<header>`, `<nav>`, `<main>` y `<footer>` (un solo `<main>`), con el contenido original intacto y HTML válido en todo momento.
