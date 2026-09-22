"""DACON (dacon.io) — the list page embeds window.__NUXT__; evaluated with Node (preinstalled on runners)."""
import json
import subprocess

from .. import http

NAME = "DACON"
CONTEST_LIST = True
URL = "https://dacon.io/competitions"

# Evaluates only the __NUXT__ assignment inside an empty sandbox context, then walks it.
NODE = r"""
const vm = require('vm'); let src = '';
process.stdin.on('data', d => src += d).on('end', () => {
  const m = src.match(/<script>(window\.__NUXT__=[\s\S]*?)<\/script>/);
  if (!m) { console.log('[]'); return; }
  const ctx = { window: {} }; vm.createContext(ctx); vm.runInContext(m[1], ctx, { timeout: 5000 });
  const out = [];
  (function walk(o) {
    if (!o || typeof o !== 'object') return;
    if (o.cpt_id && o.name && o.period_end) { out.push(o); return; }
    for (const k in o) walk(o[k]);
  })(ctx.window.__NUXT__);
  console.log(JSON.stringify(out));
});
"""


def fetch():
    html = http.get(URL).text
    out = subprocess.run(["node", "-e", NODE], input=html, capture_output=True, text=True, encoding="utf-8", check=True)
    items = {}
    for c in json.loads(out.stdout or "[]"):
        if not c.get("on_going"):
            continue
        items[c["cpt_id"]] = {
            "name": c["name"],
            "host": "DACON",
            "applyStart": (c.get("period_start") or "")[:10] or None,
            "applyEnd": (c.get("period_end") or "")[:10] or None,
            "prize": c.get("prize_info") or None,
            "url": f"https://dacon.io/competitions/official/{c['cpt_id']}/overview/description",
        }
    return list(items.values())
