# Hard-Macro Builds (`package = "block"`)

A "block" build produces a **hard-macro deliverable** instead of a packaged chip — LEF, Liberty (`.lib`), GDS, and a blackbox Verilog stub that a parent chip design can instantiate. Use this when you're delivering reusable IP to be integrated into someone else's chip rather than building a standalone chip yourself.

For a normal packaged-chip build, see [Creating a Design for Use with the ChipFlow Platform](getting-started-design.md). For instantiating a block (this build's output, or any third-party hard macro) inside another design, see [Using Hard Macros](using-hard-macros.md).

---

## When to use it

- You want to **ship an IP block** (analog macro, hardened CPU/peripheral, NDA IP) that another team will instantiate in their chip.
- You need a **physical implementation** (placed/routed, with timing models) rather than just RTL.
- You don't want pads, package bringup, or fixed clock/reset/JTAG slot reservations — block builds skip all of that.

If you just want to manufacture a chip, use a chip package (`pga144` etc.) instead.

---

## chipflow.toml

```toml
[chipflow]
project_name = "my_block"

[chipflow.top]
soc = "design.design:MySoC"

[chipflow.silicon]
process = "ihp_sg13g2"
package = "block"

[chipflow.silicon.block]
width  = 50    # pin slots on the N and S edges
height = 80    # pin slots on the W and E edges
```

`width` and `height` are **pin-slot counts** — how many signal pins fit along each edge. The backend converts them to physical microns using the process's pin pitch. Make them generous enough for every signal in your design (the build fails if you run out of slots).

## What's different vs a chip build

| | Chip (`pga144`, …) | Block (`block`) |
|---|---|---|
| Pin numbering | Anti-clockwise from top-left | Per-edge `(side, index)` |
| Bringup pins (clock/reset/JTAG/power at fixed slots) | Yes | No — clock and reset go through regular pins; power comes via straps from the parent |
| Pad cells | Yes | No |
| Floorplan | Fixed package size | Sized from `width`/`height` × pin pitch (or auto-promoted to fixed size if the perimeter dominates) |
| Outputs | GDS | GDS + LEF + Liberty `.lib` + blackbox `.bb.v` |

---

## Build outputs

After a successful block submission you can download:

| File | What it is |
|---|---|
| `<design>.gds` | Final layout |
| `<design>.lef` | Abstract view for the parent's place-and-route — pin locations + obstructions, with `USE POWER`/`USE GROUND` PINs at the boundary so the parent connects power by abutment |
| `<design>_typ.lib` | Liberty timing model (typ corner) for the parent's STA |
| `<design>.bb.v` | Blackbox Verilog stub — module declaration + ports + `(* blackbox *)` attribute, no implementation; what the parent's RTL imports |

The stub looks like:

```verilog
(* blackbox *)
module my_block (clk, rst_n, soc_pins_count_0, ...);
  input clk;
  input rst_n;
  output soc_pins_count_0;
  // ...
endmodule
```

---

## Submitting

Identical to a chip build:

```bash
CHIPFLOW_ROOT=my_block uv run chipflow pin lock
CHIPFLOW_ROOT=my_block uv run chipflow silicon submit
```

The platform detects `package = "block"` from the lockfile and runs the macro build flow (synth → floorplan → PDN → place → CTS → route → fill → GDS → abstract).

---

## Caveats

- **Clock and reset go through ordinary pins** — there's no fixed `clk`/`rst_n` slot. They're declared like any other I/O in your design and end up on the perimeter wherever pin allocation places them.
- **Power is by abutment.** The block emits M1 followpin stubs at the boundary as VDD/VSS LEF PINs; the parent must abut to those (or run straps over the macro). There are no dedicated power pads.
- **No bringup harness.** JTAG, scan, and other bringup logic that a chip flow inserts automatically is **not** added. If your block needs them, instantiate them in your design.
