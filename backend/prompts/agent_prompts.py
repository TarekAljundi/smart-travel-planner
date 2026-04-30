# backend/prompts/agent_prompts.py
"""
All static prompts used by the travel agent.
No strings are hard-coded inside the agent logic.
"""

# ---- System prompt for the cheap agent that decides tools ----
AGENT_SYSTEM_PROMPT = (
    "You are a travel research assistant. Use the available tools to gather information "
    "about destinations that match the user's query. After collecting data, return a "
    "clear summary of your findings. Always use all the tools before answering."
)

# ---- Prompt for the strong model that writes the final plan ----
SYNTHESIS_PROMPT_TEMPLATE = (
    "User query: {query}\n\n"
    "Research gathered by tools:\n{context}\n\n"
    "Write a detailed trip plan using the EXACT format below. "
    "Before each section title, add a blank line.\n"
    "DO NOT use dash separators like -----.\n\n"
    "FORMAT:\n\n"
    "RECOMMENDED DESTINATION\n"
    "- Destination name\n"
    "- Why it fits the user's preferences\n\n"
    "CURRENT WEATHER\n"
    "- Temperature and conditions (or explain why unavailable)\n"
    "- Packing advice\n\n"
    "2-WEEK ITINERARY\n"
    "- Day 1: ...\n"
    "- Day 2: ...\n"
    "... continue for all 14 days\n\n"
    "BUDGET BREAKDOWN\n"
    "- Flights: $xxx\n"
    "- Accommodation: $xxx\n"
    "- Activities: $xxx\n"
    "- Food & transport: $xxx\n"
    "- Total: $xxx\n\n"
    "IMPORTANT CAVEATS\n"
    "- Honest notes about crowds, weather, booking, etc.\n\n"
    "Now write the full trip plan."
)

# ---- Tool descriptions (used when building StructuredTools) ----
RAG_TOOL_DESCRIPTION = "Search the destination knowledge base for relevant travel information."
CLASSIFY_TOOL_DESCRIPTION = "Classify a destination's travel style (Adventure, Relaxation, Culture, Budget, Luxury, Family) based on its name."
WEATHER_TOOL_DESCRIPTION = "Get the current weather for a given city."