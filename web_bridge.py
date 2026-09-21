"""
Nayumi Web Gateway Bridge
Runs exclusively on Render (or public web server).
Relays payment webhooks from SS Empire Gateway to Nayumi Discord Bot running on external hosting.
"""

import os
import sys
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Set, Dict, Any, List

for _s in [sys.stdout, sys.stderr]:
    if _s and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from aiohttp import web, WSMsgType

# Configuration
PORT = int(os.environ.get("PORT", 10000))
BRIDGE_SECRET = os.environ.get("BRIDGE_SECRET", "nayumi_secret_bridge_2026")
GATEWAY_URL = os.environ.get("GATEWAY_URL", "https://ss-empire-gateway.onrender.com").rstrip("/")

# State
connected_bots: Set[web.WebSocketResponse] = set()
events_queue: List[Dict[str, Any]] = []
MAX_EVENTS_HISTORY = 100

bot_state = {
    "connected": False,
    "bot_user": "Unknown",
    "guilds": 0,
    "last_heartbeat": 0,
    "ping_ms": 0,
    "hosting_info": "External Hosting"
}

stats = {
    "started_at": time.time(),
    "total_webhooks": 0,
    "total_pushed_realtime": 0,
    "total_polled": 0,
    "last_payment": None
}

routes = web.RouteTableDef()


def verify_auth(request: web.Request) -> bool:
    token = request.headers.get("X-Bridge-Secret") or request.query.get("token")
    if not BRIDGE_SECRET:
        return True
    return token == BRIDGE_SECRET


@routes.get("/")
@routes.get("/health")
async def index_dashboard(request: web.Request):
    now = time.time()
    uptime_sec = int(now - stats["started_at"])
    uptime_str = f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m {uptime_sec % 60}s"

    # Bot connection status
    is_bot_online = len(connected_bots) > 0 or (now - bot_state["last_heartbeat"] < 90)
    bot_badge_color = "#00E676" if is_bot_online else "#FF5252"
    bot_badge_text = "CONNECTED & ACTIVE" if is_bot_online else "WAITING FOR BOT"

    last_hb_str = (
        f"{int(now - bot_state['last_heartbeat'])}s ago"
        if bot_state["last_heartbeat"] > 0
        else "Never"
    )

    last_pay = stats.get("last_payment")
    last_pay_html = ""
    if last_pay:
        last_pay_html = f"""
        <div class="card stat-card glow-card" style="margin-top: 20px;">
            <div class="card-title" style="font-size: 14px; font-weight: 600; color: #8E9AB0; margin-bottom: 8px;">💳 Latest Verified Transaction</div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                <span style="font-size: 24px; font-weight: 700; color: #00E676;">₹{last_pay.get('amount', '0')}</span>
                <span class="badge" style="background: rgba(0, 230, 118, 0.2); color: #00E676;">VERIFIED</span>
            </div>
            <div style="font-size: 13px; color: #9E9E9E; margin-top: 8px; line-height: 1.6;">
                Customer: <strong style="color: #ECEFF1;">{last_pay.get('customer_name', 'N/A')}</strong><br>
                Bank UTR: <code style="color: #80D8FF;">{last_pay.get('utr', 'N/A')}</code><br>
                Order ID: <code style="color: #FFD54F;">{last_pay.get('order_id', 'N/A')}</code>
            </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nayumi • Web Gateway Bridge</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #080A10;
            --card-bg: rgba(18, 22, 34, 0.75);
            --card-border: rgba(255, 255, 255, 0.08);
            --accent-pink: #FF3385;
            --accent-cyan: #00E5FF;
            --accent-green: #00E676;
            --accent-amber: #FFB300;
            --text-main: #FFFFFF;
            --text-muted: #8E9AB0;
        }}
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Outfit', sans-serif;
        }}
        body {{
            background: var(--bg-color);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 24px;
            background-image: 
                radial-gradient(circle at 15% 20%, rgba(255, 51, 133, 0.12) 0%, transparent 45%),
                radial-gradient(circle at 85% 80%, rgba(0, 229, 255, 0.12) 0%, transparent 45%),
                linear-gradient(180deg, #07090F 0%, #0D111A 100%);
        }}
        .container {{
            width: 100%;
            max-width: 820px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 28px;
        }}
        .header h1 {{
            font-size: 32px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #FFF 30%, #FF3385 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: inline-flex;
            align-items: center;
            gap: 12px;
        }}
        .header p {{
            color: var(--text-muted);
            margin-top: 8px;
            font-size: 15px;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 22px;
            backdrop-filter: blur(16px);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}
        .card:hover {{
            border-color: rgba(255, 51, 133, 0.3);
            transform: translateY(-2px);
        }}
        .card-label {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
            margin-bottom: 8px;
        }}
        .card-val {{
            font-size: 22px;
            font-weight: 700;
            color: var(--text-main);
        }}
        .card-sub {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 6px;
        }}
        .mono {{
            font-family: 'JetBrains Mono', monospace;
        }}
        .footer {{
            margin-top: 32px;
            text-align: center;
            font-size: 13px;
            color: var(--text-muted);
        }}
        .pulse-dot {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: {bot_badge_color};
            margin-right: 6px;
            box-shadow: 0 0 10px {bot_badge_color};
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.4; transform: scale(0.8); }}
            100% {{ opacity: 1; transform: scale(1); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎀 Nayumi Web Gateway Bridge</h1>
            <p>Cloud Relay & Webhook Engine connecting SS Empire Gateway to Nayumi Discord Bot</p>
        </div>

        <div class="grid">
            <div class="card">
                <div class="card-label">Discord Bot Connection</div>
                <div class="card-val" style="display: flex; align-items: center; font-size: 18px; color: {bot_badge_color};">
                    <span class="pulse-dot"></span> {bot_badge_text}
                </div>
                <div class="card-sub">
                    Target: <strong style="color: #FFF;">{bot_state.get('bot_user', 'Nayumi')}</strong> ({bot_state.get('hosting_info', 'External VPS')})<br>
                    Heartbeat: {last_hb_str}
                </div>
            </div>

            <div class="card">
                <div class="card-label">Render Cloud Bridge</div>
                <div class="card-val" style="color: var(--accent-cyan);">ONLINE 24/7</div>
                <div class="card-sub">
                    Uptime: <span class="mono">{uptime_str}</span><br>
                    Port: <span class="mono">{PORT}</span>
                </div>
            </div>

            <div class="card">
                <div class="card-label">Gateway Webhook Relay</div>
                <div class="card-val" style="color: var(--accent-pink);">{stats['total_webhooks']}</div>
                <div class="card-sub">
                    Realtime Pushed: <span style="color: #00E676;">{stats['total_pushed_realtime']}</span><br>
                    Queue Buffer: {len(events_queue)} pending
                </div>
            </div>
        </div>

        {last_pay_html}

        <div class="card" style="margin-top: 16px;">
            <div class="card-label">Active Endpoints</div>
            <div style="font-size: 13px; color: var(--text-muted); line-height: 1.8; margin-top: 4px;">
                • <code class="mono" style="color: #80D8FF;">POST /api/payment-webhook</code> - Gateway Webhook Receiver (SS Empire UPI)<br>
                • <code class="mono" style="color: #80D8FF;">GET /ws/bot</code> - Realtime WebSocket Bridge for Hosting Bot<br>
                • <code class="mono" style="color: #80D8FF;">GET /api/bot/events</code> - HTTP Polling Fallback<br>
                • <code class="mono" style="color: #80D8FF;">GET /health</code> - Keep-Alive & Status Monitor
            </div>
        </div>

        <div class="footer">
            Nayumi Cloud Bridge • Dedicated Web Service for Render • Bot runs on external hosting
        </div>
    </div>
</body>
</html>
"""
    return web.Response(text=html, content_type="text/html")


@routes.get("/status")
async def json_status(request: web.Request):
    now = time.time()
    is_bot_online = len(connected_bots) > 0 or (now - bot_state["last_heartbeat"] < 90)
    return web.json_response({
        "status": "online",
        "service": "nayumi-web-gateway-bridge",
        "bot_connected": is_bot_online,
        "connected_bot_sockets": len(connected_bots),
        "bot_user": bot_state["bot_user"],
        "bot_guilds": bot_state["guilds"],
        "last_heartbeat_sec_ago": int(now - bot_state["last_heartbeat"]) if bot_state["last_heartbeat"] else None,
        "pending_events_count": len(events_queue),
        "total_webhooks": stats["total_webhooks"],
        "total_pushed_realtime": stats["total_pushed_realtime"],
        "uptime_seconds": int(now - stats["started_at"])
    })


@routes.post("/payment-webhook")
@routes.post("/api/payment-webhook")
async def handle_payment_webhook(request: web.Request):
    """
    Receives payment webhooks from SS Empire Gateway.
    Broadcasts to connected Discord Bot via WebSocket or queues for polling.
    """
    try:
        content_type = request.content_type
        if "application/json" in content_type:
            data = await request.json()
        elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            post_data = await request.post()
            data = dict(post_data)
        else:
            raw_body = await request.text()
            try:
                data = json.loads(raw_body)
            except Exception:
                data = {}

        order_id = str(data.get("order_id") or data.get("orderId") or "N/A")
        amount = str(data.get("amount") or "0")
        utr = str(data.get("utr") or data.get("bank_utr") or "Verified")
        customer_name = str(data.get("customer_name") or data.get("customer") or "Customer")
        remark = str(data.get("remark") or "")

        event_id = str(uuid.uuid4())[:8]
        event = {
            "event_id": event_id,
            "type": "payment_webhook",
            "timestamp": time.time(),
            "iso_time": datetime.now(timezone.utc).isoformat(),
            "data": {
                "order_id": order_id,
                "amount": amount,
                "utr": utr,
                "customer_name": customer_name,
                "remark": remark
            },
            "acked": False
        }

        # Store in queue
        events_queue.append(event)
        if len(events_queue) > MAX_EVENTS_HISTORY:
            events_queue.pop(0)

        # Update stats
        stats["total_webhooks"] += 1
        stats["last_payment"] = event["data"]

        # Push to all connected WebSocket bot instances
        pushed_count = 0
        dead_sockets = []
        payload_str = json.dumps(event)

        for ws in connected_bots:
            try:
                await ws.send_str(payload_str)
                pushed_count += 1
            except Exception as e:
                print(f"[Bridge WS Send Error] {e}")
                dead_sockets.append(ws)

        for ws in dead_sockets:
            connected_bots.discard(ws)

        if pushed_count > 0:
            stats["total_pushed_realtime"] += pushed_count
            print(f"[Bridge] Realtime pushed payment event {event_id} (Rs.{amount}, Order: {order_id}) to {pushed_count} bot socket(s).", flush=True)
        else:
            print(f"[Bridge] Queued payment event {event_id} (Rs.{amount}, Order: {order_id}) for bot polling.", flush=True)

        return web.json_response({
            "success": True,
            "event_id": event_id,
            "status": "delivered_realtime" if pushed_count > 0 else "queued_for_bot",
            "active_bot_listeners": len(connected_bots)
        })

    except Exception as exc:
        print(f"[Bridge Webhook Error] {exc}")
        return web.json_response({"success": False, "error": str(exc)}, status=400)


@routes.get("/ws/bot")
async def bot_websocket_handler(request: web.Request):
    """
    WebSocket connection for the Nayumi Discord bot running on external hosting.
    """
    if not verify_auth(request):
        return web.Response(status=401, text="Unauthorized: Invalid bridge secret.")

    ws = web.WebSocketResponse(heartbeat=30.0)
    await ws.prepare(request)

    connected_bots.add(ws)
    bot_state["connected"] = True
    bot_state["last_heartbeat"] = time.time()
    print(f"[Bridge] Bot connected via WebSocket from {request.remote}. Active connections: {len(connected_bots)}")

    # Send welcome handshake + pending un-ACKed events
    unacked = [e for e in events_queue if not e.get("acked")]
    welcome_payload = {
        "type": "handshake_ack",
        "message": "Connected to Nayumi Web Gateway Bridge",
        "server_time": time.time(),
        "pending_events_count": len(unacked)
    }
    await ws.send_str(json.dumps(welcome_payload))

    # Send un-ACKed events if any
    for evt in unacked[-10:]:
        try:
            await ws.send_str(json.dumps(evt))
        except Exception:
            break

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    payload = json.loads(msg.data)
                    msg_type = payload.get("type")

                    if msg_type == "heartbeat":
                        bot_state["last_heartbeat"] = time.time()
                        bot_state["bot_user"] = payload.get("bot_user", bot_state["bot_user"])
                        bot_state["guilds"] = payload.get("guilds", bot_state["guilds"])
                        bot_state["ping_ms"] = payload.get("ping_ms", 0)
                        bot_state["hosting_info"] = payload.get("hosting_info", bot_state["hosting_info"])
                        await ws.send_str(json.dumps({
                            "type": "heartbeat_ack",
                            "time": time.time()
                        }))

                    elif msg_type == "ack":
                        acked_id = payload.get("event_id")
                        for e in events_queue:
                            if e.get("event_id") == acked_id:
                                e["acked"] = True
                                break

                except Exception as err:
                    print(f"[Bridge WS Message Error] {err}")

            elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                break

    finally:
        connected_bots.discard(ws)
        bot_state["connected"] = len(connected_bots) > 0
        print(f"[Bridge] Bot disconnected. Active connections: {len(connected_bots)}")

    return ws


@routes.get("/api/bot/events")
async def bot_get_events(request: web.Request):
    """
    HTTP polling fallback for the bot.
    """
    if not verify_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    stats["total_polled"] += 1
    bot_state["last_heartbeat"] = time.time()

    after_id = request.query.get("after")
    only_unacked = request.query.get("unacked", "1") == "1"

    results = []
    found_after = (after_id is None)

    for ev in events_queue:
        if not found_after:
            if ev.get("event_id") == after_id:
                found_after = True
            continue

        if only_unacked and ev.get("acked"):
            continue

        results.append(ev)

    return web.json_response({
        "success": True,
        "events": results,
        "server_time": time.time()
    })


@routes.post("/api/bot/ack")
async def bot_ack_event(request: web.Request):
    """
    Bot acknowledges event receipt.
    """
    if not verify_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        data = await request.json()
        event_id = data.get("event_id")
        for e in events_queue:
            if e.get("event_id") == event_id:
                e["acked"] = True
                return web.json_response({"success": True, "event_id": event_id})
        return web.json_response({"success": False, "message": "Event not found"}, status=404)
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=400)


@routes.post("/api/bot/heartbeat")
async def bot_post_heartbeat(request: web.Request):
    """
    HTTP heartbeat fallback.
    """
    if not verify_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        data = await request.json()
        bot_state["last_heartbeat"] = time.time()
        bot_state["bot_user"] = data.get("bot_user", bot_state["bot_user"])
        bot_state["guilds"] = data.get("guilds", bot_state["guilds"])
        bot_state["ping_ms"] = data.get("ping_ms", 0)
        bot_state["hosting_info"] = data.get("hosting_info", bot_state["hosting_info"])
        return web.json_response({"success": True, "server_time": time.time()})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=400)


def create_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    return app


if __name__ == "__main__":
    print(f"==================================================", flush=True)
    print(f"   NAYUMI WEB GATEWAY BRIDGE (Render Relay)      ", flush=True)
    print(f"==================================================", flush=True)
    print(f"Starting aiohttp web server on port {PORT}...", flush=True)
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=PORT)
