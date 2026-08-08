---
readingTime:
  minutes: 1.5
  words: 376
fkglResult: 8.31
---

# 03.0 Tools and Graph State

In multi-agent systems built with LangGraph, tools are not isolated helpers; they are active participants in a shared workspace called the **graph state**. This shared state acts like a blackboard where agents and tools read and write information to coordinate their work seamlessly.

## Reading Graph State with ToolRuntime

Tools often need access to information beyond their direct inputs — for example, the current user's ID, account tier, or other context stored in the graph state. Instead of passing all this data through the model's prompt or tool arguments, tools can access it directly via an injected **ToolRuntime** parameter.

Here's how you declare a tool that reads from graph state:

```python
from langchain.tools import tool, ToolRuntime

@tool
def get_user_orders(runtime: ToolRuntime) -> str:
    """List recent orders for the current user."""
    user_id = runtime.state["user_id"]  # Access graph state directly
    return f"Recent orders for user {user_id}: #1021, #1044."
```

Notice that `runtime` is automatically provided by LangGraph and hidden from the model, so the model never needs to supply or even know about this data.

## Writing Updates to Graph State with Command

Tools can also update the graph state by returning a **Command** object. This lets tools write back structured data and messages, maintaining a clear and consistent flow of information.

Example:

```python
from langgraph.types import Command
from langchain.messages import ToolMessage

@tool
def set_shipping_preference(value: str, runtime: ToolRuntime) -> Command:
    """Save the customer's shipping preference into graph state."""
    return Command(update={
        "shipping_preference": value,
        "messages": [ToolMessage("Preference saved.", tool_call_id=runtime.tool_call_id)],
    })
```

This command updates the `shipping_preference` key in the graph state and appends a tool message confirming the action.

To keep these interactions maintainable, scope each tool to only the state it needs rather than the entire conversation history or unrelated data—this reduces context bloat, improves performance, and prevents unintended coupling. Define typed state boundaries with `TypedDict` subclasses so it is explicit which keys a tool reads or writes, creating clear contracts between agents and tools. And version your state schema so that, as agents evolve independently, mismatches are caught early instead of failing silently.

The failure modes are the mirror image of these practices. Blind tools that act without the state they need produce stale or incorrect results; passing the full conversation history to every tool bloats context and degrades reasoning; free-form natural language between agents leads to ambiguity and error propagation; and shared mutable state written by multiple uncoordinated writers causes race conditions that corrupt the state.

Understanding these principles—accessing state through the injected **ToolRuntime**, writing updates back with **Command**, and scoping each tool to the minimal slice of state it needs—is essential for building maintainable, scalable multi-agent workflows.