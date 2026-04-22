# Wrapping CV32E40P (SystemVerilog RISC-V core)

A worked example of wrapping a real-world SystemVerilog IP with `RTLWrapper`. See **[`RTLWrapper`: Wrapping External RTL via TOML](rtl-wrapper.md)** for the general reference.

[CV32E40P](https://github.com/openhwgroup/cv32e40p) is the OpenHW Group's open-source 32-bit RISC-V core. It's a realistic test of the wrapper because:

- The RTL is **SystemVerilog** with package imports (`import cv32e40p_pkg::*;`) — Yosys' built-in SV mode can't parse it, so we need sv2v.
- Port names follow the **PULP `_i` / `_o` suffix convention**, not ChipFlow's `i_` / `o_` prefix — so auto-inference doesn't apply and every port needs an explicit `map`.
- The core uses an **OBI bus** for instruction and data memory, which isn't one of the built-in interfaces. We'll expose each wire individually using `Out(N)` / `In(N)`.

## Prerequisites

- `sv2v` binary installed and in `PATH` ([installation](https://github.com/zachjs/sv2v#installation)).
- CV32E40P sources checked out alongside your design.

## Directory layout

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

## Relevant port list (`cv32e40p_core`)

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

## Wrapper config (`cv32e40p.toml`)

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

# Verilog module parameter overrides — emitted as p_<NAME> on the Instance.
# Override any of these from Python via
# `load_wrapper_from_toml("cv32e40p.toml", parameters={"FPU": 1})`.
[parameters]
COREV_PULP       = 0
COREV_CLUSTER    = 0
FPU              = 0    # keep 0 to avoid pulling in the FPU wrapper
ZFINX            = 0
NUM_MHPMCOUNTERS = 1

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

## Using it in a design

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

## Caveats

- **All module ports must appear in `map`.** Unmapped ports will not be connected (the wrapper only wires what you listed).
- **APU/FPU ports exist even when `FPU = 0`** — they must still be wired or tied off. If you don't need the FPU, tie `apu_gnt_i = 0`, `apu_rvalid_i = 0`, `apu_result_i = 0`, `apu_flags_i = 0` in your design and leave the output APU signals unconnected (they'll be driven but go nowhere).
- **Debug interface:** tie `debug_req_i = 0` and ignore `debug_*_o` outputs unless you're wiring up a JTAG debug transport.
- **sv2v must be in `PATH`** when `chipflow silicon prepare` runs. CI/build environments need to have it installed.
