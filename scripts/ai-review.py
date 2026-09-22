import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, cast

NVIDIA_API_KEY = os.environ["NVIDIA_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
PR_NUMBER = os.environ.get("PR_NUMBER")
REPO = os.environ["REPO"]

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "moonshotai/kimi-k3"


def system_prompt() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "review_prompt.txt"), encoding="utf-8") as f:
        return f.read()


def read_diff() -> str:
    with open("diff.txt", "r", encoding="utf-8") as f:
        return f.read()


def read_context() -> str:
    try:
        with open("context.txt", "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def call_nvidia_api(diff_content: str, context: str = "") -> Dict[str, Any]:
    user_content = (
        f"Analyze this Pull Request diff and what it breaks when it ships. "
        f"The REPO CONTEXT below contains the CURRENT contents of every "
        f"Python file in the repo — use it to verify cross-module contracts "
        f"(e.g. the diff changes a function signature or return type but the "
        f"callers/tests elsewhere are unchanged and now disagree). Do not "
        f"guess: confirm against the context before flagging, and before "
        f"clearing any contract concern.\n\n"
        f"--- DIFF ---\n{diff_content}"
    )
    if context:
        user_content += f"\n\n--- REPO CONTEXT ---\n{context}"

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "max_tokens": 4000,
        "reasoning_effort": "low",
    }

    req = urllib.request.Request(
        NVIDIA_BASE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=280) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Error calling NVIDIA API: {e.code} {e.reason}")
        print(e.read().decode("utf-8"))
        sys.exit(1)

    text = data["choices"][0]["message"]["content"]
    clean = text.replace("```json", "").replace("```", "").strip()

    try:
        return cast(Dict[str, Any], json.loads(clean))
    except json.JSONDecodeError:
        print("Warning: AI response is not valid JSON. Raw content:")
        print(text)
        return {"summary": "Could not parse the AI response.",
                "severity": "none", "comments": []}


def build_comment_body(review: Dict[str, Any]) -> str:
    severity_emoji = {
        "none": "✅",
        "low": "🟢",
        "medium": "🟡",
        "high": "🟠",
        "critical": "🔴",
    }
    severity = review.get("severity", "none")
    emoji = severity_emoji.get(severity, "")

    body = (f"## 🤖 AI Code Review\n\n**Severity:** {emoji} {severity}\n\n"
            f"{review.get('summary', '')}\n\n")

    comments = review.get("comments", [])
    if comments:
        body += "### Findings\n\n"
        for c in comments:
            file = c.get("file", "?")
            line = c.get("line")
            location = f"{file}:{line}" if line else file
            body += (f"**`{location}`**\n- Issue: {c.get('issue', '')}\n"
                     f"- Suggestion: {c.get('suggestion', '')}\n\n")
    else:
        body += "_No relevant issues found._"

    return body


def post_comment(body: str) -> None:
    url = f"https://api.github.com/repos/{REPO}/issues/{PR_NUMBER}/comments"
    payload = json.dumps({"body": body}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        print(f"Error posting comment on PR: {e.code} {e.reason}")
        print(e.read().decode("utf-8"))
        sys.exit(1)


def main() -> None:
    diff = read_diff()

    if not diff.strip():
        print("No relevant changes to analyze.")
        return

    review = call_nvidia_api(diff, read_context())
    body = build_comment_body(review)
    if PR_NUMBER:
        post_comment(body)
        print(f"Review posted. Severity: {review.get('severity', 'none')}")
    else:
        print("Push event: review below (no PR to comment on).")
        print(body)
        print(f"Severity: {review.get('severity', 'none')}")

    if review.get("severity") == "critical":
        print("Critical issues detected. Failing the step.")
        sys.exit(1)


if __name__ == "__main__":
    main()
