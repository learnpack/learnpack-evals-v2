---
readingTime:
  minutes: 2.15
  words: 537
fkglResult: 8.5
---

# 01.0 What HTML Is and How Browsers Read It

Every website you have ever visited — a social feed, a news article, an online store — is built on **HTML** (HyperText Markup Language). HTML is the backbone of every web page: it provides the **structure** and **meaning** of content, organizing text, images, and links into a coherent document.

![/.learn/assets/vtxzvg6q5qd.jpg](/.learn/assets/vtxzvg6q5qd.jpg)

## What HTML Does and Does Not Do

HTML defines the structure of a page using **elements** like headings, paragraphs, lists, and links, and **tags** that mark up content so the browser knows what each part represents. What it deliberately leaves alone is just as important:

- HTML does **not** control how a page looks — colors, fonts, and layout are CSS's job.
- HTML does **not** add behavior or interactivity — that is JavaScript's role.
- HTML is a **markup language**, not a programming language.

This split is called the **separation of concerns**, and it is the foundation of clean web development:

| Concern       | Technology     | Purpose                                 |
|---------------|----------------|-----------------------------------------|
| Structure     | **HTML**       | Organizes and defines content meaning   |
| Presentation  | **CSS**        | Styles and visually formats content     |
| Behavior      | **JavaScript** | Adds interactivity and dynamic features |

The same HTML can look completely different under two CSS files, and JavaScript can make a button open a popup — but HTML is what defines that the button, the heading, and the image exist in the first place.

## How the Browser Reads HTML: the DOM Tree

When a browser loads your HTML, it does not just display the raw text. It parses your markup into a structured model called the **Document Object Model (DOM)** — a tree of nested elements, much like a family tree.

![GENERATING: Conceptual illustration of the DOM tree structure showing the <html> root node at the top, branching down to <body>, which further branches to <header> and <main>. <header> contains <h1>, and <main> branches to <section> and <aside>. Each node is connected with lines representing parent-child relationships, color-coded to differentiate levels, with annotations explaining siblings and nesting. The illustration uses a simplified, friendly style with flat colors to clarify the hierarchical nature of HTML documents.](/.learn/assets/x9z61k7oxj)

Consider this markup:

```html
<html>
  <body>
    <header>
      <h1>My Blog</h1>
    </header>
    <main>
      <section>
        <p>Welcome to my blog!</p>
      </section>
      <aside>
        <p>Related links</p>
      </aside>
    </main>
  </body>
</html>
```

The browser reads this as a hierarchy:

- `<html>` is the **root node** that contains everything.
- `<body>` is a **child** of `<html>`.
- `<header>` and `<main>` are **siblings** — they share the same parent.
- `<header>` contains `<h1>` (its child), and `<main>` contains the sibling pair `<section>` and `<aside>`.

These **parent–child** and **sibling** relationships are not just trivia: they are exactly how CSS targets elements ("style every paragraph inside `<main>`") and how JavaScript finds and changes them later. On a site like Instagram, the feed is a series of `<article>` elements inside a `<main>`, while the suggestions sidebar is an `<aside>` — the same tree structure, holding real content.

## See the Tree Yourself

You can inspect the DOM of any live page: right-click an element and choose **Inspect** (or open your browser's developer tools). The Elements panel shows the nested structure as a collapsible tree, so you can expand nodes and watch the parent–child and sibling relationships that the browser built from the HTML. Getting comfortable reading that tree is one of the fastest ways to understand how any web page is put together.
