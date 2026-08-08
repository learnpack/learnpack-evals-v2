---
readingTime:
  minutes: 1.59
  words: 398
fkglResult: 8.0
---

# 03.0 Images and Meaningful Alt Text

Images bring a page to life — they communicate, illustrate, and guide the eye. Adding them well means knowing the `<img>` tag, pointing it at the right file, picking a sensible format, and writing alt text that makes the image work for everyone.

## The `<img>` Tag

`<img>` is a **void element** (no closing tag) that tells the browser to display an image.

![GENERATING: Conceptual illustration showing an HTML document with an <img> tag embedded inside the body section, the image source pointing to a file path, and alt text describing the image. The illustration uses color-coded boxes to represent the HTML structure, with annotations explaining how the browser renders the image and how alt text supports accessibility. The image metaphorically shows the image as a window displaying a photo, emphasizing the connection between code and visual content.](/.learn/assets/nuv6hl9j9rb)

It has two attributes you should treat as required:

- `src` — the path to the image file.
- `alt` — alternative text describing the image, which screen readers announce and which appears if the image fails to load.

```html
<img src="images/sunset.jpg" alt="Sunset over the mountains">
```

## Paths and Formats

For images inside your project, use a **relative path** like `src="images/photo.png"`, and keep your files in a dedicated folder (such as `images/`) so the project stays tidy. For images hosted elsewhere, use an **absolute URL** like `src="https://example.com/image.png"`.

Choosing a format is a trade-off between compatibility and efficiency:

- **JPEG (.jpg)** — photographs with many colors.
- **PNG (.png)** — images needing transparency or sharp lines.
- **GIF (.gif)** — simple animations.
- **SVG (.svg)** — logos and icons that must scale without blurring.
- **WebP (.webp)** — modern format with strong compression and quality.

## Writing Effective Alt Text

Good alt text is **descriptive, concise, and meaningful** — it conveys what the image shows *in the context of the page*. For a profile photo, `alt="Photo of Jane Doe smiling"` is useful; `alt="image1"` or `alt="profile pic"` is not. Avoid repeating information that a nearby caption already provides.

```html
<img src="images/profile.jpg" alt="Photo of Jane Doe smiling">
```

Some images are purely decorative and add no information — a divider line, a background flourish. For those, use an **empty** alt attribute so screen readers skip them instead of announcing clutter:

```html
<img src="images/decorative-line.svg" alt="" aria-hidden="true">
```

The one rule that never bends: every `<img>` needs an `alt` attribute. Whether it describes the image or is deliberately empty, that single attribute is what keeps your images accessible to everyone who visits your page.
