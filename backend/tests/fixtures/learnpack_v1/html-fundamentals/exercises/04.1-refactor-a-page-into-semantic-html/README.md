---
readingTime:
  minutes: 0.57
  words: 143
fkglResult: 6.5
---

# 04.1 Refactor a Page into Semantic HTML

`app.html` contains a working page built entirely from `<div>` elements with generic class names. It renders fine, but it tells browsers and assistive technology nothing about what each part *is*. Your job is to give it meaning.

**Your task:** refactor `app.html` so its structure uses semantic elements instead of generic containers.

- Replace the `<div class="site-header">` with a `<header>`.
- Replace the `<div class="navigation">` with a `<nav>`.
- Replace the `<div class="content">` with a `<main>`.
- Replace the `<div class="site-footer">` with a `<footer>`.
- Keep all text and nested elements exactly as they are, and remove the now-unneeded class names.

**Expected result:** the page looks identical in the browser, but its markup now uses `<header>`, `<nav>`, `<main>`, and `<footer>` (one `<main>` only), with the original content untouched and valid HTML throughout.
