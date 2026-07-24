"""
content_generator.py
Generates, for any topic a student types in:
  - a structured lesson (summary, sections, key concepts)
  - worked example "test cases" (input/output/explanation) illustrating the topic
  - 5 quick mock-check questions (shown right under the lesson)
  - a full 20-question multiple-choice test (shown on the Test page)

Uses the Claude API when ANTHROPIC_API_KEY is set. Falls back to a clearly
labelled generic template if it isn't, so the app still runs end-to-end
without any key configured.
"""

import os
import json
import re

MODEL = "claude-sonnet-4-5"


def _client():
    try:
        import anthropic
    except ImportError:
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def _extract_json(text: str):
    """Claude sometimes wraps JSON in prose or code fences; pull the JSON block out."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        first = min([i for i in [text.find("{"), text.find("[")] if i != -1], default=-1)
        if first != -1:
            last = max(text.rfind("}"), text.rfind("]"))
            if last != -1:
                text = text[first:last + 1]
    return json.loads(text)


def _call_claude(prompt: str, max_tokens: int = 4000):
    client = _client()
    if client is None:
        return None
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return _extract_json(text)
    except Exception as e:
        print(f"[content_generator] Claude call failed, using fallback: {e}")
        return None


# ---------------------------------------------------------------------------
# Lesson generation
# ---------------------------------------------------------------------------
def generate_lesson(topic: str) -> dict:
    prompt = f"""You are an expert teacher creating a beginner-to-intermediate lesson on: "{topic}"

Respond with ONLY valid JSON (no prose, no markdown fences) matching this exact schema:
{{
  "title": "string, a clear lesson title",
  "summary": "2-3 sentence plain-language overview of the topic",
  "sections": [
    {{"heading": "string", "content": "3-6 sentences explaining this part clearly, with a concrete example"}}
  ],
  "key_concepts": ["short phrase", "short phrase", "..."],
  "example_cases": [
    {{"input": "string describing an example input/scenario", "output": "string describing the expected result", "explanation": "why this is the result, 1-2 sentences"}}
  ],
  "mock_questions": [
    {{"question": "string", "options": ["A", "B", "C", "D"], "answer_index": 0, "explanation": "brief reason"}}
  ],
  "video_search_query": "a good, specific YouTube search phrase for finding a tutorial on this exact topic"
}}

Include exactly 4-6 sections, exactly 4-6 key_concepts, exactly 3 example_cases, and exactly 5 mock_questions.
Keep it accurate, clear, and appropriately scoped for someone learning this topic for the first time.
"""
    data = _call_claude(prompt, max_tokens=4000)
    if data:
        return {"source": "ai", **data}
    return _fallback_lesson(topic)


def _fallback_lesson(topic: str) -> dict:
    return {
        "source": "template",
        "title": f"Introduction to {topic}",
        "summary": f"This is a starter overview of {topic}. Configure ANTHROPIC_API_KEY on the "
                   f"server to unlock full AI-generated lessons tailored exactly to this topic.",
        "sections": [
            {"heading": f"What is {topic}?",
             "content": f"{topic} is the subject you asked to learn about. With an AI key configured, "
                        f"this section would explain its core definition, where it's used, and why it matters, "
                        f"with a concrete example specific to {topic}."},
            {"heading": "Core building blocks",
             "content": f"Every topic has a handful of foundational ideas you need before anything else "
                        f"makes sense. This section would break {topic} down into those pieces, in order."},
            {"heading": "A worked example",
             "content": f"Seeing {topic} applied to one concrete example is usually the fastest way to "
                        f"understand it. This section would walk through one step by step."},
            {"heading": "Common mistakes",
             "content": f"Most learners trip on the same handful of misconceptions about {topic}. This "
                        f"section would flag the top ones so you can avoid them early."},
        ],
        "key_concepts": [f"{topic} basics", "core terminology", "common use cases", "typical pitfalls"],
        "example_cases": [
            {"input": "Example scenario 1", "output": "Expected result", "explanation": "Configure an API key for a real, topic-specific example."},
            {"input": "Example scenario 2", "output": "Expected result", "explanation": "Configure an API key for a real, topic-specific example."},
            {"input": "Example scenario 3", "output": "Expected result", "explanation": "Configure an API key for a real, topic-specific example."},
        ],
        "mock_questions": _fallback_mock_questions(topic),
        "video_search_query": f"{topic} tutorial for beginners",
    }


_FALLBACK_PROMPTS = [
    "Which of these best describes {topic}?",
    "Which statement about {topic} is most accurate?",
    "What is a key building block when learning {topic}?",
    "Which of the following is most closely related to {topic}?",
    "What would you study first when starting {topic}?",
]


def _fallback_mock_questions(topic: str) -> list:
    import random
    questions = []
    for i, template in enumerate(_FALLBACK_PROMPTS):
        correct = random.randint(0, 3)
        options = ["Option A", "Option B", "Option C", "Option D"]
        options[correct] = f"A concept directly related to {topic}"
        questions.append({
            "question": template.format(topic=topic),
            "options": options,
            "answer_index": correct,
            "explanation": "This is a placeholder question -- configure ANTHROPIC_API_KEY on the server for real, topic-specific questions.",
        })
    return questions


# ---------------------------------------------------------------------------
# Full 20-question test generation
# ---------------------------------------------------------------------------
def generate_full_test(topic: str, num_questions: int = 20) -> list:
    prompt = f"""Create a {num_questions}-question multiple-choice knowledge test on the topic: "{topic}"

Respond with ONLY a valid JSON array (no prose, no markdown fences), where each element matches:
{{
  "question": "string",
  "options": ["A", "B", "C", "D"],
  "answer_index": 0,
  "explanation": "1-2 sentence explanation of why that answer is correct"
}}

Requirements:
- Exactly {num_questions} questions.
- Mix of difficulty: roughly 40% easy/recall, 40% applied/understanding, 20% harder/edge-case.
- Questions must be specific to "{topic}", not generic filler.
- Exactly 4 options per question, only one correct, answer_index is 0-based.
- No duplicate questions.
"""
    data = _call_claude(prompt, max_tokens=6000)
    if isinstance(data, list) and len(data) >= 5:
        return data[:num_questions]
    return _fallback_test(topic, num_questions)


def _fallback_test(topic: str, num_questions: int) -> list:
    import random
    questions = []
    for i in range(num_questions):
        correct = random.randint(0, 3)
        options = ["Option A", "Option B", "Option C", "Option D"]
        options[correct] = f"The concept most directly tied to {topic} (question {i + 1})"
        questions.append({
            "question": f"Placeholder question {i + 1} about {topic} -- configure ANTHROPIC_API_KEY on the server for a real, topic-specific question here.",
            "options": options,
            "answer_index": correct,
            "explanation": "This is a placeholder -- configure an AI key on the server for real, topic-specific questions.",
        })
    return questions
