# Benchmark answer keys

`bench/<venue>/answer_key.json` holds human ground truth for one walkthrough video.
`bench/example/answer_key.json` is **illustrative only**: invented numbers that show the schema.
It is not a real venue and must not be cited as a result.

## Schema

```json
{
  "venue": "office",
  "video_sha256": "<sha256 of prepared.mp4 from prepare_video>",
  "source": "tape",
  "doors": [{"t_s": 12.4, "kind": "door", "measured_width_m": 0.91}]
}
```

- `kind`: `door`, `opening`, `exit` or `stair`. Doors and openings match each other; exits and stairs match each other. Precision counts every extracted door, stair and exit, so an unlisted stair or exit lowers it.
- `source`: `tape` (hand-measured) or `roomplan` (LiDAR iPhone scan, saved as a second key).
- `t_s`: seconds into the **prepared** video. `measured_width_m` is the clear width, or `null`.

## Capture rules

1. Get SHACK15 staff permission first. Film empty areas; keep identifiable people out of frame.
2. Three walkthroughs of 90-150 s: a SHACK15 area, an office, a home.
3. Landscape, walking slowly, pause about 2 s facing each door.
4. A second person notes the timestamp at every door and exit.
5. Tape-measure at least 5 clear widths per venue, including the anchor door.
6. Optional: with a LiDAR iPhone, also save a RoomPlan scan as a second key (`"source": "roomplan"`).
7. Run `prepare_video` and record the prepared file's sha256 in the key. Timestamps refer to that file.

Place the raw video at `bench/<venue>/walkthrough.mp4` (not committed) or pass `--video`.

## Running

```
PYTHONPATH=backend python -m walktwin.benchmark run --venue bench/office --modes static,static_hifps,agentic,agentic_loop
```

Writes `runtime/bench/<venue>.json` after each mode (one row per mode; the `agentic_loop` receipt is the agentic extraction it started from; geometry is "unavailable" with a reason when SfM failed) and receipts in `runtime/bench/receipts/`.
Needs `GEMINI_API_KEY`. Only numbers this CLI produces may be reported.
