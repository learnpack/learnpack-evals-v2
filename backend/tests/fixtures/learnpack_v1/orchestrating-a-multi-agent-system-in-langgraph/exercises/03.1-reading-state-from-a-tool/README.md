---
readingTime:
  minutes: 0.64
  words: 160
fkglResult: 9.0
---

# 03.1 Reading State From a Tool

A customer-service agent needs a shipping estimate that depends on the customer's account tier, and that tier already lives in the graph state rather than in the model's prompt.

**Your task:** in `app.py`, implement a tool that reads the tier from graph state and returns a shipping estimate.

- Declare a `@tool` named `get_shipping_estimate` whose ONLY parameter is `runtime: ToolRuntime`.
- Read the `account_tier` key from `runtime.state`.
- Return a shipping-estimate string that reflects the tier (premium customers get a faster estimate than standard ones).
- The model must NOT supply the tier — it comes only from the injected runtime state.

**Expected result:** calling the tool with `account_tier` set to `"premium"` in the runtime state returns a one-business-day estimate, while any other tier returns a slower estimate.

Because the tier flows in through the runtime, the model never has to know or pass it, keeping the tool self-contained.
