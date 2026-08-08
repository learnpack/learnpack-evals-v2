---
readingTime:
  minutes: 1.83
  words: 458
fkglResult: 8.5
---

# 05.0 Writing Clean and Valid HTML

Working HTML and *good* HTML are not the same thing. Clean, valid markup is easier to read, easier to debug, and easier for the next person (often future you) to maintain. Three habits get you there: write it cleanly, validate it, and steer clear of the common traps.

## Writing Clean HTML

**Consistent indentation** is the single biggest readability win. Indent child elements so the nesting is visible at a glance, using either 2 or 4 spaces throughout:

```html
<nav>
  <ul>
    <li><a href="index.html">Home</a></li>
    <li><a href="about.html">About</a></li>
  </ul>
</nav>
```

Beyond indentation, keep your style consistent:

- Use lowercase tag and attribute names, and always quote attribute values.
- Order attributes predictably — `id`, then `class`, then the rest (`src`, `href`, `alt`).
- Add **meaningful comments** to mark or explain non-obvious sections (`<!-- Main navigation -->`), but skip comments that just restate the obvious.
- Group related elements and separate major blocks with a blank line.

## Validating Your HTML

Even tidy-looking markup can hide structural errors. The free [W3C HTML Validator](https://validator.w3.org/) checks your code: paste it in or upload the file, and it lists every error with a line number. The most common ones are:

- **Unclosed tags** — `<p>This is <strong>important text</p>` leaves `<strong>` open. Close it: `<strong>important text</strong>`.
- **Duplicate IDs** — every `id` must be unique on a page; rename one of the clashing pair.
- **Improper nesting** — closing tags must mirror opening order. `<p><em>text</p></em>` is wrong; `<p><em>text</em></p>` is right.

Your browser's developer tools complement the validator: open **Inspect** to see the DOM the browser actually built, and you will quickly spot a tag that closed in the wrong place.

## Common Anti-Patterns to Avoid

A few habits work visually but quietly break accessibility and maintainability. Recognize them so you can avoid them:

- **Tables for layout.** `<table>` is for tabular data, not page structure. Use semantic elements with CSS for layout instead.
- **Multiple `<br>` tags for spacing.** Stacking `<br><br>` to push content down mixes content with presentation; control spacing with CSS margins.
- **Inline styles.** `<div style="color:red">` is hard to maintain; use classes and an external stylesheet.
- **`<div>` standing in for a semantic element.** `<div class="heading">` should be an `<h2>`; a menu should be a `<nav>`. Reach for the meaningful tag.
- **Skipping heading levels.** Jumping `<h2>` straight to `<h4>` breaks the outline; go in order.
- **Empty elements for spacing.** An empty `<div></div>` used only to create a gap is clutter — that is a job for CSS.

Notice the thread running through all of these: keep structure (HTML) separate from presentation (CSS), and let each tag mean what it says. Write your markup with that in mind, validate it, and your pages will stay clean long after the first draft.
