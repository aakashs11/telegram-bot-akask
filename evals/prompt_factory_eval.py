"""
Unit eval for PromptFactory.build_system_prompt profile injection logic.

No API calls needed — tests the Python guard logic only.

Usage:
    python -m evals.prompt_factory_eval
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_bot.prompts.prompt_factory import PromptFactory


def check(name: str, prompt: str, should_contain: list[str], should_not_contain: list[str]) -> list[str]:
    errors = []
    for phrase in should_contain:
        if phrase not in prompt:
            errors.append(f"missing expected phrase: {phrase!r}")
    for phrase in should_not_contain:
        if phrase in prompt:
            errors.append(f"unexpected phrase found: {phrase!r}")
    return errors


CASES = [
    {
        "name": "full_profile_injects_section",
        "profile": {"current_class": 10, "preferred_subject": "AI"},
        "should_contain": ["Class: 10", "Subject: AI", "DO NOT ask for class or subject"],
        "should_not_contain": ["not set yet", "incomplete"],
    },
    {
        "name": "class_only_injects_partial_asks_subject",
        "profile": {"current_class": 12, "preferred_subject": None},
        "should_contain": ["Class: 12", "Subject: not set yet", "missing field: **subject**"],
        "should_not_contain": ["DO NOT ask for class or subject"],
    },
    {
        "name": "subject_only_injects_partial_asks_class",
        "profile": {"current_class": None, "preferred_subject": "CS"},
        "should_contain": ["Class: not set yet", "Subject: CS", "missing field: **class**"],
        "should_not_contain": ["DO NOT ask for class or subject"],
    },
    {
        "name": "empty_profile_injects_nothing",
        "profile": {"current_class": None, "preferred_subject": None},
        "should_contain": [],
        "should_not_contain": ["DO NOT ask for class or subject", "not set yet", "both values confirmed"],
    },
    {
        "name": "none_profile_injects_nothing",
        "profile": None,
        "should_contain": [],
        "should_not_contain": ["DO NOT ask for class or subject", "not set yet", "both values confirmed"],
    },
    {
        "name": "new_user_profile_injects_nothing",
        "profile": {"user_id": 123, "username": "Riya", "current_class": None, "preferred_subject": None},
        "should_contain": [],
        "should_not_contain": ["DO NOT ask for class or subject", "not set yet", "both values confirmed"],
    },
]


def main() -> int:
    # Clear lru_cache so file edits are picked up between test runs
    PromptFactory._load_prompt_file.cache_clear()

    failed = 0
    for case in CASES:
        prompt = PromptFactory.build_system_prompt(case["profile"])
        errors = check(
            case["name"],
            prompt,
            case["should_contain"],
            case["should_not_contain"],
        )
        if errors:
            failed += 1
            print(f"FAIL {case['name']}")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"PASS {case['name']}")

    print(f"\n{len(CASES) - failed}/{len(CASES)} prompt factory evals passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
