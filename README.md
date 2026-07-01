# IssueTriage

**Triages incoming bug-tracker issues into a consistent priority + type by GenLayer validator consensus.**

[![GenLayer](https://img.shields.io/badge/GenLayer-Bradbury-ff4d6d)](https://genlayer.com) [![chainId](https://img.shields.io/badge/chainId-4221-4dd0e1)](https://docs.genlayer.com) [![contract](https://img.shields.io/badge/contract-Python%20GenVM-8a63d2)](https://docs.genlayer.com) [![tests](https://img.shields.io/badge/tests-5%2F5%20passing-3fb950)](tests) [![License](https://img.shields.io/badge/license-MIT-2dd4bf)](LICENSE)

A reporter files an issue (title + body). `triage` then has every validator independently read the
same issue and assign a **priority** (`p0`/`p1`/`p2`/`p3`) and a **kind** (`bug`/`feature`/`question`/`docs`).
The verdict is accepted only when validators **agree on the priority enum** — the decisive field — via
comparative equivalence, not on the exact wording of the reasoning. Kind and reasoning are advisory; the
priority is the consensus output that gates the queue.

The verb is **"classify one issue into a fixed priority lane"** — distinct from ranking many candidates
against each other or scoring a free-form transcript; it's a single record mapped onto a small, fixed enum
that must be reproducible across validators.

- **Contract (Bradbury, chain 4221):** `0x2c9f7ed86b302E3f1D1C12f319AF816503975a55`
- **Explorer:** https://explorer-bradbury.genlayer.com/contract/0x2c9f7ed86b302E3f1D1C12f319AF816503975a55

---

## Why GenLayer is essential

Deciding *how urgent* a free-text bug report is — and *what kind* of work it represents — is qualitative
judgment over natural language. A deterministic EVM cannot read "NullPointer in AuthService when the token
is null" and conclude it is a `p0` `bug`; it has no way to run an LLM or reach agreement on a subjective
call. GenLayer has every validator read the same issue and accept a result only when they **agree on the
priority**, turning a triage decision that would otherwise vary reviewer-to-reviewer into a reproducible,
tamper-resistant on-chain outcome. Off-chain triage bots give you *one* opinion with no consensus and no
audit trail; here the classification is agreed by the network and recorded on-chain.

## Workflow

| Step | Method | What happens |
| --- | --- | --- |
| File | `file_issue(title, body)` | Reporter opens an issue; stored `open` with empty priority/kind. |
| Triage | `triage(id)` | Consensus reads title + body → `priority` (p0–p3) + `kind` + reasoning; state → `triaged`. |
| Read | `get_issue(id)` | Full record (reporter, title, body, state, priority, kind, reasoning). |
| Stats | `stats()` | `total_issues`, `triaged`. |

### Correctness check

`_triage` wraps the local `do_triage` in **`gl.eq_principle.prompt_comparative`** with the principle:
*"the priority enum (p0|p1|p2|p3) must be identical across validators; the kind and reasoning wording may
differ."* This means validators catch a **wrong triage** by disagreeing on the *decisive value* — the
priority lane — rather than merely agreeing that the JSON has the right shape. The deterministic
`normalize_triage` clamps any raw model output onto the fixed enums (unknown priority → `p3`, unknown kind
→ `question`, reasoning trimmed) and **never raises**, while `validate_triage` enforces the enum invariants
+ a non-empty reasoning. On-chain guards reject unknown ids and forbid re-triaging an already-triaged issue.
Unit-tested on good **and** adversarial inputs, plus a full `file_issue → triage` integration run.

## Architecture

```
IssueTriage/
├── contracts/issue_triage.py  ← GenLayer Intelligent Contract (issue store + consensus triage)
└── tests/                     ← pytest: normalize/validate guards + full file → triage flow
```

**Contract-only — no frontend.** Just the intelligent contract and its test suite.

## Tests

```bash
python3 -m venv .venv && .venv/bin/pip install pytest -q
.venv/bin/python -m pytest tests -q
```
Covers `normalize_triage` / `validate_triage` (good + adversarial: bad priority → `p3`, bad kind →
`question`, non-dict inputs) and a full **file_issue → triage** integration run asserting the state
transition to `triaged` and that the finalized `priority`/`kind` land inside their enums (the shim auto-inits
`TreeMap` and varies `sender_address`).

## Deploy

```bash
genlayer deploy --contract contracts/issue_triage.py
```
After deployment, replace `0x2c9f7ed86b302E3f1D1C12f319AF816503975a55` in `.env.example` (and above) with the returned contract address.
