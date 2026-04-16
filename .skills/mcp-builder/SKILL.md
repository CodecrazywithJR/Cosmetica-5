---
name: mcp-builder
description: Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with external services through well-designed tools. Use when building MCP servers to integrate external APIs or services, whether in Python (FastMCP) or Node/TypeScript (MCP SDK).
license: MIT
---

# MCP Server Development Guide

## Overview

Create high-quality MCP (Model Context Protocol) servers that enable LLMs to effectively interact with external services. An MCP server provides tools that allow LLMs to access external APIs. Quality is measured by how well it enables LLMs to accomplish real-world tasks.

## High-Level Workflow

### Phase 1: Deep Research and Planning

#### 1.1 Agent-Centric Design Principles

**Build for Workflows, Not Just API Endpoints:**
- Don't simply wrap existing API endpoints — build thoughtful, high-impact workflow tools
- Consolidate related operations (e.g., `schedule_event` that both checks availability and creates event)
- Focus on tools that enable complete tasks, not just individual API calls

**Optimize for Limited Context:**
- Agents have constrained context windows — make every token count
- Return high-signal information, not exhaustive data dumps
- Provide "concise" vs "detailed" response format options
- Default to human-readable identifiers over technical codes

**Design Actionable Error Messages:**
- Error messages should guide agents toward correct usage patterns
- Suggest specific next steps
- Make errors educational, not just diagnostic

**Follow Natural Task Subdivisions:**
- Tool names should reflect how humans think about tasks
- Group related tools with consistent prefixes for discoverability

#### 1.2 Study MCP Protocol Documentation

Fetch the latest: `https://modelcontextprotocol.io/llms-full.txt`

#### 1.3 Create Implementation Plan

**Tool Selection:** List most valuable endpoints, prioritize by common use cases
**Shared Utilities:** Common API request patterns, pagination helpers, error handling
**Input/Output Design:** Pydantic (Python) or Zod (TypeScript) validation models, consistent response formats
**Error Handling:** Graceful failure modes, clear LLM-friendly error messages, rate limiting, auth errors

### Phase 2: Implementation

#### 2.1 Project Structure

**Python:**
```python
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

mcp = FastMCP("my-server")

class WeatherInput(BaseModel):
    location: str = Field(..., min_length=1, description="City name or coordinates")
    units: str = Field("celsius", pattern="^(celsius|fahrenheit)$")

@mcp.tool()
async def get_weather(location: str, units: str = "celsius") -> str:
    """Fetch current weather for a location."""
    data = await fetch_weather(location, units)
    return str(data)

@mcp.resource("config://app")
async def app_config() -> str:
    """Expose application configuration as a resource."""
    return json.dumps(get_config())

if __name__ == "__main__":
    mcp.run()
```

**TypeScript:**
```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({ name: "my-server", version: "1.1.0" });

server.tool(
  "get_weather",
  "Fetch current weather for a location",
  {
    location: z.string().min(1).describe("City name or coordinates"),
    units: z.enum(["celsius", "fahrenheit"]).default("celsius"),
  },
  async ({ location, units }) => {
    const data = await fetchWeather(location, units);
    return { content: [{ type: "text", text: JSON.stringify(data) }] };
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
```

#### 2.2 Tool Annotations
- `readOnlyHint`: true (for read-only operations)
- `destructiveHint`: false (for non-destructive operations)
- `idempotentHint`: true (if repeated calls have same effect)
- `openWorldHint`: true (if interacting with external systems)

### Phase 3: Review and Refine

**Code Quality Review:**
- DRY Principle: No duplicated code
- Composability: Shared logic extracted
- Consistency: Similar operations return similar formats
- Error Handling: All external calls have error handling
- Type Safety: Full type coverage
- Documentation: Every tool has comprehensive docstrings

**Testing:** Use the MCP Inspector: `npx @modelcontextprotocol/inspector`

### Phase 4: Create Evaluations

Create 10 complex, realistic evaluation questions that are independent, read-only, verifiable, and stable.

```xml
<evaluation>
  <qa_pair>
    <question>Your complex question here</question>
    <answer>Expected answer</answer>
  </qa_pair>
</evaluation>
```
