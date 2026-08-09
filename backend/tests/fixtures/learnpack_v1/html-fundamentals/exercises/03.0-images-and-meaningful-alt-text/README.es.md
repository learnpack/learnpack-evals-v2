---
readingTime:
  minutes: 1.7
  words: 424
fkglResult: 8.0
---

# 03.0 Imágenes y texto alternativo con significado

Las imágenes dan vida a una página — comunican, ilustran y guían la mirada. Añadirlas bien significa conocer la etiqueta `<img>`, apuntarla al archivo correcto, elegir un formato sensato y escribir un texto alternativo que haga que la imagen funcione para todos.

## La etiqueta `<img>`

`<img>` es un **elemento vacío** (sin etiqueta de cierre) que le dice al navegador que muestre una imagen.

![GENERATING: Conceptual illustration showing an HTML document with an <img> tag embedded inside the body section, the image source pointing to a file path, and alt text describing the image. The illustration uses color-coded boxes to represent the HTML structure, with annotations explaining how the browser renders the image and how alt text supports accessibility. The image metaphorically shows the image as a window displaying a photo, emphasizing the connection between code and visual content.](/.learn/assets/nuv6hl9j9rb)

Tiene dos atributos que deberías tratar como obligatorios:

- `src` — la ruta al archivo de imagen.
- `alt` — texto alternativo que describe la imagen, que los lectores de pantalla anuncian y que aparece si la imagen no carga.

```html
<img src="images/sunset.jpg" alt="Sunset over the mountains">
```

## Rutas y formatos

Para las imágenes dentro de tu proyecto, usa una **ruta relativa** como `src="images/photo.png"`, y mantén tus archivos en una carpeta dedicada (como `images/`) para que el proyecto siga ordenado. Para imágenes alojadas en otro lugar, usa una **URL absoluta** como `src="https://example.com/image.png"`.

Elegir un formato es un equilibrio entre compatibilidad y eficiencia:

- **JPEG (.jpg)** — fotografías con muchos colores.
- **PNG (.png)** — imágenes que necesitan transparencia o líneas nítidas.
- **GIF (.gif)** — animaciones simples.
- **SVG (.svg)** — logos e iconos que deben escalar sin volverse borrosos.
- **WebP (.webp)** — formato moderno con buena compresión y calidad.

## Escribir un texto alternativo efectivo

Un buen texto alternativo es **descriptivo, conciso y significativo** — transmite lo que muestra la imagen *en el contexto de la página*. Para una foto de perfil, `alt="Photo of Jane Doe smiling"` es útil; `alt="image1"` o `alt="profile pic"` no lo es. Evita repetir información que un pie de foto cercano ya proporciona.

```html
<img src="images/profile.jpg" alt="Photo of Jane Doe smiling">
```

Algunas imágenes son puramente decorativas y no añaden información — una línea divisoria, un adorno de fondo. Para esas, usa un atributo alt **vacío** para que los lectores de pantalla las omitan en lugar de anunciar elementos sin sentido:

```html
<img src="images/decorative-line.svg" alt="" aria-hidden="true">
```

La única regla que nunca se rompe: cada `<img>` necesita un atributo `alt`. Ya sea que describa la imagen o que esté deliberadamente vacío, ese único atributo es lo que mantiene tus imágenes accesibles para todos los que visitan tu página.
