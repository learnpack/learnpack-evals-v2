---
readingTime:
  minutes: 1.4
  words: 349
fkglResult: 9.5
---

# 06.0 Using AI to Generate HTML

AI coding tools can speed up web development dramatically — but only if you stay in control. The goal is to let AI handle the repetitive parts while you bring the judgment that keeps the code clean, semantic, and accessible.

## What AI Does Well, and Where It Falls Short

AI is excellent at **boilerplate and repetitive structure**: scaffolding a page skeleton, generating a navigation menu, or drafting a list of elements from a clear description. Given a prompt like *"Create semantic HTML for a blog post with a header, navigation, a main article with three sections, and a footer,"* it can produce a solid starting point in seconds.

Where it struggles is the subtle, context-specific judgment: it may skip a heading level, write vague or missing alt text, or pick a generic `<div>` where a semantic element belongs. The code can look correct while quietly failing accessibility. That gap is exactly why **human review is essential** — and why understanding HTML yourself is what makes you useful here.

## Writing Effective Prompts

The quality of AI output depends heavily on the prompt. Be specific: name the semantic elements you want, mention any accessibility needs, and ask for valid, clean code.

- **Weak prompt:** "Make a website."
- **Strong prompt:** "Generate a semantic HTML page with a header containing a logo and navigation, a main section with an article and two subsections, and a footer with contact info."

## Reviewing and Validating the Output

Treat every AI response as a first draft to inspect, not a finished answer. Check that it uses semantic tags correctly, follows a logical heading hierarchy, gives images meaningful alt text, and produces valid markup — the [W3C HTML Validator](https://validator.w3.org/) and your browser's developer tools are perfect for this.

A good rule of thumb: lean on AI for boilerplate, repetitive tasks, and quick prototypes, and write code by hand when you are handling unique semantic decisions, tricky accessibility, or — especially right now — learning the fundamentals. Used this way, AI augments your skills instead of replacing the understanding you are building.
