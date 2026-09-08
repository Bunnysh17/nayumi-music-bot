"""
Tool Registry — Modular, Risk-Classified Tool System for Autonomous AI Execution
"""

import os
import re
import sys
import json
import asyncio
import traceback
from datetime import datetime
from typing import Callable, Dict, Any, List, Optional

# Risk Levels
RISK_LOW = "LOW"        # Read-only / Safe actions (Help, Status, Read file)
RISK_MEDIUM = "MEDIUM"  # User-authorized actions (Timer, Purge, Env update)
RISK_HIGH = "HIGH"      # Critical actions requiring Creator/Owner permission (Code edit, Standby, Install)

class Tool:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        risk_level: str,
        handler: Callable,
        owner_only: bool = False
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.risk_level = risk_level
        self.handler = handler
        self.owner_only = owner_only

    def to_schema_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "risk_level": self.risk_level,
            "owner_only": self.owner_only
        }


class ToolRegistry:
    _tools: Dict[str, Tool] = {}

    @classmethod
    def register(
        cls,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        risk_level: str = RISK_LOW,
        owner_only: bool = False
    ):
        def decorator(func: Callable):
            cls._tools[name] = Tool(
                name=name,
                description=description,
                parameters=parameters,
                risk_level=risk_level,
                handler=func,
                owner_only=owner_only
            )
            return func
        return decorator

    @classmethod
    def get_tool(cls, name: str) -> Optional[Tool]:
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> List[Tool]:
        return list(cls._tools.values())

    @classmethod
    def get_prompt_schema(cls) -> str:
        """
        Generates clean, readable schema for the AI system prompt.
        """
        lines = ["=== AUTONOMOUS TOOLS AVAILABLE ==="]
        for t in cls._tools.values():
            param_desc = ", ".join([f"{k}: {v.get('type', 'any')}" for k, v in t.parameters.get("properties", {}).items()])
            owner_flag = " [👑 OWNER ONLY]" if t.owner_only else ""
            lines.append(f"• `{t.name}({param_desc})`{owner_flag}: {t.description}")
        lines.append(
            "\nTo trigger a tool, include its action tag at the beginning of your response:\n"
            "`[ACTION:tool_name(param1=value1, param2=value2)]`\n"
            "Example: `[ACTION:set_timer(seconds=10, reason=\"Break\")]`\n"
            "Then follow with your warm, natural conversational reply!"
        )
        return "\n".join(lines)


import inspect

# Helper Functions
register_tool = ToolRegistry.register

async def execute_tool(name: str, kwargs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    tool = ToolRegistry.get_tool(name)
    if not tool:
        return {"success": False, "error": f"Tool '{name}' not found."}

    is_owner = context.get("is_owner", False)
    is_trusted = context.get("is_trusted", False)
    if tool.owner_only and not (is_owner or is_trusted):
        return {"success": False, "error": "Permission Denied: This tool is restricted to Creator Bunny and Authorized Whitelisted Users."}

    try:
        sig = inspect.signature(tool.handler)
        bound_kwargs = {}
        has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())

        # Parameter aliases mapping
        aliases = {
            "message_content": ["target_content", "content", "text", "msg", "message", "body"],
            "target_user": ["user", "target", "recipient", "member", "target_name"],
            "channel": ["target_channel", "channel_name", "channel_id", "chan"],
            "count": ["times", "number", "amount"],
            "seconds": ["duration", "time", "delay", "secs", "sec"],
            "server_name": ["guild_name", "server", "guild"]
        }

        normalized_kwargs = dict(kwargs)
        for target_key, alias_list in aliases.items():
            if target_key not in normalized_kwargs:
                for a in alias_list:
                    if a in normalized_kwargs:
                        normalized_kwargs[target_key] = normalized_kwargs[a]
                        break

        for param_name, param in sig.parameters.items():
            if param_name == "context":
                bound_kwargs["context"] = context
            elif param_name in normalized_kwargs:
                bound_kwargs[param_name] = normalized_kwargs[param_name]
            elif param.default != inspect.Parameter.empty:
                bound_kwargs[param_name] = param.default

        if has_var_keyword:
            for k, v in normalized_kwargs.items():
                if k not in bound_kwargs:
                    bound_kwargs[k] = v

        if asyncio.iscoroutinefunction(tool.handler):
            res = await tool.handler(**bound_kwargs)
        else:
            res = tool.handler(**bound_kwargs)
        return {"success": True, "result": res}
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def get_all_tools_schema() -> str:
    return ToolRegistry.get_prompt_schema()
