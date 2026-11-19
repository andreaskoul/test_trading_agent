"""Failure alert for the H9 forward weekly job (weekly.sh): the fund runner's own two channels, reused.

    python3 research/tree/F_forward/alert.py issue --title T --body-file F [--dry]
    python3 ~/.claude/hooks/with_secrets.py 'python3 research/tree/F_forward/alert.py text --body-file F'

* issue: `gh issue create -R <fund/local/runner.py GH_REPO>`, as runner.py's issue() step does (gh's own login).
* text:  fund/local/runner.py imessage(IMESSAGE_TO, text), as runner.run() does on a failed job. IMESSAGE_TO is
  read from the environment only, which the redacting wrapper provides; this file never opens a secrets file.
Exit status 1 when the alert could not be delivered, so weekly.sh can say so in its log.
"""
import argparse
import importlib.util
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def runner():
    spec = importlib.util.spec_from_file_location("fund_runner_alert", os.path.join(ROOT, "fund", "local", "runner.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)                   # constants and functions only; nothing runs at import
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel", choices=("issue", "text"))
    ap.add_argument("--title", default="Research: H9 forward weekly job FAILED")
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--dry", action="store_true", help="resolve the helpers and print; send nothing")
    a = ap.parse_args()
    R = runner()
    body = open(a.body_file).read()
    if a.channel == "issue":
        cmd = ["gh", "issue", "create", "-R", R.GH_REPO, "--title", f"{a.title} {time.strftime('%Y-%m-%d', time.gmtime())}",
               "--body", body + "\n\n@andreaskoul"]
        if a.dry:
            print("dry: would run", cmd[:6], "| body", len(body), "chars")
            return
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())
        sys.exit(r.returncode)
    to = os.environ.get("IMESSAGE_TO")
    text = f"⚠ Research H9 forward weekly FAILED at {time.strftime('%H:%M', time.gmtime())}Z\n{body[:600]}"
    if a.dry:
        print("dry: imessage helper", R.imessage.__name__, "| recipient in environment:", bool(to), "| text", len(text), "chars")
        return
    if not to:
        print("alert NOT texted: IMESSAGE_TO is not in the environment (run through the redacting wrapper)")
        sys.exit(1)
    r = R.imessage(to, text)
    print("alert texted" if r.returncode == 0 else f"alert NOT texted: {r.stderr.strip()}")
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
