from __future__ import annotations

import os
import json
import threading
import time
from collections import deque

from fastapi.responses import HTMLResponse


class DashboardStore:
    def __init__(self, server: str) -> None:
        self.server = server
        self.started_at = time.time()
        self.routes: dict[tuple[str, str], dict] = {}
        self.blocks = deque(maxlen=25)
        self.total_blocks = 0
        self._lock = threading.Lock()

    def record(self, event: dict) -> None:
        with self._lock:
            if event.get("type") == "loop_blocked":
                self.total_blocks += 1
                self.blocks.appendleft({
                    "blocked_ms": event.get("blocked_ms", 0),
                    "timestamp": event.get("timestamp", time.time()),
                    "affected_requests": event.get("affected_requests", []),
                })
                affected = {
                    (request.get("method"), request.get("path"))
                    for request in event.get("affected_requests", [])
                    if request.get("method") and request.get("path")
                }
                for key in affected:
                    route = self._route(*key)
                    route["blocks"] += 1
                    route["worst_block_ms"] = max(
                        route["worst_block_ms"], event.get("blocked_ms", 0)
                    )
                return

            method = event.get("method")
            path = event.get("path")
            if not method or not path:
                return
            route = self._route(method, path)
            latency = event.get("latency_ms", 0)
            route["requests"] += 1
            route["failures"] += int(event.get("status", 500) >= 400)
            route["total_latency_ms"] += latency
            route["last_latency_ms"] = latency
            route["max_latency_ms"] = max(route["max_latency_ms"], latency)
            route["status"] = event.get("status", 500)
            route["last_called"] = event.get("last_called", time.time())
            route["lifecycle"] = event.get("lifecycle")

    def _route(self, method: str, path: str) -> dict:
        key = (method, path)
        if key not in self.routes:
            self.routes[key] = {
                "method": method,
                "path": path,
                "requests": 0,
                "failures": 0,
                "total_latency_ms": 0,
                "last_latency_ms": 0,
                "max_latency_ms": 0,
                "status": 200,
                "last_called": 0,
                "blocks": 0,
                "worst_block_ms": 0,
                "lifecycle": None,
            }
        return self.routes[key]

    def snapshot(self) -> dict:
        with self._lock:
            routes = []
            for route in self.routes.values():
                item = dict(route)
                count = item["requests"]
                item["avg_latency_ms"] = (
                    item.pop("total_latency_ms") / count if count else 0
                )
                routes.append(item)
            routes.sort(key=lambda item: (item["path"], item["method"]))
            return {
                "server": self.server,
                "pid": os.getpid(),
                "uptime_seconds": time.time() - self.started_at,
                "generated_at": time.time(),
                "routes": routes,
                "blocks": list(self.blocks),
                "totals": {
                    "requests": sum(route["requests"] for route in routes),
                    "failures": sum(route["failures"] for route in routes),
                    "blocks": self.total_blocks,
                },
            }


def install_dashboard(app, store: DashboardStore, path: str) -> None:
    path = "/" + path.strip("/")
    api_path = f"{path}/api/stats"

    existing = {getattr(route, "path", None) for route in app.routes}
    conflict = existing.intersection({path, api_path})
    if conflict:
        raise ValueError(f"Calf dashboard route already exists: {sorted(conflict)[0]}")

    @app.get(path, include_in_schema=False, response_class=HTMLResponse)
    async def calf_dashboard():
        return HTMLResponse(
            DASHBOARD_HTML.replace("__STATS_URL__", json.dumps(api_path))
        )

    @app.get(api_path, include_in_schema=False)
    async def calf_dashboard_stats():
        return store.snapshot()


DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Calf · FastAPI observability</title>
  <style>
    :root{color-scheme:light;--bg:#f7f7f5;--surface:#fff;--line:#deded9;--line-soft:#ecece8;--text:#151515;--muted:#70706b;--green:#15803d;--green-soft:#eaf6ee;--red:#c62828;--red-soft:#fcecec}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:12px/1.45 Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
    main{max-width:1320px;margin:auto;padding:24px}.top{display:flex;align-items:center;justify-content:space-between;gap:20px;padding-bottom:18px;border-bottom:1px solid var(--line);margin-bottom:16px}h1{margin:0;font-size:18px;line-height:1.2;font-weight:650;letter-spacing:-.025em}.cow{color:var(--text)}#meta{color:var(--muted);text-align:right;font-variant-numeric:tabular-nums}
    .cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid var(--line);background:var(--surface);margin-bottom:12px}.card{padding:13px 15px;border-right:1px solid var(--line)}.card:last-child{border-right:0}.label{color:var(--muted);font-size:9px;font-weight:650;text-transform:uppercase;letter-spacing:.1em}.value{font-size:20px;font-weight:600;line-height:1.3;margin-top:3px;font-variant-numeric:tabular-nums}.panel{background:var(--surface);border:1px solid var(--line);margin-top:12px;overflow:hidden}.panel-head{min-height:36px;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 8px 0 14px;border-bottom:1px solid var(--line)}h2{font-size:11px;font-weight:650;margin:0;letter-spacing:.01em}.panel-actions{display:flex;align-items:center;gap:6px}.panel-body{padding:0 14px 12px;overflow:auto}.panel.collapsed .panel-head{border-bottom:0}.panel.collapsed .panel-body{display:none}
    button{font:inherit}.icon-button{display:grid;place-items:center;width:25px;height:25px;padding:0;border:0;background:transparent;color:var(--muted);cursor:pointer}.icon-button:hover{color:var(--text);background:#f1f1ee}.chevron{width:6px;height:6px;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;transform:rotate(45deg) translate(-1px,-1px);transition:transform .15s ease}.collapsed .chevron{transform:rotate(-45deg)}.view-switch{display:flex;border:1px solid var(--line);padding:2px;background:#f5f5f2}.view-button{border:0;background:transparent;color:var(--muted);padding:3px 7px;font-size:9px;font-weight:650;cursor:pointer}.view-button.active{color:var(--text);background:var(--surface);box-shadow:0 0 0 1px var(--line)}
    table{border-collapse:collapse;width:100%;white-space:nowrap;font-variant-numeric:tabular-nums}th,td{padding:8px;border-bottom:1px solid var(--line-soft);text-align:right}tbody tr:last-child td{border-bottom:0}th{color:var(--muted);font-size:9px;font-weight:650;text-transform:uppercase;letter-spacing:.07em}th:first-child,td:first-child{text-align:left}.method{display:inline-block;color:#343434;background:#efefec;border-radius:3px;padding:1px 4px;font-size:9px;font-weight:700;margin-right:3px}.bad{color:var(--red);font-weight:600}.warn{color:var(--red);font-weight:600}.ok{color:var(--green);font-weight:600}
    .phase{display:grid;grid-template-columns:92px 1fr 62px;gap:8px;align-items:center;margin:6px 0;color:#4e4e4a}.track{height:4px;background:#e8e8e4;overflow:hidden}.fill{height:100%;min-width:1px;background:#41413e}.phase:nth-child(3n+1) .fill{background:var(--green)}.lifecycle{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:10px;padding-top:12px}.route-life{border:1px solid var(--line-soft);padding:11px}.route-life strong{display:block;font-size:11px;margin-bottom:9px}.empty{color:var(--muted);padding:16px 1px}.pulse{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--green);margin-right:6px}.top .label{margin-top:5px!important;color:var(--green)}
    @media(max-width:750px){main{padding:14px}.cards{grid-template-columns:repeat(2,1fr)}.card:nth-child(2){border-right:0}.card:nth-child(-n+2){border-bottom:1px solid var(--line)}.top{align-items:flex-start;flex-direction:column}#meta{text-align:left}}
  </style>
</head>
<body><main>
  <div class="top"><div><h1><span class="cow">Calf</span> request monitor</h1><div class="label" style="margin-top:8px"><span class="pulse"></span>live worker view</div></div><div id="meta">Connecting…</div></div>
  <section class="cards"><div class="card"><div class="label">Requests</div><div class="value" id="requests">—</div></div><div class="card"><div class="label">Failures</div><div class="value" id="failures">—</div></div><div class="card"><div class="label">Loop blocks</div><div class="value" id="blocks">—</div></div><div class="card"><div class="label">Routes</div><div class="value" id="routeCount">—</div></div></section>
  <section class="panel" data-panel="routes"><div class="panel-head"><h2>Routes</h2><button class="icon-button" data-collapse aria-expanded="true" aria-label="Collapse Routes"><span class="chevron"></span></button></div><div class="panel-body"><div id="routes" class="empty">Waiting for requests…</div></div></section>
  <section class="panel" data-panel="lifecycle"><div class="panel-head"><h2>Last request lifecycle</h2><div class="panel-actions"><div class="view-switch" role="group" aria-label="Lifecycle view"><button class="view-button active" data-view="blocks" aria-pressed="true">Blocks</button><button class="view-button" data-view="table" aria-pressed="false">Table</button></div><button class="icon-button" data-collapse aria-expanded="true" aria-label="Collapse Last request lifecycle"><span class="chevron"></span></button></div></div><div class="panel-body"><div id="lifecycle" class="lifecycle"><div class="empty">Waiting for lifecycle data…</div></div></div></section>
  <section class="panel" data-panel="blocks"><div class="panel-head"><h2>Recent event-loop blocks</h2><button class="icon-button" data-collapse aria-expanded="true" aria-label="Collapse Recent event-loop blocks"><span class="chevron"></span></button></div><div class="panel-body"><div id="blockList" class="empty">No stalls detected.</div></div></section>
</main><script>
const statsUrl=__STATS_URL__; const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); const ms=n=>Number(n||0).toFixed(1)+' ms';
let lifecycleView=localStorage.getItem('calf-lifecycle-view')||'blocks',latestData=null;
function renderLifecycle(d){const withLife=d.routes.filter(r=>r.lifecycle),el=document.querySelector('#lifecycle');el.className=lifecycleView==='blocks'?'lifecycle':'';document.querySelectorAll('[data-view]').forEach(b=>{const active=b.dataset.view===lifecycleView;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active))});if(!withLife.length){el.innerHTML='<div class="empty">Waiting for lifecycle data…</div>';return}if(lifecycleView==='table'){el.innerHTML=`<table><thead><tr><th>Route</th><th>Parsing</th><th>Dependencies</th><th>Endpoint</th><th>Serialization</th><th>Middleware</th><th>Background</th><th>Total</th></tr></thead><tbody>${withLife.map(r=>{const l=r.lifecycle;return `<tr><td><span class="method">${esc(r.method)}</span> ${esc(r.path)}</td><td>${ms(l.parsing)}</td><td>${ms(l.dependencies)}</td><td>${ms(l.endpoint)}</td><td>${ms(l.serialization)}</td><td>${ms(l.middleware)}</td><td>${ms(l.background)}</td><td><strong>${ms(l.total)}</strong></td></tr>`}).join('')}</tbody></table>`;return}el.innerHTML=withLife.map(r=>{const l=r.lifecycle,max=Math.max(l.total,1),ph=[['Parsing',l.parsing],['Dependencies',l.dependencies],['Endpoint',l.endpoint],['Serialization',l.serialization],['Middleware',l.middleware],['Background',l.background]];return `<article class="route-life"><strong><span class="method">${esc(r.method)}</span> ${esc(r.path)}</strong>${ph.map(([n,v])=>`<div class="phase"><span>${n}</span><div class="track"><div class="fill" style="width:${Math.max(1,v/max*100)}%"></div></div><span>${ms(v)}</span></div>`).join('')}</article>`}).join('')}
function render(d){latestData=d;document.title=`Calf · ${d.server}`;document.querySelector('#meta').textContent=`${d.server} · PID ${d.pid} · up ${Math.floor(d.uptime_seconds)}s`;for(const [id,v] of Object.entries({requests:d.totals.requests,failures:d.totals.failures,blocks:d.totals.blocks,routeCount:d.routes.length}))document.querySelector('#'+id).textContent=v;
 document.querySelector('#routes').innerHTML=d.routes.length?`<table><thead><tr><th>Route</th><th>Requests</th><th>Failures</th><th>Avg</th><th>Last</th><th>Blocks</th><th>Worst block</th><th>Status</th></tr></thead><tbody>${d.routes.map(r=>`<tr><td><span class="method">${esc(r.method)}</span> ${esc(r.path)}</td><td>${r.requests}</td><td class="${r.failures?'bad':''}">${r.failures}</td><td>${ms(r.avg_latency_ms)}</td><td>${ms(r.last_latency_ms)}</td><td class="${r.blocks?'warn':''}">${r.blocks}</td><td>${r.blocks?ms(r.worst_block_ms):'—'}</td><td class="${r.status>=400?'bad':'ok'}">${r.status}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">Waiting for requests…</div>';
 renderLifecycle(d);
 document.querySelector('#blockList').innerHTML=d.blocks.length?`<table><thead><tr><th>Time</th><th>Duration</th><th>Affected requests</th></tr></thead><tbody>${d.blocks.map(b=>`<tr><td>${new Date(b.timestamp*1000).toLocaleTimeString()}</td><td class="warn">${ms(b.blocked_ms)}</td><td>${esc(b.affected_requests.map(r=>r.method+' '+r.path).join(', ')||'No active request')}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">No stalls detected.</div>'}
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>{lifecycleView=button.dataset.view;localStorage.setItem('calf-lifecycle-view',lifecycleView);if(latestData)renderLifecycle(latestData)}));
document.querySelectorAll('[data-collapse]').forEach(button=>button.addEventListener('click',()=>{const panel=button.closest('.panel'),collapsed=panel.classList.toggle('collapsed');button.setAttribute('aria-expanded',String(!collapsed));button.setAttribute('aria-label',(collapsed?'Expand ':'Collapse ')+panel.querySelector('h2').textContent)}));
async function refresh(){try{const r=await fetch(statsUrl,{cache:'no-store'});if(!r.ok)throw Error(r.status);render(await r.json())}catch(e){document.querySelector('#meta').textContent='Dashboard disconnected'}}refresh();setInterval(refresh,1000);
</script></body></html>"""
