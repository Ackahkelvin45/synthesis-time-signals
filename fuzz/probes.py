"""probes.py — single-feature probe strategies for UNCONFOUNDED attribution.

Motivation (from the proxy-signal critique): even though json-parser DOES return
a per-input error string, we still cannot get an AGGREGATE picture of which
feature is being rejected across a run from that alone. Bucketing a multi-feature input
into all its feature buckets is statistically confounded — one broken \\uXXXX
implementation would tank the "big-number" and "deep-nesting" buckets purely by
co-occurrence. The fix is a controlled experiment: generate inputs that differ
from a baseline-valid JSON by EXACTLY ONE feature. Near-zero acceptance in a
single-feature probe then unambiguously indicts that one feature's encoding.

These probes are the REPAIR signal. They do not replace the rich multi-feature
generation used for bug-finding; they run on a reserved slice of the budget
purely to attribute low acceptance to a specific production/feature.

Each probe is a Hypothesis strategy producing a `str` (the candidate JSON text).
"""
from __future__ import annotations

import json

from hypothesis import strategies as st

# A minimal always-valid baseline each probe perturbs by exactly one feature.
# Using json.dumps guarantees the baseline itself is RFC-valid, so any rejection
# is caused by the injected feature, not incidental malformedness.

# 1. unicode / escape handling: a string value full of \uXXXX escapes.
_hex4 = st.integers(min_value=0, max_value=0xFFFF).map(lambda n: f"\\u{n:04x}")
probe_unicode = st.lists(_hex4, min_size=1, max_size=8).map(
    lambda escs: '{"k":"' + "".join(escs) + '"}'
)

# 2. extreme numeric magnitude / exponent edge cases (one number, nothing else).
_big_numbers = st.sampled_from([
    "1e309", "-1e309", "1e-400", "9" * 400, "-" + "9" * 400,
    "1" + "0" * 308, "0." + "0" * 350 + "1", "1e1000000",
])
probe_bignum = _big_numbers.map(lambda n: "[" + n + "]")

# 3. deep nesting (json-parser has no cap; deep nesting stresses the first pass).
# The innermost element is a value, so the grammar-derived depth (re-entries of
# the recursive rule, fuzz/formats.py) equals the bracket depth d exactly; a
# nest ending in an empty container would read d-1.
probe_deepnest = st.integers(min_value=1500, max_value=2100).map(
    lambda d: "[" * d + "1" + "]" * d
)

# 4. duplicate keys in one object (legal per grammar; a known edge for hashers).
probe_dupkeys = st.integers(min_value=2, max_value=50).map(
    lambda n: "{" + ",".join(f'"k":{i}' for i in range(n)) + "}"
)

# 5. empty containers (base cases parsers sometimes mishandle).
probe_empty = st.sampled_from(['{}', '[]', '[[]]', '{"a":{}}', '[{},{}]'])

# 6. near-valid-but-malformed (exercises the REJECT path deliberately, one defect).
probe_near_valid = st.sampled_from([
    '{"a" 1}', '{"a":}', '"unterminated', '[1 2]', '{,}', '[1,,2]', '[,1]',
])  # NB: a SINGLE trailing comma ('[1,2,]') is VALID in json-parser, so it is
   # deliberately NOT here — these are inputs json-parser genuinely rejects.

PROBES: dict[str, st.SearchStrategy] = {
    "unicode_escape": probe_unicode,
    "big_number": probe_bignum,
    "deep_nesting": probe_deepnest,
    "duplicate_keys": probe_dupkeys,
    "empty_container": probe_empty,
    "near_valid_malformed": probe_near_valid,
}

# Which probes SHOULD parse as valid (so near-zero acceptance = a real defect to
# repair), vs. which are expected to be rejected (near_valid_malformed).
PROBE_EXPECT_VALID = {
    "unicode_escape": True,
    "big_number": True,      # json-parser ACCEPTS non-finite (overflow -> inf)
    "deep_nesting": True,    # json-parser has no depth cap -> always valid
    "duplicate_keys": True,
    "empty_container": True,
    "near_valid_malformed": False,
}


def is_strict_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except ValueError:
        return False


# --- per-format probe registry (paper: multi-format targets) ------------------
#
# Probes are the human-authored part of the proxy signal and are declared as
# such in the paper. Each format gets the same six ROLES (escape handling,
# numeric extremes, deep nesting, duplicate keys, empty containers, near-valid
# malformed) realised in that format's syntax, so the repair signal has the
# same shape across targets.

def _toml_probes() -> dict[str, st.SearchStrategy]:
    hex4 = st.integers(min_value=0x20, max_value=0xFFFF).filter(
        lambda n: not 0xD800 <= n <= 0xDFFF).map(lambda n: f"\\u{n:04X}")
    p_unicode = st.lists(hex4, min_size=1, max_size=8).map(
        lambda escs: 'k = "' + "".join(escs) + '"\n')
    p_bignum = st.sampled_from([
        "9223372036854775807", "-9223372036854775808", "1e308", "-1e308", "1.7976931348623157e308",
        "0xFFFFFFFFFFFFFFF", "1_000_000", "6.02e23", "inf", "-inf", "nan",
    ]).map(lambda n: f"k = {n}\n")
    p_deepnest = st.integers(min_value=1500, max_value=2048).map(
        lambda d: "k = " + "[" * d + "1" + "]" * d + "\n")
    p_dupkeys = st.integers(min_value=2, max_value=20).map(
        lambda n: "".join(f"k = {i}\n" for i in range(n)))
    p_empty = st.sampled_from(["k = []\n", "k = {}\n", "[t]\n", "[[a]]\n", "k = [[]]\n", ""])
    p_near_valid = st.sampled_from([
        "k = \n", "k 1\n", "= 1\n", 'k = "unterminated\n', "k = [1 2]\n", "k = {a = 1\n",
        "[t\n", "k = 1 extra\n", "k.. = 1\n",
    ])
    return {
        "unicode_escape": p_unicode, "big_number": p_bignum, "deep_nesting": p_deepnest,
        "duplicate_keys": p_dupkeys, "empty_container": p_empty, "near_valid_malformed": p_near_valid,
    }


_PROBES_BY_FORMAT = {"JSON": PROBES}
_EXPECT_BY_FORMAT = {
    "JSON": PROBE_EXPECT_VALID,
    "TOML": {"unicode_escape": True, "big_number": True, "deep_nesting": True,
             # TOML forbids duplicate keys (tomllib rejects); tomlc99's behaviour is
             # measured, so a low target rate here is a DEVIATION finding, not a repair
             "duplicate_keys": True,
             "empty_container": True, "near_valid_malformed": False},
}


def probes_for(fmt: str) -> tuple[dict[str, st.SearchStrategy], dict[str, bool]]:
    """(probes, expect_valid) for a format. Unknown formats get no probes."""
    if fmt == "TOML" and "TOML" not in _PROBES_BY_FORMAT:
        _PROBES_BY_FORMAT["TOML"] = _toml_probes()
    return _PROBES_BY_FORMAT.get(fmt, {}), _EXPECT_BY_FORMAT.get(fmt, {})
