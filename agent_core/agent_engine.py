"""
Agent Engine — Autonomous Intent Resolver, Tool Dispatcher, and Response Synthesizer
"""

import os
import re
import sys
import json
import asyncio
import traceback
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple, Optional, List

from .tool_registry import ToolRegistry, register_tool, execute_tool, RISK_LOW, RISK_MEDIUM, RISK_HIGH
from .safe_code_engine import SafeCodeEngine


# ==========================================
# REGISTER DEFAULT CORE TOOLS
# ==========================================

@register_tool(
    name="tag_user",
    description="Tags a specific Discord user in the current channel. If count > 1 (e.g. 5 baar tag karo), sends multiple separate tag messages.",
    parameters={
        "type": "object",
        "properties": {
            "target_user": {"type": "string", "description": "Username, display name, or user ID to tag (e.g. 'suyash', 'vivek')"},
            "count": {"type": "integer", "description": "Number of separate tag messages to send (1 to 10). Default 1."}
        },
        "required": ["target_user"]
    },
    risk_level=RISK_LOW
)
async def tool_tag_user(context: Dict[str, Any], target_user: str, count: int = 1) -> str:
    ctx_msg = context.get("message")
    bot = context.get("bot")
    if not ctx_msg:
        return "Message context missing."

    guild = ctx_msg.guild
    target_member = None

    clean_target = str(target_user).replace("<@", "").replace(">", "").replace("!", "").strip()
    if clean_target.isdigit():
        if guild:
            target_member = guild.get_member(int(clean_target))
        if not target_member and bot:
            try:
                target_member = await bot.fetch_user(int(clean_target))
            except Exception:
                pass

    if not target_member and guild:
        for m in guild.members:
            if m.name.lower() == target_user.lower() or m.display_name.lower() == target_user.lower():
                target_member = m
                break
            if target_user.lower() in m.name.lower() or target_user.lower() in m.display_name.lower():
                if not target_member:
                    target_member = m

    mention_str = target_member.mention if target_member else (f"<@{clean_target}>" if clean_target.isdigit() else f"@{target_user}")
    display_name = target_member.display_name if target_member else target_user

    num_tags = min(max(int(count) if count else 1, 1), 10)

    # If count > 1 (e.g. 5 baar tag karo), send separate ping messages:
    if num_tags > 1:
        for i in range(num_tags):
            try:
                await ctx_msg.channel.send(f"📢 {mention_str} *(Ping #{i+1}/{num_tags})*")
                await asyncio.sleep(0.4)
            except Exception:
                pass
        return f"Successfully sent {num_tags} tag messages for {display_name}."
    else:
        # For single tag (count = 1), Nayumi's conversational reply handles it in 1 single message!
        return f"Tagged {display_name} 1 time."


@register_tool(
    name="set_timer",
    description="Sets a countdown timer for a specified duration with optional recurring alerts/pings. ONLY use when user explicitly asks for a timer / countdown / delay.",
    parameters={
        "type": "object",
        "properties": {
            "seconds": {"type": "integer", "description": "Initial countdown delay in seconds (e.g. 10, 30, 300)"},
            "reason": {"type": "string", "description": "Reason or purpose for setting the timer"},
            "target_user": {"type": "string", "description": "Username or ID of the user to tag upon timer completion (Defaults to requester)."},
            "repeat_interval": {"type": "integer", "description": "Seconds between repeated pings if user asks to keep tagging every N seconds (e.g. 2, 5). Set 0 if one-time."},
            "repeat_count": {"type": "integer", "description": "Maximum number of repeat pings (1 to 10). Default 5 if repeating."},
            "stop_on_reply": {"type": "boolean", "description": "Whether to stop repeating once the user replies in the channel (Default True)."}
        },
        "required": ["seconds"]
    },
    risk_level=RISK_LOW
)
async def tool_set_timer(
    context: Dict[str, Any],
    seconds: int,
    reason: str = "Timer Complete!",
    target_user: str = "",
    repeat_interval: int = 0,
    repeat_count: int = 1,
    stop_on_reply: bool = True
) -> str:
    message = context.get("message")
    bot = context.get("bot")
    if not message or not bot:
        return "Message context missing."

    total_sec = min(max(int(seconds), 1), 604800)
    user = message.author
    ch = message.channel
    r_text = reason if reason else "Timer Complete!"

    # Resolve target user if specified
    target_member = user
    if target_user:
        clean_t = str(target_user).replace("<@", "").replace(">", "").replace("!", "").strip()
        if clean_t.isdigit() and ch.guild:
            target_member = ch.guild.get_member(int(clean_t)) or user
        elif ch.guild:
            for m in ch.guild.members:
                if m.name.lower() == target_user.lower() or m.display_name.lower() == target_user.lower():
                    target_member = m
                    break
                if target_user.lower() in m.name.lower() or target_user.lower() in m.display_name.lower():
                    target_member = m
                    break

    rep_int = max(int(repeat_interval), 0) if repeat_interval else 0
    if rep_int > 0:
        max_reps = min(max(int(repeat_count) if repeat_count > 1 else 5, 1), 10)
    else:
        max_reps = 1

    if total_sec < 60:
        dur_text = f"{total_sec} second(s)"
    elif total_sec < 3600:
        dur_text = f"{total_sec // 60} minute(s)"
    elif total_sec < 86400:
        dur_text = f"{total_sec // 3600} hour(s)"
    else:
        dur_text = f"{total_sec // 86400} day(s)"

    async def run_timer_task():
        await asyncio.sleep(total_sec)

        def check_user_reply(m):
            return m.author.id == target_member.id and m.channel.id == ch.id

        for i in range(max_reps):
            try:
                pings = f"{target_member.mention} {target_member.mention} {target_member.mention} {target_member.mention}"
                rep_note = f" *(Alert #{i+1}/{max_reps})*" if max_reps > 1 else ""
                alert_text = (
                    f"⏰ **WAKE UP / TIME'S UP!** 🚨{rep_note}\n"
                    f"{pings}\n"
                    f"**{target_member.display_name}**, aapka `{dur_text}` ka timer finish ho gaya hai!\n"
                    f"📌 **Reason:** `{r_text}` 🎀✨"
                )
                await ch.send(alert_text)
            except Exception:
                pass

            if i < max_reps - 1 and rep_int > 0:
                try:
                    if stop_on_reply:
                        await bot.wait_for("message", check=check_user_reply, timeout=float(rep_int))
                        break
                    else:
                        await asyncio.sleep(rep_int)
                except asyncio.TimeoutError:
                    continue

    bot.loop.create_task(run_timer_task())
    return f"Timer started for {dur_text} (Repeats: {max_reps}, Target: {target_member.display_name})."


@register_tool(
    name="purge_messages",
    description="Deletes previous messages from the current Discord channel (Requires Manage Messages or Owner permission).",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "description": "Number of messages to delete (1 to 100)"}
        },
        "required": ["count"]
    },
    risk_level=RISK_MEDIUM
)
async def tool_purge_messages(context: Dict[str, Any], count: int = 10) -> str:
    message = context.get("message")
    is_owner = context.get("is_owner", False)
    if not message:
        return "Message context missing."

    has_perm = is_owner or (hasattr(message.author, "guild_permissions") and message.author.guild_permissions.manage_messages)
    if not has_perm:
        return "Permission Denied: Manage Messages permission required."

    cnt = min(max(int(count), 1), 100)
    try:
        deleted = await message.channel.purge(limit=cnt + 1)
        del_count = len(deleted) - 1 if len(deleted) > 1 else len(deleted)
        
        # Flush channel memory if available
        ai_convs = context.get("ai_conversations")
        cid = str(message.channel.id)
        if ai_convs and cid in ai_convs:
            ai_convs[cid] = []

        return f"Successfully purged {del_count} messages."
    except Exception as e:
        return f"Purge error: {str(e)}"


@register_tool(
    name="manage_memory",
    description="Allows Bunny (Owner) to delete, view, clear, or update user memories, facts, promises, or specific memories (e.g. deleting chai/meetup memory for Anuj/desijaat).",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "Action: 'delete_keyword' (removes facts/promises matching keyword), 'clear_user' (wipes user profile), 'clear_all' (resets memory)"},
            "target_user": {"type": "string", "description": "Target username, nickname, or user ID (e.g. 'anuj', 'desijaat', 'vivek', 'suyash')"},
            "memory_keyword": {"type": "string", "description": "Keyword(s) to remove (e.g. 'chai,dhaba,milna,pakode')"}
        },
        "required": ["action"]
    },
    risk_level=RISK_LOW,
    owner_only=True
)
def tool_manage_memory(context: Dict[str, Any], action: str, target_user: str = "", memory_keyword: str = "") -> str:
    mem_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "nayumi_memory.json"))
    if not os.path.exists(mem_file):
        return "Memory database file not found."

    try:
        with open(mem_file, "r", encoding="utf-8") as f:
            db = json.load(f)
    except Exception as e:
        return f"Failed to load memory file: {str(e)}"

    users = db.get("users", {})
    action_low = action.lower().strip()

    if action_low in ["clear_all", "reset_all"]:
        db["users"] = {}
        db["channel_histories"] = {}
        with open(mem_file, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        return "All user memories and conversation histories have been completely wiped."

    target_uid = None
    target_profile = None

    clean_t = str(target_user).replace("<@", "").replace(">", "").replace("!", "").strip()
    if clean_t in users:
        target_uid = clean_t
        target_profile = users[clean_t]
    else:
        for uid, prof in users.items():
            u_name = prof.get("name", "").lower()
            if clean_t.lower() == u_name or clean_t.lower() in u_name:
                target_uid = uid
                target_profile = prof
                break
            for fact in prof.get("facts", []):
                if clean_t.lower() in fact.lower():
                    target_uid = uid
                    target_profile = prof
                    break
            if target_uid:
                break

    if not target_profile and target_user:
        return f"No memory profile found for user '{target_user}'."

    if action_low in ["clear_user", "delete_user"]:
        if target_uid:
            del users[target_uid]
            with open(mem_file, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=2, ensure_ascii=False)
            return f"Successfully deleted complete memory profile for user '{target_user}'."

    if action_low in ["delete", "delete_keyword", "remove_keyword", "delete_memory"]:
        kw_list = [k.strip().lower() for k in str(memory_keyword).split(",") if k.strip()]
        if not kw_list:
            kw_list = ["chai", "dhaba", "pakode", "milna", "meet"]
            
        removed_count = 0
        if target_profile:
            old_facts = target_profile.get("facts", [])
            new_facts = []
            for fact in old_facts:
                if any(kw in fact.lower() for kw in kw_list):
                    removed_count += 1
                else:
                    new_facts.append(fact)
            target_profile["facts"] = new_facts

            old_promises = target_profile.get("promises", [])
            new_promises = []
            for p in old_promises:
                if any(kw in p.lower() for kw in kw_list):
                    removed_count += 1
                else:
                    new_promises.append(p)
            target_profile["promises"] = new_promises

            if any(kw in target_profile.get("relationship", "").lower() for kw in kw_list):
                target_profile["relationship"] = "User / Friend"
            if any(kw in target_profile.get("personality_notes", "").lower() for kw in kw_list):
                target_profile["personality_notes"] = ""

        with open(mem_file, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)

        user_label = target_profile.get('name', target_user) if target_profile else "All matching"
        return f"Successfully removed {removed_count} memory items matching '{memory_keyword}' from {user_label}'s profile."

    return "Invalid memory action."


@register_tool(
    name="system_status",
    description="Inspects real-time API keys rotation pool, server memory, and active backend modules.",
    parameters={"type": "object", "properties": {}},
    risk_level=RISK_LOW
)
def tool_system_status(context: Dict[str, Any]) -> str:
    raw_keys = [k.strip() for k in os.getenv("GEMINI_API_KEY", "").split(",") if k.strip()]
    hbx_st = "Active" if os.getenv("HELLBYTEX_API_KEY") else "Not Set"
    phone_st = "Active (with Worker Fallback)" if os.getenv("PHONE_API_KEY") else "Not Set"
    return f"Active Gemini Keys: {len(raw_keys)} | HellByteX: {hbx_st} | Phone API: {phone_st}"


@register_tool(
    name="read_workspace_file",
    description="Reads the exact content of any backend file (e.g. .env, bot.py, ai_config.json) for the Owner.",
    parameters={
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Target filename to read (e.g. '.env', 'bot.py')"}
        },
        "required": ["filename"]
    },
    risk_level=RISK_LOW,
    owner_only=True
)
def tool_read_workspace_file(context: Dict[str, Any], filename: str) -> str:
    success, filepath, content = SafeCodeEngine.read_file(filename)
    if success:
        return content
    return f"Error: {content}"


@register_tool(
    name="update_env_variables",
    description="Adds or updates environment variables in .env and synchronizes os.environ in real-time.",
    parameters={
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Environment variable key name (e.g. 'GEMINI_API_KEY')"},
            "value": {"type": "string", "description": "Value to set or append"}
        },
        "required": ["key", "value"]
    },
    risk_level=RISK_MEDIUM,
    owner_only=True
)
def tool_update_env_variables(context: Dict[str, Any], key: str, value: str) -> str:
    try:
        env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
        current_env = {}
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f.read().splitlines():
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.split("=", 1)
                        current_env[k.strip()] = v.strip()

        # If Gemini Key, append to existing list if not present
        if key == "GEMINI_API_KEY" and "GEMINI_API_KEY" in current_env:
            cur_list = [x.strip() for x in current_env["GEMINI_API_KEY"].split(",") if x.strip()]
            if value not in cur_list:
                cur_list.append(value)
            current_env["GEMINI_API_KEY"] = ",".join(cur_list)
        else:
            current_env[key] = value

        os.environ[key] = current_env[key]

        with open(env_file, "w", encoding="utf-8") as f:
            for k, v in current_env.items():
                f.write(f"{k}={v}\n")

        return f"Successfully updated `{key}` in .env."
    except Exception as e:
        return f"Env update error: {str(e)}"


@register_tool(
    name="self_code_update",
    description="Autonomously modifies source code with syntax validation, automatic backup creation, and hot-reload.",
    parameters={
        "type": "object",
        "properties": {
            "target_file": {"type": "string", "description": "File to modify (e.g. 'bot.py')"},
            "target_snippet": {"type": "string", "description": "Exact existing code snippet to replace (or 'ALL')"},
            "replacement_snippet": {"type": "string", "description": "New replacement code snippet"}
        },
        "required": ["target_file", "target_snippet", "replacement_snippet"]
    },
    risk_level=RISK_HIGH,
    owner_only=True
)
def tool_self_code_update(context: Dict[str, Any], target_file: str, target_snippet: str, replacement_snippet: str) -> str:
    success, msg = SafeCodeEngine.apply_code_modification(target_file, target_snippet, replacement_snippet)
    if success:
        return msg
    return f"Modification Failed: {msg}"


@register_tool(
    name="standby_mode",
    description="Puts the bot into complete silent sleep/standby mode until Owner triggers wakeup.",
    parameters={"type": "object", "properties": {}},
    risk_level=RISK_MEDIUM,
    owner_only=True
)
def tool_standby_mode(context: Dict[str, Any]) -> str:
    set_standby_state = context.get("set_standby_state")
    message = context.get("message")
    if set_standby_state:
        set_standby_state(True, message.channel.id if message else 0)
    return "Standby mode activated."


@register_tool(
    name="wakeup_mode",
    description="Wakes the bot up from standby/sleep mode.",
    parameters={"type": "object", "properties": {}},
    risk_level=RISK_LOW,
    owner_only=True
)
def tool_wakeup_mode(context: Dict[str, Any]) -> str:
    set_standby_state = context.get("set_standby_state")
    if set_standby_state:
        set_standby_state(False)
    return "Bot awake and operational."


@register_tool(
    name="send_dm",
    description="Sends a direct private message (DM) to any Discord user/member on behalf of Bunny with stylish formatting.",
    parameters={
        "type": "object",
        "properties": {
            "target_user": {"type": "string", "description": "Username, nickname, or user ID to DM (e.g. 'vivek', '913264406912188456')"},
            "message_content": {"type": "string", "description": "The exact message to send to them in their DM"}
        },
        "required": ["target_user", "message_content"]
    },
    risk_level=RISK_LOW,
    owner_only=False
)
async def tool_send_dm(context: Dict[str, Any], target_user: str = "", message_content: str = "", **kwargs) -> str:
    bot = context.get("bot")
    message = context.get("message")
    if not bot or not message:
        return "Context missing."

    guild = message.guild
    target_member = None

    clean_target = str(target_user).replace("<@", "").replace(">", "").replace("!", "").strip()
    if clean_target.isdigit():
        try:
            target_member = await bot.fetch_user(int(clean_target))
        except Exception:
            pass

    if not target_member and guild:
        for m in guild.members:
            if m.name.lower() == target_user.lower() or m.display_name.lower() == target_user.lower():
                target_member = m
                break
            if target_user.lower() in m.name.lower() or target_user.lower() in m.display_name.lower():
                if not target_member:
                    target_member = m

    # Also search across all guilds if not in current guild
    if not target_member:
        for g in bot.guilds:
            for m in g.members:
                if m.name.lower() == target_user.lower() or m.display_name.lower() == target_user.lower() or target_user.lower() in m.name.lower():
                    target_member = m
                    break
            if target_member:
                break

    if not target_member:
        return f"User '{target_user}' could not be found."

    try:
        import discord
        dm_channel = await target_member.create_dm()

        # Store relay mapping so target user's DM reply forwards back to the sender
        dm_relays = context.get("dm_relays")
        sender_display = message.author.display_name if message else "Admin"
        if dm_relays is not None:
            sender_id = message.author.id if message else 913264406912188456
            sender_name = sender_display
            channel_id = message.channel.id if message and message.channel else 0
            guild_name = message.guild.name if message and message.guild else "Direct DM"
            dm_relays[target_member.id] = {
                "sender_id": sender_id,
                "sender_name": sender_name,
                "channel_id": channel_id,
                "guild_name": guild_name,
                "target_name": target_member.display_name,
                "updated_at": str(datetime.now())
            }
            try:
                import json
                with open("nayumi_dm_relays.json", "w", encoding="utf-8") as f:
                    json.dump({str(k): v for k, v in dm_relays.items()}, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

        msg_text = (
            f"<a:blackcrown:1543148226100600922> **OFFICIAL MESSAGE FROM {sender_display.upper()}** <a:crown:1543148555500392501>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{message_content}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 **Tip:** *Aap is DM mein apna reply likh sakte hain, aapka message directly {sender_display} tak deliver ho jayega!*\n"
            f"<a:booster:1543148240432660500> *Delivered by Nayumi Autonomous Engine*"
        )
        files_to_send = []
        if message and message.attachments:
            for att in message.attachments:
                try:
                    f = await att.to_file()
                    files_to_send.append(f)
                except Exception:
                    pass

        if files_to_send:
            await dm_channel.send(content=msg_text, files=files_to_send)
        else:
            await dm_channel.send(content=msg_text)
        return f"Successfully sent DM to {target_member.display_name} (with {len(files_to_send)} attachments)."
    except Exception as e:
        if "403" in str(e) or "Forbidden" in str(e) or "Cannot send messages to this user" in str(e):
            return f"Could not DM {target_member.display_name} (their DMs are closed/disabled)."
        return f"DM Error: {str(e)}"


@register_tool(
    name="send_channel_message",
    description="Sends an announcement or message to ANY channel by channel ID (e.g. '1471557800365785095') or channel name (e.g. 'announcement', 'general') in any server (e.g. 'SS EMPIRE').",
    parameters={
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel ID (e.g. '1471557800365785095') or channel name (e.g. 'announcement', 'general')"},
            "message_content": {"type": "string", "description": "The exact message or announcement content to post"},
            "server_name": {"type": "string", "description": "Optional server/guild name or ID (e.g. 'SS EMPIRE') to target a specific server"}
        },
        "required": ["channel", "message_content"]
    },
    risk_level=RISK_LOW,
    owner_only=False
)
async def tool_send_channel_message(context: Dict[str, Any], channel: str = "", message_content: str = "", server_name: str = "", **kwargs) -> str:
    bot = context.get("bot")
    orig_msg = context.get("message")
    if not bot:
        return "Bot instance missing."

    import discord

    target_ch = None
    clean_ch = str(channel).replace("<#", "").replace(">", "").replace("#", "").strip()

    # 1. By numeric Channel ID
    if clean_ch.isdigit():
        target_ch = bot.get_channel(int(clean_ch))
        if not target_ch:
            try:
                target_ch = await bot.fetch_channel(int(clean_ch))
            except Exception:
                pass

    # 2. Resolve Target Guild
    target_guild = None
    clean_server = str(server_name).strip() if server_name else ""

    if clean_server:
        if clean_server.isdigit():
            target_guild = bot.get_guild(int(clean_server))
            if not target_guild:
                try:
                    target_guild = await bot.fetch_guild(int(clean_server))
                except Exception:
                    pass

        if not target_guild:
            clean_s_low = clean_server.lower()
            for g in bot.guilds:
                if clean_s_low == g.name.lower() or clean_s_low in g.name.lower() or g.name.lower() in clean_s_low:
                    target_guild = g
                    break

    # If no server specified, prioritize current message's server
    if not target_guild and orig_msg and orig_msg.guild:
        target_guild = orig_msg.guild

    # 3. Channel Search by Name if not found by ID
    if not target_ch:
        search_guilds = [target_guild] if target_guild else bot.guilds

        def normalize_name(n: str) -> str:
            return re.sub(r'[^a-zA-Z0-9]', '', n).lower()

        norm_query = normalize_name(clean_ch)

        for g in search_guilds:
            # Collect all sendable channels (TextChannels, NewsChannels, Threads, ForumChannels)
            all_channels = []
            if hasattr(g, "channels"):
                all_channels.extend([c for c in g.channels if hasattr(c, "send") and not isinstance(c, (discord.CategoryChannel, discord.VoiceChannel))])
            if hasattr(g, "threads"):
                all_channels.extend(g.threads)

            # Pass 1: Exact Name Match
            for ch in all_channels:
                if ch.name.lower() == clean_ch.lower():
                    target_ch = ch
                    break
            if target_ch:
                break

            # Pass 2: Normalized Name Match (ignoring emojis/symbols e.g. 📢┃announcements -> announcements)
            if norm_query:
                for ch in all_channels:
                    norm_ch = normalize_name(ch.name)
                    if norm_ch == norm_query or (len(norm_query) >= 4 and (norm_query in norm_ch or norm_ch in norm_query)):
                        target_ch = ch
                        break
                if target_ch:
                    break

            # Pass 3: Announcement keyword matching
            if any(k in clean_ch.lower() for k in ["announc", "annc", "update", "news", "notice", "broadcast"]):
                for ch in all_channels:
                    c_low = ch.name.lower()
                    if any(k in c_low for k in ["announc", "annc", "update", "news", "notice", "broadcast"]):
                        target_ch = ch
                        break
                if target_ch:
                    break

    if not target_ch:
        guild_info = f"in server '{target_guild.name}'" if target_guild else "in any connected servers"
        avail_channels = []
        if target_guild and hasattr(target_guild, "channels"):
            avail_channels = [f"#{c.name} (`{c.id}`)" for c in target_guild.channels if hasattr(c, "send") and not isinstance(c, (discord.CategoryChannel, discord.VoiceChannel))][:8]
        hint = f" Available channels: {', '.join(avail_channels)}" if avail_channels else ""
        return f"Could not find channel '{channel}' {guild_info}.{hint}"

    try:
        files_to_send = []

        # 1. Attachments from current message
        if orig_msg and orig_msg.attachments:
            for att in orig_msg.attachments:
                try:
                    f = await att.to_file()
                    files_to_send.append(f)
                except Exception:
                    pass

        # 2. Attachments from referenced message (if user replied to an image/message)
        if orig_msg and getattr(orig_msg, "reference", None) and getattr(orig_msg.reference, "message_id", None) and not files_to_send:
            try:
                ref_msg = orig_msg.reference.cached_message
                if not ref_msg and orig_msg.channel:
                    ref_msg = await orig_msg.channel.fetch_message(orig_msg.reference.message_id)
                if ref_msg and ref_msg.attachments:
                    for att in ref_msg.attachments:
                        try:
                            f = await att.to_file()
                            files_to_send.append(f)
                        except Exception:
                            pass
            except Exception:
                pass

        # Split message into chunks if > 2000 chars
        if len(message_content) <= 2000:
            if files_to_send:
                await target_ch.send(content=message_content, files=files_to_send)
            else:
                await target_ch.send(content=message_content)
        else:
            chunks = [message_content[i:i+1950] for i in range(0, len(message_content), 1950)]
            for idx, chunk in enumerate(chunks):
                if idx == 0 and files_to_send:
                    await target_ch.send(content=chunk, files=files_to_send)
                else:
                    await target_ch.send(content=chunk)

        g_name = target_ch.guild.name if hasattr(target_ch, "guild") and target_ch.guild else "Direct"
        return f"Successfully sent message to #{target_ch.name} (ID: `{target_ch.id}`) in server '{g_name}' with {len(files_to_send)} attachment(s)."
    except discord.Forbidden:
        return f"Permission Denied: Bot lacks 'Send Messages' permission in channel #{target_ch.name} (ID: {target_ch.id})."
    except Exception as e:
        return f"Failed to send to channel #{target_ch.name}: {str(e)}"


@register_tool(
    name="list_guilds_and_channels",
    description="Lists all servers (guilds) and their text channels with IDs that the bot has access to.",
    parameters={"type": "object", "properties": {}},
    risk_level=RISK_LOW,
    owner_only=False
)
def tool_list_guilds_and_channels(context: Dict[str, Any], **kwargs) -> str:
    bot = context.get("bot")
    if not bot or not bot.guilds:
        return "No servers connected."

    lines = []
    for g in bot.guilds:
        ch_list = [f"#{c.name} (`{c.id}`)" for c in g.text_channels[:10]]
        lines.append(f"🏰 **{g.name}** (ID: `{g.id}`):\n  " + ", ".join(ch_list))

    return "\n\n".join(lines)


@register_tool(
    name="server_info",
    description="Gets total members, online counts, channels, and guild details of the current server.",
    parameters={"type": "object", "properties": {}},
    risk_level=RISK_LOW
)
def tool_server_info(context: Dict[str, Any]) -> str:
    message = context.get("message")
    if not message or not message.guild:
        return "Server context not available."
    g = message.guild
    return f"Server: {g.name} | Total Members: {g.member_count} | Channels: {len(g.channels)} | Roles: {len(g.roles)}"


@register_tool(
    name="run_custom_action",
    description="Executes arbitrary dynamic Python code or custom Discord automation for Creator Bunny on the fly.",
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code snippet or async expression to execute. Can access bot, message, channel, guild, etc."}
        },
        "required": ["code"]
    },
    risk_level=RISK_HIGH,
    owner_only=True
)
async def tool_run_custom_action(context: Dict[str, Any], code: str) -> str:
    bot = context.get("bot")
    message = context.get("message")
    if not message or not bot:
        return "Context missing."

    clean_code = code.strip()
    clean_code = re.sub(r'^```python\s*|^```\s*|```$', '', clean_code, flags=re.MULTILINE).strip()
    
    import discord
    env = {
        "bot": bot,
        "message": message,
        "channel": message.channel,
        "guild": message.guild,
        "author": message.author,
        "discord": discord,
        "asyncio": asyncio,
        "os": os,
        "sys": sys,
        "json": json,
        "re": re,
        "context": context
    }

    try:
        lines = clean_code.splitlines()
        indented = "\n".join(f"        {l}" for l in lines)
        func_code = f"async def __run_custom_task():\n{indented}\n"
        
        exec_scope = {**env}
        exec(compile(func_code, "<custom_action>", "exec"), exec_scope)
        coro = exec_scope["__run_custom_task"]()
        result = await asyncio.wait_for(coro, timeout=15.0)
        return str(result) if result is not None else "Custom action completed."
    except Exception as e:
        return f"Execution Error: {str(e)}"


def parse_action_params(params_raw: str) -> Dict[str, Any]:
    """
    Robustly extracts key=value arguments from action parameter string,
    safely handling multiline text, inner unescaped quotes, markdown, emojis,
    JSON format, and triple quotes.
    """
    kwargs = {}
    if not params_raw:
        return kwargs

    raw_str = params_raw.strip()

    # 1. First attempt: Standard AST Parse (for well-formed python expressions)
    import ast
    try:
        expr = f"func({raw_str})"
        parsed = ast.parse(expr, mode='eval')
        if isinstance(parsed.body, ast.Call):
            for kw in parsed.body.keywords:
                try:
                    kwargs[kw.arg] = ast.literal_eval(kw.value)
                except Exception:
                    kwargs[kw.arg] = ast.unparse(kw.value)
            if kwargs and all(v != "" for v in kwargs.values()):
                return kwargs
    except Exception:
        pass

    # 2. Second attempt: Direct JSON payload parsing if model formatted params as JSON
    if raw_str.startswith("{") and raw_str.endswith("}"):
        try:
            parsed_json = json.loads(raw_str)
            if isinstance(parsed_json, dict):
                return parsed_json
        except Exception:
            pass

    # 3. Third attempt: Intelligent Key-Value Scanner
    # Identifies parameter boundaries like channel=..., server_name=..., target_user=..., message_content=...
    known_keys = [
        "message_content", "channel", "server_name", "server", "target_user",
        "count", "seconds", "reason", "repeat_interval", "repeat_count",
        "stop_on_reply", "action", "memory_keyword", "code"
    ]
    
    # Find positions of all key= matches in the raw string
    key_pos = []
    for k in known_keys:
        for m in re.finditer(rf'(?:^|[\s,;])({k})\s*=\s*', raw_str, re.IGNORECASE):
            key_pos.append((m.start(1), m.end(), m.group(1).lower()))

    if key_pos:
        key_pos.sort(key=lambda x: x[0])
        for idx, (k_start, val_start, k_name) in enumerate(key_pos):
            if idx + 1 < len(key_pos):
                val_end = key_pos[idx + 1][0]
                val_raw = raw_str[val_start:val_end].strip().rstrip(',;').strip()
            else:
                val_raw = raw_str[val_start:].strip().rstrip(')').strip()

            # Clean outer quotes (triple or single/double quotes)
            if (val_raw.startswith('"""') and val_raw.endswith('"""')) or (val_raw.startswith("'''") and val_raw.endswith("'''")):
                val_clean = val_raw[3:-3]
            elif (val_raw.startswith('"') and val_raw.endswith('"')) or (val_raw.startswith("'") and val_raw.endswith("'")):
                val_clean = val_raw[1:-1]
            elif val_raw.startswith(('"', "'")):
                val_clean = val_raw[1:]
                if val_clean.endswith(('"', "'")):
                    val_clean = val_clean[:-1]
            else:
                val_clean = val_raw

            # Unescape newlines / escaped characters if present
            if "\\n" in val_clean:
                val_clean = val_clean.replace("\\n", "\n")
            if "\\t" in val_clean:
                val_clean = val_clean.replace("\\t", "\t")
            if '\\"' in val_clean:
                val_clean = val_clean.replace('\\"', '"')
            if "\\'" in val_clean:
                val_clean = val_clean.replace("\\'", "'")

            # Type conversions
            v_low = val_clean.lower().strip()
            if v_low == "true":
                kwargs[k_name] = True
            elif v_low == "false":
                kwargs[k_name] = False
            elif v_low.isdigit() and k_name in ["count", "seconds", "repeat_interval", "repeat_count"]:
                kwargs[k_name] = int(v_low)
            else:
                kwargs[k_name] = val_clean

        if kwargs:
            return kwargs

    # 4. Fourth attempt: General Regex Fallback
    pattern = r'([a-zA-Z0-9_]+)\s*=\s*(?:"""(.*?)"""|\'\'\'(.*?)\'\'\'|"((?:\\.|[^"\\])*)"|\'((?:\\.|[^\'\\])*)\'|([^\s,]+))'
    matches = re.finditer(pattern, raw_str, re.DOTALL)
    for m in matches:
        k = m.group(1).lower()
        v = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else (m.group(4) if m.group(4) is not None else (m.group(5) if m.group(5) is not None else m.group(6))))
        if v is None:
            v = ""
        if isinstance(v, str):
            v_low = v.lower().strip()
            if v_low == "true":
                v = True
            elif v_low == "false":
                v = False
            elif v_low.isdigit() and k in ["count", "seconds", "repeat_interval", "repeat_count"]:
                v = int(v_low)
        kwargs[k] = v

    return kwargs


class AgentEngine:
    @staticmethod
    def get_tool_schema_for_prompt() -> str:
        return ToolRegistry.get_prompt_schema()

    @staticmethod
    async def process_response(
        raw_response: str,
        context: Dict[str, Any]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Parses action tags from AI response, executes tools, and returns clean human text.
        """
        clean_text = raw_response
        executed_results = []

        # Strip any thinking tags or markdown reasoning blocks
        clean_text = re.sub(r'<think>.*?</think>', '', clean_text, flags=re.DOTALL).strip()
        clean_text = re.sub(r'<thought>.*?</thought>', '', clean_text, flags=re.DOTALL).strip()

        # Robust action pattern supporting optional whitespace, newlines, and brackets
        action_pattern = r'\[\s*ACTION:\s*([a-zA-Z0-9_]+)(?:\((.*?)\))?\s*\]'
        matches = re.findall(action_pattern, clean_text, re.DOTALL)

        for tool_name, params_raw in matches:
            kwargs = parse_action_params(params_raw.strip() if params_raw else "")
            exec_res = await execute_tool(tool_name.strip(), kwargs, context)
            executed_results.append({"tool": tool_name.strip(), "params": kwargs, "result": exec_res})

        # Strip all [ACTION: ...] tags including any surrounding markdown stars or extra whitespace
        clean_text = re.sub(r'\*?\*?\[\s*ACTION:\s*[a-zA-Z0-9_]+(?:\(.*?\))?\s*\]\*?\*?', '', clean_text, flags=re.DOTALL)
        clean_text = re.sub(r'\[(?:Nayumi\'s Reply to|Reply to|Nayumi to)[^\]]+\]:\s*', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'^\s*(?:\([^)]+\)|\*[^*]+\*)\s*', '', clean_text)

        # Strip internal analysis / reasoning bullet preambles from models
        lines = clean_text.splitlines()
        clean_lines = []
        in_analysis = True
        for l in lines:
            st = l.strip()
            if in_analysis:
                if st.startswith(("•", "o ")) or re.match(r'^(?:[A-Z0-9_\s]+\s*\([^)]+\)\.?|"[^"]+"\s*\([^)]+\)\.?|Analysis:|Intent:|Context:|Persona:|Speaker:|Draft \d+:|Constraint:)', st, re.IGNORECASE):
                    continue
                if not st:
                    continue
                in_analysis = False
            clean_lines.append(l)
        
        if clean_lines:
            clean_text = "\n".join(clean_lines).strip()

        # If any executed tool encountered an error or channel not found, append clear status to prevent hallucination
        for r in executed_results:
            res_data = r.get("result", {})
            if isinstance(res_data, dict) and not res_data.get("success", True):
                err_msg = res_data.get("error", "Action failed")
                clean_text += f"\n\n⚠️ *(Note: {err_msg})*"
            elif isinstance(res_data, dict) and isinstance(res_data.get("result"), str) and ("Could not find channel" in res_data.get("result") or "Permission Denied" in res_data.get("result") or "Failed to send" in res_data.get("result")):
                warn_msg = res_data.get("result")
                clean_text += f"\n\n⚠️ *{warn_msg}*"

        return clean_text.strip(), executed_results

