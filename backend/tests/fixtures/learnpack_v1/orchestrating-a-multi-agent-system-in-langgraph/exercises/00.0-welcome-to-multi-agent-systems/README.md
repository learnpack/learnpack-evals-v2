---
readingTime:
  minutes: 1.65
  words: 412
fkglResult: 12.81
---

# 00.0 Welcome to Multi-Agent Systems

Imagine trying to solve a complex puzzle all by yourself. At first, it might seem manageable, but as the pieces multiply and the picture becomes more intricate, the task quickly becomes overwhelming. This is the challenge faced by single-agent systems when tackling problems that require diverse expertise or multiple coordinated steps.

## Why Multiple Agents?

A **single agent** equipped with many tools can handle straightforward tasks well. However, when the problem grows in complexity—such as managing customer support requests involving billing, technical issues, and returns, or producing a detailed report that requires research, drafting, and editing—the single agent struggles. It becomes a **"todólogo" agent** (a do-it-all agent), overloaded with contradictory instructions and prone to mistakes.

![GENERATING: Conceptual illustration of multi-agent collaboration: multiple specialized agents represented as distinct colored circles, each labeled with roles like "Billing", "Technical Support", "Returns", connected by arrows to a central orchestrator node, symbolizing structured coordination and clear communication pathways](/.learn/assets/5uknttqz302)

This illustration shows how specialized agents work together under an orchestrator's guidance, sharing information through a common coordination medium.

### Real-World Examples Where Multi-Agent Systems Shine:

- **Customer Support:** A triage agent routes tickets to specialized agents for billing, technical support, or returns.
- **Content Creation Pipeline:** Separate agents handle research, writing, and editing sequentially.
- **Financial Reporting:** An orchestrator splits a report into sections, workers summarize each, and a synthesizer merges the results.
- **Code Review:** Different agents check style and security, then combine their findings.
- **Travel Planning:** Specialized agents manage flights, hotels, and itineraries before assembling the full plan.

## What This Course Offers

In this course you will:

- Develop a **workflow mindset** to design structured, maintainable agent collaborations.
- Learn the **pattern landscape** of multi-agent workflows, including common flow patterns.
- Take the first concrete step: replacing manual tool-dispatch loops with a **ToolNode** that enables agents and tools to coordinate through shared graph state.

## Key Principles of Multi-Agent Design

- **One Purpose per Agent:** Each agent has a specialized role, avoiding the pitfalls of generalists.
- **Explicit Interfaces:** Agents communicate through well-defined, typed messages, not vague natural language.
- **Replaceability:** Agents can be swapped or updated independently without breaking the system.
- **Stateless Orchestrator:** The orchestrator delegates tasks but does not execute domain logic itself.

This structured, collaborative approach is what lets multi-agent systems handle complexity that overwhelms a single agent. In the sections ahead, you'll design and implement these workflows step by step.