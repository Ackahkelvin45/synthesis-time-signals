Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

def _hex4():
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

def _unicode_escape():
    return st.tuples(st.just("\\u"), _hex4()).map(lambda t: t[0] + t[1])

def _surrogate_escape():
    return st.sampled_from([
        "\\ud800", "\\udfff", "\\uD800", "\\uDFFF",
        "\\ud83d\\ude00", "\\uD83D\\uDE00",
    ])

def _simple_escape():
    return st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _safe_cp():
    # SAFECODEPOINT: ~ ["\\\u0000-\u001F]
    return st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters='"\u0000\u0001\u0002\u0003\u0004\u0005\u0006\u0007'
        "\u0008\u0009\u000a\u000b\u000c\u000d\u000e\u000f\u0010\u0011\u0012"
        "\u0013\u0014\u0015\u0016\u0017\u0018\u0019\u001a\u001b\u001c\u001d"
        "\u001e\u001f\\",
    )

def _string_body_piece():
    return st.one_of(
        _safe_cp(),
        _simple_escape(),
        _unicode_escape(),
        _surrogate_escape(),
        st.sampled_from(["\u0000", "\u0001", "\u001f", "\u007f", "\u000b", "\u000c"]),
    )

def _string_body():
    return st.lists(_string_body_piece(), max_size=8).map("".join)

def _string():
    return st.tuples(st.just('"'), _string_body(), st.just('"')).map(lambda t: t[0] + t[1] + t[2])

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.tuples(
            st.integers(min_value=1, max_value=9),
            st.text(alphabet="0123456789", max_size=10),
        ).map(lambda t: str(t[0]) + t[1]),
        st.text(alphabet="0123456789", min_size=1, max_size=20),
    )

def _frac():
    return st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=8)).map(
        lambda t: t[0] + t[1]
    )

def _exp():
    return st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.text(alphabet="0123456789", min_size=1, max_size=6),
    ).map(lambda t: t[0] + t[1] + t[2])

def _number():
    sign = st.sampled_from(["", "-", "+"])
    body = st.tuples(
        _int_part(),
        st.one_of(st.just(""), _frac()),
        st.one_of(st.just(""), _exp()),
    ).map(lambda t: t[0] + t[1] + t[2])
    normal = st.tuples(sign, body).map(lambda t: t[0] + t[1])
    weird = st.sampled_from([
        "-", "1e309", "-1e309", "1e-309", "1E+999", "0e0", "0e00",
        ".5", "1.", "+1", "01", "0x1F", "1e", "1e+", "-.5", "00",
        "1e999999999999", "-0", "0.0", "-0.0", "1.0e0",
    ])
    return st.one_of(normal, weird)

# ---------- recursive values ----------

def _value(depth):
    leaf = st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
    )
    if depth <= 0:
        return leaf
    child = st.deferred(lambda: _value(depth - 1))
    obj = _obj(child)
    arr = _arr(child)
    return st.one_of(leaf, obj, arr)

def _pair(child):
    return st.tuples(_string(), st.just(":"), child).map(lambda t: t[0] + t[1] + t[2])

def _obj(child):
    return st.one_of(
        st.just("{}"),
        st.tuples(
            st.just("{"),
            st.lists(_pair(child), min_size=1, max_size=4).map(lambda ps: ",".join(ps)),
            st.just("}"),
        ).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(
            st.just("{"),
            st.lists(_pair(child), min_size=1, max_size=3).map(lambda ps: ",".join(ps)),
            st.just(",}"),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )

def _arr(child):
    return st.one_of(
        st.just("[]"),
        st.tuples(
            st.just("["),
            st.lists(child, min_size=1, max_size=4).map(lambda xs: ",".join(xs)),
            st.just("]"),
        ).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(
            st.just("["),
            st.lists(child, min_size=1, max_size=3).map(lambda xs: ",".join(xs)),
            st.just(",]"),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )

# ---------- deep nesting ----------

def _deep_nesting():
    def _mk(kind, n):
        return kind * n + (("{}" if kind == "{" else "[]") if kind == "{" else "[]")

    deep_obj = st.integers(min_value=1, max_value=200).map(
        lambda n: "{" + ",".join(['"k":' for _ in range(0)]) + "{}" if False else _deep_obj(n)
    )
    return st.integers(min_value=1, max_value=200).flatmap(
        lambda n: st.one_of(
            st.just("[" * n + "]" * n),
            st.just("{" + '"a":{' * n + "}" * n + "}"),
            st.just("[" * n + "0" + "]" * n),
        )
    )

def _deep_obj(n):
    return "{" + '"k":' * n + "null" + "}" * n

# ---------- malformed / near-valid ----------

def _malformed():
    return st.sampled_from([
        "[1,,2]", "[,]", "[,1]", "{,}", "{\"a\":1,,}", "{\"a\":1 \"b\":2}",
        "{a:1}", "{'a':1}", "{\"a\" 1}", "{\"a\":}", "{:1}",
        "[1 2]", "[1,2", "{\"a\":1", "\"unterminated", "\"a\\\"",
        "1abc", "[]xyz", "1 garbage", "true false", "nul", "tru", "fals",
        "+1", ".5", "1.", "01", "0x1F", "1e", "1e+", "--1", "-.",
        "//x", "/* */1", "'x'", "{\"a\":1,}", "[1,2,]",
        "\"\\uD800\"", "\"\\u\"", "\"\\uZZZZ\"", "\"\\q\"",
        "\u0000", "{\u0000}", "[\u0000]", "\"a\u0000b\"",
        "\"\\ud800\\udc00\"", "{\"a\":1}\u0000",
        "{}", "[]", "null", "", " ", "\n", "\t",
    ])

# ---------- near-crash intensification ----------

_CRASH_SEEDS = [
    '"\\ud800"',
    '"\\uD800"',
    '"\ud800"',
    '["\\ud800"]',
    '{"a":"\\ud800"}',
    '{"\\ud800":1}',
    '"\\ud800\\udc00"',
    '"\\udbff\\udfff"',
    '"\\uD83D\\uDE00"',
    '"\\u"',
    '"\\u0"',
    '"\\u00"',
    '"\\u000"',
    '"\\u0000"',
    '"\\uD800\\uD800"',
    '"\\uDC00"',
    '"\\uDFFF"',
    '"' + 'a' * 200 + '"',
    '[' * 300 + ']' * 300,
    '{' + '"a":{' * 200 + '}' * 200 + '}',
    '{"a":' * 200 + 'null' + '}' * 200,
    '"' + '\\u0041' * 100 + '"',
    '"' + '\\n' * 200 + '"',
    '"' + 'a' * 1000 + '"',
    '[' + ','.join(['"\\ud800"'] * 50) + ']',
    '{"k":' + '[' * 100 + ']' * 100 + '}',
    '"\\ud800' + 'a' * 100 + '"',
    '"' + '\\uD800' * 50 + '"',
    '[' * 500 + '0' + ']' * 500,
    '{' * 400 + '}' * 400,
]

def _mutate_around_crash(s):
    """Structurally mutate around a crashing input."""
    def _mut(s):
        return st.one_of(
            st.just(s),
            # duplicate the whole input (deepens nesting / repeats tokens)
            st.just(s + s),
            # wrap in array / object
            st.just("[" + s + "]"),
            st.just("{" + '"a":' + s + "}"),
            st.just("[" + s + "," + s + "]"),
            # truncate at various points
            st.integers(min_value=0, max_value=max(len(s) - 1, 0)).map(
                lambda i: s[:i]
            ),
            # append trailing junk
            st.sampled_from(["", " ", "\n", "\u0000", ",", "]", "}", '"', "\\"]).map(
                lambda suf: s + suf
            ),
            # prepend junk
            st.sampled_from(["", " ", "\n", "\u0000", "[", "{", '"', "\\"]).map(
                lambda pre: pre + s
            ),
            # swap a single byte-ish character to a structural char
            st.integers(min_value=0, max_value=max(len(s) - 1, 0)).flatmap(
                lambda i: st.sampled_from(list("[]{}\",:\\ \n\t\u0000")).map(
                    lambda c: s[:i] + c + s[i + 1:]
                )
            ),
            # delete a character
            st.integers(min_value=0, max_value=max(len(s) - 1, 0)).map(
                lambda i: s[:i] + s[i + 1:]
            ),
            # replace a char with a hex escape
            st.integers(min_value=0, max_value=max(len(s) - 1, 0)).map(
                lambda i: s[:i] + "\\u" + s[i + 1:]
            ),
            # nest deeper
            st.integers(min_value=1, max_value=50).map(
                lambda n: "[" * n + s + "]" * n
            ),
            st.integers(min_value=1, max_value=50).map(
                lambda n: "{" + '"a":{' * n + s + "}" * n + "}"
            ),
            # repeat the input many times
            st.integers(min_value=1, max_value=20).map(lambda n: s * n),
            # ----- intensified structural mutations -----
            # splice seed into the middle of a nested container
            st.integers(min_value=1, max_value=40).flatmap(
                lambda n: st.sampled_from([
                    "[" * n + s + "]" * n,
                    "{" + '"k":' * n + s + "}" * n,
                    "[" * n + s + "," + s + "]" * n,
                    '{"a":[' * n + s + "]}" * n,
                ])
            ),
            # interleave seed with structural tokens
            st.tuples(
                st.integers(min_value=1, max_value=30),
                st.sampled_from(["", ",", ":", " ", "\n", "\u0000"]),
            ).map(lambda t: (s + t[1]) * t[0] + s),
            # inject seed inside string/escape context
            st.sampled_from([
                '"' + s + '"',
                '"\\u' + s + '"',
                '"' + s + '\\u0000"',
                s + '"',
                '"' + s,
            ]),
            # balanced truncation: cut then re-close brackets
            st.integers(min_value=0, max_value=max(len(s) - 1, 0)).map(
                lambda i: s[:i] + "]" * (s[:i].count("[") - s[:i].count("]"))
                + "}" * (s[:i].count("{") - s[:i].count("}"))
            ),
            # double every structural character
            st.just("".join(c * 2 if c in "[]{}\"," else c for c in s)),
            # swap halves
            st.just(s[len(s) // 2:] + s[:len(s) // 2]),
            # reverse
            st.just(s[::-1]),
        )
    return st.one_of([_mut(s) for s in _CRASH_SEEDS])

# ---------- top-level strategy ----------

def _top():
    deep = _deep_nesting()
    root = st.recursive(
        st.one_of(
            _string(),
            _number(),
            st.sampled_from(["true", "false", "null"]),
        ),
        lambda child: st.one_of(_obj(child), _arr(child)),
        max_leaves=20,
    )
    return st.one_of(
        root,
        deep,
        _malformed(),
        st.tuples(
            st.one_of(_string(), _number()),
            st.sampled_from(["", " ", "\n", "\t"]),
        ).map(lambda t: t[0] + t[1]),
    )

strategy = st.one_of(
    _top(),
    _obj(_value(3)),
    _arr(_value(3)),
    _value(4),
    _mutate_around_crash('"\\ud800"'),
).map(lambda s: s if isinstance(s, str) else json.dumps(s))
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 44.51,
  "region_coverage_pct": 44.19,
  "least_covered_functions": [
    "would_overflow (0% of branches)",
    "json_parse (0% of branches)",
    "json_alloc (33% of branches)",
    "json_parse_ex (38% of branches)",
    "hex_value (75% of branches)"
  ]
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.