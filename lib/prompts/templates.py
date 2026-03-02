"""Task-specific prompt templates for Gemini delegation.

Each template returns (system_instruction, user_prompt) tuple.
System instructions are kept separate for injection safety.
"""

SYSTEM_INSTRUCTIONS = {
    "analyze": (
        "You are a code analysis assistant. Analyze the provided code and return "
        "structured JSON with your findings. Be precise, cite line numbers, and "
        "focus on actionable insights. Do not include opinions — only facts and evidence."
    ),
    "summarize": (
        "You are a summarization assistant. Condense the provided content into a "
        "clear, structured summary. Return JSON with: summary, key_points (array), "
        "and important_details (array). Be concise but don't lose critical information."
    ),
    "vision": (
        "You are a visual analysis assistant. Analyze the provided image(s) and "
        "return structured JSON describing what you see. Be specific about UI elements, "
        "text content, layout, colors, and any issues you notice."
    ),
    "generate": (
        "You are a code generation assistant. Generate code based on the requirements. "
        "Return JSON with: code (the generated code as a string), language, "
        "explanation (brief), and dependencies (array of required packages)."
    ),
    "ask": (
        "You are a technical assistant. Answer the question based on the provided "
        "context. Return JSON with: answer, confidence (0-1), sources (array of "
        "relevant file paths or references), and follow_up (suggested next steps)."
    ),
    "diff": (
        "You are a code review assistant. Analyze the provided diff or code changes. "
        "Return JSON with: summary, issues (array of {severity, file, line, description}), "
        "suggestions (array), and risk_level (low/medium/high)."
    ),
    "bulk": (
        "You are a batch processing assistant. Process each item in the provided list "
        "and return JSON with: results (array matching input order), "
        "summary, and errors (array of any failures)."
    ),
}


def get_analyze_prompt(focus: str = "") -> tuple[str, str]:
    system = SYSTEM_INSTRUCTIONS["analyze"]
    user = (
        "Analyze the code provided above. Return JSON with:\n"
        '{\n'
        '  "language": "detected language",\n'
        '  "purpose": "what this code does",\n'
        '  "complexity": "low|medium|high",\n'
        '  "issues": [{"severity": "low|medium|high|critical", "line": N, "description": "..."}],\n'
        '  "patterns": ["pattern names detected"],\n'
        '  "dependencies": ["external deps used"],\n'
        '  "suggestions": ["improvement suggestions"]\n'
        '}'
    )
    if focus:
        user += f"\n\nFocus specifically on: {focus}"
    return system, user


def get_summarize_prompt(max_length: str = "medium") -> tuple[str, str]:
    lengths = {"short": "3-5 sentences", "medium": "1-2 paragraphs", "long": "detailed multi-paragraph"}
    system = SYSTEM_INSTRUCTIONS["summarize"]
    user = (
        f"Summarize the content above in {lengths.get(max_length, lengths['medium'])}. "
        "Return JSON:\n"
        '{\n'
        '  "summary": "...",\n'
        '  "key_points": ["point 1", "point 2"],\n'
        '  "important_details": ["detail 1", "detail 2"],\n'
        '  "content_type": "code|docs|logs|config|other",\n'
        '  "word_count_original": N\n'
        '}'
    )
    return system, user


def get_vision_prompt(task: str = "describe") -> tuple[str, str]:
    system = SYSTEM_INSTRUCTIONS["vision"]
    tasks = {
        "describe": "Describe what you see in this image in detail.",
        "ui-review": "Review this UI screenshot. Identify layout issues, accessibility concerns, and UX improvements.",
        "extract-text": "Extract all visible text from this image, preserving structure.",
        "compare": "Compare these images and describe the differences.",
        "debug": "This is a screenshot of an error or bug. Identify the issue and suggest fixes.",
    }
    user = (
        f"{tasks.get(task, tasks['describe'])}\n\n"
        "Return JSON:\n"
        '{\n'
        '  "description": "...",\n'
        '  "elements": [{"type": "text|button|image|layout|error", "content": "...", "location": "..."}],\n'
        '  "issues": [{"severity": "low|medium|high", "description": "..."}],\n'
        '  "extracted_text": "..." \n'
        '}'
    )
    return system, user


def get_generate_prompt(language: str = "", style: str = "") -> tuple[str, str]:
    system = SYSTEM_INSTRUCTIONS["generate"]
    user = "Generate code based on the requirements above.\n\nReturn JSON:\n"
    user += '{\n'
    user += '  "code": "...the generated code...",\n'
    user += f'  "language": "{language or "auto-detect"}",\n'
    user += '  "explanation": "brief explanation",\n'
    user += '  "dependencies": ["required packages"],\n'
    user += '  "usage": "how to use this code"\n'
    user += '}'
    if style:
        user += f"\n\nCode style: {style}"
    return system, user


def get_ask_prompt() -> tuple[str, str]:
    system = SYSTEM_INSTRUCTIONS["ask"]
    user = (
        "Answer the question above using the provided context.\n\n"
        "Return JSON:\n"
        '{\n'
        '  "answer": "...",\n'
        '  "confidence": 0.0-1.0,\n'
        '  "reasoning": "brief explanation of how you arrived at the answer",\n'
        '  "sources": ["relevant file paths or references"],\n'
        '  "follow_up": ["suggested next steps or related questions"]\n'
        '}'
    )
    return system, user


def get_diff_prompt() -> tuple[str, str]:
    system = SYSTEM_INSTRUCTIONS["diff"]
    user = (
        "Review the code changes above.\n\n"
        "Return JSON:\n"
        '{\n'
        '  "summary": "what changed and why",\n'
        '  "risk_level": "low|medium|high",\n'
        '  "issues": [{"severity": "...", "file": "...", "line": N, "description": "..."}],\n'
        '  "suggestions": ["improvement suggestions"],\n'
        '  "breaking_changes": ["any breaking changes detected"],\n'
        '  "test_coverage": "assessment of whether changes need new tests"\n'
        '}'
    )
    return system, user


def get_bulk_prompt(operation: str = "summarize") -> tuple[str, str]:
    system = SYSTEM_INSTRUCTIONS["bulk"]
    user = (
        f"Process each item above. Operation: {operation}\n\n"
        "Return JSON:\n"
        '{\n'
        '  "results": [{"item": "identifier", "result": "..."}],\n'
        '  "summary": "overall summary",\n'
        '  "errors": [{"item": "identifier", "error": "..."}]\n'
        '}'
    )
    return system, user
