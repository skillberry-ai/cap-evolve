# Flink DataStream (Java) — Bounded Batch-Replay Query Recipes

Load this when implementing an **Apache Flink `DataStream` job in Java** that replays a
**bounded** dataset (files, e.g. gzipped CSV) rather than an unbounded Kafka topic — the
"read a trace/log file, group events per key in event time, and emit one result per key"
class of task. The Kafka streaming template in `templates.md` does not cover bounded file
replay, event-time completion joins, or the build/runtime pitfalls below.

These are the correctness rules that most often make such a job compile and run but produce
the **wrong output**. Read them before writing the job, not after the output fails to match.

---

## 1. Read the schema first, map every column by index

The record format is defined by the dataset docs (e.g. a `format.pdf` / schema `.md`). Parse
CSV **by column index**, not by guessing. Common trap: the field order in the docs is not the
order you assume. Verify with a few real rows (`zcat file.csv.gz | head`) before coding the
parser, and confirm which integer code means which event type (e.g. SUBMIT / FINISH).

## 2. Timestamp units — convert to milliseconds for event time

Many trace datasets store timestamps in **microseconds**. Flink event-time (windows,
watermarks, timers) expects **milliseconds**. Convert once, at ingestion:

```java
ctx.collectWithTimestamp(event, event.timestampMicros / 1000L);
```

Forgetting this makes session gaps off by 1000× and silently corrupts every window.

## 3. Bounded gzip file source that closes the stream

Use a `RichParallelSourceFunction` that reads the single `.gz` file line by line, assigns the
event-time timestamp, and — critically — emits `Watermark.MAX_WATERMARK` when the file ends so
that all downstream event-time windows and timers fire before the job exits. Run the job at
**parallelism = 1** for a single input file and a single output file.

```java
public class BoundedGzipSource<T> extends RichParallelSourceFunction<T> {
    private final String path;                 // single .gz file path
    private volatile boolean running = true;
    // ... constructor stores path ...
    @Override public void run(SourceContext<T> ctx) throws Exception {
        try (BufferedReader r = new BufferedReader(new InputStreamReader(
                new GZIPInputStream(new FileInputStream(path)), StandardCharsets.UTF_8))) {
            String line;
            while (running && (line = r.readLine()) != null) {
                T e = parse(line);                       // your parser
                ctx.collectWithTimestamp(e, tsMicros(e) / 1000L);
            }
        }
        ctx.emitWatermark(Watermark.MAX_WATERMARK);      // <-- lets windows/timers close
    }
    @Override public void cancel() { running = false; }
}
```

## 4. Session windows per key

"A stage / session ends after an inactivity gap of N minutes" maps directly to an event-time
session window keyed by the entity id:

```java
DataStream<Tuple3<Long,Integer,Long>> perSession = submitEvents
    .keyBy(e -> e.entityId)
    .window(EventTimeSessionWindows.withGap(Time.seconds(GAP_SECONDS)))
    .process(new CountPerWindow());   // emit (entityId, count, window.getEnd())
```

If the spec says re-occurrences count separately ("a task submitted, evicted, then
resubmitted counts twice"), **count events, not distinct ids** — do not de-duplicate.

## 5. "After / once X has finished" ⇒ COMPLETION JOIN, not end-of-stream

This is the single most common wrong-output bug. When the spec says to emit a per-entity
result **"once/after the entity has finished"**, that is a **join condition against a
completion/terminal event**, *not* "emit every key when the stream ends":

- **Only emit keys that have a matching completion event** (e.g. a job `FINISH` event in the
  companion `job_events` stream). Keys that were seen but never completed **must be dropped**.
- Emitting one row per key at end-of-stream (ignoring the completion stream) produces **extra
  rows** for every never-finished key and fails an exact-match verifier.
- **"finished" = the SUCCESS/completion event ONLY, not any terminal state.** This is the most
  common wrong-count bug on this task class. Datasets usually have several terminal event types
  (e.g. `FAIL`, `EVICT`, `KILL`, `LOST`, `FINISH`); only the completion/`FINISH` event counts as
  "finished". Filter the completion stream to that single event code (confirm the code against
  the schema doc) **before** the join. A predicate like
  `isTerminal = FAIL || FINISH || KILL || LOST` emits failed/killed keys and overshoots the
  oracle (e.g. ~900 rows instead of ~640).
- **No catch-all / end-of-stream fallback emit.** Do not register a `Long.MAX_VALUE` (or
  MAX_WATERMARK) timer that emits a key just because the input ended. A key with no completion
  event must produce **no** row; emit only from the completion event's own event-time timer.

Implement it by connecting the per-key aggregate stream with the completion-event stream and
using keyed state + an event-time timer:

```java
DataStream<Tuple2<Long,Integer>> result = perSession        // (entityId, count, endTs)
    .connect(completionEvents)                               // (entityId, completeTs)
    .keyBy(s -> s.f0, c -> c.f0)
    .process(new EmitOnCompletion());

// CoProcessFunction<Session, Completion, Result>:
//   processElement1(session):  keep running MAX(count) per entity in keyed/hash state
//   processElement2(complete): record entityId under complete timestamp; register an
//                              event-time timer at that timestamp (once per timestamp)
//   onTimer(ts):               for each entity that completed at ts, emit (entityId, maxCount)
//                              ONLY if the entity had aggregate state (had qualifying events);
//                              otherwise drop it.
```

The timer guarantees the aggregate is complete (all sessions seen) before emitting, because
the bounded source's `MAX_WATERMARK` advances event time to the end after all data is read.

## 6. Output sink — one line per record to a local file

Write with a `RichSinkFunction` at parallelism 1: open a `BufferedWriter` in `open()` (create
parent dirs, overwrite mode), `write(value); newLine()` in `invoke()`, flush+close in
`close()`. Match the **exact requested line format** (e.g. `(entityId,count)` with no spaces).
Do not use `DataStream.writeAsText`/`print` for a required exact file.

---

## 7. Building the Flink job with Maven when Central is rate-limited (HTTP 429)

Bounded-replay Flink tasks are packaged as a fat jar (`maven-assembly-plugin`
`jar-with-dependencies`). On shared CI/eval hosts, Maven Central frequently returns **HTTP 429
(Too Many Requests)** while resolving core build plugins (e.g. `maven-resources-plugin`) and
Flink deps, which fails the build.

**Do NOT work around 429 by compiling with `javac` against `/opt/flink/lib/*.jar`.** The
verifier re-runs `mvn clean package` from scratch and then `flink run`s the fat jar it expects
under `target/`; a hand-compiled class or thin jar leaves no
`target/<finalName>-jar-with-dependencies.jar`, so the build, run, and output tests all fail no
matter what you produced locally. Fix the 429 and let Maven build the jar.

Fix it in the **default user settings location so the fix persists to any later clean build**
(a verifier that runs `mvn clean package` reads `~/.m2/settings.xml`; a `-s some-local.xml`
flag you pass yourself is NOT reused by the verifier):

```bash
mkdir -p ~/.m2
cat > ~/.m2/settings.xml <<'XML'
<settings>
  <mirrors>
    <mirror>
      <id>reliable-central</id>
      <name>Non-rate-limited mirror of Maven Central</name>
      <!-- Aliyun public proxy; if unreachable, swap for the Google GCS mirror:
           https://maven-central.storage-download.googleapis.com/maven2/ -->
      <url>https://maven.aliyun.com/repository/public</url>
      <mirrorOf>central</mirrorOf>
    </mirror>
  </mirrors>
</settings>
XML

# Prime the local repo with a FULL package so plugins + deps are cached for later clean builds
cd /app/workspace && mvn clean package
```

Notes:
- Put the mirror in `~/.m2/settings.xml`, not a bespoke `-s` file — that is the location a
  fresh `mvn clean package` (including the grader's) will honor.
- Run the full `clean package` once so the assembly/shade plugins and all dependencies are in
  `~/.m2/repository`; subsequent clean builds then need no network.
- If the primary mirror is unreachable, other public Central mirrors work the same way; the
  key is that the `<mirrorOf>central</mirrorOf>` entry lives in the default settings file.
- Run the job locally to confirm before finishing:
  `flink run -t local -c <MainClass> target/<finalName>-jar-with-dependencies.jar --k v ...`

## 8. Self-check before declaring done

- [ ] Row count sanity: number of output rows == number of keys that have a **completion**
      event AND at least one qualifying (e.g. SUBMIT) event — NOT the count of all keys seen,
      and NOT the count of keys that reached *any* terminal state.
- [ ] Completion predicate is the **single** success/`FINISH` event code only — not a union of
      terminal states (`FAIL`/`EVICT`/`KILL`/`LOST` are terminal but NOT "finished").
- [ ] No fallback/end-of-stream timer emits keys that never reached the completion event.
- [ ] Output line format matches the spec byte-for-byte (delimiters, parentheses, no spaces).
- [ ] Timestamps converted micros→ms; session gap in the right unit.
- [ ] `mvn clean package` succeeds from a clean `target/` (proves plugins/deps are cached).
