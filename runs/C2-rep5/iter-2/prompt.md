Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- small building blocks ----------

HEX = "0123456789abcdefABCDEF"

safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"',
).filter(lambda c: c >= " ")

# Raw control bytes / NUL allowed and encouraged inside strings (parser tests them)
raw_control = st.sampled_from(
    ["\x00", "\x01", "\x1f", "\x7f", "\x0b", "\x0c", "\x08", "\x1b"]
)

escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

unicode_escapes = st.builds(
    lambda h: "\\u" + h,
    st.text(alphabet=HEX, min_size=4, max_size=4),
)

# lone surrogate escapes (parser accepts them)
surrogate_escapes = st.sampled_from(
    ["\\ud800", "\\udc00", "\\udfff", "\\ud83d", "\\ude00", "\\uD800", "\\uDFFF"]
)

string_body = st.one_of(
    st.text(alphabet=safe_chars, max_size=12),
    escapes,
    unicode_escapes,
    surrogate_escapes,
    raw_control,
)

# A JSON string literal (well-formed)
json_string = st.lists(string_body, max_size=6).map(lambda parts: '"' + "".join(parts) + '"')

# Also produce unterminated / bare string fragments for malformed cases
unterminated_string = st.lists(string_body, max_size=6).map(
    lambda parts: '"' + "".join(parts)
)

# ---------- numbers ----------

digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

int_part = st.one_of(
    st.just("0"),
    st.builds(lambda d: d, st.text(alphabet="123456789", min_size=1, max_size=1).flatmap(
        lambda first: st.text(alphabet="0123456789", min_size=0, max_size=6).map(
            lambda rest: first + rest
        )
    )),
)

frac_part = st.builds(
    lambda d: "." + d,
    st.text(alphabet="0123456789", min_size=1, max_size=6),
)

exp_part = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
)

sign = st.sampled_from(["", "-"])

valid_number = st.builds(
    lambda s, i, f, e: s + i + f + e,
    sign,
    int_part,
    st.one_of(st.just(""), frac_part),
    st.one_of(st.just(""), exp_part),
)

# extreme magnitudes / overflow
extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e308", "1e-309", "1e999999", "-1e999999",
    "0e0", "0e999", "-0", "-0.0", "1e+308", "1E-308",
    "9" * 20, "1" + "0" * 300, "1e" + "9" * 10,
    "123456789012345678901234567890.123456789e10",
])

# malformed / lenient numbers (parser accepts lone '-', non-finite)
malformed_number = st.sampled_from([
    "-", "+1", ".5", "1.", "01", "007", "0x1F", "1e", "1e+", "1e-",
    "--1", "1..2", "1.2.3", "1e1e1", "+-1", "0.", ".0", "1_000",
])

number = st.one_of(valid_number, extreme_number, malformed_number)

# ---------- literals ----------

literal = st.sampled_from(["true", "false", "null"])

# ---------- malformed tokens ----------

malformed_string = st.one_of(
    unterminated_string,
    st.just('"'),
    st.just('"\\'),
    st.just('"\\u"'),
    st.just('"\\u12"'),
    st.just('"\\uZZZZ"'),
    st.just("'single'"),
    st.just(""),
)

# ---------- recursive structure ----------

def make_value(draw, value_strategy):
    return draw(value_strategy)

def make_pair(draw, value_strategy):
    key = draw(json_string)
    val = draw(value_strategy)
    return key + ":" + val

def make_obj(draw, value_strategy):
    n = draw(st.integers(min_value=0, max_value=5))
    if n == 0:
        return "{}"
    pairs = [draw(make_pair(value_strategy)) for _ in range(n)]
    body = ",".join(pairs)
    # occasionally trailing comma (parser accepts single trailing comma)
    if draw(st.booleans()):
        body = body + ","
    return "{" + body + "}"

def make_arr(draw, value_strategy):
    n = draw(st.integers(min_value=0, max_value=5))
    if n == 0:
        return "[]"
    vals = [draw(value_strategy) for _ in range(n)]
    body = ",".join(vals)
    if draw(st.booleans()):
        body = body + ","
    return "[" + body + "]"

def make_ws(draw):
    return draw(st.text(alphabet=" \t\n\r", max_size=3))

# Build the recursive value strategy.
value_strategy = st.recursive(
    st.one_of(json_string, number, literal, malformed_string),
    lambda children: st.one_of(
        st.builds(make_obj, st.just(None), st.just(children)),
        st.builds(make_arr, st.just(None), st.just(children)),
    ),
    max_leaves=12,
)

# Wrap obj/arr builders correctly (they take value_strategy directly)
def obj_builder(value_strategy):
    return st.builds(lambda v: make_obj_from(v, value_strategy), st.nothing())

# Simpler: define composite strategies for obj/arr using the recursive children.

def _obj_from_children(children):
    @st.composite
    def _obj(draw):
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return "{}"
        pairs = []
        for _ in range(n):
            key = draw(json_string)
            val = draw(children)
            pairs.append(key + ":" + val)
        body = ",".join(pairs)
        if draw(st.booleans()):
            body += ","
        return "{" + body + "}"
    return _obj()

def _arr_from_children(children):
    @st.composite
    def _arr(draw):
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return "[]"
        vals = [draw(children) for _ in range(n)]
        body = ",".join(vals)
        if draw(st.booleans()):
            body += ","
        return "[" + body + "]"
    return _arr()

value_strategy = st.recursive(
    st.one_of(json_string, number, literal, malformed_string),
    lambda children: st.one_of(
        _obj_from_children(children),
        _arr_from_children(children),
    ),
    max_leaves=12,
)

# ---------- deep nesting (objects, stressed path) ----------

def deep_obj(depth):
    return "{" + '"a":' * depth + "1" + "}" * depth

def deep_arr(depth):
    return "[" * depth + "1" + "]" * depth

deep_nesting = st.integers(min_value=1, max_value=200).map(
    lambda d: deep_obj(d) if d % 2 == 0 else deep_arr(d)
)

# ---------- near-valid malformed whole documents ----------

malformed_doc = st.sampled_from([
    "[1,,2]",
    "[,]",
    "[,1]",
    "[1 2]",
    '{"a" 1}',
    '{"a":}',
    '{"a":1 "b":2}',
    "{,}",
    "{,}",
    "{\"a\":1,,\"b\":2}",
    "[1,2",
    '{"a":1',
    "}",
    "]",
    "{]",
    "[}",
    "1abc",
    "[]xyz",
    "1 garbage",
    "true false",
    "null null",
    "//comment\n1",
    "/* c */1",
    "{a:1}",
    "'x'",
    "",
    " ",
    "\x00",
    "\x00{}",
    "{}\x00",
    '"\x00"',
    '{"\x00":1}',
])

# ---------- object-with-members bias ----------

def obj_with_members(draw):
    n = draw(st.integers(min_value=1, max_value=6))
    pairs = []
    for _ in range(n):
        key = draw(json_string)
        val = draw(value_strategy)
        pairs.append(key + ":" + val)
    body = ",".join(pairs)
    if draw(st.booleans()):
        body += ","
    return "{" + body + "}"

object_biased = st.composite(obj_with_members)()

# ---------- top-level strategy ----------

top_value = st.one_of(
    value_strategy,
    object_biased,
    deep_nesting,
    malformed_doc,
)

strategy = st.one_of(
    top_value,
    st.builds(lambda v: v, top_value),
).map(lambda s: s if isinstance(s, str) else json.dumps(s))
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 9,
    "reject": 11,
    "crash": 12
  },
  "acceptance_rate": 0.281,
  "max_nesting_depth": 1,
  "productions_accepted": [
    "NUMBER",
    "STRING",
    "arr",
    "json",
    "obj",
    "value"
  ],
  "productions_gap": [
    "pair",
    "true",
    "false",
    "null"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 5,
  "divergences": 2,
  "divergence_examples": [
    "b'[[1e309],[],{},]'",
    "b'[[null,]]'"
  ],
  "unique_crash_signatures": [
    "ubsan:applying-non-zero-offset-to-null-pointer|the parse function>harness_parse>run_stdin_mode"
  ],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.