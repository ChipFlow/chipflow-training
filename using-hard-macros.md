# Using Hard Macros (`load_blackbox_wrapper`)

`chipflow.rtl.load_blackbox_wrapper` instantiates a hard macro (SRAM, PLL, vendor IP, an NDA cell, or a block produced by a previous [`package = "block"`](block-package.md) build) inside an Amaranth design. The macro's physical artifacts — LEF, Liberty, frame-view or real GDS, Verilog stub — travel with the submission so the platform's place-and-route can integrate them without exposing layout to anyone who shouldn't see it.

For producing a hard macro, see **[Hard-Macro Builds](block-package.md)**. For wrapping plain Verilog/SystemVerilog RTL, see **[Wrapping External RTL](wrapping-external-rtl.md)** or **[`RTLWrapper`](rtl-wrapper.md)**.

---

## How it fits together

Hard-macro integration uses two tools:

1. **[`macrostrip`](https://github.com/ChipFlow/macrostrip)** — runs once per macro to produce a `*.blackbox.json` describing the macro (pin list, physical dimensions, paths to LEF/Liberty/GDS/stub). For NDA macros, `macrostrip frame` first replaces the real GDS with a frame view that has the same boundary and pin geometry but no internal layout.
2. **chipflow-lib** — `load_blackbox_wrapper` reads the JSON and gives you an Amaranth `wiring.Component` you instantiate like any other submodule. At submit time, the macro's companion files are packed into the submission `bundle.zip` under `macros/<logical_name>/`.

The `*.blackbox.json` is the single contract between the two tools — once it exists, the chipflow side doesn't care where it came from.

---

## Declaring a macro in `chipflow.toml`

Each macro is given a **logical name** (the key you'll use from Python) and pointed at its blackbox JSON:

```toml
[chipflow.silicon.macros.sram_64x64]
blackbox = "vendor/ihp/sram_64x64.blackbox.json"

[chipflow.silicon.macros.pll_core]
blackbox = "vendor/pll/pll_core.blackbox.json"
```

`blackbox` is a path relative to `CHIPFLOW_ROOT`. Companion-file paths inside the JSON are interpreted relative to the JSON's own directory, so a typical layout looks like:

```
my_design/
├── chipflow.toml
├── design/design.py
└── vendor/ihp/
    ├── sram_64x64.blackbox.json
    ├── sram_64x64.lef
    ├── sram_64x64.lib
    ├── sram_64x64.gds       # frame-view for NDA, real GDS otherwise
    └── sram_64x64.v         # blackbox Verilog stub
```

---

## Instantiating from Python

```python
from amaranth import Module
from amaranth.lib import wiring
from chipflow.rtl import load_blackbox_wrapper


class MyDesign(wiring.Component):
    # ... signature omitted

    def elaborate(self, platform):
        m = Module()

        m.submodules.sram = sram = load_blackbox_wrapper(
            "sram_64x64",
            clocks={"sys": "CLK"},
            resets={"sys": "RST_N"},
        )

        # sram.signature has one member per signal pin (In(width) / Out(width)).
        # Power and ground pins are handled by the platform — not visible here.
        m.d.sync += sram.A.eq(addr)
        m.d.sync += sram.D.eq(write_data)
        m.d.comb += read_data.eq(sram.Q)

        return m
```

The returned `BlackboxWrapper` is a `wiring.Component` whose signature mirrors the macro's **signal pins**:

- Direction `in` → `In(width)`
- Direction `out` → `Out(width)`
- Power, ground, clock, and reset pins are **omitted from the signature** — clocks and resets are wired via the `clocks=` / `resets=` arguments, and power/ground are connected at the platform/PDN level.
- `inout` signal pins are not auto-wrapped; declare them explicitly if needed.

`clocks` / `resets` map an Amaranth clock-domain name to the macro's pin name (the LEF pin, verbatim — typically uppercase). `RST_N` is wired with active-low semantics, matching `RTLWrapper`.

---

## What gets uploaded

When you run `chipflow silicon submit`, every macro you instantiated is packed into `bundle.zip` alongside the RTLIL and `pins.lock`:

```
bundle.zip
├── manifest.json
├── top.il
├── pins.lock
└── macros/
    └── sram_64x64/
        ├── sram_64x64.lef
        ├── sram_64x64.lib
        ├── sram_64x64.gds
        ├── sram_64x64.v
        └── sram_64x64.blackbox.json
```

The manifest carries a `"macros"` dict keyed by logical name with `_file`-suffixed paths to each artifact, so the backend can locate them without parsing the JSON itself. The platform feeds them to OpenROAD as `ADDITIONAL_LEFS` / `ADDITIONAL_LIBS` / `ADDITIONAL_GDS_FILES`.

---

## Security model

There are two tiers of protection for the macro layout, depending on how strict your IP-handling requirements are. Both use the same `load_blackbox_wrapper` API — the difference is only what gets bundled into the submission.

### Tier 1 — Real layout never leaves your premises

For NDA macros (vendor IP, foundry SRAMs, anything where the agreement bars *any* external transmission of the GDS):

- Use `macrostrip frame` to produce a **frame-view GDS** — same boundary and pin geometry, **no internal layout**. Roughly the GDS analogue of a LEF abstract.
- The submission carries the frame view + LEF + Liberty + Verilog stub — the artifacts vendor NDAs typically permit sharing with foundries and EDA tools anyway.
- After the build returns, `macrostrip swap` substitutes the **real** GDS back in locally before tape-out.
- The cloud sees, stores, and processes only abstracts. The real layout never reaches it.

This is the right tier when the customer's NDA explicitly forbids external transmission of the macro GDS, or when "real GDS in a third-party cloud" is itself the concern.

### Tier 2 — Real layout goes to the cloud, isolated within ChipFlow's tenancy

For internal IP, your own block builds, open-source macros, or vendor IP whose NDA permits use in cloud EDA services:

- Skip `macrostrip frame` and point `macrostrip blackbox` at the real GDS directly.
- The real layout travels in `bundle.zip` and is processed inside ChipFlow's cloud environment. It's isolated per customer (auth-scoped storage, internal access controls), not shared with other customers, and not transmitted to third parties.
- Common case: the layout shouldn't end up in competitors' hands, but trusting ChipFlow as a vendor is fine — the same trust posture you'd extend to a hosted EDA tool.

For ChipFlow's specific data-handling commitments (tenancy boundaries, retention, internal access, sub-processors, audit), see ChipFlow's published policy or contact the team.

### Choosing a tier

| You want… | Use |
|---|---|
| Real GDS never on a third-party server | Tier 1 (frame workflow) |
| Real GDS not exposed to other customers or third parties, but ChipFlow as vendor is OK | Tier 2 (real GDS) |
| Macro is open-source / public IP | Tier 2 (or skip the security framing entirely) |

Tier 2 is the simpler workflow (no frame/swap step). Tier 1 is the right answer whenever the contract requires it — when in doubt, ask the IP owner what artifacts they permit you to send to a cloud EDA service.

---

## NDA vs non-NDA workflows

The same `load_blackbox_wrapper` path serves both tiers above. The difference is purely how you produce the JSON.

**NDA macros** (you've signed something — vendor IP, foundry SRAMs you can't redistribute):

```bash
# 1. Strip the real GDS down to a frame view (same boundary + pin geometry, no internal layout).
macrostrip frame --gds real.gds --top SRAM_64X64 -o sram_64x64.gds

# 2. Build the blackbox JSON pointing at the frame GDS.
macrostrip blackbox \
  --lef sram_64x64.lef --top SRAM_64X64 \
  --frame-gds sram_64x64.gds \
  --liberty sram_64x64.lib \
  --verilog-stub sram_64x64.v \
  -o sram_64x64.blackbox.json

# 3. After the build returns, swap the real GDS back into the result before tape-out.
macrostrip swap --result build.gds --real real.gds --top SRAM_64X64 -o build.final.gds
```

The frame view is what travels to ChipFlow; the real layout never leaves your premises.

**Non-NDA macros** (anything you're free to ship in full — your own block from a previous `package = "block"` build, open-source IP, etc.):

```bash
# Skip the frame step — point macrostrip at the real GDS directly.
macrostrip blackbox \
  --lef macro.lef --top MY_MACRO \
  --frame-gds macro.real.gds \
  --liberty macro.lib \
  --verilog-stub macro.v \
  -o macro.blackbox.json
```

The schema field is named `frame_gds` for historical reasons but chipflow-lib treats it as "the GDS to include" — frame-view or real, the submission path is identical. Skip `macrostrip swap` on return: there's nothing to substitute back.

---

## See also

- **[Hard-Macro Builds](block-package.md)** — produce a macro using ChipFlow (the inverse operation).
- **[macrostrip](https://github.com/ChipFlow/macrostrip)** — the tool that produces the `*.blackbox.json`.
- **[`RTLWrapper`](rtl-wrapper.md)** — wrapping ordinary Verilog/SystemVerilog RTL (no physical artifacts).
