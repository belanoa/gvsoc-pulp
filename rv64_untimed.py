#
# Copyright (C) 2020 ETH Zurich and University of Bologna
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import gvsoc.runner
import cpu.iss.riscv as iss
import memory.memory as memory
from vp.clock_domain import Clock_domain
import interco.router as router
import devices.uart.ns16550 as ns16550
import cpu.clint
import cpu.plic
import utils.loader.loader
import gvsoc.systree as st
from interco.bus_watchpoint import Bus_watchpoint
from elftools.elf.elffile import *
import gvsoc.runner as gvsoc


GAPY_TARGET = True

class Soc(st.Component):

    def __init__(self, parent, name, parser):
        super().__init__(parent, name)

        parser.add_argument("--isa", dest="isa", type=str, default="rv64imafdc",
            help="RISCV-V ISA string (default: %(default)s)")

        parser.add_argument("--arg", dest="args", action="append",
            help="Specify application argument (passed to main)")

        [args, __] = parser.parse_known_args()

        binary = None
        if parser is not None:
            [args, otherArgs] = parser.parse_known_args()
            binary = args.binary

        mem = memory.Memory(self, 'mem', size=0x80000000, atomics=True)
        rom = memory.Memory(self, 'rom', size=0x10000, stim_file=self.get_file_path('pulp/chips/rv64/rom.bin'))
        uart = ns16550.Ns16550(self, 'uart')
        clint = cpu.clint.Clint(self, 'clint')
        plic = cpu.plic.Plic(self, 'plic', ndev=1)

        ico = router.Router(self, 'ico')

        ico.add_mapping('mem', base=0x80000000, remove_offset=0x80000000, size=0x80000000)
        self.bind(ico, 'mem', mem, 'input')

        ico.add_mapping('rom', base=0x00001000, remove_offset=0x00001000, size=0x10000)
        self.bind(ico, 'rom', rom, 'input')

        ico.add_mapping('uart', base=0x10000000, remove_offset=0x10000000, size=0x100)
        self.bind(ico, 'uart', uart, 'input')

        ico.add_mapping('clint', base=0x2000000, remove_offset=0x2000000, size=0x10000)
        self.bind(ico, 'clint', clint, 'input')

        ico.add_mapping('plic', base=0xC000000, remove_offset=0xC000000, size=0x1000000)
        self.bind(ico, 'plic', plic, 'input')
        self.bind(uart, 'irq', plic, 'irq1')

        host = iss.Riscv(self, 'host', isa=args.isa, boot_addr=0x1000, timed=False,
            memory_start=0x80000000, memory_size=0x80000000, untimed_loop=False)

        loader = utils.loader.loader.ElfLoader(self, 'loader', binary=binary)

        self.bind(host, 'data', ico, 'input')

        self.bind(host, 'meminfo', mem, 'meminfo')
        self.bind(host, 'fetch', ico, 'input')
        self.bind(host, 'time', clint, 'time')
        self.bind(loader, 'out', ico, 'input')
        self.bind(loader, 'start', host, 'fetchen')
        # self.bind(loader, 'entry', host, 'bootaddr')

        self.bind(clint, 'sw_irq_0', host, 'msi')
        self.bind(clint, 'timer_irq_0', host, 'mti')
        self.bind(plic, 's_irq_0', host, 'sei')
        self.bind(plic, 'm_irq_0', host, 'mei')


class Rv64(st.Component):

    def __init__(self, parent, name, parser, options):

        super(Rv64, self).__init__(parent, name, options=options)

        clock = Clock_domain(self, 'clock', frequency=10000000)

        soc = Soc(self, 'soc', parser)

        self.bind(clock, 'out', soc, 'clock')


class Target(gvsoc.Target):

    def __init__(self, parser, options):
        super(Target, self).__init__(parser, options,
            model=Rv64, description="RV64 virtual board")

