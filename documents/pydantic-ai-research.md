# Pydantic AI Comprehensive Documentation

**Research Date:** 2026-02-12
**Source:** Pydantic AI official documentation (ai.pydantic.dev)
**Context:** Building VTV AI Agent Service with FastAPI + Pydantic AI

---

## Table of Contents

1. [Agent Creation and Configuration](#1-agent-creation-and-configuration)
2. [Running Agents](#2-running-agents)
3. [FastAPI Integration](#3-fastapi-integration)
4. [Dependencies and Context](#4-dependencies-and-context)
5. [Tools](#5-tools)
6. [Result Types and Output](#6-result-types-and-output)
7. [Models Configuration](#7-models-configuration)

---

## 1. Agent Creation and Configuration

### Basic Agent Creation

```python
from pydantic_ai import Agent

# Simple agent with model string
agent = Agent('openai:gpt-4o')

# Agent with system prompt
agent = Agent(
    'anthropic:claude-sonnet-4-5',
    system_prompt='You are a helpful assistant for transit operations.'
)

# Agent with structured output
from pydantic import BaseModel

class CityLocation(BaseModel):
    city: str
    country: str

agent = Agent(
    'openai:gpt-4o',
    output_type=CityLocation,
    system_prompt='Extract city location information.'
)
```

### Agent Constructor Parameters

The `Agent.__init__()` method accepts:

```python
Agent(
    model: Model | KnownModelName | str | None = None,
    *,
    output_type: OutputSpec[OutputDataT] = str,  # Default is str
    instructions: Instructions[AgentDepsT] = None,
    system_prompt: str | Sequence[str] = (),
    deps_type: type[AgentDepsT] = NoneType,
    name: str | None = None,
    model_settings: ModelSettings | None = None,
    retries: int = 1,
    validation_context: Any | Callable[[RunContext[AgentDepsT]], Any] = None,
    output_retries: int | None = None,
    tools: Sequence[Tool[AgentDepsT] | ToolFuncEither[AgentDepsT, ...]] = (),
    builtin_tools: Sequence[AbstractBuiltinTool | BuiltinToolFunc[AgentDepsT]] = (),
    prepare_tools: ToolsPrepareFunc[AgentDepsT] | None = None,
    prepare_output_tools: ToolsPrepareFunc[AgentDepsT] | None = None,
    toolsets: Sequence[AbstractToolset[AgentDepsT] | ToolsetFunc[AgentDepsT]] | None = None,
    defer_model_check: bool = False,
    end_strategy: EndStrategy = "early",
    instrument: InstrumentationSettings | bool | None = None,
    metadata: AgentMetadata[AgentDepsT] | None = None,
    history_processors: Sequence[HistoryProcessor[AgentDepsT]] | None = None,
    event_stream_handler: EventStreamHandler[AgentDepsT] | None = None,
    tool_timeout: float | None = None,
)
```

**Key Parameters:**

- **`model`**: Model identifier (e.g., `'openai:gpt-4o'`, `'anthropic:claude-sonnet-4-5'`, `'gateway/anthropic:claude-sonnet-4-5'`)
- **`output_type`**: Type for structured output (Pydantic model, TypedDict, or `str`)
- **`system_prompt`**: Static system instructions (string or sequence of strings)
- **`deps_type`**: Type hint for runtime dependencies (for type safety)
- **`model_settings`**: Default model settings (temperature, max_tokens, etc.)
- **`retries`**: Number of retries for tool calls (default: 1)
- **`tools`**: List of tool functions to register
- **`instrument`**: Enable instrumentation for observability (set to `True` for built-in)
- **`tool_timeout`**: Global timeout for all tools (in seconds)

### Dynamic System Prompts

```python
from pydantic_ai import Agent, RunContext
from dataclasses import dataclass
import httpx

@dataclass
class MyDeps:
    api_key: str
    http_client: httpx.AsyncClient

agent = Agent(
    'openai:gpt-4o',
    deps_type=MyDeps,
)

@agent.system_prompt
async def get_system_prompt(ctx: RunContext[MyDeps]) -> str:
    # Fetch dynamic content using dependencies
    response = await ctx.deps.http_client.get(
        'https://example.com/context',
        headers={'Authorization': f'Bearer {ctx.deps.api_key}'},
    )
    response.raise_for_status()
    return f'System instructions: {response.text}'
```

---

## 2. Running Agents

### Five Ways to Run an Agent

1. **`agent.run()`** - Async function returning `RunResult`
2. **`agent.run_sync()`** - Synchronous wrapper (calls async `run()` internally)
3. **`agent.run_stream()`** - Async context manager returning `StreamedRunResult`
4. **`agent.run_stream_sync()`** - Synchronous streaming wrapper
5. **`agent.run_stream_events()`** - Returns async iterable of events

### Basic Run Methods

```python
from pydantic_ai import Agent

agent = Agent('openai:gpt-4o')

# Synchronous run
result = agent.run_sync('What is the capital of Italy?')
print(result.output)
# Output: The capital of Italy is Rome.

# Asynchronous run
async def main():
    result = await agent.run('What is the capital of France?')
    print(result.output)
    # Output: The capital of France is Paris.
```

### Streaming Text Output

```python
from pydantic_ai import Agent

agent = Agent('openai:gpt-4o')

async def stream_example():
    async with agent.run_stream('What is the capital of the UK?') as response:
        async for text in response.stream_text():
            print(text)
            # Output (incremental):
            # The capital of
            # The capital of the UK is
            # The capital of the UK is London.
```

**Key streaming methods:**

- **`stream_text(delta=False)`**: Stream text output
  - `delta=False` (default): Yields complete text so far
  - `delta=True`: Yields only new text since last yield
- **`stream_output(debounce_by=None)`**: Stream structured output (for Pydantic models)
- **`stream_responses(debounce_by=None)`**: Stream raw response messages
- **`get_output()`**: Get final output after stream completes

### Streaming Structured Output

```python
from datetime import date
from typing_extensions import NotRequired, TypedDict
from pydantic_ai import Agent

class UserProfile(TypedDict):
    name: str
    dob: NotRequired[date]
    bio: NotRequired[str]

agent = Agent(
    'openai:gpt-4o',
    output_type=UserProfile,
    system_prompt='Extract a user profile from the input',
)

async def main():
    user_input = 'My name is Ben, born January 28th 1990, I like dogs.'
    async with agent.run_stream(user_input) as result:
        async for profile in result.stream_output(debounce_by=0.01):
            print(profile)
            # Outputs partial profiles as they're built
```

### Run Parameters

```python
result = await agent.run(
    user_prompt: str | Sequence[UserContent] | None = None,
    *,
    output_type: OutputSpec[RunOutputDataT] | None = None,  # Override agent's output_type
    message_history: Sequence[ModelMessage] | None = None,  # Previous conversation
    deferred_tool_results: DeferredToolResults | None = None,  # For human-in-the-loop
    model: Model | KnownModelName | str | None = None,  # Override agent's model
    instructions: Instructions[AgentDepsT] | None = None,  # Additional instructions
    deps: AgentDepsT | None = None,  # Runtime dependencies
    model_settings: ModelSettings | None = None,  # Override model settings
    usage_limits: UsageLimits | None = None,  # Token/request limits
    usage: RunUsage | None = None,  # Starting usage (for continuation)
    metadata: AgentMetadata[AgentDepsT] | None = None,  # Run metadata
    infer_name: bool = True,  # Infer agent name from call frame
    toolsets: Sequence[AbstractToolset[AgentDepsT]] | None = None,  # Additional toolsets
    builtin_tools: Sequence[AbstractBuiltinTool | BuiltinToolFunc[AgentDepsT]] | None = None,
    event_stream_handler: EventStreamHandler[AgentDepsT] | None = None,  # Event handler
)
```

---

## 3. FastAPI Integration

### Method 1: Using Adapter (Recommended)

Pydantic AI provides adapters for different UI protocols:

- **`VercelAIAdapter`** - For Vercel AI SDK compatibility
- **`AGUIAdapter`** - For AG-UI protocol

#### Simple Dispatch Pattern

```python
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response

from pydantic_ai import Agent
from pydantic_ai.ui.vercel_ai import VercelAIAdapter

agent = Agent('openai:gpt-4o', instructions='Be helpful!')

app = FastAPI()

@app.post('/chat')
async def chat(request: Request) -> Response:
    # Simplest approach: dispatch_request handles everything
    return await VercelAIAdapter.dispatch_request(request, agent=agent)
```

#### Manual Adapter Usage (More Control)

```python
import json
from http import HTTPStatus

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import Response, StreamingResponse
from pydantic import ValidationError

from pydantic_ai import Agent
from pydantic_ai.ui import SSE_CONTENT_TYPE
from pydantic_ai.ui.vercel_ai import VercelAIAdapter

agent = Agent('openai:gpt-4o')

app = FastAPI()

@app.post('/chat')
async def chat(request: Request) -> Response:
    accept = request.headers.get('accept', SSE_CONTENT_TYPE)

    # Parse request body
    try:
        run_input = VercelAIAdapter.build_run_input(await request.body())
    except ValidationError as e:
        return Response(
            content=json.dumps(e.json()),
            media_type='application/json',
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    # Create adapter and stream events
    adapter = VercelAIAdapter(agent=agent, run_input=run_input, accept=accept)
    event_stream = adapter.run_stream()
    sse_event_stream = adapter.encode_stream(event_stream)

    return StreamingResponse(sse_event_stream, media_type=accept)
```

### Method 2: Custom Streaming Response

For full control (e.g., chat application with database):

```python
from fastapi import FastAPI, Depends
from fastapi.responses import StreamingResponse
import json
from datetime import datetime, timezone

agent = Agent('openai:gpt-4o', instructions='Be fun!')
app = FastAPI()

@app.post('/chat/')
async def post_chat(
    prompt: str,
    database: Database = Depends(get_db)
) -> StreamingResponse:
    async def stream_messages():
        # Stream user prompt immediately
        yield (
            json.dumps({
                'role': 'user',
                'timestamp': datetime.now(tz=timezone.utc).isoformat(),
                'content': prompt,
            }).encode('utf-8') + b'\n'
        )

        # Get chat history for context
        messages = await database.get_messages()

        # Run agent with streaming
        async with agent.run_stream(prompt, message_history=messages) as result:
            async for text in result.stream_output(debounce_by=0.01):
                message = {
                    'role': 'assistant',
                    'timestamp': result.timestamp().isoformat(),
                    'content': text,
                }
                yield json.dumps(message).encode('utf-8') + b'\n'

        # Save conversation to database
        await database.add_messages(result.new_messages_json())

    return StreamingResponse(stream_messages(), media_type='text/plain')
```

---

## 4. Dependencies and Context

### Defining Dependencies

Dependencies are passed to tools and system prompts via `RunContext`. Use `deps_type` for type safety.

```python
from dataclasses import dataclass
import httpx
from pydantic_ai import Agent

@dataclass
class MyDeps:
    api_key: str
    http_client: httpx.AsyncClient
    database_session: Any  # e.g., AsyncSession

# Set deps_type for type checking
agent = Agent(
    'openai:gpt-4o',
    deps_type=MyDeps,
)
```

### Passing Dependencies at Runtime

```python
async def main():
    async with httpx.AsyncClient() as client:
        deps = MyDeps(
            api_key='secret-key',
            http_client=client,
            database_session=session,
        )

        result = await agent.run(
            'Tell me a joke.',
            deps=deps  # Pass dependencies here
        )
        print(result.output)
```

### Accessing Dependencies in Tools

```python
from pydantic_ai import RunContext

@agent.tool
async def get_user_data(ctx: RunContext[MyDeps], user_id: str) -> dict:
    """Fetch user data from database."""
    # Access dependencies through ctx.deps
    response = await ctx.deps.http_client.get(
        f'https://api.example.com/users/{user_id}',
        headers={'Authorization': f'Bearer {ctx.deps.api_key}'},
    )
    response.raise_for_status()
    return response.json()
```

### RunContext Attributes

```python
@dataclass
class RunContext[AgentDepsT]:
    deps: AgentDepsT                    # Your dependencies
    usage: RunUsage                     # Current usage stats
    partial_output: bool                # True if validating partial output
    # ... other attributes
```

### Multi-Agent with Shared Dependencies

```python
from pydantic_ai import Agent, RunContext

@dataclass
class ClientAndKey:
    http_client: httpx.AsyncClient
    api_key: str

# Primary agent
selection_agent = Agent(
    'openai:gpt-4o',
    deps_type=ClientAndKey,
    system_prompt='Choose the best joke from the joke_factory tool.',
)

# Delegate agent
generation_agent = Agent(
    'anthropic:claude-sonnet-4-5',
    deps_type=ClientAndKey,
    output_type=list[str],
    system_prompt='Generate jokes using the get_jokes tool.',
)

@selection_agent.tool
async def joke_factory(ctx: RunContext[ClientAndKey], count: int) -> list[str]:
    # Call delegate agent with same dependencies
    result = await generation_agent.run(
        f'Generate {count} jokes.',
        deps=ctx.deps,       # Pass dependencies through
        usage=ctx.usage,     # Share usage tracking
    )
    return result.output

@generation_agent.tool
async def get_jokes(ctx: RunContext[ClientAndKey], count: int) -> str:
    # Use dependencies to make HTTP request
    response = await ctx.deps.http_client.get(
        'https://api.jokes.com/random',
        params={'count': count},
        headers={'Authorization': f'Bearer {ctx.deps.api_key}'},
    )
    response.raise_for_status()
    return response.text
```

---

## 5. Tools

### Registering Tools

Tools are functions that the agent can call. Use the `@agent.tool` decorator:

```python
from pydantic_ai import Agent, RunContext

agent = Agent('openai:gpt-4o', deps_type=str)

@agent.tool
def get_player_name(ctx: RunContext[str]) -> str:
    """Get the player's name.

    This docstring becomes the tool description sent to the LLM.
    """
    return ctx.deps
```

### Tool Decorator Parameters

```python
@agent.tool(
    name: str | None = None,  # Tool name (default: function name)
    description: str | None = None,  # Tool description (default: docstring)
    retries: int | None = None,  # Retries for this tool (default: agent's retries)
    prepare: ToolPrepareFunc[AgentDepsT] | None = None,  # Customize tool per step
    docstring_format: DocstringFormat = 'auto',  # 'auto', 'google', 'numpy', 'sphinx'
    require_parameter_descriptions: bool = False,  # Error if param docs missing
    schema_generator: type[GenerateJsonSchema] = GenerateToolJsonSchema,
    strict: bool | None = None,  # Enforce JSON schema (OpenAI only)
    sequential: bool = False,  # Requires sequential execution
    requires_approval: bool = False,  # Human-in-the-loop approval
    metadata: dict[str, Any] | None = None,  # Tool metadata (not sent to model)
    timeout: float | None = None,  # Tool execution timeout (seconds)
)
```

### Tool Function Signatures

**With Context (most common):**

```python
@agent.tool
async def search_database(
    ctx: RunContext[MyDeps],
    query: str,
    limit: int = 10
) -> list[dict]:
    """Search the database for records matching the query.

    Args:
        query: Search query string
        limit: Maximum number of results (default: 10)

    Returns:
        List of matching records
    """
    async with ctx.deps.db_session() as session:
        results = await session.execute(
            select(Record).where(Record.content.contains(query)).limit(limit)
        )
        return [r.to_dict() for r in results.scalars()]
```

**Without Context (for tools that don't need dependencies):**

```python
import random

@agent.tool_plain  # Use tool_plain for no-context tools
def roll_dice() -> str:
    """Roll a six-sided die and return the result."""
    return str(random.randint(1, 6))
```

### Tool Docstrings for LLMs

**Critical for agent tool selection.** The docstring guides the LLM on WHEN and HOW to use the tool:

```python
@agent.tool
async def query_bus_status(
    ctx: RunContext[TransitDeps],
    route_id: str | None = None,
    vehicle_id: str | None = None
) -> dict:
    """Get real-time status for buses.

    Use this tool when the user asks about:
    - Current bus location or position
    - Bus delays or how late a bus is
    - Estimated arrival times

    Performance: Fetches from live GTFS-RT feed (<200ms typical).

    Args:
        route_id: Filter by route (e.g., "1A"). Omit to get all routes.
        vehicle_id: Get specific vehicle (e.g., "BUS-042"). More efficient than route_id.

    Returns:
        Dictionary with vehicle positions, delays, and ETAs.

    Composition:
        - For adherence analysis, use get_adherence_report() instead
        - For schedule planning, call get_route_schedule() first

    Examples:
        - "Where is bus 1A?" → Use route_id="1A"
        - "How late is vehicle BUS-042?" → Use vehicle_id="BUS-042"
    """
    # Implementation...
```

### Tool Best Practices

1. **First parameter is `RunContext[DepsType]`** (unless using `@agent.tool_plain`)
2. **All parameters must have type hints** (used for JSON schema generation)
3. **Docstring is mandatory** - it's sent to the LLM for tool selection
4. **Use Google-style docstrings** for parameter descriptions
5. **Return type should be JSON-serializable** (dict, list, str, int, float, bool, Pydantic models)
6. **For LLM-facing tools:** Guide tool selection, prevent token waste, enable composition, set expectations

---

## 6. Result Types and Output

### RunResult Attributes and Methods

```python
from pydantic_ai import Agent

agent = Agent('openai:gpt-4o', system_prompt='Be helpful.')

result = agent.run_sync('Tell me a joke.')

# Access output
print(result.output)  # Final output (str or structured type)

# Message history
all_msgs = result.all_messages()  # Complete conversation including system prompt
new_msgs = result.new_messages()   # Only new messages from this run

# JSON serialization
all_json = result.all_messages_json()  # bytes
new_json = result.new_messages_json()  # bytes

# Usage tracking
usage = result.usage()
print(usage)
# RunUsage(input_tokens=309, output_tokens=32, requests=4, tool_calls=2)
```

### RunUsage Details

```python
@dataclass
class RunUsage:
    input_tokens: int       # Total input tokens consumed
    output_tokens: int      # Total output tokens generated
    requests: int           # Number of API requests made
    tool_calls: int         # Number of tool invocations
```

### Message History for Multi-Turn Conversations

```python
agent = Agent('openai:gpt-4o', system_prompt='Be a helpful assistant.')

# First interaction
result1 = agent.run_sync('Tell me a joke.')
print(result1.output)

# Continue conversation with history
result2 = agent.run_sync(
    'Explain it to me.',
    message_history=result1.new_messages()  # Pass previous messages
)
print(result2.output)

# Access full conversation
print(result2.all_messages())  # Includes system prompt + both turns
```

### StreamedRunResult Methods

```python
async with agent.run_stream('Write a story.') as result:
    # Stream text (delta mode)
    async for text_delta in result.stream_text(delta=True):
        print(text_delta, end='', flush=True)

    # OR: Stream complete text so far
    async for complete_text in result.stream_text(delta=False):
        print(complete_text)

    # After streaming completes
    final_output = result.get_output()  # Get final output
    timestamp = result.timestamp()       # Get timestamp
    usage = result.usage()               # Get usage stats
    messages = result.new_messages()     # Get message history
```

### Structured Output with Pydantic Models

```python
from pydantic import BaseModel

class CityLocation(BaseModel):
    city: str
    country: str

agent = Agent('openai:gpt-4o', output_type=CityLocation)

result = agent.run_sync('Where were the 2012 Olympics held?')
print(result.output)
# CityLocation(city='London', country='United Kingdom')
print(result.output.city)  # Access as typed object
# London
```

### Structured Output with TypedDict

```python
from typing_extensions import TypedDict, NotRequired

class UserProfile(TypedDict):
    name: str
    age: NotRequired[int]
    email: NotRequired[str]

agent = Agent('openai:gpt-4o', output_type=UserProfile)

result = agent.run_sync('Extract profile: John Doe, 30 years old')
print(result.output)
# {'name': 'John Doe', 'age': 30}
```

### Output Validation

```python
from pydantic_ai import Agent, ModelRetry, RunContext

agent = Agent('openai:gpt-4o')

@agent.output_validator
def validate_output(ctx: RunContext, output: str) -> str:
    # Skip validation for partial outputs during streaming
    if ctx.partial_output:
        return output

    # Validate final output
    if len(output) < 50:
        raise ModelRetry('Output is too short. Write at least 50 characters.')
    return output

result = agent.run_sync('Write a story.')
# Agent will retry if output is too short
```

### Partial Output Validation During Streaming

```python
from pydantic import ValidationError

async with agent.run_stream(user_input) as result:
    async for message, is_last in result.stream_responses(debounce_by=0.01):
        try:
            profile = await result.validate_response_output(
                message,
                allow_partial=not is_last  # Allow partial validation until last message
            )
            print(profile)  # Print valid partial outputs
        except ValidationError:
            continue  # Skip invalid partial states
```

---

## 7. Models Configuration

### Model Identifier Formats

Pydantic AI supports multiple model identifier formats:

```python
# Direct provider access
agent = Agent('openai:gpt-4o')
agent = Agent('anthropic:claude-sonnet-4-5')
agent = Agent('google-gla:gemini-2.5-flash')

# Via Anthropic Gateway (recommended for production)
agent = Agent('gateway/openai:gpt-4o')
agent = Agent('gateway/anthropic:claude-sonnet-4-5')
agent = Agent('gateway/google-gla:gemini-2.5-flash')
```

### Anthropic Model Initialization

```python
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai import ModelSettings

# Basic initialization
model = AnthropicModel('claude-sonnet-4-5')

# With provider specification
model = AnthropicModel(
    'claude-sonnet-4-5',
    provider='anthropic',  # or 'gateway'
)

# With default settings
model = AnthropicModel(
    'claude-sonnet-4-5',
    settings=ModelSettings(
        temperature=0.7,
        max_tokens=2000,
    )
)

# Use with agent
agent = Agent(model)
```

### ModelSettings

Generic settings that work across providers:

```python
from pydantic_ai import ModelSettings

settings = ModelSettings(
    temperature=0.7,        # Randomness (0.0-1.0)
    max_tokens=2000,        # Maximum output tokens
    top_p=0.9,              # Nucleus sampling
    # ... other provider-agnostic settings
)

agent = Agent('openai:gpt-4o', model_settings=settings)
```

### AnthropicModelSettings (Anthropic-Specific)

All fields are prefixed with `anthropic_` for compatibility:

```python
from pydantic_ai.models.anthropic import AnthropicModelSettings

settings = AnthropicModelSettings(
    # Generic settings (inherited from ModelSettings)
    temperature=0.7,
    max_tokens=2000,

    # Anthropic-specific settings
    anthropic_metadata={'user_id': 'user-123'},
    anthropic_thinking=True,  # Enable extended thinking blocks

    # Prompt caching (reduces costs for repeated content)
    anthropic_cache_instructions=True,      # Cache system prompt (TTL: 5m default)
    anthropic_cache_tool_definitions='1h',  # Cache tool schemas (TTL: 1h)
    anthropic_cache_messages=True,          # Cache conversation history
)

agent = Agent('anthropic:claude-sonnet-4-5', model_settings=settings)
```

### Anthropic Prompt Caching

Caching reduces costs by reusing identical content across requests:

```python
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.anthropic import AnthropicModelSettings

agent = Agent(
    'anthropic:claude-sonnet-4-5',
    system_prompt='Detailed system instructions...' * 100,  # Long prompt
    model_settings=AnthropicModelSettings(
        anthropic_cache_instructions=True,      # Cache system prompt
        anthropic_cache_tool_definitions='1h',  # Cache tool definitions (1 hour TTL)
        anthropic_cache_messages=True,          # Cache conversation history
    ),
)

@agent.tool
def search_docs(ctx: RunContext, query: str) -> str:
    """Search documentation."""
    return f'Results for {query}'

# First request: Cache miss, full cost
result1 = agent.run_sync('Search for Python patterns')

# Subsequent requests: Cache hit, reduced cost
result2 = agent.run_sync('Search for FastAPI patterns')
```

**Cache TTL Options:**
- `True`: Uses default TTL (5 minutes)
- `'5m'`: 5-minute TTL
- `'1h'`: 1-hour TTL
- Note: Bedrock doesn't support explicit TTL; it's automatically omitted

**Anthropic Cache Points:**
- Max 4 cache points per request
- `anthropic_cache_messages` uses 1 cache point
- Additional cache points can be set manually in messages
- Automatically limited to 4 maximum

### FallbackModel

Chain multiple models with automatic fallback:

```python
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai import ModelSettings, Agent

# Create models with individual settings
openai_model = OpenAIChatModel(
    'gpt-4o',
    settings=ModelSettings(temperature=0.7, max_tokens=1000)
)

anthropic_model = AnthropicModel(
    'claude-sonnet-4-5',
    settings=ModelSettings(temperature=0.2, max_tokens=1000)
)

# Create fallback chain (tries OpenAI first, then Anthropic)
fallback_model = FallbackModel(openai_model, anthropic_model)

agent = Agent(fallback_model)

# If OpenAI fails, automatically falls back to Anthropic
result = agent.run_sync('Write a creative story.')
```

### Per-Run Model Override

Override model or settings for specific runs:

```python
agent = Agent('openai:gpt-4o')

# Use different model for this run
result = await agent.run(
    'Translate this text.',
    model='anthropic:claude-sonnet-4-5',
)

# Use different settings for this run
result = await agent.run(
    'Write creatively.',
    model_settings=ModelSettings(temperature=1.0, max_tokens=3000),
)
```

### Model Settings Priority

Settings are merged in this order (later overrides earlier):

1. Model's default settings (from initialization)
2. Agent's `model_settings` parameter
3. Per-run `model_settings` parameter

```python
# Model default
model = AnthropicModel(
    'claude-sonnet-4-5',
    settings=ModelSettings(temperature=0.5)
)

# Agent override
agent = Agent(
    model,
    model_settings=ModelSettings(temperature=0.7, max_tokens=2000)
)
# Result: temperature=0.7, max_tokens=2000

# Per-run override
result = await agent.run(
    'Write something.',
    model_settings=ModelSettings(max_tokens=5000)
)
# Result: temperature=0.7, max_tokens=5000 (merged)
```

---

## Summary and Key Takeaways

### For VTV AI Agent Service

**Recommended Architecture:**

1. **Agent Setup:**
   ```python
   from pydantic_ai import Agent
   from pydantic_ai.models.anthropic import AnthropicModelSettings

   agent = Agent(
       'anthropic:claude-sonnet-4-5',
       deps_type=TransitDeps,  # Database session, API clients, etc.
       system_prompt='You are a transit operations assistant...',
       model_settings=AnthropicModelSettings(
           temperature=0.2,  # Lower for factual responses
           max_tokens=2000,
           anthropic_cache_instructions=True,
           anthropic_cache_tool_definitions='1h',
       ),
       retries=2,
       tool_timeout=30.0,  # 30 second global timeout
   )
   ```

2. **Dependencies Pattern:**
   ```python
   @dataclass
   class TransitDeps:
       db_session: AsyncSession
       gtfs_client: GTFSClient
       user_id: str
   ```

3. **FastAPI Integration:**
   ```python
   from pydantic_ai.ui.vercel_ai import VercelAIAdapter

   @app.post('/v1/chat/completions')
   async def chat(request: Request) -> Response:
       return await VercelAIAdapter.dispatch_request(request, agent=agent)
   ```

4. **Tool Registration:**
   ```python
   @agent.tool(retries=3, timeout=10.0)
   async def query_bus_status(
       ctx: RunContext[TransitDeps],
       route_id: str | None = None
   ) -> dict:
       """Get real-time bus status.

       [Detailed docstring for LLM tool selection]
       """
       async with ctx.deps.db_session as session:
           # Query database using dependencies
           ...
   ```

5. **Structured Output:**
   ```python
   class BusStatusResponse(BaseModel):
       route_id: str
       vehicle_id: str
       delay_minutes: float
       location: dict

   # Override output type per tool or conversation
   ```

**Best Practices:**

- Use **Anthropic Claude models** for production (better instruction following)
- Enable **prompt caching** for cost optimization
- Use **`deps_type`** for type-safe dependency injection
- Write **comprehensive tool docstrings** (LLMs use them for tool selection)
- Use **`run_stream`** for FastAPI endpoints (better UX)
- Track **usage metrics** via `result.usage()` for cost monitoring
- Use **message history** for multi-turn conversations
- Set **tool timeouts** to prevent hanging requests
- Use **output validation** for quality control

**Monitoring and Limits:**

```python
from pydantic_ai import UsageLimits

limits = UsageLimits(
    max_tokens=50000,      # Total tokens per conversation
    max_requests=20,       # Max API requests per conversation
)

result = await agent.run(
    'Complex query...',
    usage_limits=limits,
)
```

---

## Additional Resources

- **Official Docs:** https://ai.pydantic.dev/
- **Anthropic Models:** https://ai.pydantic.dev/models/anthropic/
- **Tools Guide:** https://ai.pydantic.dev/tools/
- **FastAPI Integration:** https://ai.pydantic.dev/ui/overview/
- **Message History:** https://ai.pydantic.dev/message-history/
- **Output Types:** https://ai.pydantic.dev/output/

---

**End of Documentation**
