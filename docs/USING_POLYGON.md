A Model Context Protocol (MCP) server that provides access to the full Massive.com financial data API through an LLM-friendly interface.

Rather than exposing one tool per endpoint, this server gives the LLM four composable tools — search, docs, call, and query — that cover the entire Massive.com API surface. Data can be stored in-memory as DataFrames, queried with SQL, and enriched with built-in financial functions.

# Install the server (one-time — downloads dependencies ahead of time)
uv tool install "mcp_massive @ git+https://github.com/massive-com/mcp_massive@v0.8.5"

# Register with Claude Code
claude mcp add massive -e MASSIVE_API_KEY=your_api_key_here -- mcp_massive

## Install in claude code
claude mcp add massive -e MASSIVE_API_KEY="uTRwyNRjCWjLQG8m_RJWvYvjLNIOc45h" -- mcp_massive

#
uv tool upgrade mcp_massive

# to remove
claude mcp remove massive