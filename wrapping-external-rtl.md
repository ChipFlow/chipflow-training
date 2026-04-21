# Wrapping External RTL (Verilog / SystemVerilog)

If you already have a design written in Verilog or SystemVerilog, you can wrap it as an Amaranth component and use it in a ChipFlow design. There are two ways to do this:

1. **Manual `Instance(...)`** — you write Python to instantiate the Verilog module and connect its ports. Best for simple modules or one-off wrapping. Covered below.
2. **TOML-based `RTLWrapper`** — you describe the module in a TOML file and `chipflow.rtl.wrapper` generates the component for you. Best for peripherals that speak Wishbone/CSR/UART/etc., or for SystemVerilog that needs preprocessing. See **[`RTLWrapper`: Wrapping External RTL via TOML](rtl-wrapper.md)**.

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

## See also

- **[`RTLWrapper`: Wrapping External RTL via TOML](rtl-wrapper.md)** — higher-level TOML-based wrapping, with built-in sv2v / SpinalHDL / yosys-slang preprocessing and a worked CV32E40P example.
