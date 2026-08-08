from langchain.tools import tool, ToolRuntime

@tool
def get_shipping_estimate(runtime: ToolRuntime) -> str:
    tier = runtime.state["account_tier"]
    days = 1 if tier == "premium" else 5
    return f"Estimated shipping: {days} business day(s) for a {tier} customer."