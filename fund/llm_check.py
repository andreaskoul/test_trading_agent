"""Which OpenRouter providers will serve the fund's model for this account? One tiny call each.
Prints status and the provider's reason, so a pin that the account's data policy blocks is caught."""
import json, os, urllib.error, urllib.request
from common import MODEL
for prov in ["deepseek", "novita", "deepinfra", "gmicloud", "fireworks", "baseten", "atlas-cloud", None]:
    body = {"model": MODEL, "max_tokens": 20, "messages": [{"role": "user", "content": "Reply with the word ok."}]}
    if prov:
        body["provider"] = {"order": [prov], "allow_fallbacks": False}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.load(r); print(f"{str(prov):12s} OK   served by {d.get('provider')}")
    except urllib.error.HTTPError as e:
        print(f"{str(prov):12s} HTTP {e.code}: {e.read()[:250].decode(errors='replace')}")
    except Exception as e:
        print(f"{str(prov):12s} {e!r}")
