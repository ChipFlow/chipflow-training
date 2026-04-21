# ChipFlow Training

Training materials for learning the [ChipFlow platform](https://build.chipflow.com) — a cloud-based RTL-to-GDS chip design service.

## What's included

- **[Creating a Design for Use with the ChipFlow Platform](getting-started-design.md)** — how to create a new design from scratch for the ChipFlow platform
- **[Wrapping External RTL](wrapping-external-rtl.md)** — integrating existing Verilog or SystemVerilog modules into an Amaranth design (manual `Instance`)
- **[`RTLWrapper` (TOML-based wrapping)](rtl-wrapper.md)** — higher-level wrapper with auto-mapping and sv2v preprocessing
- **[Wrapping CV32E40P](cv32e40p-example.md)** — worked example: wrapping the OpenHW Group RISC-V core with sv2v and `RTLWrapper`
- **Upcounter example** — a simple Amaranth HDL design targeting the IHP SG13G2 130nm process, ready to build and submit to the platform
- **[Training Command Reference](training-commands.md)** — step-by-step guide covering prerequisites, setup, authentication, building, and submitting designs
- **[chipflow.toml Reference](chipflow-toml-reference.md)** — complete configuration format documentation
- **[Simulation](simulation.md)** — testing designs locally with CXXRTL-based simulation
- **[Upcounter Simulation Walkthrough](upcounter-walkthrough.md)** — step-by-step guide to simulating the upcounter with waveforms

## Quick start

```bash
# Clone this repo
git clone https://github.com/ChipFlow/chipflow-training.git
cd chipflow-training

# Install dependencies
make init

# Build and submit the upcounter design
make upcounter-submit
```

See the [Training Command Reference](training-commands.md) for detailed instructions including prerequisites for macOS, Linux, and Windows.

## Project structure

```
chipflow-training/
├── Makefile                    # Build commands
├── pyproject.toml              # Python dependencies
├── getting-started-design.md   # How to write a new design
├── wrapping-external-rtl.md    # Wrapping Verilog / SystemVerilog IP (manual Instance)
├── rtl-wrapper.md              # TOML-based RTLWrapper reference
├── cv32e40p-example.md         # CV32E40P worked example
├── training-commands.md        # Full training guide
├── chipflow-toml-reference.md  # Configuration reference
├── simulation.md               # Simulation guide
└── upcounter/
    ├── chipflow.toml           # Design config (process, package)
    └── design/
        └── design.py           # Amaranth HDL upcounter design
```

## Links

- [ChipFlow Platform](https://build.chipflow.com)
- [chipflow-lib](https://github.com/ChipFlow/chipflow-lib) — core client library
- [chipflow-examples](https://github.com/ChipFlow/chipflow-examples) — additional example designs
