"""
Spice methods

Collection of methods provided as a mixin class

Initially restructured to this package Marko Kosunen 2022
"""

import os
import numpy as np
import pandas as pd
import sys
import abc
import subprocess
import multiprocessing

from thesdk import traceback 


class spice_methods(metaclass=ABCMeta):

    def filter_strobed(self, key, ioname):
        """
        RELOCATED TO SPECTRE SPECIFIC FILES spice/spectre/spectre.py
        """
        self.print_log(
            type="O",
            msg="Function filter_strobed has been relocated to spectre-specific files. Please call self.spice_simulator.filter_strobed!",
        )

    def check_output_accuracy(self):
        """
        Helper function to check output accuracy
        """
        keys = list(self.iofile_eventdict.keys())
        if len(keys) > 0:
            try:
                key = keys[0]
                tdiff = np.diff(self.iofile_eventdict[key.upper()][:, 0])
                if np.any(tdiff == 0.0):
                    self.print_log(
                        type="W",
                        msg="Accuracy of output file is insufficient. Increase value of 'digits' parameter and re-run simulation!",
                    )
            except:  # Requested output wasn't in output file, do nothing
                self.print_log(
                    type="W", msg="Couldn't check output file accuracy"
                )
                self.print_log(type="W", msg=traceback.format_exc())
        else:
            self.print_log(
                type="I",
                msg="Output file has no lines or was not read before checking output accuracy.",
            )

    def get_buswidth(self, signame):
        """Extract buswidth from signal name.

        Little-endian example::

            start,stop,width,busrange = get_buswidth('BUS<10:0>')
            # start = 10
            # stop = 0
            # width = 11
            # busrange = range(10,-1,-1)

        Big-endian example::

            start,stop,width,busrange = get_buswidth('BUS<0:8>')
            # start = 0
            # stop = 8
            # width = 9
            # busrange = range(0,9)

        """
        signame = (
            signame.replace("<", " ")
            .replace(">", " ")
            .replace("[", " ")
            .replace("]", " ")
            .replace(":", " ")
            .split(" ")
        )
        if "" in signame:
            signame.remove("")
        if len(signame) == 1:
            busstart = 0
            busstop = 0
        elif len(signame) == 2:
            busstart = int(signame[1])
            busstop = int(signame[1])
        else:
            busstart = int(signame[1])
            busstop = int(signame[2])
        if busstart > busstop:
            buswidth = busstart - busstop + 1
            busrange = range(busstart, busstop - 1, -1)
        else:
            buswidth = busstop - busstart + 1
            busrange = range(busstart, busstop + 1)
        return busstart, busstop, buswidth, busrange

    def si_string_to_float(self, strval):
        """Convert SI-formatted string to float

        E.g. self.si_string_to_float('3 mV') returns 3e-3.
        """
        parts = strval.split()
        if len(parts) == 2:
            val = float(parts[0])
            if len(parts[1]) == 1:  # No prefix
                mult = 1
            else:
                try:
                    mult = self.si_prefix_mult[parts[1][0]]
                except (
                    KeyError
                ):  # Could not convert, just return the text value
                    self.print_log(
                        type="W",
                        msg="Invalid SI-prefix %s, failed to convert."
                        % parts[1][0],
                    )
                    return strval
            return val * mult
        else:
            return strval  # Was a text value

    def sorter(self, val, index=0):
        """
        Function for sorting the files in correct order
        Files that are output from simulation are of form

        SweepN-<integer>_SweepN-1-<integer>_ ... _oppoint.dc

        Strategy: Extract the innermost sweep (e.g. Sweep0) string, find the sweep number
        and sort based on that. If the sweep is nested, run this algorithm N times with increasing
        index to sort the outer sweep results.

        """
        base = os.path.basename(val)
        sweeps = list(reversed(base.split("_")[:-1]))
        key = sweeps[index].split("-")[-1]
        return int(key)
