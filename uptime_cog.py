import asyncio
import os
import json
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple

import aiohttp
import discord
from discord.ext import commands, tasks

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "uptime_config.json")

# Custom server emojis for luxury aesthetic
E_BLACKCROWN = "<a:blackcrown:1543148226100600922>"
E_TICK = "<:tick:1543148221264826418>"
E_CROSS = "<:cross:1543148199273828432>"
E_PING = "<:ping:1543148205284524073>"
E_FIRE = "<:fire:1543148203526856704>"
E_ARROW = "<a:arrow:1543148228558721024>"
E_DIAMOND = "<a:diamond:1545473841315319891>"
E_WARNING = "<:warning:1543148211328520242>"
E_GEAR = "<a:gear:1543148201547268156>"


def load_config() -> Dict[str, Any]:
    default_config = {
        "enabled": True,
        "interval_seconds": 90,
        "alert_channel_id": None,
        "render_api_key": "rnd_7u6NIqx09YMLAsPp88fL3QO16wIX",
        "mention_users": [913264406912188456, 1438763359322247249, 1459031472576008306],
        "ping_everyone_on_down": True,
        "auto_restart_enabled": True,
        "timeout_seconds": 10,
        "targets": []
    }
    if not os.path.exists(CONFIG_PATH):
        return default_config
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_config


def save_config(cfg: Dict[str, Any]) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[Uptime Cog] Failed to save config: {e}")


class UptimeRefreshView(discord.ui.View):
    def __init__(self, cog: "UptimeCog"):
        super().__init__(timeout=180)
        self.cog = cog

    @discord.ui.button(label="Refresh Now", style=discord.ButtonStyle.success, emoji="🔄")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.check_all_targets()
        embed = self.cog.build_status_embed(author=interaction.user)
        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except Exception:
            pass


class UptimeCog(commands.Cog, name="Uptime"):
    """24/7 Render Keep-Alive Pinger, Auto-Restart Watchdog & Real-time Uptime Monitoring."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = load_config()
        self.session: Optional[aiohttp.ClientSession] = None
        self.telemetry: Dict[str, Dict[str, Any]] = {}
        self.total_pings = 0
        self.last_loop_time: Optional[float] = None
        self._restart_cooldowns: Dict[str, float] = {}
        self._init_telemetry()
        interval = max(30, self.config.get("interval_seconds", 90))
        self.keepalive_task.change_interval(seconds=interval)
        self.keepalive_task.start()

    def _init_telemetry(self):
        for target in self.config.get("targets", []):
            tid = target["id"]
            if tid not in self.telemetry:
                self.telemetry[tid] = {
                    "status": "pending",
                    "http_code": None,
                    "latency_ms": None,
                    "last_checked": None,
                    "consecutive_fails": 0,
                    "total_checks": 0,
                    "success_checks": 0,
                    "error_msg": None
                }

    async def cog_unload(self):
        self.keepalive_task.cancel()
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.get("timeout_seconds", 10))
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NayumiKeepAlive/3.0"},
                timeout=timeout
            )
        return self.session

    def get_mention_string(self, is_down: bool = True) -> str:
        """Returns the mention string for Bunny, Suyash, and Admin/Everyone."""
        uids = self.config.get("mention_users", [913264406912188456, 1438763359322247249, 1459031472576008306])
        mentions = " ".join([f"<@{uid}>" for uid in uids])
        if is_down and self.config.get("ping_everyone_on_down", True):
            mentions += " @everyone"
        return mentions

    async def auto_restart_render_service(self, service_id: str, service_name: str) -> Tuple[bool, str]:
        """Automatically resumes and restarts a Render service via REST API."""
        api_key = self.config.get("render_api_key")
        if not api_key or not service_id:
            return False, "Render API Key or Service ID not configured"

        now = time.time()
        cooldown = self._restart_cooldowns.get(service_id, 0)
        if (now - cooldown) < 180:
            remaining = round(180 - (now - cooldown))
            return False, f"Cooldown active (re-triggerable in {remaining}s)"

        self._restart_cooldowns[service_id] = now
        session = await self.get_session()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # 1. Resume service if suspended
        try:
            async with session.post(f"https://api.render.com/v1/services/{service_id}/resume", headers=headers, json={}) as resp:
                print(f"[Render Watchdog] Resume call for {service_name}: HTTP {resp.status}", flush=True)
        except Exception as e:
            print(f"[Render Watchdog Resume Error] {e}", flush=True)

        # 2. Trigger instant restart
        try:
            async with session.post(f"https://api.render.com/v1/services/{service_id}/restart", headers=headers, json={}) as resp:
                print(f"[Render Watchdog] Restart call for {service_name}: HTTP {resp.status}", flush=True)
                if resp.status in [200, 201, 202]:
                    return True, "Auto-Restart triggered successfully on Render"
                else:
                    text = await resp.text()
                    return False, f"Render API returned HTTP {resp.status}: {text[:80]}"
        except Exception as e:
            print(f"[Render Watchdog Restart Error] {e}", flush=True)
            return False, f"Error calling Render API: {e}"

    async def ping_single_target(self, target: Dict[str, Any]) -> Dict[str, Any]:
        session = await self.get_session()
        tid = target["id"]
        url = target["url"]
        t_start = time.time()

        old_state = self.telemetry.get(tid, {}).get("status", "unknown")

        try:
            async with session.get(url, allow_redirects=True) as resp:
                latency = round((time.time() - t_start) * 1000)
                status_code = resp.status
                is_ok = (200 <= status_code < 400) or status_code in [401, 403, 405]
                new_status = "online" if is_ok else "offline"
                if is_ok and latency > 3000:
                    new_status = "slow"

                telem = self.telemetry.setdefault(tid, {})
                telem["status"] = new_status
                telem["http_code"] = status_code
                telem["latency_ms"] = latency
                telem["last_checked"] = datetime.now(timezone.utc)
                telem["total_checks"] = telem.get("total_checks", 0) + 1

                if is_ok:
                    telem["success_checks"] = telem.get("success_checks", 0) + 1
                    telem["consecutive_fails"] = 0
                    telem["error_msg"] = None
                else:
                    telem["consecutive_fails"] = telem.get("consecutive_fails", 0) + 1
                    telem["error_msg"] = f"HTTP Status {status_code}"

                # State change detection
                if old_state == "offline" and new_status in ["online", "slow"]:
                    await self._notify_recovery(target, latency, status_code)
                elif old_state in ["online", "slow"] and new_status == "offline":
                    await self._notify_downtime(target, f"HTTP Status {status_code}")

                return telem

        except asyncio.TimeoutError:
            latency = round((time.time() - t_start) * 1000)
            telem = self.telemetry.setdefault(tid, {})
            telem["status"] = "offline"
            telem["http_code"] = 504
            telem["latency_ms"] = latency
            telem["last_checked"] = datetime.now(timezone.utc)
            telem["total_checks"] = telem.get("total_checks", 0) + 1
            telem["consecutive_fails"] = telem.get("consecutive_fails", 0) + 1
            telem["error_msg"] = "Connection Timed Out"

            if old_state in ["online", "slow"]:
                await self._notify_downtime(target, "Request Timed Out (10s)")

            return telem

        except Exception as e:
            latency = round((time.time() - t_start) * 1000)
            err_str = str(e) or "Network Connection Error"
            telem = self.telemetry.setdefault(tid, {})
            telem["status"] = "offline"
            telem["http_code"] = 503
            telem["latency_ms"] = latency
            telem["last_checked"] = datetime.now(timezone.utc)
            telem["total_checks"] = telem.get("total_checks", 0) + 1
            telem["consecutive_fails"] = telem.get("consecutive_fails", 0) + 1
            telem["error_msg"] = err_str[:80]

            if old_state in ["online", "slow"]:
                await self._notify_downtime(target, err_str[:80])

            return telem

    async def check_all_targets(self):
        targets = self.config.get("targets", [])
        if not targets:
            return
        tasks_list = [self.ping_single_target(t) for t in targets]
        await asyncio.gather(*tasks_list, return_exceptions=True)
        self.total_pings += len(targets)
        self.last_loop_time = time.time()

    @tasks.loop(seconds=90)
    async def keepalive_task(self):
        if not self.config.get("enabled", True):
            return
        try:
            await self.check_all_targets()
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] [Nayumi Keep-Alive] Pinged {len(self.config.get('targets', []))} Render endpoints. All hot & awake.", flush=True)
        except Exception as e:
            print(f"[Nayumi Keep-Alive Error] {e}", flush=True)

    @keepalive_task.before_loop
    async def before_keepalive(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(2)
        await self.check_all_targets()

    async def _notify_downtime(self, target: Dict[str, Any], reason: str):
        """Dispatches emergency outage alert, mentions Bunny & Suyash, and auto-restarts Render!"""
        service_id = target.get("service_id")
        restarted = False
        restart_msg = "Auto-Restart disabled"

        if self.config.get("auto_restart_enabled", True) and service_id:
            restarted, restart_msg = await self.auto_restart_render_service(service_id, target["name"])

        mentions = self.get_mention_string(is_down=True)
        embed = discord.Embed(
            title=f"{E_WARNING} ⚠️ EMERGENCY: HOSTING DOWN DETECTED!",
            description=(
                f"### {E_BLACKCROWN} **SERVICE OUTAGE REPORT**\n\n"
                f"{E_ARROW} **Hosting Name:** `{target['name']}`\n"
                f"{E_ARROW} **Target URL:** {target['url']}\n"
                f"{E_ARROW} **Failure Cause:** `{reason}`\n"
                f"{E_ARROW} **Status:** 🔴 **UNREACHABLE / OFF**\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{E_FIRE} **Auto-Healer Watchdog:**\n"
                f"{E_ARROW} **Render Action:** `{'⚡ Restart Triggered' if restarted else '⚠️ Attempted'}`\n"
                f"{E_ARROW} **Details:** `{restart_msg}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{E_PING} **Notified:** Bunny & Suyash"
            ),
            color=0xFF3366,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name="NAYUMI WATCHDOG • AUTO-HEAL SYSTEM", icon_url="https://ss-empire-gateway.onrender.com/logo.png")
        embed.set_footer(text="Nayumi 24/7 Watchdog • Auto-Recovery in progress...", icon_url="https://ss-empire-gateway.onrender.com/logo.png")

        # 1. Send to configured Alert Channel
        channel_id = self.config.get("alert_channel_id")
        if channel_id:
            try:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(content=f"🚨 {mentions} **HOSTING DOWN! AUTO-RESTART EXECUTED!**", embed=embed)
            except Exception as e:
                print(f"[Alert Channel Error] {e}")

        # 2. Direct DM to Bunny & Suyash for instant mobile notifications
        for uid in self.config.get("mention_users", []):
            try:
                user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
                if user:
                    await user.send(content=f"🚨 **[URGENT] {target['name']} is DOWN! Nayumi auto-restarted the hosting.**", embed=embed)
            except Exception:
                pass

    async def _notify_recovery(self, target: Dict[str, Any], latency: int, status_code: int):
        """Notifies Bunny & Suyash when a service comes back online."""
        mentions = self.get_mention_string(is_down=False)
        embed = discord.Embed(
            title=f"{E_TICK} ✅ HOSTING RESTORED & BACK ONLINE!",
            description=(
                f"### {E_BLACKCROWN} **SERVICE RESTORATION REPORT**\n\n"
                f"{E_ARROW} **Hosting Name:** `{target['name']}`\n"
                f"{E_ARROW} **Target URL:** {target['url']}\n"
                f"{E_ARROW} **Current Status:** 🟢 **ONLINE (HTTP {status_code})**\n"
                f"{E_ARROW} **Response Time:** `{latency}ms`\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{E_TICK} **All systems operational. The hosting reboot was successful.**"
            ),
            color=0x00E676,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name="NAYUMI WATCHDOG • AUTO-HEAL SYSTEM", icon_url="https://ss-empire-gateway.onrender.com/logo.png")
        embed.set_footer(text="Nayumi 24/7 Watchdog • System Healthy", icon_url="https://ss-empire-gateway.onrender.com/logo.png")

        channel_id = self.config.get("alert_channel_id")
        if channel_id:
            try:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(content=f"✅ {mentions} **Hosting is back ONLINE!**", embed=embed)
            except Exception as e:
                print(f"[Alert Channel Error] {e}")

        for uid in self.config.get("mention_users", []):
            try:
                user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
                if user:
                    await user.send(content=f"✅ **[RESTORED] {target['name']} is back online!**", embed=embed)
            except Exception:
                pass

    def build_status_embed(self, author: Optional[discord.User] = None) -> discord.Embed:
        targets = self.config.get("targets", [])
        all_online = True
        any_offline = False

        card_lines = []
        for t in targets:
            tid = t["id"]
            name = t["name"]
            url = t["url"]
            telem = self.telemetry.get(tid, {})
            st = telem.get("status", "pending")
            lat = telem.get("latency_ms")
            code = telem.get("http_code")
            total = telem.get("total_checks", 0)
            success = telem.get("success_checks", 0)
            pct = round((success / total * 100), 1) if total > 0 else 100.0

            if st == "online":
                status_icon = "🟢 `ONLINE`"
                code_str = f"HTTP {code}" if code else "200 OK"
                lat_str = f"`{lat}ms`" if lat is not None else "`--ms`"
            elif st == "slow":
                status_icon = "🟡 `DEGRADED`"
                code_str = f"HTTP {code}" if code else "Slow"
                lat_str = f"`{lat}ms`" if lat is not None else "`--ms`"
                all_online = False
            elif st == "offline":
                status_icon = "🔴 `OFFLINE`"
                err = telem.get("error_msg", "Error")
                code_str = f"Err: {err}"
                lat_str = "`Timeout`"
                all_online = False
                any_offline = True
            else:
                status_icon = "⚪ `CHECKING`"
                code_str = "Pending"
                lat_str = "`--`"

            card_lines.append(
                f"{E_DIAMOND} **{name}**\n"
                f"   {E_ARROW} Status: {status_icon} • {code_str}\n"
                f"   {E_ARROW} Latency: {lat_str} • Uptime: `{pct}%`\n"
                f"   {E_ARROW} Link: [Open Endpoint]({url})"
            )

        color = 0x00E676 if all_online else (0xFF3366 if any_offline else 0xFFB300)
        overall_text = "🟢 **All Systems Operational (Auto-Restart Watchdog Active)**" if all_online else ("🔴 **One or More Services Offline!**" if any_offline else "🟡 **Performance Degraded**")

        desc = (
            f"### {E_BLACKCROWN} **RENDER 24/7 UPTIME & AUTO-HEAL MONITOR**\n\n"
            f"> {overall_text}\n"
            f"> Nayumi Bot automatically pings each target every **90 seconds**. If any service goes down, Nayumi **immediately triggers an API Auto-Restart** and alerts Bunny & Suyash!\n\n"
            + "\n\n".join(card_lines)
            + f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{E_PING} **Bot Ping:** `{round(self.bot.latency * 1000)}ms` | {E_FIRE} **Total Pings Sent:** `{self.total_pings}`"
        )

        embed = discord.Embed(
            description=desc,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(
            name="NAYUMI WATCHDOG • 24/7 MONITORING",
            icon_url="https://ss-empire-gateway.onrender.com/logo.png",
            url="https://ss-empire-gateway.onrender.com"
        )
        embed.set_thumbnail(url=author.display_avatar.url if (author and hasattr(author, "display_avatar") and author.display_avatar) else "https://ss-empire-gateway.onrender.com/logo.png")
        embed.set_footer(
            text="SS Empire Watchdog • Auto-Heal & Mentions Enabled • Click 'Refresh Now' for live ping",
            icon_url="https://ss-empire-gateway.onrender.com/logo.png"
        )
        return embed

    @commands.command(name="webstatus", aliases=["webuptime", "renderstatus", "statusweb", "keepalive", "pingweb", "websites"])
    async def webstatus_cmd(self, ctx: commands.Context):
        """Displays live 24/7 Uptime status & latency for all Render websites."""
        async with ctx.typing():
            if not self.last_loop_time or (time.time() - self.last_loop_time) > 45:
                await self.check_all_targets()

            embed = self.build_status_embed(author=ctx.author)
            view = UptimeRefreshView(cog=self)
            await ctx.send(embed=embed, view=view)

    @commands.command(name="pingnow", aliases=["checknow", "forceping"])
    @commands.has_permissions(administrator=True)
    async def pingnow_cmd(self, ctx: commands.Context):
        """Forces an immediate check and keep-alive ping for all endpoints."""
        msg = await ctx.send(f"{E_GEAR} Pinging all Render endpoints now...")
        t0 = time.time()
        await self.check_all_targets()
        dur = round((time.time() - t0) * 1000)
        embed = self.build_status_embed(author=ctx.author)
        view = UptimeRefreshView(cog=self)
        await msg.edit(content=f"{E_TICK} Ping completed in `{dur}ms`!", embed=embed, view=view)

    @commands.command(name="restartrender", aliases=["rebootweb", "renderrestart"])
    @commands.has_permissions(administrator=True)
    async def restart_render_cmd(self, ctx: commands.Context, target_name: Optional[str] = None):
        """Manually triggers a Render API restart for any configured website."""
        targets = self.config.get("targets", [])
        matched = None
        if target_name:
            for t in targets:
                if target_name.lower() in t["name"].lower() or target_name.lower() in t["id"].lower():
                    matched = t
                    break
        else:
            # Default to first target (SS Empire Gateway)
            matched = targets[0] if targets else None

        if not matched:
            await ctx.send(f"{E_CROSS} No matching website found. Options: " + ", ".join([f"`{t['id']}`" for t in targets]))
            return

        sid = matched.get("service_id")
        if not sid:
            await ctx.send(f"{E_CROSS} Service ID not configured for `{matched['name']}`.")
            return

        msg = await ctx.send(f"{E_GEAR} Requesting Render API to restart `{matched['name']}`...")
        # Clear cooldown for manual trigger
        self._restart_cooldowns.pop(sid, None)
        ok, res_text = await self.auto_restart_render_service(sid, matched["name"])
        if ok:
            await msg.edit(content=f"{E_TICK} **Render Restart Triggered Successfully!**\n{E_ARROW} Service: `{matched['name']}`\n{E_ARROW} Render is rebooting the container now. It will be back in 20-30s.")
        else:
            await msg.edit(content=f"{E_CROSS} **Restart Failed!**\n{E_ARROW} Reason: `{res_text}`")

    @commands.command(name="setuptimechannel")
    @commands.has_permissions(administrator=True)
    async def set_uptime_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Sets the Discord channel where website DOWN / RESTORED alerts will be posted."""
        target_ch = channel or ctx.channel
        self.config["alert_channel_id"] = target_ch.id
        save_config(self.config)
        embed = discord.Embed(
            title=f"{E_TICK} Uptime Alert Channel Configured",
            description=(
                f"{E_ARROW} All website downtime, auto-restart triggers, and recovery notifications will now be sent to {target_ch.mention}.\n"
                f"{E_ARROW} **Mentions:** Bunny & Suyash + @everyone."
            ),
            color=0x00E676
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(UptimeCog(bot))
