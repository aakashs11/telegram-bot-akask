"""
Local eval runner for the platform-neutral ChatRuntime.

Usage:
    python -m evals.chat_runtime_eval
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from telegram_bot.runtime import ChatMessage, ChatRuntime, ChatType, Platform


CASES_PATH = Path(__file__).with_name("chat_runtime_cases.jsonl")
logging.getLogger("telegram_bot").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)


@dataclass
class FakeModerationResult:
    is_flagged: bool
    category: str = ""
    raw_response: str = ""


class FakeModerator:
    def __init__(self, flagged_terms: List[str]):
        self.flagged_terms = [term.lower() for term in flagged_terms]

    async def check(self, text: str) -> FakeModerationResult:
        lowered = text.lower()
        is_flagged = any(term in lowered for term in self.flagged_terms)
        return FakeModerationResult(
            is_flagged=is_flagged,
            category="content_violation" if is_flagged else "",
            raw_response="YES" if is_flagged else "NO",
        )


class FakeUserService:
    def __init__(self, profiles: Dict[str, Dict[str, Any]]):
        self.profiles = profiles

    async def get_user_profile(self, user_id: int, username: str = "") -> Dict[str, Any]:
        return self.profiles.get(str(user_id), {})


class FakeAgent:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    async def process(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return f"agent:{kwargs.get('chat_type')}:{kwargs.get('user_message')}"


def build_message(raw: Dict[str, Any]) -> ChatMessage:
    return ChatMessage(
        platform=Platform(raw.get("platform", "test")),
        platform_user_id=raw["platform_user_id"],
        platform_chat_id=raw["platform_chat_id"],
        chat_type=ChatType(raw["chat_type"]),
        text=raw["text"],
        username=raw.get("username", ""),
        message_id=raw.get("message_id"),
        reply_to_text=raw.get("reply_to_text"),
        is_bot_mentioned=raw.get("is_bot_mentioned", False),
        bot_username=raw.get("bot_username", ""),
        group_title=raw.get("group_title", ""),
        is_admin=raw.get("is_admin", False),
        metadata=raw.get("metadata", {}),
    )


def assert_case(case: Dict[str, Any], response, agent: FakeAgent) -> List[str]:
    errors = []
    expect = case["expect"]
    agent_called = bool(agent.calls)

    if response.metadata.get("route") != expect.get("route"):
        errors.append(
            f"route expected {expect.get('route')!r}, got {response.metadata.get('route')!r}"
        )
    if response.reply_mode.value != expect.get("reply_mode"):
        errors.append(
            f"reply_mode expected {expect.get('reply_mode')!r}, got {response.reply_mode.value!r}"
        )
    if expect.get("visibility") and response.visibility.value != expect["visibility"]:
        errors.append(
            f"visibility expected {expect['visibility']!r}, got {response.visibility.value!r}"
        )
    if expect.get("action") and response.metadata.get("action") != expect["action"]:
        errors.append(
            f"action expected {expect['action']!r}, got {response.metadata.get('action')!r}"
        )
    if agent_called != expect.get("agent_called"):
        errors.append(
            f"agent_called expected {expect.get('agent_called')!r}, got {agent_called!r}"
        )

    if agent_called:
        call = agent.calls[-1]
        if expect.get("agent_chat_type") and call.get("chat_type") != expect["agent_chat_type"]:
            errors.append(
                f"agent_chat_type expected {expect['agent_chat_type']!r}, got {call.get('chat_type')!r}"
            )
        if expect.get("agent_input_contains") and expect["agent_input_contains"] not in call.get("user_message", ""):
            errors.append(
                f"agent input did not contain {expect['agent_input_contains']!r}: {call.get('user_message')!r}"
            )
        if "agent_is_admin" in expect and call.get("is_admin") != expect["agent_is_admin"]:
            errors.append(
                f"agent_is_admin expected {expect['agent_is_admin']!r}, got {call.get('is_admin')!r}"
            )

    if expect.get("response_contains") and expect["response_contains"] not in response.text:
        errors.append(
            f"response did not contain {expect['response_contains']!r}: {response.text!r}"
        )

    return errors


async def run_case(case: Dict[str, Any]) -> List[str]:
    agent = FakeAgent()
    runtime = ChatRuntime(
        agent=agent,
        user_service=FakeUserService(case.get("profiles", {})),
        content_moderator=FakeModerator(case.get("flagged_terms", [])),
    )

    response = await runtime.handle(build_message(case["message"]))
    return assert_case(case, response, agent)


async def main() -> int:
    cases = [
        json.loads(line)
        for line in CASES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    failed = 0
    for case in cases:
        errors = await run_case(case)
        if errors:
            failed += 1
            print(f"FAIL {case['name']}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"PASS {case['name']}")

    print(f"\n{len(cases) - failed}/{len(cases)} chat runtime evals passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
