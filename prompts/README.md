# Prompt templates (F11)

Every prompt sent to the local LLM lives here as a versioned TOML file, never as a
string literal in Python. The reason is traceability: `caissa.llm.guardrails` records
the prompt `id`, `version` and content `sha256` on every call, so a regression in
recognition quality can be attributed to a prompt edit instead of being blamed on the
model.

## File format

```toml
id = "verify_diagram"      # stable identifier, matches the file stem
version = 3                 # bump on ANY change to system/template
description = "..."         # one line, English
max_tokens = 192            # hard cap for this prompt
temperature = 0.0           # 0.0 for everything structured
output = "json"             # "json" or "text"
stop = []                   # optional stop strings

system = """..."""          # system turn
template = """..."""        # user turn, with {placeholders}
```

## Rules

1. **Bump `version` on every content change.** The loader does not enforce it, but the
   audit log makes an un-bumped edit obvious: same id and version, different sha256.
2. **Placeholders are `str.format` fields.** Missing or extra fields raise at render
   time, in a test, rather than producing a silently truncated prompt.
3. **The prompt is not a guardrail.** "Do not guess" in a system message is a request,
   not a constraint. Everything that matters is enforced in `guardrails.py` after the
   model answers.
4. **English instructions, user-facing output in the caller's language.** Gemma follows
   English instructions more reliably; the `language` placeholder controls the answer.

## Selecting a version

`load_prompt("verify_diagram")` takes the highest version present. `load_prompt(
"verify_diagram", version=2)` pins one, which is how an A/B run in
`benchmarks/bench_llm.py` compares two prompt revisions on the same corpus.

Files are named `<id>.v<version>.toml`.
