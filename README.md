# ChipFlow Training

Training materials for learning the [ChipFlow platform](https://build.chipflow.com) — a cloud-based RTL-to-GDS chip design service.

## What's included

- **Upcounter example** — a simple Amaranth HDL design targeting the IHP SG13G2 130nm process, ready to build and submit to the platform
- **[Training Command Reference](training-commands.md)** — step-by-step guide covering prerequisites, setup, authentication, building, and submitting designs
- **[chipflow.toml Reference](chipflow-toml-reference.md)** — complete configuration format documentation

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
├── training-commands.md        # Full training guide
├── chipflow-toml-reference.md  # Configuration reference
└── upcounter/
    ├── chipflow.toml           # Design config (process, package)
    └── design/
        └── design.py           # Amaranth HDL upcounter design
```

## Links

- [ChipFlow Platform](https://build.chipflow.com)
- [chipflow-lib](https://github.com/ChipFlow/chipflow-lib) — core client library
- [chipflow-examples](https://github.com/ChipFlow/chipflow-examples) — additional example designs
