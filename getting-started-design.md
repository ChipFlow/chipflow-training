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

## Wrapping existing Verilog / SystemVerilog

Both manual `Instance(...)` wrapping and a TOML-based `RTLWrapper` system are available for integrating external RTL into a ChipFlow design. See **[Wrapping External RTL](wrapping-external-rtl.md)** for the full guide.

---

## Complete example

See the [upcounter](upcounter/) design in this repository for a working example — an 8-bit counter with enable and overflow detection.

For more examples, see [chipflow-examples](https://github.com/ChipFlow/chipflow-examples).
