---
readingTime:
  minutes: 1.78
  words: 445
fkglResult: 10.81
---

# 01.0 What Is an Agent Workflow

Understanding how agents collaborate in a system is key to designing effective multi-agent workflows. This lesson explores what an agent workflow is, where systems lie on the control-flow spectrum, and how to decide when to split responsibilities across specialized agents.

---

## What Is an Agent Workflow?

An **agent workflow** is a structured system where language models and tools are connected through a defined process to accomplish a task. The core question is: **Who controls the flow of actions?**

### The Control-Flow Spectrum

Systems fall somewhere between two ends of this spectrum:

- **LLM Embedded in Predefined Code Paths:** Here, the developer hard-codes the exact sequence of steps. The language model fills in the content at each step but does not decide the order.

- **LLM Directs Control Flow:** The model chooses which path to take at each decision point, selecting tools or agents dynamically within predefined options.

Most real-world systems blend these approaches, combining predictable structure with model-driven decisions at key junctions.

---

## When to Use One Agent vs. Multiple Agents

Deciding whether to keep a single well-equipped agent or split work across specialized agents depends on the problem's nature:

- Use **one agent** when the task is coherent and the toolset is small and related.
- Use **multiple agents** when the task spans different expertise areas, when instructions conflict if combined, or when parts can run independently.

Splitting agents introduces coordination overhead but improves clarity, maintainability, and potential parallelism.

---

## Design Rules for Splitting Agents

To build maintainable multi-agent systems, follow these best practices:

1. **One Purpose per Agent:** Each agent has a clear, specialized role (e.g., planner, executor, verifier).
2. **Explicit, Typed Interfaces:** Agents communicate through well-defined, structured messages, not vague natural language.
3. **Replaceability:** Agents can be swapped or updated independently without breaking the system.
4. **Stateless Orchestrator:** The orchestrator delegates tasks but does not execute domain logic.

These rules exist because their opposites are common failure modes. A single "todólogo" agent that tries to do everything collapses under complexity and errors; blind agents that act without sufficient context produce misaligned outputs; an orchestrator that performs domain logic itself becomes a bottleneck and erodes modularity; and free-form natural language between agents breeds ambiguity and propagates errors.

---

## Example Scenario

Imagine a customer support system:

- A **triage agent** classifies incoming tickets.
- Specialized agents handle **billing**, **technical support**, or **returns**.
- The orchestrator routes requests but does not solve issues itself.

This clear division improves accuracy and scalability.

By mastering these concepts, you are equipped to design multi-agent workflows that balance control, clarity, and collaboration—splitting work only when the problem genuinely demands it.