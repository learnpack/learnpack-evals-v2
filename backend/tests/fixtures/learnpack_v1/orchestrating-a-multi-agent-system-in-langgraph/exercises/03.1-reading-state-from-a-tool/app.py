from langchain.tools import tool, ToolRuntime

@tool
def get_shipping_estimate(runtime: ToolRuntime) -> str:
    # TODO: Read the account_tier from runtime.state and return the correct shipping estimate string
    pass
