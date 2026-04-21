# Wrapping External RTL (Verilog / SystemVerilog)

If you already have a design written in Verilog or SystemVerilog, you can wrap it as an Amaranth component and use it in a ChipFlow design. There are two ways to do this:

1. **Manual `Instance(...)`** — you write Python to instantiate the Verilog module and connect its ports. Best for simple modules or one-off wrapping.
2. **TOML-based `RTLWrapper`** — you describe the module in a TOML file and `chipflow.rtl.wrapper` generates the component for you. Best for peripherals that speak Wishbone/CSR/UART/etc., or for SystemVerilog that needs preprocessing.

---

## Manual wrapping with `Instance`

Amaranth's `Instance` construct lets you instantiate a Verilog module and connect its ports to Amaranth signals.

### Add the Verilog file

Place your Verilog source alongside `design.py`:

```
my_design/
├── chipflow.toml
└── design/
    ├── design.py
    └── my_module.v
```

### Example Verilog module

```verilog
// my_module.v
module my_module (
    input  wire       clk,
    input  wire       rst,
    input  wire [7:0] data_in,
    input  wire       enable,
    output reg  [7:0] data_out,
    output wire       valid
);
    assign valid = enable;
    always @(posedge clk or posedge rst) begin
        if (rst)
            data_out <= 8'b0;
        else if (enable)
            data_out <= data_in + 1;
    end
endmodule
```

### Wrap it in Amaranth

In `design.py`, use `Instance()` to instantiate the Verilog module inside `elaborate`. Register the Verilog source file with `platform.add_file()` so it is included in the build.

```python
import pathlib
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, flipped, connect
from chipflow.platform import InputIOSignature, OutputIOSignature

MySignature = wiring.Signature({
    "data_in":  Out(InputIOSignature(8)),
    "enable":   Out(InputIOSignature(1)),
    "data_out": Out(OutputIOSignature(8)),
    "valid":    Out(OutputIOSignature(1)),
})


class MyDesign(wiring.Component):
    design_name = "my_design"

    def __init__(self):
        interfaces = {
            "pins": Out(MySignature),
        }
        super().__init__(interfaces)

    def elaborate(self, platform):
        m = Module()

        # Register the Verilog file with the platform
        verilog_path = pathlib.Path(__file__).parent / "my_module.v"
        platform.add_file(verilog_path.name, verilog_path.read_text())

        # Instantiate the Verilog module
        m.submodules.my_module = Instance("my_module",
            i_clk      = ClockSignal(),
            i_rst      = ResetSignal(),
            i_data_in  = self.pins.data_in.i,
            i_enable   = self.pins.enable.i,
            o_data_out = self.pins.data_out.o,
            o_valid    = self.pins.valid.o,
        )

        return m


MySoC = MyDesign
```

### How Instance ports map

| Prefix | Direction | Description |
|--------|-----------|-------------|
| `i_`   | input     | Drives a Verilog `input` port |
| `o_`   | output    | Reads from a Verilog `output` port |
| `io_`  | bidirectional | For `inout` ports |

- `ClockSignal()` and `ResetSignal()` connect to the default Amaranth clock domain (`sync`).
- Port names after the prefix must match the Verilog port names exactly (e.g., `i_data_in` maps to the Verilog port `data_in`).

### Notes

- `platform.add_file()` takes a filename and its contents as a string. The file is included during synthesis.
- You can instantiate multiple Verilog modules in the same design.
- The Verilog module is synthesised by Yosys alongside the Amaranth-generated RTL — no separate compilation step is needed.
- If your Verilog module uses parameters, pass them with the `p_` prefix: `p_WIDTH=8`.

---

## SystemVerilog

`.sv` files are accepted by `platform.add_file()` — the platform dispatches on extension and passes SystemVerilog sources to Yosys with `read_verilog -sv`. The `Instance(...)` wrapping is identical to plain Verilog.

```python
sv_path = pathlib.Path(__file__).parent / "my_module.sv"
platform.add_file(sv_path.name, sv_path.read_text())
```

Supported extensions: `.v`, `.vh`, `.sv`.

**The built-in parser is limited.** Yosys' `read_verilog -sv` handles simple SV (`logic`, `always_ff` / `always_comb`, generate blocks, basic typedefs) but does **not** accept SystemVerilog package imports (`import pkg::*;`) in any position. Most real-world SV IP — including the OpenHW Group CV32E40P and similar cores — uses packages heavily and will not parse through this path. Non-synthesisable SV (classes, `covergroup`, UVM, most concurrent assertions) isn't needed for synthesis and also isn't supported.

**For SV IP that uses packages, interfaces, typedefs, or packed structs,** preprocess the sources with [sv2v](https://github.com/zachjs/sv2v) first:

```bash
sv2v -I<include_dirs> my_module.sv > my_module.v
```

Then add the generated `.v` file via `platform.add_file("my_module.v", …)` as with plain Verilog. sv2v desugars packages, interfaces, and typedefs into Verilog 2005, which Yosys reads cleanly.

---

## Wrapping external RTL via TOML (`RTLWrapper`)

`chipflow.rtl.wrapper` provides a higher-level alternative to hand-written `Instance(...)` wrapping. Instead of writing Python to connect ports manually, you describe the external module in a TOML file — source files, clocks/resets, bus ports, and pad pins — and get back a `wiring.Component` ready to use in your design.

It also handles source preprocessing: `.sv` files via sv2v, Verilog generated from SpinalHDL (via `sbt`), or SystemVerilog via Yosys' slang frontend.

### How port names work

Verilog port names are whatever the author chose — ChipFlow doesn't dictate them. The `i_` / `o_` / `io_` prefixes you see throughout this doc are *Amaranth Instance kwarg prefixes*: they tag direction on the Python side, and Amaranth strips them to get the underlying Verilog port name.

So for a Verilog port `data_bus`:

- **Input:** Amaranth kwarg is `i_data_bus = <signal>` — the `i_` is Amaranth's direction tag, not part of the Verilog port.
- **Output:** `o_data_bus = <signal>`.
- **Bidir:** `io_data_bus = <signal>`.

`RTLWrapper` follows the same rule. In TOML:

- `[clocks]` and `[resets]` entries give the **Verilog port name as written** — the wrapper adds the `i_` direction tag internally when building the Instance call.
- `[ports.X]` / `[pins.X]` explicit `map` values are the full Amaranth Instance kwarg, so they include the `i_` / `o_` / `io_` direction tag. The text after the prefix is the Verilog port name.
- For known bus interfaces (Wishbone, CSR, UART, SPI, I2C, GPIO), the wrapper can auto-infer the mapping by matching patterns against the parsed Verilog ports.

### Minimal example: a Wishbone timer

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

### Using the wrapper in a design

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

### Key TOML sections

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

### Preprocessing SystemVerilog sources

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
| `systemverilog` | `sv2v` | `sv2v` binary in `PATH` |
| `yosys_slang` | Yosys' slang frontend | Native Yosys with slang plugin (override `yosys_command` in the config); yowasp-yosys's bundled slang currently can't spawn threads and fails on non-trivial designs |
| `spinalhdl` | `sbt` | Scala/sbt toolchain |

The generated Verilog is written to `./build/verilog/<name>.v` by default and fed to the synthesis flow automatically — you don't need to call `add_file` yourself.
