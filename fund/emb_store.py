"""Permanent home of the research desk's embedding cache: a private Hugging Face
dataset repo, <hf user>/fund-embeddings (created on first push).

    python fund/emb_store.py pull   # before research: fetch the cache if the Actions cache missed
    python fund/emb_store.py push   # after research: upload it, keep only the latest version

The cache is the dashboard pipeline's own file (data/cache/emb-<model>.npz:
text hash -> float16 vector); build.py already drops texts that left the news
window, so the file stays bounded. The GitHub Actions cache stays as a fast path.
Needs HF_TOKEN (write). Without it, or on any Hub error, this warns and exits 0:
losing the cache only costs re-embedding, never a decision.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMBED = "openrouter:google/gemini-embedding-2"
FNAME = f"emb-{re.sub(r'[^A-Za-z0-9]+', '-', EMBED).strip('-')}.npz"
LOCAL = os.path.join(ROOT, "fund_research", "data", "cache", FNAME)
REPO_NAME = "fund-embeddings"

if os.environ.get("FUND_MOCK") == "1":
    sys.exit(0)
tok = os.environ.get("HF_TOKEN")
if not tok:
    print("emb_store: HF_TOKEN not set; skipping (Actions cache only)")
    sys.exit(0)
try:
    from huggingface_hub import HfApi, hf_hub_download
    api = HfApi(token=tok)
    repo = f"{api.whoami()['name']}/{REPO_NAME}"
    mode = sys.argv[1]
    if mode == "pull":
        if os.path.exists(LOCAL):
            print(f"emb_store: Actions cache hit ({os.path.getsize(LOCAL) / 1e6:.0f} MB); not pulling")
        elif not api.repo_exists(repo, repo_type="dataset"):
            print(f"emb_store: {repo} does not exist yet; first run embeds from scratch")
        else:
            os.makedirs(os.path.dirname(LOCAL), exist_ok=True)
            p = hf_hub_download(repo, FNAME, repo_type="dataset", token=tok, local_dir=os.path.dirname(LOCAL))
            print(f"emb_store: pulled {FNAME} from {repo} ({os.path.getsize(p) / 1e6:.0f} MB)")
    elif mode == "push":
        if not os.path.exists(LOCAL):
            print("emb_store: no local cache to push"); sys.exit(0)
        api.create_repo(repo, repo_type="dataset", private=True, exist_ok=True)
        api.upload_file(path_or_fileobj=LOCAL, path_in_repo=FNAME, repo_id=repo, repo_type="dataset",
                        commit_message="embedding cache")
        api.super_squash_history(repo, repo_type="dataset")        # keep one version, not one per week
        print(f"emb_store: pushed {os.path.getsize(LOCAL) / 1e6:.0f} MB to {repo} (private)")
except Exception as exc:                                             # never fail the fund over a cache
    print(f"emb_store: warning, {exc!r}")
