"""Simulation testbench for the upcounter design."""

from amaranth.sim import Simulator
from design import UpCounter


dut = UpCounter()
sim = Simulator(dut)
sim.add_clock(1e-6)  # 1 MHz clock


async def testbench(ctx):
    # Set limit to 5 and enable the counter
    ctx.set(dut.pins.limit.i, 5)
    ctx.set(dut.pins.en.i, 1)

    # Run for 10 clock cycles and observe
    for cycle in range(10):
        count = ctx.get(dut.pins.count.o)
        ovf = ctx.get(dut.pins.ovf.o)
        print(f"cycle {cycle:2d}:  count={count}  ovf={ovf}")
        await ctx.tick()

    # Disable counter and run a few more cycles
    ctx.set(dut.pins.en.i, 0)
    print("-- counter disabled --")

    for cycle in range(10, 13):
        count = ctx.get(dut.pins.count.o)
        ovf = ctx.get(dut.pins.ovf.o)
        print(f"cycle {cycle:2d}:  count={count}  ovf={ovf}")
        await ctx.tick()


sim.add_testbench(testbench)

with sim.write_vcd("upcounter.vcd"):
    sim.run()

print("\nWrote upcounter.vcd — open with GTKWave or Surfer to view waveforms.")
