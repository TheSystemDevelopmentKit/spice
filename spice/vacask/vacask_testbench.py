"""
=================
VACASK Testbench
=================

Simulators specific testbench generation class for VACASK.

Initially written by Miikka Mäki, 2026
"""

import os
import sys
import subprocess
import shlex
import fileinput
from thesdk import *
from spice.testbench_common import testbench_common
import pdb

import numpy as np
import pandas as pd
from functools import reduce
import textwrap
from datetime import datetime


class vacask_testbench(testbench_common):
    def __init__(self, parent=None, **kwargs):
        """Executes init of testbench_common, thus having the same attributes and
        parameters.

        Parameters
        ----------
            **kwargs :
               See module testbench_common

        """
        super().__init__(parent=parent, **kwargs)

    # Generating spice options string
    @property
    def options(self):
        """String

        Spice options string parsed from self.spiceoptions -dictionary in the
        parent entity.
        """
        if not hasattr(self, "_options"):
            self._options = (
                "%s Options\n" % self.parent.spice_simulator.commentchar
            )
            for optname, optval in self.parent.spiceoptions.items():
                if optval != "":
                    self._options += (
                        self.parent.spice_simulator.option
                        + " "
                        + optname
                        + "="
                        + optval
                        + "\n"
                    )
                else:
                    self._options += "option " + optname + "\n"
        return self._options

    @options.setter
    def options(self, value):
        self._options = value

    @property
    def libcmd(self):
        """str : Library inclusion string. Parsed from self.spicecorner -dictionary in
        the parent entity, as well as 'VACASKLIBFILE' global variables in TheSDK.config.
        """
        if not hasattr(self, "_libcmd"):
            libfile = ""
            corner = "top_tt"
            temp = "27"
            for optname, optval in self.parent.spicecorner.items():
                if optname == "temp":
                    temp = optval
                if optname == "corner":
                    corner = optval
            try:
                libfile = thesdk.GLOBALS["VACASKLIBFILE"]
                if libfile == "":
                    raise ValueError
                else:
                    self._libcmd = "// VACASK device models\n"
                    self._libcmd += (
                        "include " + libfile + " section=" + corner + "\n"
                    )
            except:
                self.print_log(
                    type="W",
                    msg="Global TheSDK variable VACASKLIBFILE not set.",
                )
                self._libcmd = "// VACASK device models (undefined)\n"
                self._libcmd += (
                    "include " + libfile + " section=" + corner + "\n"
                )

            self._libcmd += (
                self.parent.spice_simulator.option + " temp=" + str(temp) + "\n"
            )
        return self._libcmd

    @libcmd.setter
    def libcmd(self, value):
        self._libcmd = value

    @libcmd.deleter
    def libcmd(self, value):
        self._libcmd = None

    @property
    def portsrcstr(self):
        """
        Port source definitions parsed from from self.parent.spice_ports
        """
        if not hasattr(self, "_portsrcstr"):
            self._portsrcstr = ""  # ["", ""]
        return self._portsrcstr

    @portsrcstr.setter
    def portsrcstr(self, val):
        self._portsrcstr = val

    @portsrcstr.deleter
    def portsrcstr(self, val):
        self._portsrcstr = None

    @property
    def dcsourcestr(self):
        """str : DC source definitions parsed from spice_dcsource objects instantiated
        in the parent entity.
        """
        if not hasattr(self, "_dcsourcestr"):
            self._dcsourcestr = (
                "%s DC sources\n" % self.parent.spice_simulator.commentchar
            )
            for name, val in self.dcsources.Members.items():
                value = val.value if val.paramname is None else val.paramname
                supply = "%s%s" % (val.sourcetype.upper(), val.name.upper())
                self._dcsourcestr += "%s (%s %s) vsource dc=%s\n" % (
                    name,
                    val.pos,
                    val.neg,
                    value,
                )
        return self._dcsourcestr

    @property
    def inputsignals(self):
        """str : Input signal definitions parsed from spice_iofile objects instantiated
        in the parent entity.
        """
        # TODO:
        if not hasattr(self, "_inputsignals"):
            self._inputsignals = (
                "%s Input signals\n" % self.parent.spice_simulator.commentchar
            )
            for name, val in self.iofiles.Members.items():
                # Input file becomes a source
                if val.dir.lower() == "in" or val.dir.lower() == "input":
                    # Event signals are analog
                    if val.iotype.lower() == "event":
                        for i in range(len(val.ionames)):
                            # Finding the max time instant
                            try:
                                maxtime = val.Data[-1, 0]
                            except TypeError:
                                self.print_log(
                                    type="F",
                                    msg="Input data not assigned to IO %s! Terminating."
                                    % name,
                                )
                            if float(self._trantime) < float(maxtime):
                                self._trantime_name = name
                                self._trantime = maxtime
                            # Adding the source
                            self._inputsignals += (
                                '%s%s %s %s pwl file="%s"\n'
                                % (
                                    val.sourcetype.upper(),
                                    val.ionames[i].lower(),
                                    val.pos,
                                    val.neg,
                                    val.file[i],
                                )
                            )
                    # Sample signals are digital
                    elif val.iotype.lower() == "sample":
                        for i in range(len(val.ionames)):
                            pattstr = ""
                            for d in val.Data[:, i]:
                                pattstr += "%s " % str(d)
                            try:
                                if (
                                    float(self._trantime)
                                    < len(val.Data) / val.rs
                                ):
                                    self._trantime = len(val.Data) / val.rs
                                    self._trantime_name = name
                            except:
                                pass
                            # VACASK digital signal handling
                            signame = val.ionames[i]
                            # Extracting the bus width
                            busstart, busstop, buswidth, busrange = (
                                self.parent.get_buswidth(signame)
                            )
                            signame = (
                                signame.replace("<", " ")
                                .replace(">", " ")
                                .replace("[", " ")
                                .replace("]", " ")
                                .replace(":", " ")
                                .split(" ")
                            )
                            # Checking if the given bus is actually a 1-bit signal
                            if (
                                ("<" not in val.ionames[i])
                                and (">" not in val.ionames[i])
                                and len(str(val.Data[0, i])) == 1
                            ):
                                busname = "%s_BUS" % val.ionames[i]
                                self._inputsignals += ".setbus %s %s\n" % (
                                    busname,
                                    val.ionames[i],
                                )
                            else:
                                busname = val.ionames[i]
                            # Adding the source
                            self._inputsignals += (
                                ".sigbus %s vhi=%s vlo=%s tfall=%s trise=%s thold=%s tdelay=%s base=%s PATTERN %s\n"
                                % (
                                    busname,
                                    str(val.vhi),
                                    str(val.vlo),
                                    str(val.tfall),
                                    str(val.trise),
                                    str(1 / val.rs),
                                    "0",
                                    "bin",
                                    pattstr,
                                )
                            )
                    else:
                        self.print_log(
                            type="F",
                            msg="Input type '%s' undefined." % val.iotype,
                        )

            if self._trantime == 0:
                self._trantime = "UNDEFINED"
                self.print_log(
                    type="I",
                    msg="Transient time could not be inferred from input signals. Make sure to provide tstop argument to spice_simcmd.",
                )
        return self._inputsignals

    @inputsignals.setter
    def inputsignals(self, value):
        self._inputsignals = value

    @inputsignals.deleter
    def inputsignals(self, value):
        self._inputsignals = None

    @property
    def simcmdstr(self):
        """str : Simulation command definition parsed from spice_simcmd object
        instantiated in the parent entity.
        """
        # TODO: verify this
        if not hasattr(self, "_simcmdstr"):
            self._simcmdstr = (
                "%s Simulation commands\n"
                % self.parent.spice_simulator.commentchar
            )
            for sim, val in self.simcmds.Members.items():
                printfile = val.parent.spicetbsrc.split(".vac")[0] + ".raw"
                if str(sim).lower() == "tran":
                    simtime = (
                        val.tstop if val.tstop is not None else self._trantime
                    )
                    if val.tstop is None:
                        self.print_log(
                            type="D",
                            msg="Inferred transient duration is %g s from '%s'."
                            % (simtime, self._trantime_name),
                        )
                    self._simcmdstr += (
                        "analysis %s tran stop=%s step=%s write=%s\n"
                        % (
                            sim,
                            str(simtime),
                            str(val.tprint),
                            printfile,
                        )
                    )
                    if val.noise:
                        self._simcmdstr += (
                            "noisefmin=%s noisefmax=%s noisemode=%s noiseseed=%s\n"
                            % (
                                str(val.fmin),
                                str(val.fmax),
                                str(val.noiseseed),
                                (
                                    "seed=%d" % (val.seed)
                                    if val.seed is not None
                                    else ""
                                ),
                            )
                        )

                elif str(sim).lower() == "dc":
                    self._simcmdstr += "analysis %s op write=%s\n" % (
                        sim,
                        printfile,
                    )

                elif str(sim).lower() == "ac":
                    if val.fscale.lower() == "log":
                        if val.fpoints != 0:
                            pts_str = 'mode="dec" points=%d' % val.fpoints
                        else:
                            self.print_log(
                                type="F",
                                msg="Set either fpoints for AC simulation!",
                            )
                    elif val.fscale.lower() == "lin":
                        if val.fpoints != 0:
                            pts_str = 'mode="lin" points=%d' % val.fpoints
                        elif val.fstepsize != 0:
                            pts_str = "step=%d" % val.fstepsize
                        else:
                            self.print_log(
                                type="F",
                                msg="Set either fpoints or fstepsize for linear AC simulation!",
                            )
                    else:
                        self.print_log(
                            type="F",
                            msg="Unsupported frequency scale %s for AC simulation!"
                            % val.fscale,
                        )
                    self._simcmdstr += (
                        "analysis %s ac from=%s to=%s %s write=%s\n\n"
                        % (
                            sim,
                            val.fmin,
                            val.fmax,
                            pts_str,
                            printfile,
                        )
                    )

                elif str(sim).lower() == "pz":
                    self.print_log(
                        type="F", msg="PZ simulation not supported in VACASK."
                    )

                elif str(sim).lower() == "sp":
                    if val.fscale.lower() == "log":
                        if val.fpoints != 0:
                            pts_str = 'mode="dec" points=%d' % val.fpoints
                        else:
                            self.print_log(
                                type="F",
                                msg="Set either fpoints for SP simulation!",
                            )
                    elif val.fscale.lower() == "lin":
                        if val.fpoints != 0:
                            pts_str = 'mode="lin" points=%d' % val.fpoints
                        elif val.fstepsize != 0:
                            pts_str = "step=%d" % val.fstepsize
                        else:
                            self.print_log(
                                type="F",
                                msg="Set either fpoints or fstepsize for linear SP simulation!",
                            )
                    else:
                        self.print_log(
                            type="F",
                            msg="Unsupported frequency scale %s for SP simulation!"
                            % val.fscale,
                        )
                    self._simcmdstr += (
                        f"analysis %s acsp ports=%s from=%s to=%s %s write=%s\n\n"
                        % (
                            sim,
                            val.ports,
                            val.fmin,
                            val.fmax,
                            pts_str,
                            printfile,
                        )
                    )

                elif str(sim).lower() == "noise":
                    if val.fscale.lower() == "log":
                        if val.fpoints != 0:
                            pts_str = 'mode="dec" points=%d' % val.fpoints
                        else:
                            self.print_log(
                                type="F",
                                msg="Set either fpoints for noise simulation!",
                            )
                    elif val.fscale.lower() == "lin":
                        if val.fpoints != 0:
                            pts_str = 'mode="lin" points=%d' % val.fpoints
                        elif val.fstepsize != 0:
                            pts_str = "step=%d" % val.fstepsize
                        else:
                            self.print_log(
                                type="F",
                                msg="Set either fpoints or fstepsize for linear noise simulation!",
                            )
                    else:
                        self.print_log(
                            type="F",
                            msg="Unsupported frequency scale %s for noise simulation!"
                            % val.fscale,
                        )
                    if len(val.nodes) == 0:
                        self.print_log(
                            type="F",
                            msg="Nodes list is empty. Set the nodes for noise simulation!",
                        )
                    if val.fmin == None:
                        self.print_log(
                            type="F",
                            msg="Fmin must be given for noise simulation",
                        )
                    if val.fmax == None:
                        self.print_log(
                            type="F",
                            msg="Fmax must be given for noise simulation",
                        )
                    if val.noisesrc == None:
                        self.print_log(
                            type="F",
                            msg="noisesrc must be given for noise simulation",
                        )
                    for node in val.nodes:
                        self._simcmdstr += (
                            f"analysis %s noise out=%s in=%s from=%s to=%s %s write=%s\n"
                            % (
                                sim,
                                node,
                                self.noisesrc,
                                self.fmin,
                                self.fmax,
                                pts_str,
                                printfile,
                            )
                        )
                elif str(sim).lower() == "stb":
                    self.print_log(
                        type="F",
                        msg="Stability analysis not yet implemented for VACASK.",
                    )
                elif str(sim).lower() == "pss":
                    self.print_log(
                        type="F",
                        msg="PSS analysis not yet implemented for VACASK.",
                    )
                elif str(sim).lower() == "pac":
                    self.print_log(
                        type="F",
                        msg="PAC analysis not yet implemented for VACASK.",
                    )
                elif str(sim).lower() == "pnoise":
                    self.print_log(
                        type="F",
                        msg="PNoise analysis not yet implemented for VACASK.",
                    )
                elif str(sim).lower() == "hb":
                    self.print_log(
                        type="F",
                        msg="HB analysis not yet implemented for VACASK.",
                    )
                elif str(sim).lower() == "hbac":
                    self.print_log(
                        type="F",
                        msg="HBAC analysis not yet implemented for VACASK.",
                    )
                elif str(sim).lower() == "hbnoise":
                    self.print_log(
                        type="F",
                        msg="HB noise analysis not yet implemented for VACASK.",
                    )
                else:
                    self.print_log(
                        type="E",
                        msg="Simulation type '%s' not yet implemented."
                        % str(sim),
                    )
        return self._simcmdstr

    @simcmdstr.setter
    def simcmdstr(self, value):
        self._simcmdstr = value

    @simcmdstr.deleter
    def simcmdstr(self, value):
        self._simcmdstr = None

    @property
    def plotcmd(self):
        """str : All output IOs are mapped to plot or print statements in the testbench.
        Also manual plot commands through `spice_simcmd.plotlist` are handled here.

        """

        if not hasattr(self, "_plotcmd"):
            self._plotcmd = ""
            for name, val in self.simcmds.Members.items():
                # Manual probes
                if len(val.plotlist) > 0 and name.lower() != "dc":
                    self._plotcmd = (
                        "%s Manually probed signals\n"
                        % self.parent.spice_simulator.commentchar
                    )
                    self._plotcmd += ".plot "

                    for i in val.plotlist:
                        self._plotcmd += self.esc_bus(i) + " "
                    self._plotcmd += "\n\n"
                # DC probes
                if len(val.plotlist) > 0 and name.lower() == "dc":
                    self._plotcmd = (
                        "%s DC operating points to be captured:\n"
                        % self.parent.spice_simulator.commentchar
                    )
                    self._plotcmd += ".plot "

                    for i in val.plotlist:
                        self._plotcmd += self.esc_bus(i, esc_colon=False) + " "
                    if val.excludelist != []:
                        self._plotcmd += "exclude=[ "
                        for i in val.excludelist:
                            self._plotcmd += i + " "
                        self._plotcmd += "]"
                    self._plotcmd += "\n\n"

                if name.lower() == "tran" or name.lower() == "ac":
                    self._plotcmd += (
                        "%s Output signals\n"
                        % self.parent.spice_simulator.commentchar
                    )

                    # Parsing output iofiles
                    for name, val in self.iofiles.Members.items():
                        # Output iofile becomes a plot/print command
                        if (
                            val.dir.lower() == "out"
                            or val.dir.lower() == "output"
                        ):
                            if val.iotype == "event":
                                for i in range(len(val.ionames)):
                                    signame = self.esc_bus(val.ionames[i])
                                    self._plotcmd += (
                                        ".printfile %s(%s) file=%s\n"
                                        % (val.sourcetype, signame, val.file[i])
                                    )
                            elif val.iotype == "sample":
                                for i in range(len(val.ionames)):
                                    # Checking the given trigger(s)
                                    if isinstance(val.trigger, list):
                                        if len(val.trigger) == len(val.ionames):
                                            trig = val.trigger[i]
                                        else:
                                            trig = val.trigger[0]
                                            self.print_log(
                                                type="W",
                                                msg="%d triggers given for %d ionames. Using the first trigger for all ionames."
                                                % (
                                                    len(val.trigger),
                                                    len(val.ionames),
                                                ),
                                            )
                                    else:
                                        trig = val.trigger
                                    # Extracting the bus width
                                    signame = val.ionames[i]
                                    busstart, busstop, buswidth, busrange = (
                                        self.parent.get_buswidth(signame)
                                    )
                                    signame = (
                                        signame.replace("<", " ")
                                        .replace(">", " ")
                                        .replace("[", " ")
                                        .replace("]", " ")
                                        .replace(":", " ")
                                        .split(" ")
                                    )
                                    # If not already, add the respective trigger signal voltage to iofile_eventdict
                                    if trig not in self.parent.iofile_eventdict:
                                        self.parent.iofile_eventdict[trig] = (
                                            None
                                        )
                                        self._plotcmd += (
                                            ".printfile %s(%s) file=%s\n"
                                            % (
                                                val.sourcetype,
                                                self.esc_bus(trig),
                                                val.file[i],
                                            )
                                        )
                                    for j in busrange:
                                        if (
                                            buswidth == 1
                                            and "<" not in val.ionames[i]
                                        ):
                                            bitname = signame[0]
                                        else:
                                            bitname = "%s<%d>" % (signame[0], j)
                                        # If not already, add the bit voltage to iofile_eventdict
                                        if (
                                            bitname
                                            not in self.parent.iofile_eventdict
                                        ):
                                            self.parent.iofile_eventdict[
                                                bitname
                                            ] = None
                                            self._plotcmd += (
                                                ".printfile %s(%s) file=%s\n"
                                                % (
                                                    val.sourcetype,
                                                    self.esc_bus(bitname),
                                                    val.file[i],
                                                )
                                            )
                            elif val.iotype == "time":
                                # For time IOs, the node voltage is saved as
                                # event and the time information is later
                                # parsed in Python
                                for i in range(len(val.ionames)):
                                    signame = self.esc_bus(val.ionames[i])
                                    # Check if this same node was already saved as event type
                                    if (
                                        val.ionames[i]
                                        not in self.parent.iofile_eventdict
                                    ):
                                        # Requested node was not saved as event
                                        # -> add to eventdict + save to output database
                                        self.parent.iofile_eventdict[
                                            val.ionames[i]
                                        ] = None
                                        self._plotcmd += (
                                            ".printfile %s(%s) file=%s\n"
                                            % (
                                                val.sourcetype,
                                                signame,
                                                val.file[i],
                                            )
                                        )
                            elif val.iotype == "vsample":
                                self.print_log(
                                    type="O",
                                    msg="IO type 'vsample' is obsolete. Please use type 'sample' and set ioformat='volt'.",
                                )
                                self.print_log(
                                    type="F", msg="Please do it now :)"
                                )
                            else:
                                self.print_log(
                                    type="W",
                                    msg="Output filetype incorrectly defined.",
                                )

                    # Parsing supply currents here as well
                    for name, val in self.dcsources.Members.items():
                        if val.extract:
                            supply = "%s%s" % (
                                val.sourcetype.upper(),
                                val.name.upper(),
                            )
                            if supply not in self.parent.iofile_eventdict:
                                self.parent.iofile_eventdict[supply] = None
                            # Plotting power and current waveforms for this supply
                            self._plotcmd += ".plot POW(%s)\n" % supply
                            self._plotcmd += ".plot I(%s)\n" % supply
                            # Writing source current consumption to a file
                            self._plotcmd += ".printfile I(%s) file=%s\n" % (
                                supply,
                                val.ext_file,
                            )
        return self._plotcmd

    @plotcmd.setter
    def plotcmd(self, value):
        self._plotcmd = value

    @plotcmd.deleter
    def plotcmd(self, value):
        self._plotcmd = None
