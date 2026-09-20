from mcp.server.fastmcp import FastMCP

server = FastMCP("autoflow-test")


@server.tool(description="Return the supplied text")
def echo(text: str) -> str:
    return f"echo:{text}"


if __name__ == "__main__":
    server.run("stdio")
