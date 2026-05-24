## chipflow.toml — Configuration Reference

Based on chipflow-lib v0.3.3 Pydantic config models.

---

### Root Structure

All configuration lives under the `[chipflow]` section.

---

### Top-Level Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `project_name` | string | **Yes** | — | Name of the ChipFlow project |
| `top` | dict | No | `{}` | Top-level design config, typically contains `soc = "design.design:MySoC"` |
| `steps` | dict of strings | No | `None` | Step definitions mapping step names to Python class references |
| `clock_domains` | list of strings | No | `None` | Additional clock domain names beyond the default `sync` |

---

### `[chipflow.silicon]`

Required for silicon builds.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `process` | enum | **Yes** | — | Target manufacturing process |
| `package` | string | **Yes** | — | Package identifier (e.g. `"pga144"`, `"block"`) |
| `power` | dict of voltages | No | `{}` | Power domain voltages |
| `debug` | dict of booleans | No | `None` | Debug configuration flags |
| `block` | table | No (Yes when `package = "block"`) | `None` | Per-project block dimensions for hard-macro builds — see [`[chipflow.silicon.block]`](#chipflowsiliconblock) |

**Allowed `process` values:**

| Value | Description |
|-------|-------------|
| `ihp_sg13g2` | IHP 130nm SiGe BiCMOS open-source process |
| `gf180mcu` | GlobalFoundries 180nm MCU open-source PDK — four-size SRAM IP available for automatic memory inference |

**Voltage format:** float or string with optional `V` suffix (e.g. `1.8`, `"1.8V"`, `"1.8v"`).

---

### `[chipflow.silicon.block]`

Required when `package = "block"`, ignored otherwise. Used for hard-macro deliverables — see [Hard-Macro Builds](block-package.md).

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `width` | integer | **Yes** | — | Pin slots on the N and S edges |
| `height` | integer | **Yes** | — | Pin slots on the W and E edges |

```toml
[chipflow.silicon]
process = "ihp_sg13g2"
package = "block"

[chipflow.silicon.block]
width  = 50
height = 80
```

`width`/`height` are pin-slot counts, not microns — the backend translates them using the process's pin pitch.

---

### `[chipflow.silicon.macros]`

Optional. Declares hard macros (NDA SRAMs, vendor IP, PLLs, blocks produced by an earlier `package = "block"` build) for inclusion in the build. See [Using Hard Macros](using-hard-macros.md).

Each entry is keyed by a **logical name** (used from Python as `load_blackbox_wrapper("<logical_name>", ...)`) and points at a `*.blackbox.json` produced by [`macrostrip`](https://github.com/ChipFlow/macrostrip):

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `blackbox` | path | **Yes** | — | Path to a `*.blackbox.json` describing the macro. Relative paths resolve against `CHIPFLOW_ROOT`. |

```toml
[chipflow.silicon.macros.sram_64x64]
blackbox = "vendor/ihp/sram_64x64.blackbox.json"

[chipflow.silicon.macros.pll_core]
blackbox = "vendor/pll/pll_core.blackbox.json"
```

The blackbox JSON itself carries paths to companion artifacts (LEF, Liberty, frame-view or real GDS, Verilog stub), interpreted relative to the JSON's own directory. At submit time those artifacts are packed into `bundle.zip` under `macros/<logical_name>/`.

---

### `[chipflow.backend]`

Optional. Free-form parameters passed through to the ChipFlow cloud backend. Everything under this table is copied verbatim into the submission bundle's `manifest.json` under the `backend` key — `chipflow-lib` does no validation. The backend owns the schema, so new knobs can be exposed without a chipflow-lib release.

When the table is empty or absent, the `backend` key is omitted from the manifest entirely.

The currently documented knobs are below. For the build-mode switch (`full` vs `synth_only`), see [Build modes](training-commands.md#build-modes) — that one is set via CLI flag or environment variable, not under this table.

#### `[chipflow.backend.check.drc]`

Controls DRC sign-off on the post-route GDS. The DRC check has two independent engines — the foundry-shipped KLayout decks (gated by `enable` + `level`) and Magic DRC (gated by `magic`). Either, both, or neither can run on any given build.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enable` | bool | No | `false` | `true` runs KLayout DRC against the PDK's deck list. |
| `level` | string | No | `"default"` | KLayout deck tier (PDK-specific — see below). Ignored when `enable = false`. |
| `magic` | bool | No | `false` | `true` also runs Magic DRC (gf180mcu only). Independent of `enable`. |

**Allowed `level` values per process:**

| Process | Level | What it runs |
|---------|-------|--------------|
| `gf180mcu` | `fast` | Antenna check only — quickest sanity check. |
|  | `default` | Main DRC deck + antenna. The everyday choice. |
|  | `signoff` | Main DRC + antenna + density rules. Use for tape-out. |

```toml
[chipflow.backend.check.drc]
enable = true              # KLayout decks
level  = "default"
magic  = true              # Magic DRC as a second-opinion engine
```

When enabled, each engine's report lands in the build's `outputs.zip`:

- KLayout decks → `drc_<deck_name>.lyrdb` (one file per deck, openable in the KLayout GUI)
- Magic DRC → `drc_magic` (`magic_drc.rpt` text report)

#### `[chipflow.backend.check.lvs]`

Controls KLayout LVS sign-off (post-route GDS vs synthesised netlist).

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enable` | bool | No | `false` | `true` runs LVS. |

```toml
[chipflow.backend.check.lvs]
enable = true
```

Both checks are **opt-in** — a build with no `[chipflow.backend.check.*]` entries skips them and finishes faster. Turn them on for tape-out-grade builds, leave them off during early iteration.

#### `[chipflow.backend.fill]`

Controls post-route metal fill (added to satisfy minimum metal-density rules). Currently meaningful only for `gf180mcu` — the `signoff` DRC level enforces ≥30% coverage on metals M1–M5 and ≥14% on Poly2, which raw designs almost never hit without added fill.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `magic` | bool | No | `false` | `true` runs Magic's metal-fill on the post-PnR GDS and merges the result into the final layout. |

```toml
[chipflow.backend.fill]
magic = true
```

Fill runs before DRC, so a typical tape-out config combines all three knobs:

```toml
[chipflow.backend.check.drc]
enable = true
level  = "signoff"

[chipflow.backend.check.lvs]
enable = true

[chipflow.backend.fill]
magic = true
```

---

### `[chipflow.simulation]`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `num_steps` | integer | No | `3000000` | Number of simulation timesteps to run |

---

### `[chipflow.software.riscv]`

Compiler configuration for RISC-V based designs.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `cpu` | string | Yes (if section present) | — | CPU architecture string (e.g. `"baseline_rv32-a-c-d"`) |
| `abi` | string | Yes (if section present) | — | ABI string (e.g. `"ilp32"`) |

---

### `[chipflow.test]`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `event_reference` | path | Yes (if section present) | — | Path to event reference file for testing |

---

### Minimal Example

For a simple design targeting IHP SG13G2:

```toml
[chipflow]
project_name = "my_design"

[chipflow.top]
soc = "design.design:MySoC"

[chipflow.silicon]
process = "ihp_sg13g2"
package = "pga144"
```

### Full Example

```toml
[chipflow]
project_name = "my_soc"
clock_domains = ["fast_clk"]

[chipflow.top]
soc = "design.design:MySoC"

[chipflow.steps]
silicon = "chipflow_lib.steps.silicon:SiliconStep"

[chipflow.silicon]
process = "ihp_sg13g2"
package = "pga144"

[chipflow.silicon.power]
vdd = 1.8
vss = 0.0

[chipflow.silicon.debug]
heartbeat = true

[chipflow.simulation]
num_steps = 5000000

[chipflow.software.riscv]
cpu = "baseline_rv32-a-c-d"
abi = "ilp32"

[chipflow.test]
event_reference = "tests/events.txt"
```

---

### Legacy Fields (Ignored)

The following sections appear in older TOML files but are **not parsed** by chipflow-lib and have no effect:

- `[chipflow.clocks]` — silently ignored
- `[chipflow.resets]` — silently ignored
- `[chipflow.silicon.pads]` — silently ignored
