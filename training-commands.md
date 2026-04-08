# ChipFlow Platform — Training Command Reference

## Prerequisites

### <u>Python 3.12+</u>

**macOS:**
```bash
brew install python@3.12
```

**Ubuntu/Debian Linux:**
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv
```

**Windows:**

Download and install from https://www.python.org/downloads/ (tick "Add to PATH" during install).

**Verify:**
```bash
python3 --version    # macOS / Linux
python --version     # Windows
```

### <u>Git</u>

**macOS:**
```bash
# Git comes with Xcode Command Line Tools
xcode-select --install
```

**Ubuntu/Debian Linux:**
```bash
sudo apt install git
```

**Windows:**

Download and install from https://git-scm.com/download/win (use default settings, this includes Git Bash).

**Verify:**
```bash
git --version
```

### <u>uv (Python package manager)</u>

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Verify:**
```bash
uv --version
```

### <u>GitHub CLI (optional)</u>

GitHub CLI enables automatic authentication with the ChipFlow platform. If you prefer not to install it, you can authenticate using an API key instead — see Part 3, Option B.

**macOS:**
```bash
brew install gh
```

**Ubuntu/Debian Linux:**
```bash
sudo apt install gh
```
If not available via apt, see https://github.com/cli/cli/blob/trunk/docs/install_linux.md

**Windows:**
```powershell
winget install GitHub.cli
```

**Verify and authenticate:**
```bash
gh --version
gh auth login
```

Follow the prompts to authenticate with your GitHub account.

**Important:** After logging in, add the `user` scope (required for ChipFlow to read your email):
```bash
gh auth refresh -h github.com -s user
```

---

## Part 1: Clone and Set Up

### Clone the examples repository

```bash
git clone https://github.com/ChipFlow/chipflow-test-socs.git
cd chipflow-test-socs
```

### Install dependencies

```bash
make init
```

This runs `uv sync`, which installs Python dependencies including `chipflow-lib` and `amaranth`.

---

## Part 2: Explore the Project Structure

Each design lives in its own directory. For example, the `upcounter` design:

```
chipflow-test-socs/
├── Makefile                    # Build commands for all designs
├── pyproject.toml              # Python project config + dependencies
├── upcounter/
│   ├── chipflow.toml           # ChipFlow config (process, package)
│   ├── design/
│   │   └── design.py           # Amaranth HDL design code
│   ├── pins.lock               # Deterministic pin assignments (auto-generated)
│   └── build/                  # Build outputs (created after prepare)
├── rom/
│   ├── chipflow.toml
│   └── design/
│       └── design.py
└── sram/
    ├── chipflow.toml
    └── design/
        └── design.py
```

### View a design

```bash
cat upcounter/design/design.py
```

### View the ChipFlow configuration

```bash
cat upcounter/chipflow.toml
```

The minimal required fields are:

```toml
[chipflow]
project_name = "upcounter"

[chipflow.top]
soc = "design.design:MySoC"

[chipflow.silicon]
process = "ihp_sg13g2"
package = "pga144"
```

---

## Part 3: Authenticate with ChipFlow Platform

There are two ways to authenticate. Choose whichever suits your setup.

### <u>Option A: GitHub CLI (recommended)</u>

If you have `gh` installed and authenticated (see Prerequisites), authentication happens automatically. When you run a submit command, chipflow-lib will:
1. Detect your `gh` CLI token
2. Exchange it for a ChipFlow API key
3. Save it to `~/.config/chipflow/credentials`

```bash
# Trigger auth manually (optional — happens automatically on first submit)
CHIPFLOW_ROOT=upcounter uv run chipflow auth login
```

### <u>Option B: API key via environment variable</u>

If you don't have `gh` installed, you can set the API key directly:

1. Log in to https://build.chipflow.com
2. Go to your profile / API keys
3. Generate a new API key
4. Set it as an environment variable:

```bash
# macOS / Linux — add to your shell profile (~/.bashrc, ~/.zshrc)
export CHIPFLOW_API_KEY="your-api-key-here"

# Windows (PowerShell)
$env:CHIPFLOW_API_KEY = "your-api-key-here"

# Or set it inline for a single command
CHIPFLOW_API_KEY="your-api-key-here" uv run chipflow silicon submit
```

When `CHIPFLOW_API_KEY` is set, chipflow-lib uses it directly and skips all other auth methods.

### Check saved credentials

```bash
cat ~/.config/chipflow/credentials
```

### Logout (removes saved credentials from Option A)

```bash
uv run chipflow auth logout
```

---

## Part 4: Build and Submit a Design

### Option A: Using Make (recommended)

The Makefile provides shortcuts for all designs:

```bash
# Step 1: Lock pin assignments
make upcounter/pins.lock

# Step 2: Prepare RTLIL (synthesise design) and submit to platform
make upcounter-submit
```

Or for other designs:

```bash
make rom-submit
make sram-submit
```

### Option B: Using chipflow commands directly

```bash
# Step 1: Lock pin assignments
CHIPFLOW_ROOT=upcounter uv run chipflow pin lock

# Step 2: Prepare RTLIL (synthesise the design locally)
CHIPFLOW_ROOT=upcounter uv run chipflow silicon prepare

# Step 3: Submit to the cloud platform for backend build (RTL → GDS)
CHIPFLOW_ROOT=upcounter uv run chipflow silicon submit
```

### Submit and wait for build to complete

```bash
CHIPFLOW_ROOT=upcounter uv run chipflow silicon submit --wait
```

The `--wait` flag keeps the terminal open and streams build logs until the build finishes.

---

## Part 5: View Build Results

### On the web

Open https://build.chipflow.com in your browser. You will see your builds listed with:
- Build status (running / success / failed)
- Build logs (click to view real-time streaming logs)
- Download links for: GDS file, build report (JSON), PNG renders, post-PnR Verilog

### Build outputs locally

After `chipflow silicon prepare`, local build outputs are in:

```bash
ls upcounter/build/
```

---

## Part 6: Clean Up

### Clean a single design's build outputs

```bash
make upcounter-clean
```

### Clean all designs

```bash
make clean
```

---

## Quick Reference

| Command | What it does |
|---------|-------------|
| `make init` | Install all Python dependencies |
| `make upcounter` | Pin lock + prepare RTLIL for upcounter |
| `make upcounter-submit` | Pin lock + prepare + submit to platform |
| `make upcounter-clean` | Delete upcounter build outputs |
| `make rom-submit` | Build and submit the ROM design |
| `make sram-submit` | Build and submit the SRAM design |
| `make lint` | Run code style checks on all designs |
| `make clean` | Clean all build outputs |

### Direct chipflow commands

| Command | What it does |
|---------|-------------|
| `chipflow pin lock` | Generate deterministic pin assignments (pins.lock) |
| `chipflow silicon prepare` | Synthesise design to RTLIL locally |
| `chipflow silicon submit` | Submit RTLIL to cloud platform for backend build |
| `chipflow silicon submit --wait` | Submit and stream build logs until complete |
| `chipflow auth login` | Authenticate with the platform |
| `chipflow auth logout` | Remove saved credentials |

All `chipflow` commands require either `CHIPFLOW_ROOT=<design_dir>` environment variable or being run from within a design directory. See the [CHIPFLOW_ROOT](#chipflow_root) section for details.

---

## CHIPFLOW_ROOT

The `CHIPFLOW_ROOT` environment variable tells `chipflow` which directory contains your design's `chipflow.toml`. This is useful when you keep multiple designs as sub-folders within a single repository:

```
my-project/
├── Makefile
├── pyproject.toml
├── upcounter/
│   ├── chipflow.toml
│   └── design/
├── rom/
│   ├── chipflow.toml
│   └── design/
└── sram/
    ├── chipflow.toml
    └── design/
```

In this layout, you run commands from the repo root and point `CHIPFLOW_ROOT` at the design you want to build:

```bash
# Build the upcounter design
CHIPFLOW_ROOT=upcounter uv run chipflow silicon prepare

# Build the rom design
CHIPFLOW_ROOT=rom uv run chipflow silicon prepare
```

If `CHIPFLOW_ROOT` is **not set**, `chipflow` uses the current working directory as the design root. This works fine when your repo contains only a single design or when you `cd` into the design directory first:

```bash
cd upcounter
uv run chipflow silicon prepare
```

The Makefile in this repository sets `CHIPFLOW_ROOT` automatically for each design target, so `make upcounter-submit` just works from the repo root.

---

## Supported Processes

| Process | Value in chipflow.toml |
|---------|----------------------|
| IHP 130nm SiGe BiCMOS | `ihp_sg13g2` |

---

## Troubleshooting

### "Authentication failed" or "Could not retrieve email from GitHub"

```bash
# Ensure gh has the user scope (required for ChipFlow to read your email)
gh auth refresh -h github.com -s user

# Then re-login with ChipFlow
CHIPFLOW_ROOT=upcounter uv run chipflow auth login
```

### "No module named chipflow"

```bash
# Re-install dependencies
make init
```

### Build fails on platform

- Check build logs at https://build.chipflow.com
- Common issues: DRC violations, timing failures, missing pin assignments
- Re-run `chipflow pin lock` if pin assignments are stale

### Python version mismatch

This project requires Python 3.12–3.13. Check with:

```bash
python3 --version
```
