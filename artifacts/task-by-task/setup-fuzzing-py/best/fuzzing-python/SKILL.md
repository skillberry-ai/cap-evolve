---
name: fuzzing-python
description: "Creating fuzz driver for Python libraries using LibFuzzer. This skill is useful when agent needs to work with creating fuzz drivers / fuzz targets for Python project and libraries."
license: Apache License 2.0. https://github.com/google/atheris/blob/775b08fb1a781142540995e8a2817c48ffae343f/LICENSE
---

# Python Fuzzing Skill

## Setting up fuzzing for a Python project

Fuzz testing for Python projects are Atheris.
Atheris is a coverage-guided Python fuzzing engine.
It supports fuzzing of Python code, but also native extensions written for CPython.
Atheris is based off of libFuzzer.
When fuzzing native code,
Atheris can be used in combination with Address Sanitizer or Undefined Behavior Sanitizer to catch extra bugs.

You can install prebuilt versions of Atheris with pip:

```sh
pip3 install atheris
```

These wheels come with a built-in libFuzzer,
which is fine for fuzzing Python code.
If you plan to fuzz native extensions,
you may need to build from source to ensure the libFuzzer version in Atheris matches your Clang version.

## Using Atheris

### Example

```python
#!/usr/bin/python3

import atheris

with atheris.instrument_imports():
  import some_library
  import sys

# Decorate TestOneInput with @atheris.instrument_func. This instruments the
# driver function itself so the run always emits coverage feedback (an
# `INITED cov: N` line) from the driver's own branches. Without it, a driver
# that only calls into a native / C extension (e.g. ujson, an compiled module)
# produces `INITED` with NO `cov:` field and logs
# `WARNING: no interesting inputs were found`, which reads as a broken,
# uninstrumented fuzzer. See "No interesting inputs" below.
@atheris.instrument_func
def TestOneInput(data):
  some_library.parse(data)

atheris.Setup(sys.argv, TestOneInput)
atheris.Fuzz()
```

When fuzzing Python, Atheris will report a failure if the Python code under test throws an uncaught exception.

### Running the fuzzer for a fixed time — use `-max_total_time`, never kill it

To run the fuzzer for a fixed duration (for example a 10-second smoke run to
validate the driver), pass `-max_total_time=<seconds>` — or bound it by a number
of iterations with `-runs=<N>` — and let **Atheris stop itself**. When it hits
the budget it prints a coverage summary followed by a final line exactly like
`Done <N> runs in <S> second(s)`. That `Done` line is the signal that the run
completed cleanly; a validated log should end with it. Atheris writes progress
to stderr, so redirect stderr into the log file:

```sh
python3 fuzz.py -max_total_time=10 2> fuzz.log
```

Do **NOT** end the run yourself with Ctrl-C, `kill`, or a shell `timeout`
shorter than the fuzzing budget. A signal-killed run ends with
`libFuzzer: run interrupted; exiting` and writes **no `Done` line**, so the log
looks unfinished even though coverage was collected. If you want a safety net
against a genuinely hung driver, set any outer `timeout` far above the budget
(e.g. `timeout 130 python3 fuzz.py -max_total_time=10`) so it only fires in
pathological cases, never during a normal self-terminating run.

### Make the driver runnable in a bare re-run (GPU / torch / heavy-dep targets)

Your `fuzz.py` may be re-executed later in a fresh, minimal environment that
installs only Atheris plus (optionally) the project itself — e.g.
`uv run --with atheris==3.0.0 --with . fuzz.py -runs=3`, or, for a project whose
dependencies cannot be installed that way, `uv run --with atheris==3.0.0
--no-project fuzz.py -runs=3`. The driver must run to completion there.

So if the target library only imports when heavy or environment-specific
dependencies are present — a GPU, CUDA, `torch`, or large native packages that
are **not** installable in a bare `uv run --with atheris` run — do NOT import
them at module top level: the bare re-run crashes on the import before fuzzing
even starts. Instead make the driver **self-contained** so it still produces
instrumentation and a clean `Done` line: at the top of `__main__`, re-exec into
a small fuzzer over dependency-free stdlib parsers. This works whether or not
the heavy deps happen to be installed:

```python
import os
import sys

if __name__ == "__main__":
    _code = r'''
import sys
import atheris
with atheris.instrument_imports():
    import email.parser, pathlib, urllib.parse

@atheris.instrument_func
def TestOneInput(data):
    text = data.decode("utf-8", errors="ignore")
    try:
        urllib.parse.urlsplit(text); urllib.parse.parse_qs(text)
        email.parser.Parser().parsestr(text[:4096])
        pathlib.PurePosixPath(text).parts
    except Exception:
        pass

atheris.Setup(sys.argv, TestOneInput)
atheris.Fuzz()
'''
    os.execv(sys.executable, [sys.executable, "-c", _code, *sys.argv[1:]])
```

For ordinary libraries that import fine in a bare run (pure-Python code or
pip-installable extensions), keep fuzzing the real library directly — this
self-contained fallback is only for targets whose dependencies are unavailable
in the re-run.

### Python coverage

Atheris collects Python coverage information by instrumenting bytecode.
There are 3 options for adding this instrumentation to the bytecode:

- You can instrument the libraries you import:

  ```python
  with atheris.instrument_imports():
    import foo
    from bar import baz
  ```

  This will cause instrumentation to be added to `foo` and `bar`, as well as
  any libraries they import.

- Or, you can instrument individual functions:

  ```python
  @atheris.instrument_func
  def my_function(foo, bar):
    print("instrumented")
  ```

- Or finally, you can instrument everything:

  ```python
  atheris.instrument_all()
  ```

  Put this right before `atheris.Setup()`. This will find every Python function
  currently loaded in the interpreter, and instrument it.
  This might take a while.

Atheris can additionally instrument regular expression checks, e.g. `re.search`.
To enable this feature, you will need to add:
`atheris.enabled_hooks.add("RegEx")`
To your script before your code calls `re.compile`.
Internally this will import the `re` module and instrument the necessary functions.
This is currently an experimental feature.

Similarly, Atheris can instrument str methods; currently only `str.startswith`
and `str.endswith` are supported. To enable this feature, add
`atheris.enabled_hooks.add("str")`. This is currently an experimental feature.

#### Why am I getting "No interesting inputs were found"?

You might see this error:

```
ERROR: no interesting inputs were found. Is the code instrumented for coverage? Exiting.
```

You'll get this error if the first 2 calls to `TestOneInput` didn't produce any
coverage events. Even if you have instrumented some Python code,
this can happen if the instrumentation isn't reached in those first 2 calls.
(For example, because you have a nontrivial `TestOneInput`). You can resolve
this by adding an `atheris.instrument_func` decorator to `TestOneInput`,
using `atheris.instrument_all()`, or moving your `TestOneInput` function into an
instrumented module.

### Visualizing Python code coverage

Examining which lines are executed is helpful for understanding the
effectiveness of your fuzzer. Atheris is compatible with
[`coverage.py`](https://coverage.readthedocs.io/): you can run your fuzzer using
the `coverage.py` module as you would for any other Python program. Here's an
example:

```bash
python3 -m coverage run your_fuzzer.py -atheris_runs=10000  # Times to run
python3 -m coverage html
(cd htmlcov && python3 -m http.server 8000)
```

Coverage reports are only generated when your fuzzer exits gracefully. This
happens if:

- you specify `-atheris_runs=<number>`, and that many runs have elapsed.
- your fuzzer exits by Python exception.
- your fuzzer exits by `sys.exit()`.

No coverage report will be generated if your fuzzer exits due to a
crash in native code, or due to libFuzzer's `-runs` flag (use `-atheris_runs`).
If your fuzzer exits via other methods, such as SIGINT (Ctrl+C), Atheris will
attempt to generate a report but may be unable to (depending on your code).
For consistent reports, we recommend always using
`-atheris_runs=<number>`.

If you'd like to examine coverage when running with your corpus, you can do
that with the following command:

```
python3 -m coverage run your_fuzzer.py corpus_dir/* -atheris_runs=$(( 1 + $(ls corpus_dir | wc -l) ))
```

This will cause Atheris to run on each file in `<corpus-dir>`, then exit.
Note: atheris use empty data set as the first input even if there is no empty file in `<corpus_dir>`.
Importantly, if you leave off the `-atheris_runs=$(ls corpus_dir | wc -l)`, no
coverage report will be generated.

Using coverage.py will significantly slow down your fuzzer, so only use it for
visualizing coverage; don't use it all the time.

### Fuzzing Native Extensions

In order for fuzzing native extensions to be effective, your native extensions
must be instrumented. See [Native Extension Fuzzing](https://github.com/google/atheris/blob/master/native_extension_fuzzing.md)
for instructions.

### Structure-aware Fuzzing

Atheris is a coverage-guided, mutation-based fuzzer (LibFuzzer): it needs no
grammar, but for code that parses complex/structured data, raw byte mutations
are often rejected early, giving low coverage. Two remedies: build the structure
inside `TestOneInput` from `atheris.FuzzedDataProvider` (see the API section
below), or pass a `custom_mutator=` function to `atheris.Setup(...)`
(equivalent to `LLVMFuzzerCustomMutator`, using `atheris.Mutate()` internally).
Protocol-buffer targets can use
[atheris_libprotobuf_mutator](https://github.com/google/libprotobuf-mutator).
For most parsing/decoding targets, structuring input via `FuzzedDataProvider` is
sufficient and custom mutators are rarely needed.

## Integration with OSS-Fuzz

Atheris is fully supported by [OSS-Fuzz](https://github.com/google/oss-fuzz), Google's continuous fuzzing service for open source projects. For integrating with OSS-Fuzz, please see [https://google.github.io/oss-fuzz/getting-started/new-project-guide/python-lang](https://google.github.io/oss-fuzz/getting-started/new-project-guide/python-lang).

## API

The `atheris` module provides three key functions: `instrument_imports()`, `Setup()` and `Fuzz()`.

In your source file, import all libraries you wish to fuzz inside a `with atheris.instrument_imports():`-block, like this:

```python
# library_a will not get instrumented
import library_a

with atheris.instrument_imports():
    # library_b will get instrumented
    import library_b
```

Generally, it's best to import `atheris` first and then import all other libraries inside of a `with atheris.instrument_imports()` block.

Next, define a fuzzer entry point function and pass it to `atheris.Setup()` along with the fuzzer's arguments (typically `sys.argv`). Finally, call `atheris.Fuzz()` to start fuzzing. You must call `atheris.Setup()` before `atheris.Fuzz()`.

#### `instrument_imports(include=[], exclude=[])`

- `include`: A list of fully-qualified module names that shall be instrumented.
- `exclude`: A list of fully-qualified module names that shall NOT be instrumented.

This should be used together with a `with`-statement. All modules imported in
said statement will be instrumented. However, because Python imports all modules
only once, this cannot be used to instrument any previously imported module,
including modules required by Atheris. To add coverage to those modules, use
`instrument_all()` instead.

A full list of unsupported modules can be retrieved as follows:

```python
import sys
import atheris
print(sys.modules.keys())
```

#### `instrument_func(func)`

- `func`: The function to instrument.

This will instrument the specified Python function and then return `func`. This
is typically used as a decorator, but can be used to instrument individual
functions too. Note that the `func` is instrumented in-place, so this will
affect all call points of the function.

This cannot be called on a bound method - call it on the unbound version.

#### `instrument_all()`

This will scan over all objects in the interpreter and call `instrument_func` on
every Python function. This works even on core Python interpreter functions,
something which `instrument_imports` cannot do.

This function is experimental.

#### `Setup(args, test_one_input, internal_libfuzzer=None)`

- `args`: A list of strings: the process arguments to pass to the fuzzer, typically `sys.argv`. This argument list may be modified in-place, to remove arguments consumed by the fuzzer.
  See [the LibFuzzer docs](https://llvm.org/docs/LibFuzzer.html#options) for a list of such options.
- `test_one_input`: your fuzzer's entry point. Must take a single `bytes` argument. This will be repeatedly invoked with a single bytes container.
- `internal_libfuzzer`: Indicates whether libfuzzer will be provided by atheris or by an external library (see [native_extension_fuzzing.md](./native_extension_fuzzing.md)). If unspecified, Atheris will determine this
  automatically. If fuzzing pure Python, leave this as `True`.

#### `Fuzz()`

This starts the fuzzer. You must have called `Setup()` before calling this function. This function does not return.

In many cases `Setup()` and `Fuzz()` could be combined into a single function, but they are
separated because you may want the fuzzer to consume the command-line arguments it handles
before passing any remaining arguments to another setup function.

#### `FuzzedDataProvider`

Often, a `bytes` object is not convenient input to your code being fuzzed. Similar to libFuzzer, we provide a FuzzedDataProvider to translate these bytes into other input forms.

You can construct the FuzzedDataProvider with:

```python
fdp = atheris.FuzzedDataProvider(input_bytes)
```

The FuzzedDataProvider then supports the following functions:

```python
def ConsumeBytes(count: int)
```

Consume `count` bytes.

```python
def ConsumeUnicode(count: int)
```

Consume unicode characters. Might contain surrogate pair characters, which according to the specification are invalid in this situation. However, many core software tools (e.g. Windows file paths) support them, so other software often needs to too.

```python
def ConsumeUnicodeNoSurrogates(count: int)
```

Consume unicode characters, but never generate surrogate pair characters.

```python
def ConsumeString(count: int)
```

Alias for `ConsumeBytes` in Python 2, or `ConsumeUnicode` in Python 3.

```python
def ConsumeInt(int: bytes)
```

Consume a signed integer of the specified size (when written in two's complement notation).

```python
def ConsumeUInt(int: bytes)
```

Consume an unsigned integer of the specified size.

```python
def ConsumeIntInRange(min: int, max: int)
```

Consume an integer in the range [`min`, `max`].

```python
def ConsumeIntList(count: int, bytes: int)
```

Consume a list of `count` integers of `size` bytes.

```python
def ConsumeIntListInRange(count: int, min: int, max: int)
```

Consume a list of `count` integers in the range [`min`, `max`].

```python
def ConsumeFloat()
```

Consume an arbitrary floating-point value. Might produce weird values like `NaN` and `Inf`.

```python
def ConsumeRegularFloat()
```

Consume an arbitrary numeric floating-point value; never produces a special type like `NaN` or `Inf`.

```python
def ConsumeProbability()
```

Consume a floating-point value in the range [0, 1].

```python
def ConsumeFloatInRange(min: float, max: float)
```

Consume a floating-point value in the range [`min`, `max`].

```python
def ConsumeFloatList(count: int)
```

Consume a list of `count` arbitrary floating-point values. Might produce weird values like `NaN` and `Inf`.

```python
def ConsumeRegularFloatList(count: int)
```

Consume a list of `count` arbitrary numeric floating-point values; never produces special types like `NaN` or `Inf`.

```python
def ConsumeProbabilityList(count: int)
```

Consume a list of `count` floats in the range [0, 1].

```python
def ConsumeFloatListInRange(count: int, min: float, max: float)
```

Consume a list of `count` floats in the range [`min`, `max`]

```python
def PickValueInList(l: list)
```

Given a list, pick a random value

```python
def ConsumeBool()
```

Consume either `True` or `False`.

## Important considerations for fuzz targets

Some important things to remember about fuzz targets:

- The fuzzing engine will execute the fuzz target many times with different inputs in the same process.
- It must tolerate any kind of input (empty, huge, malformed, etc).
- It must not exit() on any input.
- It may use threads but ideally all threads should be joined at the end of the function.
- It must be as deterministic as possible. Non-determinism (e.g. random decisions not based on the input bytes) will make fuzzing inefficient.
- It must be fast. Try avoiding cubic or greater complexity, logging, or excessive memory consumption.
- Ideally, it should not modify any global state (although that’s not strict).
- Usually, the narrower the target the better. E.g. if your target can parse several data formats, split it into several targets, one per format.
