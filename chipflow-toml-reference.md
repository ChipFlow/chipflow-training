## chipflow.toml — Configuration Reference

Based on chipflow-lib v0.3.3 Pydantic config models.

---

### Root Structure

All configuration lives under the `[chipflow]` section.

---

### Top-Level Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `project_name` | string | **Yes** | — | Name of the ChipFlow project |
| `top` | dict | No | `{}` | Top-level design config, typically contains `soc = "design.design:MySoC"` |
| `steps` | dict of strings | No | `None` | Step definitions mapping step names to Python class references |
| `clock_domains` | list of strings | No | `None` | Additional clock domain names beyond the default `sync` |

---

### `[chipflow.silicon]`

Required for silicon builds.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `process` | enum | **Yes** | — | Target manufacturing process |
| `package` | string | **Yes** | — | Package identifier (e.g. `"pga144"`) |
| `power` | dict of voltages | No | `{}` | Power domain voltages |
| `debug` | dict of booleans | No | `None` | Debug configuration flags |

**Allowed `process` values:**

| Value | Description |
|-------|-------------|
| `ihp_sg13g2` | IHP 130nm SiGe BiCMOS open-source process |

**Voltage format:** float or string with optional `V` suffix (e.g. `1.8`, `"1.8V"`, `"1.8v"`).

---

### `[chipflow.simulation]`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `num_steps` | integer | No | `3000000` | Number of simulation timesteps to run |

---

### `[chipflow.software.riscv]`

Compiler configuration for RISC-V based designs.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `cpu` | string | Yes (if section present) | — | CPU architecture string (e.g. `"baseline_rv32-a-c-d"`) |
| `abi` | string | Yes (if section present) | — | ABI string (e.g. `"ilp32"`) |

---

### `[chipflow.test]`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `event_reference` | path | Yes (if section present) | — | Path to event reference file for testing |

---

### Minimal Example

For a simple design targeting IHP SG13G2:

```toml
[chipflow]
project_name = "my_design"

[chipflow.top]
soc = "design.design:MySoC"

[chipflow.silicon]
process = "ihp_sg13g2"
package = "pga144"
```

### Full Example

```toml
[chipflow]
project_name = "my_soc"
clock_domains = ["fast_clk"]

[chipflow.top]
soc = "design.design:MySoC"

[chipflow.steps]
silicon = "chipflow_lib.steps.silicon:SiliconStep"

[chipflow.silicon]
process = "ihp_sg13g2"
package = "pga144"

[chipflow.silicon.power]
vdd = 1.8
vss = 0.0

[chipflow.silicon.debug]
heartbeat = true

[chipflow.simulation]
num_steps = 5000000

[chipflow.software.riscv]
cpu = "baseline_rv32-a-c-d"
abi = "ilp32"

[chipflow.test]
event_reference = "tests/events.txt"
```

---

### Legacy Fields (Ignored)

The following sections appear in older TOML files but are **not parsed** by chipflow-lib and have no effect:

- `[chipflow.clocks]` — silently ignored
- `[chipflow.resets]` — silently ignored
- `[chipflow.silicon.pads]` — silently ignored
