# Gets examples and api docs

## Adding to project
claude mcp add context7 -- npx -y @upstash/context7-mcp
claude

# to remove
claude mcp remove context7

## Calling with context7
"use mcp context7 to summarize for me the right way to use OpenAI Agents SDK with a model other than OpenAI's models"

## Returns
⏺ context7 - query-docs (MCP)(libraryId: "/openai/openai-agents-python", query: "using non-OpenAI models custom model providers LiteLLM       
                             Anthropic Claude external models")                                                                               
  ⎿  ### Enabling Usage Tracking for LiteLLM Models in Agents (Python)                                                                        
                                                                                                                                              
     Source: https://github.com/openai/openai-agents-python/blob/main/docs/usage.md                                                           
     … +36 lines (ctrl+o to expand)                                                                                                           
                                                                                                                                              
⏺ Here's the summary:                                                                                                                         
                                                                                                                                              
  Using Non-OpenAI Models with OpenAI Agents SDK (Python)                                                                                     
                                                                                                                                              
  There are 3 integration paths, in order of increasing flexibility:                                                                          
                                                                                                                                              
  ---                                                                                                                                         
  1. OpenAI-compatible endpoint (simplest)                                                                                                  
                                                                                                                                              
  If the provider has an OpenAI-compatible API:                                                                                               
  from openai import AsyncOpenAI                                                                                                              
  from agents import set_default_openai_client, Agent                                                                                         
                                                                                                                                              
  client = AsyncOpenAI(base_url="https://your-provider.com/v1", api_key="...")                                                                
  set_default_openai_client(client)  # applies globally to all agents                                                                         
                                                                                                                                              
  ---                                                                                                                                         
  2. LiteLLM (recommended for broad provider support)                                                                                       
                                                                                                                                              
  Supports Anthropic, Gemini, Cohere, etc. Install the extra:                                                                               
  pip install openai-agents[litellm]                                                                                                          
  from agents import Agent, ModelSettings, Runner                                                                                           
  from agents.extensions.models.litellm_model import LitellmModel                                                                             
                                                                                                                                            
  agent = Agent(                                                                                                                              
      name="Assistant",
      model=LitellmModel(model="anthropic/claude-opus-4-6", api_key="..."),                                                                   
      model_settings=ModelSettings(include_usage=True),  # needed for token tracking with LiteLLM                                           
  )                                                                                                                                           
                                                                                                                                              
  ---                                                                                                                                         
  3. Custom ModelProvider (most flexible)                                                                                                     
                                                                                                                                            
  Pass a custom provider at Runner.run level (affects all agents in that run):
  result = await Runner.run(agent, "...", model_provider=my_custom_provider)                                                                  
  Or set model= directly on an Agent instance to mix providers per agent.   
                                                                                                                                              
  ---                                                                                                                                         
  Key gotchas                                                                                                                                 
                                                                                                                                              
  - Disable tracing if you don't have an platform.openai.com API key: set_tracing_disabled()                                                
  - Or use set_tracing_export_api_key(openai_key) to send traces to OpenAI's dashboard even when the model is non-OpenAI                      
  - LiteLLM usage metrics are off by default — always pass ModelSettings(include_usage=True)                                                  
  - Prefer the Chat Completions API model when using third-party providers, as most don't support the Responses API yet                       
  ⎿  Stop says: 🔄 Ralph iteration 3 | No completion promise set - loop runs infinitely                                                       
                                                                                                                                              
