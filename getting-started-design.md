# Creating a Design for Use with the ChipFlow Platform

This guide walks you through creating a new hardware design using [Amaranth HDL](https://amaranth-lang.org/) and submitting it to the [ChipFlow platform](https://build.chipflow.com) for RTL-to-GDS silicon build.

## Before you begin

Make sure you have the prerequisites installed and the training repo set up. See the [Training Command Reference](training-commands.md) for details.

---

## Step 1: Create the design directory

Each design lives in its own directory with a `chipflow.toml` config and a `design/` sub-directory containing the HDL code:

```
my_design/
├── chipflow.toml
└── design/
    └── design.py
```

```bash
mkdir -p my_design/design
```

---

## Step 2: Write the chipflow.toml

Create `my_design/chipflow.toml` with the minimum required configuration:

```toml
[chipflow]
project_name = "my_design"

[chipflow.top]
soc = "design.design:MySoC"

[chipflow.silicon]
process = "ihp_sg13g2"
package = "pga144"
```

| Field | Description |
|-------|-------------|
| `project_name` | A unique name for your design |
| `soc` | Python import path to your top-level component, in `module:class` format |
| `process` | Target manufacturing process (`ihp_sg13g2` — IHP 130nm) |
| `package` | Chip package type |

See [chipflow.toml Reference](chipflow-toml-reference.md) for the full list of options.

---

## Step 3: Write the design

Create `my_design/design/design.py`. A ChipFlow design is an Amaranth `wiring.Component` with I/O defined through pin signatures.

### Imports

```python
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, flipped, connect
from chipflow.platform import InputIOSignature, OutputIOSignature
```

### Define I/O signatures

Use `InputIOSignature(width)` and `OutputIOSignature(width)` to declare chip-level I/O pins. The `width` parameter sets the bit-width of the signal.

- **`InputIOSignature(width)`** — data flowing **into** the chip. Provides an `.i` signal you read from.
- **`OutputIOSignature(width)`** — data flowing **out of** the chip. Provides an `.o` signal you drive.

Group your I/O into a signature:

```python
MySignature = wiring.Signature({
    "data_in":  Out(InputIOSignature(8)),    # 8-bit input
    "enable":   Out(InputIOSignature(1)),    # 1-bit input
    "data_out": Out(OutputIOSignature(8)),   # 8-bit output
    "valid":    Out(OutputIOSignature(1)),   # 1-bit output
})
```

> **Note:** Members in the signature use `Out(...)` because the top-level component _provides_ these interfaces to the platform for pad connection.

### Write the component

```python
class MyDesign(wiring.Component):
    design_name = "my_design"

    def __init__(self):
        interfaces = {
            "pins": Out(MySignature),
        }
        super().__init__(interfaces)

    def elaborate(self, platform):
        m = Module()

        # Read inputs via .i
        # Drive outputs via .o
        m.d.comb += self.pins.data_out.o.eq(self.pins.data_in.i)
        m.d.comb += self.pins.valid.o.eq(self.pins.enable.i)

        return m

# Entry point — referenced by chipflow.toml [chipflow.top] soc
MySoC = MyDesign
```

### Key rules

- The class must inherit from `wiring.Component`.
- The class must have a `design_name` attribute matching your `project_name` in `chipflow.toml`.
- The `__init__` must define a `"pins"` interface containing your I/O signature.
- The `elaborate` method returns an Amaranth `Module` with your logic.
- The module must export a `MySoC` alias (or whatever name you set in the `soc` field of `chipflow.toml`).

### Combinational vs sequential logic

Amaranth provides two signal domains:

```python
# Combinational — output updates immediately when inputs change
m.d.comb += output.eq(input_a & input_b)

# Synchronous — output updates on the rising clock edge
m.d.sync += counter.eq(counter + 1)
```

Use `m.If`, `m.Elif`, `m.Else` for conditional logic:

```python
with m.If(self.pins.enable.i):
    m.d.sync += counter.eq(counter + 1)
with m.Else():
    m.d.sync += counter.eq(0)
```

---

## Step 4: Add to the Makefile

Add a build target for your design in the `Makefile`:

```makefile
$(eval $(call soc_target, my_design))
```

This generates the following targets automatically:

| Target | What it does |
|--------|-------------|
| `make my_design` | Pin lock + prepare RTLIL |
| `make my_design-submit` | Prepare + submit to ChipFlow platform |
| `make my_design-clean` | Delete build outputs |

---

## Step 5: Build and submit

```bash
# Install / update dependencies
make init

# Build and submit
make my_design-submit
```

Or run the chipflow commands directly:

```bash
CHIPFLOW_ROOT=my_design uv run chipflow pin lock
CHIPFLOW_ROOT=my_design uv run chipflow silicon prepare
CHIPFLOW_ROOT=my_design uv run chipflow silicon submit
```

Check your build results at https://build.chipflow.com.

---

## Wrapping an existing Verilog module

If you already have a design written in Verilog, you can wrap it as an Amaranth component and use it in a ChipFlow design. Amaranth's `Instance` construct lets you instantiate a Verilog module and connect its ports to Amaranth signals.

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

### SystemVerilog

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

### Wrapping external RTL via TOML (`RTLWrapper`)

`chipflow.rtl.wrapper` provides a higher-level alternative to hand-written `Instance(...)` wrapping. Instead of writing Python to connect ports manually, you describe the external module in a TOML file — source files, clocks/resets, bus ports, and pad pins — and get back a `wiring.Component` ready to use in your design.

It also handles source preprocessing: `.sv` files via sv2v, Verilog generated from SpinalHDL (via `sbt`), or SystemVerilog via Yosys' slang frontend.

#### Port naming convention

The wrapper expects the external Verilog module to follow ChipFlow's direction-prefix naming:

| Prefix | Meaning |
|--------|---------|
| `i_` | input port |
| `o_` | output port |
| `io_` | bidirectional port |

In TOML, you reference ports **without the prefix** — the wrapper adds it. If the Verilog port is `i_clk`, the TOML entry is `clk`.

If your external RTL doesn't use these prefixes, you either need to rename the ports in a thin wrapper `.v` file, or use the manual `Instance(...)` approach described above.

#### Minimal example: a Wishbone timer

Assume you have a Verilog peripheral `wb_timer.v` with this port list:

```verilog
module wb_timer (
    input  wire        i_clk,
    input  wire        i_rst_n,
    // Wishbone classic slave
    input  wire        i_wb_cyc,
    input  wire        i_wb_stb,
    input  wire        i_wb_we,
    input  wire [3:0]  i_wb_adr,
    input  wire [31:0] i_wb_dat_w,
    input  wire [3:0]  i_wb_sel,
    output wire        o_wb_ack,
    output wire [31:0] o_wb_dat_r,
    // Interrupt line
    output wire        o_irq
);
```

The TOML wrapper config (`wb_timer.toml`):

```toml
name = "wb_timer"

[files]
path = "./rtl"              # directory scanned for .v / .sv sources

[clocks]
sys = "clk"                  # i_clk, connected to ClockSignal() of "sync" domain

[resets]
sys = "rst_n"                # i_rst_n, connected to ~ResetSignal()

[ports.bus]
interface = "amaranth_soc.wishbone.Signature"
params = { addr_width = 4, data_width = 32, granularity = 8 }
# No `map` — auto-inferred from Wishbone signal names (i_wb_cyc, o_wb_ack, ...)

[pins.irq]
interface = "amaranth.lib.wiring.Out(1)"
map = "o_irq"                # explicit mapping for a simple 1-bit signal
```

#### Using the wrapper in a design

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

#### Key TOML sections

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

#### Preprocessing SystemVerilog sources

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

---

## Complete example

See the [upcounter](upcounter/) design in this repository for a working example — an 8-bit counter with enable and overflow detection.

For more examples, see [chipflow-examples](https://github.com/ChipFlow/chipflow-examples).
