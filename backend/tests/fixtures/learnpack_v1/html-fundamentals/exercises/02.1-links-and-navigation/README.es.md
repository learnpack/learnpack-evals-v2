---
readingTime:
  minutes: 1.35
  words: 338
fkglResult: 8.5
---

# 02.1 Enlaces y navegación

Los enlaces son lo que convierte páginas separadas en un sitio web conectado. La **etiqueta de ancla** `<a>` crea un enlace, y su atributo `href` indica a dónde va. Agrupar esos enlaces en un menú de navegación es la forma en que los visitantes se mueven por tu sitio.

## Crear enlaces

Para enlazar a un sitio externo, usa una **URL absoluta** con la dirección web completa:

```html
<a href="https://twitter.com">Visit Twitter</a>
```

Para páginas dentro de tu propio proyecto, usa una **URL relativa** que apunte a un archivo en tu carpeta. Esto mantiene el sitio portátil:

```html
<a href="about.html">About Us</a>
```

También puedes saltar a una sección de la *misma* página. Dale al elemento de destino un `id` y luego enlaza a él con un `#`:

```html
<h2 id="features">Features</h2>
<a href="#features">Jump to Features</a>
```

Para abrir un enlace en una nueva pestaña del navegador — útil para enlaces externos, para que los visitantes mantengan tu sitio abierto — añade `target="_blank"`:

```html
<a href="https://instagram.com" target="_blank">Instagram Profile</a>
```

Sea cual sea el destino, escribe un **texto de enlace descriptivo** que nombre a dónde va el enlace. "Sobre nuestro equipo" es claro; "haz clic aquí" no le dice nada a un usuario de lector de pantalla y no ayuda a nadie.

## Construir un menú de navegación semántico

Un menú de navegación en realidad es solo una *lista de enlaces*, así que la forma semántica de construirlo es una lista desordenada dentro de un elemento `<nav>`:

```html
<nav>
  <ul>
    <li><a href="index.html" aria-current="page">Home</a></li>
    <li><a href="about.html">About</a></li>
    <li><a href="contact.html">Contact</a></li>
  </ul>
</nav>
```

Cada parte cumple su función: `<nav>` les dice a los navegadores y a la tecnología de asistencia "esto es un bloque de navegación", `<ul>` y `<li>` expresan que los enlaces pertenecen juntos como un grupo, y `aria-current="page"` marca el enlace de la página en la que te encuentras actualmente para que un lector de pantalla pueda anunciarlo.

Para construir un sitio de varias páginas, coloca este mismo menú en cada página y mueve `aria-current="page"` al enlace que corresponda a la página actual. Esa consistencia es lo que permite que los visitantes siempre sepan dónde están y cómo llegar a otro lugar — la columna vertebral silenciosa de un sitio que se siente fácil de usar.
