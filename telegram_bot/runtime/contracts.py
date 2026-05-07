from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class Platform(str, Enum):
    TELEGRAM = "telegram"
    WEBSITE = "website"
    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    TEST = "test"


class ChatType(str, Enum):
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"


class ReplyMode(str, Enum):
    REPLY = "reply"
    DM = "dm"
    SILENT = "silent"


class ResponseVisibility(str, Enum):
    NORMAL = "normal"
    EPHEMERAL = "ephemeral"


@dataclass
class ChatMessage:
    platform: Platform
    platform_user_id: str
    platform_chat_id: str
    chat_type: ChatType
    text: str
    username: str = ""
    message_id: Optional[str] = None
    reply_to_text: Optional[str] = None
    is_bot_mentioned: bool = False
    bot_username: str = ""
    group_title: str = ""
    is_admin: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    text: str = ""
    reply_mode: ReplyMode = ReplyMode.REPLY
    visibility: ResponseVisibility = ResponseVisibility.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
