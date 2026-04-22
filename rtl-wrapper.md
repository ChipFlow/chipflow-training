# `RTLWrapper`: Wrapping External RTL via TOML

`chipflow.rtl.wrapper` provides a higher-level alternative to hand-written `Instance(...)` wrapping. Instead of writing Python to connect ports manually, you describe the external module in a TOML file — source files, clocks/resets, bus ports, and pad pins — and get back a `wiring.Component` ready to use in your design.

It also handles source preprocessing: `.sv` files via sv2v, Verilog generated from SpinalHDL (via `sbt`), or SystemVerilog via Yosys' slang frontend.

For manual `Instance(...)` wrapping (no TOML, no preprocessing), see **[Wrapping External RTL](wrapping-external-rtl.md)**.

---

## How port names work

Verilog port names are whatever the author chose — ChipFlow doesn't dictate them. The `i_` / `o_` / `io_` prefixes you see throughout this doc are *Amaranth Instance kwarg prefixes*: they tag direction on the Python side, and Amaranth strips them to get the underlying Verilog port name.

So for a Verilog port `data_bus`:

- **Input:** Amaranth kwarg is `i_data_bus = <signal>` — the `i_` is Amaranth's direction tag, not part of the Verilog port.
- **Output:** `o_data_bus = <signal>`.
- **Bidir:** `io_data_bus = <signal>`.

`RTLWrapper` follows the same rule. In TOML:

- `[clocks]` and `[resets]` entries give the **Verilog port name as written** — the wrapper adds the `i_` direction tag internally when building the Instance call.
- `[ports.X]` / `[pins.X]` explicit `map` values are the full Amaranth Instance kwarg, so they include the `i_` / `o_` / `io_` direction tag. The text after the prefix is the Verilog port name.
- For known bus interfaces (Wishbone, CSR, UART, SPI, I2C, GPIO), the wrapper can auto-infer the mapping by matching patterns against the parsed Verilog ports.

---

## Minimal example: a Wishbone timer

Assume you have a Verilog peripheral `wb_timer.v` with this port list:

```verilog
module wb_timer (
    input  wire        clk,
    input  wire        rst_n,
    // Wishbone classic slave
    input  wire        wb_cyc,
    input  wire        wb_stb,
    input  wire        wb_we,
    input  wire [3:0]  wb_adr,
    input  wire [31:0] wb_dat_w,
    input  wire [3:0]  wb_sel,
    output wire        wb_ack,
    output wire [31:0] wb_dat_r,
    // Interrupt line
    output wire        irq
);
```

The TOML wrapper config (`wb_timer.toml`):

```toml
name = "wb_timer"

[files]
path = "./rtl"              # directory scanned for .v / .sv sources

[clocks]
sys = "clk"                  # Verilog port "clk" — wrapper wires it to ClockSignal() via i_clk
[resets]
sys = "rst_n"                # Verilog port "rst_n" — wired to ~ResetSignal() via i_rst_n

[ports.bus]
interface = "amaranth_soc.wishbone.Signature"
params = { addr_width = 4, data_width = 32, granularity = 8 }
# Each map value is an Amaranth Instance kwarg: direction tag + Verilog port name.
map = { cyc   = "i_wb_cyc",
        stb   = "i_wb_stb",
        we    = "i_wb_we",
        adr   = "i_wb_adr",
        dat_w = "i_wb_dat_w",
        sel   = "i_wb_sel",
        ack   = "o_wb_ack",
        dat_r = "o_wb_dat_r" }

[pins.irq]
interface = "amaranth.lib.wiring.Out(1)"
map = "o_irq"                # direction tag "o_" + Verilog port name "irq"
```

For common bus interfaces (`amaranth_soc.wishbone.Signature`, `amaranth_soc.csr.Signature`) and pin interfaces (UART / SPI / I2C / GPIO from `chipflow.platform`), the wrapper can skip the `map` field when the Verilog port names follow predictable patterns that already include a direction tag (e.g., `i_wb_cyc`, `o_wb_ack`). When names are bare (`wb_cyc`, `wb_ack`) or follow a different convention, provide `map` explicitly as above.

## Using the wrapper in a design

```python
from amaranth import Module
from amaranth.lib import wiring
from chipflow.rtl.wrapper import load_wrapper_from_toml


class MyDesign(wiring.Component):
    # ... signature omitted

    def elaborate(self, platform):
        m = Module()

        # Load the Verilog peripheral as a Component
        m.submodules.timer = timer = load_wrapper_from_toml("wb_timer.toml")

        # `timer.bus` is a Wishbone interface; `timer.irq` is a 1-bit output.
        # Connect them to the rest of your design (e.g., a Wishbone decoder).
        ...

        return m


MySoC = MyDesign
```

The wrapper automatically:

1. Adds the source files via `platform.add_file()`.
2. Creates an `Instance(...)` with all port connections.
3. Hooks clock/reset to the `sync` domain (reset is inverted for active-low `rst_n`).
4. Attaches a `MemoryMap` to any Wishbone port so it can be added to a decoder.

## Key TOML sections

| Section | Purpose |
|---------|---------|
| `name` | Verilog module name (used as `Instance` type) |
| `[files]` | Either `path = "./rtl"` (directory) or `module = "some.python.module"` (resource-packaged RTL) |
| `[clocks]` / `[resets]` | Map Amaranth clock domain name → Verilog port (without `i_` prefix). Domain `sys` means the default `sync` domain. |
| `[ports.<name>]` | Bus interfaces (Wishbone, CSR). Default direction `in` (master connects into this component). |
| `[pins.<name>]` | Pad-facing interfaces (UART, SPI, I2C, GPIO, or simple `Out(N)`/`In(N)`). Default direction `out`. |
| `[generate]` | Optional: preprocess sources before handing to Yosys. |
| `[driver]` | Optional: generate C header/struct for software access. |

Auto-mapping is built in for these interfaces — the wrapper parses the Verilog and matches well-known signal name patterns:

- `amaranth_soc.wishbone.Signature` (`cyc`, `stb`, `we`, `adr`, `dat_w`, `dat_r`, `ack`, …)
- `amaranth_soc.csr.Signature`
- `chipflow.platform.UARTSignature`, `SPISignature`, `I2CSignature`, `GPIOSignature`

For other interfaces, or when the Verilog uses non-standard names, provide an explicit `map` in TOML.

## Verilog module parameters

Verilog `parameter` / `localparam` values can be overridden from TOML, from Python, or both. Declare defaults in the TOML `[parameters]` table:

```toml
name = "wb_timer"

[parameters]
DATA_WIDTH = 32
ADDR_WIDTH = 4
```

At load time, pass a `parameters=` kwarg to override specific values. The Python kwarg wins on collisions; parameters you don't mention fall back to the TOML defaults:

```python
# DATA_WIDTH=64 (override), ADDR_WIDTH=4 (TOML default)
timer = load_wrapper_from_toml("wb_timer.toml", parameters={"DATA_WIDTH": 64})
```

The merged set is emitted as `p_<NAME>=<value>` kwargs on the `Instance(...)` at elaboration — equivalent to `Instance("wb_timer", p_DATA_WIDTH=64, p_ADDR_WIDTH=4, …)`.

When a `[generate]` section is present, the merged parameters are also fed into the generator's template substitution, so SpinalHDL Scala args, sv2v `-D` defines, and yosys-slang `-D` / `--top` placeholders all see the final values. The same `{name}` substitution works in `[ports.*] params = { … }` — writing `params = { addr_width = "{ADDR_WIDTH}" }` resolves against the merged parameters.

## Preprocessing SystemVerilog sources

If your external RTL is SystemVerilog that uses packages/interfaces/typedefs, add a `[generate]` section to preprocess it:

```toml
name = "fancy_peripheral"

[files]
path = "./rtl"

[generate]
generator = "systemverilog"   # = run sv2v

[generate.sv2v]
include_dirs = ["./rtl/include"]
defines = { SYNTHESIS = "1" }
top_module = "fancy_peripheral"

[clocks]
sys = "clk"

# ...ports and pins as usual
```

Generators available:

| `generator` | Tool used | Needs |
|-------------|-----------|-------|
| `verilog` | none (files used as-is) | — |
| `systemverilog` | `sv2v` | `sv2v` binary in `PATH` ([install](https://github.com/zachjs/sv2v#installation)) |
| `yosys_slang` | Yosys' slang frontend | Native Yosys with slang plugin (override `yosys_command` in the config); yowasp-yosys's bundled slang currently can't spawn threads and fails on non-trivial designs |
| `spinalhdl` | `sbt` | Scala/sbt toolchain |

The generated Verilog is written to `./build/verilog/<name>.v` by default and fed to the synthesis flow automatically — you don't need to call `add_file` yourself.

---

## See also

- **[Wrapping CV32E40P](cv32e40p-example.md)** — a worked example: wrapping the OpenHW Group CV32E40P RISC-V core (SystemVerilog with package imports and PULP-style port naming) using sv2v preprocessing and explicit `map` entries.
