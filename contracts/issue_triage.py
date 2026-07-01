# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
IssueTriage — incoming bug-tracker issues triaged to a consistent priority + type
by GenLayer validator consensus.

A reporter files an issue (title + body). `triage` then has every validator
independently read the same issue and assign a **priority** (p0/p1/p2/p3) and a
**kind** (bug/feature/question/docs). The result is accepted only when validators
agree on the decisive field — the **priority enum** — via comparative equivalence,
not on the exact wording of the reasoning. Kind and reasoning are advisory; the
priority is the consensus output that gates the queue.

The verb is "classify one issue into a fixed priority lane" — distinct from ranking
many candidates against each other or scoring a free-form transcript; it's a single
record mapped onto a small, fixed enum that must be reproducible across validators.
"""
import json
from genlayer import *

PRIORITIES = ("p0", "p1", "p2", "p3")
KINDS = ("bug", "feature", "question", "docs")


def normalize_triage(raw) -> dict:
    """Deterministic clamp of a raw LLM triage into the fixed enums. Never raises."""
    if not isinstance(raw, dict):
        raw = {}
    priority = str(raw.get("priority", "")).strip().lower()
    if priority not in PRIORITIES:
        priority = "p3"            # conservative default: lowest priority
    kind = str(raw.get("kind", "")).strip().lower()
    if kind not in KINDS:
        kind = "question"          # conservative default: needs clarification
    reasoning = raw.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        reasoning = "no reasoning"
    return {"priority": priority, "kind": kind, "reasoning": reasoning.strip()[:600]}


def validate_triage(data) -> bool:
    """Enforce the priority/kind enums + a non-empty reasoning."""
    if not isinstance(data, dict):
        return False
    if data.get("priority") not in PRIORITIES:
        return False
    if data.get("kind") not in KINDS:
        return False
    r = data.get("reasoning")
    return isinstance(r, str) and bool(r.strip())


class IssueTriage(gl.Contract):
    issues: TreeMap[str, str]
    issue_count: u256
    triaged_count: u256

    def __init__(self):
        self.issue_count = u256(0)
        self.triaged_count = u256(0)

    # -------------------------------------------------------------- file
    @gl.public.write
    def file_issue(self, title: str, body: str) -> str:
        """Report a new issue. Stored 'open' until triaged by consensus."""
        title = str(title).strip()
        body = str(body).strip()
        if not title or not body:
            raise Exception("title and body required")
        key = str(int(self.issue_count))
        rec = {
            "reporter": str(gl.message.sender_address),
            "title": title[:300],
            "body": body[:4000],
            "state": "open",          # open -> triaged
            "priority": "",
            "kind": "",
            "reasoning": "",
        }
        self.issues[key] = json.dumps(rec)
        self.issue_count += u256(1)
        return key

    # -------------------------------------------------------------- triage
    @gl.public.write
    def triage(self, issue_id: str) -> dict:
        """Consensus reads the issue and assigns priority + kind."""
        issue_id = str(issue_id)
        if issue_id not in self.issues:
            raise Exception("unknown issue")
        rec = json.loads(self.issues[issue_id])
        if rec["state"] == "triaged":
            raise Exception("issue already triaged")

        result = self._triage(rec["title"], rec["body"])
        rec["priority"] = result["priority"]
        rec["kind"] = result["kind"]
        rec["reasoning"] = result["reasoning"]
        rec["state"] = "triaged"
        self.issues[issue_id] = json.dumps(rec)
        self.triaged_count += u256(1)
        return {"issue": issue_id, "priority": result["priority"], "kind": result["kind"]}

    def _triage(self, title: str, body: str) -> dict:
        def do_triage() -> str:
            prompt = f"""You are an experienced bug-tracker maintainer. Read the issue and triage it.

TITLE: {title}

BODY:
{body}

Assign a priority and a kind:
- priority: "p0" (critical / outage / data loss), "p1" (high / major broken flow),
  "p2" (medium / annoying but has workaround), "p3" (low / nice-to-have)
- kind: "bug" (something is broken), "feature" (new capability),
  "question" (needs clarification / support), "docs" (documentation only)

Reply ONLY JSON: {{"priority":"p0|p1|p2|p3","kind":"bug|feature|question|docs","reasoning":"<short>"}}"""
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(raw, dict):
                try:
                    raw = json.loads(str(raw))
                except Exception:
                    raw = {}
            return json.dumps(normalize_triage(raw))

        result = gl.eq_principle.prompt_comparative(
            do_triage,
            principle="The priority enum (p0|p1|p2|p3) must be identical across validators; the kind and reasoning wording may differ.",
        )
        data = json.loads(result) if isinstance(result, str) else result
        if not validate_triage(data):
            data = normalize_triage(data if isinstance(data, dict) else {})
        return data

    # -------------------------------------------------------------- views
    @gl.public.view
    def get_issue(self, issue_id: str) -> dict:
        issue_id = str(issue_id)
        if issue_id not in self.issues:
            return {"exists": False}
        rec = json.loads(self.issues[issue_id])
        rec["exists"] = True
        return rec

    @gl.public.view
    def stats(self) -> dict:
        return {"total_issues": int(self.issue_count), "triaged": int(self.triaged_count)}
