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

        In VACASK, options are inside control sequence, for this reason,
        the are defined in property plotcmd.
        """
        if not hasattr(self, "_options"):
            self._options = ""
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
            for optname, optval in self.parent.spicecorner.items():
                if optname == "corner":
                    corner = optval
            try:
                libfile = thesdk.GLOBALS["VACASKLIBFILE"]
                if libfile == "":
                    raise ValueError
                else:
                    self._libcmd = "// VACASK device models\n"
                    self._libcmd += (
                        'include "' + libfile + '" section=' + corner + "\n"
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
            self._dcsourcestr += "model v vsource\n"
            for name, val in self.dcsources.Members.items():
                value = val.value if val.paramname is None else val.paramname
                supply = "%s%s" % (val.sourcetype.upper(), val.name.upper())
                self._dcsourcestr += "%s (%s %s) v dc=%s\n" % (
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
                            if val.pos and val.neg:
                                self._inputsignals += (
                                    '%s%s (%s %s) %s type="pwl" file="%s"\n'
                                    % (
                                        val.sourcetype.upper(),
                                        self.esc_bus(val.name.lower()),
                                        self.esc_bus(val.pos),
                                        self.esc_bus(val.neg),
                                        val.sourcetype.lower(),
                                        val.file[i],
                                    )
                                )
                            else:
                                self._inputsignals += (
                                    '%s%s (%s 0) %s type="pwl" file="%s"\n'
                                    % (
                                        val.sourcetype.upper(),
                                        self.esc_bus(val.name.lower()),
                                        self.esc_bus(val.ionames[i]),
                                        val.sourcetype.lower(),
                                        val.file[i],
                                    )
                                )
                    # Sample signals are digital
                    elif val.iotype.lower() == "sample":
                        self.print_log(
                            type="F",
                            msg="Input type '%s' undefined. (TODO.)"
                            % val.iotype,
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

        In VACASK, simcmdstr is inside control sequence. For this reason it is empty
        and property "analysis" is used.
        """
        if not hasattr(self, "_simcmdstr"):
            self._simcmdstr = ""
            self.analysis = (
                "%s Simulation commands\n"
                % self.parent.spice_simulator.commentchar
            )
            for sim, val in self.simcmds.Members.items():
                printfile = val.parent.runname
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
                    self.analysis += (
                        "analysis %s tran (\n stop=%s step=%s write=1"
                        % (
                            printfile,
                            str(simtime),
                            str(val.tprint),
                        )
                    )
                    if val.noise:
                        self.analysis += (
                            ' noisefmin=%s noisefmax=%s noisemode="zoh" %s \n)\n'
                            % (
                                str(val.fmin),
                                str(val.fmax),
                                (
                                    " noiseseed=%d" % (val.seed)
                                    if val.seed is not None
                                    else ""
                                ),
                            )
                        )
                    else:
                        self.analysis += "\n)\n"

                elif str(sim).lower() == "dc":
                    self.analysis += "analysis %s op (\n write=1\n)\n" % (
                        printfile,
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
                    self.analysis += (
                        "analysis %s ac (\n from=%s to=%s %s write=1\n)\n"
                        % (
                            printfile,
                            val.fmin,
                            val.fmax,
                            pts_str,
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
                    self.analysis += (
                        f"analysis %s acsp (\n ports=%s from=%s to=%s %s write=1\n)\n"
                        % (
                            printfile,
                            self.portsrcstr,
                            val.fmin,
                            val.fmax,
                            pts_str,
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
                        self.analysis += (
                            f"analysis %s noise (\n out=%s in=%s from=%s to=%s %s write=1\n)\n"
                            % (
                                printfile,
                                node,
                                self.noisesrc,
                                self.fmin,
                                self.fmax,
                                pts_str,
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
        options = "%s Options\n" % self.parent.spice_simulator.commentchar
        for optname, optval in self.parent.spiceoptions.items():
            if optval != "":
                options += (
                    self.parent.spice_simulator.option
                    + " "
                    + optname
                    + "="
                    + optval
                    + "\n"
                )
            else:
                options += "option " + optname + "\n"
        for optname, optval in self.parent.spicecorner.items():
            if optname == "temp":
                options += (
                    self.parent.spice_simulator.option
                    + " "
                    + optname
                    + "="
                    + optval
                    + "\n"
                )
        if not hasattr(self, "_plotcmd"):
            self._plotcmd = ""
            self._plotcmd += "control\n"
            self._plotcmd += options
            """
            self._plotcmd += (
                "%s Output signals\n"
                % self.parent.spice_simulator.commentchar
            )
            """
            self._plotcmd += self.analysis

        return self._plotcmd

    @plotcmd.setter
    def plotcmd(self, value):
        self._plotcmd = value

    @plotcmd.deleter
    def plotcmd(self, value):
        self._plotcmd = None
