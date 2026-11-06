"""
=======
VACASK
=======

Simulator specific definitions for VACASK.

Initially written by Miikka Mäki, 2026
"""

import os
import re
import pandas as pd
import subprocess
import multiprocessing
from spice.spice_common import spice_common
import numpy as np
import traceback
import glob

from spice.vacask.vacask_rawread import rawread


class vacask(spice_common):
    """This class is used as instance in simulatormodule property of
    spice class. Contains language dependent definitions.

    Parameters
    ----------
    parent: object, None (mandatory to define). TheSyDeKick parent entity object for this simulator class.

    **kwargs :
       None


    """

    def __init__(self, parent=None, **kwargs):
        if parent is None:
            self.print_log(type="F", msg="Parent of simulator module not given")
        else:
            self.parent = parent

    @property
    def syntaxdict(self):
        """dict : Internally used dictionary for syntax conversions"""
        self.print_log(
            type="O", msg="Syntaxdict is obsoleted. Access properties directly"
        )
        self._syntaxdict = {
            "cmdfile_ext": self.cmdfile_ext,
            "resultfile_ext": self.resultfile_ext,
            "commentchar": self.commentchar,
            "commentline": self.commentline,
            "nprocflag": self.nprocflag,
            "simulatorcmd": self.simulatorcmd,
            "dcsource_declaration": self.dcsource_declaration,
            "parameter": self.parameter,
            "option": self.option,
            "include": self.include,
            "dspfinclude": self.dspfinclude,
            "subckt": self.subckt,
            "lastline": self.lastline,
            "eventoutdelim": self.eventoutdelim,  # Two spaces
            "csvskip": self.csvskip,
        }
        return self._syntaxdict

    @syntaxdict.setter
    def syntaxdict(self, value):
        self._syntaxdict = value

    @property
    def cmdfile_ext(self):
        """str : Extension of the command file"""
        return ".inc"  # TODO: proposal

    @property
    def resultfile_ext(self):
        """str : Extension of the result file"""
        return ".raw"

    @property
    def commentchar(self):
        """str : Comment character of the simulator"""
        return "//"

    @property
    def commentline(self):
        """str : Comment line for the simulator"""
        return "/*************************/\n"

    @property
    def nprocflag(self):
        """str : String for defining multithread execution"""
        # return "openblas_set_num_threads"  # TODO: not sure
        return "-n"

    @property
    def simulatorcmd(self):
        """str : Simulator execution command
        (Default: 'vacask')
        """
        return "vacask"

    @property
    def dcsource_declaration(self):
        """str : DC source declaration"""
        self.print_log(
            type="F", msg="DC source declaration not defined for ngspice"
        )
        return ""  # v{name} ({p} {m}) v dc=

    @property
    def parameter(self):
        """str : Netlist parameter definition string"""
        return ""  # don't know

    @property
    def option(self):
        """str : Netlist option definition string"""
        return "options"

    @property
    def include(self):
        """str : Netlist include string"""
        return "include"

    @property
    def dspfinclude(self):
        """str : Netlist dspf-file include string"""
        return "include"

    @property
    def subckt(self):
        """str : Subcircuit include string"""
        return "subckt"

    @property
    def lastline(self):
        """str : Last line of the simulator command file"""
        return "endc"

    @property
    def eventoutdelim(self):
        """str : Delimiter for the events"""
        return "  "  # Two spaces TODO: what is this even?

    @property
    def csvskip(self):
        """Needs documentation. Lines skipped in result file : int"""
        return 1  # TODO

    @property
    def plflag_simcmd_prefix(self):
        """
        Simulator specific prefix for enabling postlayout optimization
        Postfix comes from self.plflag (user defined)
        """
        if not hasattr(self, "_plflag_simcmd_prefix"):
            self.print_log(
                type="I",
                msg="Postlayout prefix unsupported for %s"
                % (self.parent.model),
            )
            self._plflag_simcmd_prefix = ""
        return self._plflag_simcmd_prefix

    @property
    def plflag(self):
        """
        Postlayout simulation accuracy/RC reduction flag.
        """
        self.print_log(
            type="W",
            msg="Postlayout flag unsupported for %s" % (self.parent.model),
        )
        if not hasattr(self, "_plflag"):
            self._plflag = ""
        return self._plflag

    @plflag.setter
    def plflag(self, val):
        self.print_log(type="W", msg="Postlayout flag unsupported for vacask")

    @property
    def plotprogram(self):
        """str : Sets the program to be used for visualizing waveform databases.
        Default 'gnuplot'.
        """
        if not hasattr(self, "_plotprogram"):
            self._plotprogram = "gnuplot"
        return self._plotprogram

    @plotprogram.setter
    def plotprogram(self, value):
        if value not in ["gnuplot"]:
            self.print_log(
                type="F",
                msg="%s not supported for plotprogram, only gnuplot is  supported",
            )
        else:
            self._plotprogram = value

    @property
    def plotprogcmd(self):
        """str : Command to be run for interactive simulations."""
        if not hasattr(self, "_plotprogcmd"):
            if self.plotprogram == "ezwave":
                self._plotprogcmd = "%s -MAXWND -LOGfile %s/ezwave.log %s &" % (
                    self.plotprogram,
                    self.parent.spicesimpath,
                    self.parent.spicedbpath,
                )
            elif self.plotprogram == "viva":
                self._plotprogcmd = "%s -datadir %s -nocdsinit &" % (
                    self.plotprogram,
                    self.parent.spicedbpath,
                )
            else:
                self.print_log(
                    type="F",
                    msg="Unsupported plot program '%s'." % self.plotprogram,
                )
        return self._plotprogcmd

    @plotprogcmd.setter
    def plotprogcmd(self, value):
        self._plotprogcmd = value

    @property
    def spicecmd(self):
        """str : Simulation command string to be executed on the command line.
        Automatically generated.
        """
        if not hasattr(self, "_vacask_spicecmd"):
            if self.parent.nproc:
                nprocflag = " %s %d " % (self.nprocflag, self.parent.nproc)
                self.print_log(
                    type="I", msg="Enabling multithreading '%s'." % nprocflag
                )
            else:
                nprocflag = ""

            if self.parent.postlayout:
                self.print_log(
                    type="W",
                    msg="Post-layout optimization not suported for VACASK",
                )

            if self.parent.interactive_spice:
                self.print_log(
                    type="W",
                    msg="Interactive spice not available for VACASK",
                )
            try:
                tomlfile = self.GLOBALS["VACASKTOMLFILE"]
            except:
                self.print_log(
                    type="F",
                    msg="VACASKTOMLFILE not found for VACASK!",
                )

            self._vacask_spicecmd = (
                self.parent.spice_submission
                + self.simulatorcmd
                + nprocflag
                + " --tomlfile "
                + tomlfile
                + " "
                + self.parent.spicetbsrc
            )
        return self._vacask_spicecmd

    def run_plotprogram(self):
        """Starting a parallel process for waveform viewer program.

        The plotting program command can be set with 'plotprogram'.
        """
        self.print_log(
            type="W", msg="Interactive plotting not implemented for vacask."
        )
        return 0

    def read_sp_result(self, **kwargs):
        """Internally called function to read the S-parameter simulation results"""
        self.print_log(
            type="W",
            msg="Reading S-parameters not yet implemented.",
        )

    def read_noise_result(self, **kwargs):
        """Internally called function to read the noise simulation results"""
        self.print_log(
            type="W",
            msg="Reading noise results not yet implemented.",
        )
        return None, None

    def read_stb_result(self, **kwargs):
        """Internally called function to read the stb simulation results"""
        self.print_log(
            type="W",
            msg="Reading stb results not yet implemented.",
        )

    def create_nested_sweepresult_dict(
        self, level, fileptr, sweeps_ran_dict, files, read_type
    ):
        """Documentation missing"""
        self.print_log(
            type="F",
            msg="create_nested_sweepresulsts unsupported for %s"
            % (self.parent.model),
        )
        return None, None

    def read_oppts(self):
        """Internally called function to read the DC operating points of the circuit"""
        self.print_log(
            type="W",
            msg="Something went wrong while extracting DC operating points.",
        )

    def parse_io_from_file(self, filepath, start, stop, dtype, labels, queue):
        """Parse specific lines from a vacask print file.

        This is wrapped to a function to allow parallelism.
        """
        self.print_log(type="W", msg="IO file parse not impemented yet")

    def read_output_file(self, file, dtype):
        """
        Interfacing function to read in results from an output file
        """
        import pdb

        pdb.set_trace()
        raw = rawread(file)

        self.print_log(type="W", msg="Output file reading not impemented yet")
