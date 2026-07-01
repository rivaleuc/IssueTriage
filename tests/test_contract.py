"""IssueTriage tests: triage normalize/validate guards + full file_issue → triage flow."""

A = "0xAAa0000000000000000000000000000000000001"
B = "0xBBb0000000000000000000000000000000000002"


def test_normalize_triage(contract):
    n = contract.normalize_triage
    good = n({"priority": "p0", "kind": "bug", "reasoning": "prod is down"})
    assert good["priority"] == "p0" and good["kind"] == "bug"
    # case-insensitive + trimmed
    caps = n({"priority": " P1 ", "kind": "FEATURE", "reasoning": "x"})
    assert caps["priority"] == "p1" and caps["kind"] == "feature"
    # bad priority -> conservative default p3
    assert n({"priority": "urgent", "kind": "bug", "reasoning": "x"})["priority"] == "p3"
    # bad kind -> conservative default question
    assert n({"priority": "p0", "kind": "chore", "reasoning": "x"})["kind"] == "question"
    # empty dict -> full defaults (this is what the shim's exec_prompt returns)
    assert n({})["priority"] == "p3" and n({})["kind"] == "question"
    # non-dict inputs never raise, fall back to defaults
    assert n("not a dict")["priority"] == "p3"
    assert n(None)["kind"] == "question"
    assert n(123)["reasoning"] == "no reasoning"


def test_validate_triage(contract):
    v = contract.validate_triage
    assert v({"priority": "p2", "kind": "docs", "reasoning": "typo in the readme"})
    assert not v({"priority": "p9", "kind": "bug", "reasoning": "x"})     # bad priority
    assert not v({"priority": "p1", "kind": "task", "reasoning": "x"})    # bad kind
    assert not v({"priority": "p1", "kind": "bug", "reasoning": "   "})   # blank reasoning
    assert not v({"priority": "p1", "kind": "bug"})                       # missing reasoning
    assert not v("nope")                                                 # non-dict


def _new(contract):
    return contract, contract.IssueTriage()


def test_file_issue_requires_fields(contract):
    mod, c = _new(contract)
    mod.gl.message.sender_address = A
    try:
        c.file_issue("", "has body"); assert False, "empty title rejected"
    except Exception:
        pass
    try:
        c.file_issue("has title", "   "); assert False, "empty body rejected"
    except Exception:
        pass
    assert c.stats()["total_issues"] == 0
    mod.gl.message.sender_address = A


def test_full_triage_flow(contract):
    mod, c = _new(contract)
    mod.gl.message.sender_address = A
    iid = c.file_issue("App crashes on login", "NullPointer in AuthService when the token is null.")
    rec = c.get_issue(iid)
    assert rec["exists"] and rec["state"] == "open" and rec["reporter"] == A
    assert rec["priority"] == "" and rec["kind"] == ""

    # triage by consensus — under the shim exec_prompt returns {} -> normalized defaults
    mod.gl.message.sender_address = B
    out = c.triage(iid)
    assert out["priority"] in ("p0", "p1", "p2", "p3")
    assert out["kind"] in ("bug", "feature", "question", "docs")

    rec2 = c.get_issue(iid)
    assert rec2["state"] == "triaged"
    assert rec2["priority"] in ("p0", "p1", "p2", "p3")
    assert rec2["kind"] in ("bug", "feature", "question", "docs")
    # shim consensus yields the conservative defaults
    assert rec2["priority"] == "p3" and rec2["kind"] == "question"
    assert rec2["reasoning"]

    st = c.stats()
    assert st["total_issues"] == 1 and st["triaged"] == 1

    # cannot re-triage an already-triaged issue
    try:
        c.triage(iid); assert False, "double triage rejected"
    except Exception:
        pass
    mod.gl.message.sender_address = A


def test_unknown_issue_guards(contract):
    mod, c = _new(contract)
    mod.gl.message.sender_address = A
    assert c.get_issue("999") == {"exists": False}
    try:
        c.triage("999"); assert False, "unknown issue rejected"
    except Exception:
        pass
    st = c.stats()
    assert st["total_issues"] == 0 and st["triaged"] == 0
    mod.gl.message.sender_address = A
