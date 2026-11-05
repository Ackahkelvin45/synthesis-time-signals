"""test_strict_policy.py: offline check of the gate fallback (PLAN_replication2.md, section 9).

Drives the real loop on parson with a scripted model (no API call, no spend): a shared first draft, three
working refinements, then a round 5 that raises and whose one repair raises too. Under --policy common the
loop keeps the broken round-5 generator (the first replication's behaviour); under --policy strict it must
return round 4's generator.

    .venv/bin/python eval/followup/test_strict_policy.py
"""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "fuzz" / "loop"))
os.environ["LLM_MOCK"] = "1"
import agent  # noqa: E402


def good(i):
    return f'from hypothesis import strategies as st\nstrategy = st.sampled_from(["{{}}", "[]", "{{\\"k{i}\\": {i}}}"])\n'


BAD = "from hypothesis import strategies as st\nstrategy = st.builds(lambda: 1 // 0)\n"


def run(policy, tmp, script=None, name=None):
    replies = iter(script or [good(2), good(3), good(4), BAD, BAD])
    agent.call_llm = lambda messages, stop, config: f"```python\n{next(replies)}```"
    seed = Path(tmp) / "seed.py"; seed.write_text(good(1))
    orig = agent.select_target

    def select(name):
        h = orig(name); agent.RUNS = Path(tmp); return h
    agent.select_target = select
    sys.argv = ["agent.py", "--target", "parson", "--run-name", name or policy, "--ablate", "signal",
                "--policy", policy, "--seed-from", str(seed), "--max-examples", "60"]
    agent.main()
    agent.select_target = orig
    rd = Path(tmp) / (name or policy)
    return json.loads((rd / "final.json").read_text()), (rd / "final_strategy.py").read_text()


def main():
    with tempfile.TemporaryDirectory() as tmp:
        fin, code = run("common", tmp)
        assert fin["source_iter"] == 5 and code.strip() == BAD.strip(), fin
        fin, code = run("strict", tmp)
        assert fin["source_iter"] == 4 and code.strip() == good(4).strip(), fin
        assert fin["selection"] == "last_working_strict"
        # a broken middle round: round 4 must refine round 2's working code with the plain instruction
        fin, code = run("strict", tmp, [good(2), BAD, BAD, good(4), good(5)], "strict_mid")
        prompt4 = (Path(tmp) / "strict_mid" / "iter-4" / "prompt.md").read_text()
        assert fin["source_iter"] == 5 and code.strip() == good(5).strip(), fin
        assert 'k2' in prompt4 and agent._COMMON_ACTION[1] in prompt4 and "1 // 0" not in prompt4
    print("ok: common keeps the gated round-5 generator; strict returns round 4's and refines working code after a broken middle round")


if __name__ == "__main__":
    main()
