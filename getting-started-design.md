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

`chipflow.rtl.wrapper` offers a higher-level alternative to hand-written `Instance(...)` wrapping. A TOML file describes the external module — source files, clocks/resets, ports, and their mapping to Amaranth interface signatures (Wishbone, CSR, UART, I2C, SPI, GPIO). Port-name patterns are auto-inferred from the Verilog where possible.

It also has built-in preprocessing hooks for:

- **SpinalHDL** — runs `sbt` to generate Verilog from a Scala project.
- **sv2v** — runs sv2v on a directory of `.sv` files (sv2v must be in `PATH`).
- **yosys-slang** — uses Yosys' slang frontend (fully supported in native Yosys with the slang plugin).

Entry point: `chipflow.rtl.wrapper.load_wrapper_from_toml(path)`. This returns a `wiring.Component` you can instantiate in your design. See `chipflow/rtl/wrapper.py` in the installed package for the TOML schema (`ExternalWrapConfig`).

---

## Complete example

See the [upcounter](upcounter/) design in this repository for a working example — an 8-bit counter with enable and overflow detection.

For more examples, see [chipflow-examples](https://github.com/ChipFlow/chipflow-examples).
