---
readingTime:
  minutes: 1.44
  words: 359
fkglResult: 8.5
---

# 01.1 The HTML Skeleton, Tags, and Attributes

Every HTML page starts from the same basic skeleton, built out of tags, elements, and attributes. Once you recognize these building blocks, you can read and write any HTML document with confidence.

## The Document Skeleton

Here is the minimal structure every page needs:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <title>Sample Page</title>
  </head>
  <body>
    <h1>Hello World</h1>
    <p>This is a simple HTML document.</p>
  </body>
</html>
```

Each part has a job:

- `<!DOCTYPE html>` tells the browser to render the page in standards mode (this is HTML5).
- `<html lang="en">` is the root element wrapping the whole document; `lang` declares the language for search engines and screen readers.
- `<head>` holds metadata the user does not see directly — `<meta charset="UTF-8">` sets the character encoding so text from any language displays correctly, and `<title>` names the browser tab (and matters for SEO).
- `<body>` contains everything visible: headings, paragraphs, images, and the rest.

## Tags and Elements

A **tag** is the markup you type, like `<p>` or `<img>`. An **element** is the whole package: the opening tag, the content, and the closing tag together. In `<p>Hello</p>`, `<p>` and `</p>` are tags, and the entire `<p>Hello</p>` is the element.

![/.learn/assets/shs4nx3l6g.png](/.learn/assets/shs4nx3l6g.png)

Most elements come in pairs: an **opening tag** (`<p>`) and a **closing tag** (`</p>`) with content between them.

### Void Elements

A few elements have no content and therefore no closing tag — these are **void elements**, and they are self-closing. The most common are:

- `<img>` — inserts an image.
- `<br>` — inserts a line break.
- `<input>` — creates a form field.

```html
<img src="profile.jpg" alt="User profile picture">
```

Notice there is no `</img>`.

## Attributes

**Attributes** add extra information to an element, written as `name="value"` pairs inside the opening tag:

```html
<img src="photo.jpg" alt="Sunset over mountains" width="300">
```

Here `src` points to the image file, `alt` describes it for accessibility, and `width` sets its display width. Always wrap attribute values in double quotes.

## Common Mistakes to Avoid

The most frequent beginner errors are forgetting a closing tag (except on void elements), leaving the quotes off attribute values, and misspelling a tag or attribute name:

```html
<img src=photo.jpg alt=Sunset>
```

Browsers will try to repair markup like this, but the results are unpredictable — so it pays to close your tags, quote your values, and keep your nesting tidy from the start.
