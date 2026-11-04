#!/usr/bin/env python3
"""Queue a ComfyUI API-format workflow, wait for it, and download the outputs.

Usage:
  python run_workflow.py workflow_api.json [--server 127.0.0.1:8188] [--out outputs]
                         [--set NODE_ID.INPUT=VALUE ...] [--timeout 600]

Example:
  python run_workflow.py wf.json --set 6.text="a red fox in snow" --set 3.seed=42
Only the Python standard library is used.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


def http(server, path, data=None):
    req = urllib.request.Request(f"http://{server}{path}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode()
    with urllib.request.urlopen(req) as r:
        return r.read()


def parse_value(raw):
    try:
        return json.loads(raw)  # numbers, true/false, lists...
    except json.JSONDecodeError:
        return raw  # plain string


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow")
    ap.add_argument("--server", default="127.0.0.1:8188")
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--set", action="append", default=[], metavar="NODE.INPUT=VALUE")
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()

    with open(a.workflow) as f:
        prompt = json.load(f)
    if "nodes" in prompt and "links" in prompt:
        sys.exit("This is a UI workflow. Export it with 'Export (API)' in ComfyUI instead.")

    for s in a.set:
        key, _, val = s.partition("=")
        node, _, inp = key.partition(".")
        if node not in prompt:
            sys.exit(f"Node {node} not found in workflow")
        prompt[node]["inputs"][inp] = parse_value(val)

    try:
        res = json.loads(http(a.server, "/prompt", {"prompt": prompt, "client_id": str(uuid.uuid4())}))
    except urllib.error.HTTPError as e:
        sys.exit(f"Rejected ({e.code}): {e.read().decode()}")
    except urllib.error.URLError as e:
        sys.exit(f"Cannot reach ComfyUI at {a.server}: {e.reason}")
    pid = res["prompt_id"]
    print(f"queued prompt_id={pid}", file=sys.stderr)

    deadline = time.time() + a.timeout
    while True:
        hist = json.loads(http(a.server, f"/history/{pid}"))
        if pid in hist:
            entry = hist[pid]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                sys.exit("Execution error:\n" + json.dumps(status.get("messages", []), indent=2))
            if status.get("completed", True):
                break
        if time.time() > deadline:
            sys.exit("Timed out waiting for the result")
        time.sleep(1)

    os.makedirs(a.out, exist_ok=True)
    saved = []
    for node_out in entry.get("outputs", {}).values():
        for kind in ("images", "gifs", "videos", "audio", "files"):
            for item in node_out.get(kind, []) or []:
                if not isinstance(item, dict) or "filename" not in item:
                    continue
                q = urllib.parse.urlencode({
                    "filename": item["filename"],
                    "subfolder": item.get("subfolder", ""),
                    "type": item.get("type", "output"),
                })
                path = os.path.join(a.out, item["filename"])
                with open(path, "wb") as f:
                    f.write(http(a.server, f"/view?{q}"))
                saved.append(path)
    print(json.dumps({"prompt_id": pid, "files": saved}, indent=2))


if __name__ == "__main__":
    main()
