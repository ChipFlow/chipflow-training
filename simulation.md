# Simulation

ChipFlow provides a CXXRTL-based simulation platform for testing designs locally before submitting them for a silicon build.

## How it works

The simulation pipeline:

1. Converts your Amaranth design to RTLIL, then to C++ via Yosys's CXXRTL backend.
2. Compiles it into a native executable (`sim_soc`).
3. Runs it for a configurable number of clock cycles.

## Commands

```bash
# Build the simulation model
CHIPFLOW_ROOT=my_design uv run chipflow sim build

# Build and run the simulation
CHIPFLOW_ROOT=my_design uv run chipflow sim run

# Run simulation and check events against a reference file
CHIPFLOW_ROOT=my_design uv run chipflow sim check
```

## Configuration

Add a `[chipflow.simulation]` section to your `chipflow.toml`:

```toml
[chipflow.simulation]
num_steps = 3000000
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `num_steps` | integer | `3000000` | Number of clock cycles to simulate |

## Simulation inputs and event logging

The simulation can be driven by an input file and produces an event log:

- **Inputs** — define simulation stimuli in `design/tests/input.json`. These drive signals during the simulation run.
- **Event log** — the simulation writes observed events to `build/sim/events.json`.

## Regression testing with event references

You can use `chipflow sim check` to catch unintended behavior changes by comparing simulation output against a known-good reference.

### Setting up a reference

1. Run the simulation and produce an event log:

   ```bash
   CHIPFLOW_ROOT=my_design uv run chipflow sim run
   ```

2. Review `build/sim/events.json` and confirm the output is correct.

3. Save it as your reference file:

   ```bash
   cp my_design/build/sim/events.json my_design/tests/events_reference.json
   ```

4. Point to it in `chipflow.toml`:

   ```toml
   [chipflow.test]
   event_reference = "tests/events_reference.json"
   ```

5. From now on, `chipflow sim check` will compare future simulation runs against this reference and report any differences.

## Built-in peripheral models

The simulation platform includes models for common peripherals, useful for SoC designs:

- UART
- SPI
- SPI Flash (with data loading)
- I2C
- GPIO

These models are automatically included when your design uses the corresponding interfaces.

## Python API for custom testbenches

For more control, chipflow-lib provides a low-level Python simulation interface:

```python
from chipflow.sim import CxxrtlSimulator, build_cxxrtl_from_amaranth

# Build CXXRTL shared library from an Amaranth design
lib_path = build_cxxrtl_from_amaranth(elaboratable, output_dir=Path("build/sim"))

# Create simulator instance
sim = CxxrtlSimulator(lib_path, top_module="top")
sim.reset()

# Step through simulation
sim.set("clk", 1)
sim.step()
value = sim.get("data_out")
```

Key methods:

| Method | Description |
|--------|-------------|
| `reset()` | Reset simulation to initial state |
| `step()` | Single simulation step (evaluate + commit) |
| `get(name)` | Read a signal value |
| `set(name, value)` | Set a signal value |
| `signals()` | List all signals in the design |
| `inputs()` | List input signals |
| `outputs()` | List output signals |

The simulator also supports use as a context manager:

```python
with CxxrtlSimulator(lib_path, top_module="top") as sim:
    sim.reset()
    sim.step()
```
