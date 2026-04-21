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
| `systemverilog` | `sv2v` | `sv2v` binary in `PATH` |
| `yosys_slang` | Yosys' slang frontend | Native Yosys with slang plugin (override `yosys_command` in the config); yowasp-yosys's bundled slang currently can't spawn threads and fails on non-trivial designs |
| `spinalhdl` | `sbt` | Scala/sbt toolchain |

The generated Verilog is written to `./build/verilog/<name>.v` by default and fed to the synthesis flow automatically — you don't need to call `add_file` yourself.

---

## Worked example: wrapping CV32E40P (SystemVerilog RISC-V core)

[CV32E40P](https://github.com/openhwgroup/cv32e40p) is the OpenHW Group's open-source 32-bit RISC-V core. It's a realistic test of the wrapper because:

- The RTL is **SystemVerilog** with package imports (`import cv32e40p_pkg::*;`) — Yosys' built-in SV mode can't parse it, so we need sv2v.
- Port names follow the **PULP `_i` / `_o` suffix convention**, not ChipFlow's `i_` / `o_` prefix — so auto-inference doesn't apply and every port needs an explicit `map`.
- The core uses an **OBI bus** for instruction and data memory, which isn't one of the built-in interfaces. We'll expose each wire individually using `Out(N)` / `In(N)`.

### Prerequisites

- `sv2v` binary installed and in `PATH` ([installation](https://github.com/zachjs/sv2v#installation)).
- CV32E40P sources checked out alongside your design.

### Directory layout

```
my_soc/
├── chipflow.toml
├── cv32e40p/                  # git clone https://github.com/openhwgroup/cv32e40p.git
│   └── rtl/
│       ├── include/
│       │   ├── cv32e40p_pkg.sv
│       │   └── ...
│       ├── cv32e40p_core.sv
│       └── ...
└── design/
    ├── design.py
    └── cv32e40p.toml          # wrapper config (shown below)
```

### Relevant port list (`cv32e40p_core`)

```systemverilog
module cv32e40p_core #(
    parameter COREV_PULP      = 0,
    parameter COREV_CLUSTER   = 0,
    parameter FPU             = 0,   // keep 0 to avoid the FPU wrapper
    parameter ZFINX           = 0,
    parameter NUM_MHPMCOUNTERS = 1
) (
    input  logic        clk_i,
    input  logic        rst_ni,
    input  logic        pulp_clock_en_i,
    input  logic        scan_cg_en_i,
    input  logic [31:0] boot_addr_i,
    input  logic [31:0] mtvec_addr_i,
    input  logic [31:0] dm_halt_addr_i,
    input  logic [31:0] hart_id_i,
    input  logic [31:0] dm_exception_addr_i,
    // Instruction memory (OBI master)
    output logic        instr_req_o,
    input  logic        instr_gnt_i,
    input  logic        instr_rvalid_i,
    output logic [31:0] instr_addr_o,
    input  logic [31:0] instr_rdata_i,
    // Data memory (OBI master)
    output logic        data_req_o,
    input  logic        data_gnt_i,
    input  logic        data_rvalid_i,
    output logic        data_we_o,
    output logic [ 3:0] data_be_o,
    output logic [31:0] data_addr_o,
    output logic [31:0] data_wdata_o,
    input  logic [31:0] data_rdata_i,
    // APU / FPU — exist even with FPU=0; tie off in the design
    // ...
    // Interrupts, debug, control
    input  logic [31:0] irq_i,
    output logic        irq_ack_o,
    output logic [ 4:0] irq_id_o,
    input  logic        debug_req_i,
    output logic        debug_havereset_o,
    output logic        debug_running_o,
    output logic        debug_halted_o,
    input  logic        fetch_enable_i,
    output logic        core_sleep_o
);
```

### Wrapper config (`cv32e40p.toml`)

Because the Verilog ports use `_i` / `_o` suffixes, the `map` values are of the form `i_<full_port_name>` / `o_<full_port_name>` — e.g., `o_instr_req_o` is the Amaranth Instance kwarg `o_instr_req_o`, which Amaranth strips to "output from Verilog port `instr_req_o`".

```toml
name = "cv32e40p_core"

[files]
path = "./cv32e40p/rtl"

[generate]
generator = "systemverilog"   # preprocess with sv2v

[generate.sv2v]
include_dirs = ["./cv32e40p/rtl/include"]
top_module = "cv32e40p_core"

[clocks]
sys = "clk_i"                 # wrapper generates i_clk_i = ClockSignal()

[resets]
sys = "rst_ni"                # i_rst_ni = ~ResetSignal() — active-low reset

# --- Static identity / config inputs (typically tied off) ---
[pins.boot_addr]
interface = "amaranth.lib.wiring.In(32)"
map = "i_boot_addr_i"

[pins.mtvec_addr]
interface = "amaranth.lib.wiring.In(32)"
map = "i_mtvec_addr_i"

[pins.hart_id]
interface = "amaranth.lib.wiring.In(32)"
map = "i_hart_id_i"

[pins.dm_halt_addr]
interface = "amaranth.lib.wiring.In(32)"
map = "i_dm_halt_addr_i"

[pins.dm_exception_addr]
interface = "amaranth.lib.wiring.In(32)"
map = "i_dm_exception_addr_i"

[pins.pulp_clock_en]
interface = "amaranth.lib.wiring.In(1)"
map = "i_pulp_clock_en_i"

[pins.scan_cg_en]
interface = "amaranth.lib.wiring.In(1)"
map = "i_scan_cg_en_i"

# --- Instruction memory bus (OBI master) ---
[pins.instr_req]
interface = "amaranth.lib.wiring.Out(1)"
map = "o_instr_req_o"

[pins.instr_gnt]
interface = "amaranth.lib.wiring.In(1)"
map = "i_instr_gnt_i"

[pins.instr_rvalid]
interface = "amaranth.lib.wiring.In(1)"
map = "i_instr_rvalid_i"

[pins.instr_addr]
interface = "amaranth.lib.wiring.Out(32)"
map = "o_instr_addr_o"

[pins.instr_rdata]
interface = "amaranth.lib.wiring.In(32)"
map = "i_instr_rdata_i"

# --- Data memory bus (OBI master) ---
[pins.data_req]
interface = "amaranth.lib.wiring.Out(1)"
map = "o_data_req_o"

[pins.data_gnt]
interface = "amaranth.lib.wiring.In(1)"
map = "i_data_gnt_i"

[pins.data_rvalid]
interface = "amaranth.lib.wiring.In(1)"
map = "i_data_rvalid_i"

[pins.data_we]
interface = "amaranth.lib.wiring.Out(1)"
map = "o_data_we_o"

[pins.data_be]
interface = "amaranth.lib.wiring.Out(4)"
map = "o_data_be_o"

[pins.data_addr]
interface = "amaranth.lib.wiring.Out(32)"
map = "o_data_addr_o"

[pins.data_wdata]
interface = "amaranth.lib.wiring.Out(32)"
map = "o_data_wdata_o"

[pins.data_rdata]
interface = "amaranth.lib.wiring.In(32)"
map = "i_data_rdata_i"

# --- Interrupts, debug, control (abbreviated; tie off or connect in design) ---
[pins.irq]
interface = "amaranth.lib.wiring.In(32)"
map = "i_irq_i"

[pins.fetch_enable]
interface = "amaranth.lib.wiring.In(1)"
map = "i_fetch_enable_i"

# ... APU interface, debug, core_sleep_o, irq_ack_o, irq_id_o
# all need entries of the same form — every module port must be in `map`.
```

### Using it in a design

```python
from amaranth import Module, Signal, C
from amaranth.lib import wiring
from amaranth.lib.wiring import Out
from chipflow.rtl.wrapper import load_wrapper_from_toml


class MySoC(wiring.Component):
    # ... signature omitted: bring out the OBI buses to chip pads,
    # or connect them to on-chip memory / peripherals.

    def elaborate(self, platform):
        m = Module()

        m.submodules.cpu = cpu = load_wrapper_from_toml("design/cv32e40p.toml")

        # Tie off static/config inputs
        m.d.comb += [
            cpu.boot_addr.eq(C(0x0000_0080, 32)),
            cpu.mtvec_addr.eq(C(0x0000_0000, 32)),
            cpu.hart_id.eq(0),
            cpu.dm_halt_addr.eq(C(0x1A11_0800, 32)),
            cpu.dm_exception_addr.eq(C(0x1A11_1000, 32)),
            cpu.pulp_clock_en.eq(1),
            cpu.scan_cg_en.eq(0),
            cpu.fetch_enable.eq(1),
            cpu.irq.eq(0),
        ]

        # Connect cpu.instr_req / instr_addr / ... to an instruction memory,
        # and cpu.data_req / data_addr / ... to a data memory or bus fabric.
        # ...

        return m


MySoC = MySoC
```

### Caveats

- **Parameters aren't set by the wrapper.** CV32E40P uses its module defaults (`FPU = 0`, `COREV_PULP = 0`, `COREV_CLUSTER = 0`). If you need different values, you'd either need to extend the wrapper or add an `Instance(..., p_FPU=1, ...)` manually.
- **All module ports must appear in `map`.** Unmapped ports will not be connected (the wrapper only wires what you listed).
- **APU/FPU ports exist even when `FPU = 0`** — they must still be wired or tied off. If you don't need the FPU, tie `apu_gnt_i = 0`, `apu_rvalid_i = 0`, `apu_result_i = 0`, `apu_flags_i = 0` in your design and leave the output APU signals unconnected (they'll be driven but go nowhere).
- **Debug interface:** tie `debug_req_i = 0` and ignore `debug_*_o` outputs unless you're wiring up a JTAG debug transport.
- **sv2v must be in `PATH`** when `chipflow silicon prepare` runs. CI/build environments need to have it installed.
