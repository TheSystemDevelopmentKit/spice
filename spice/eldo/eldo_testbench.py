"""
==============
Eldo Testbench
==============

Simulators sepecific testbench generation class for Ngspice.

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

class eldo_testbench(testbench_common):
    def __init__(self, parent=None, **kwargs):
        ''' Executes init of testbench_common, thus having the same attributes and 
        parameters.

        Parameters
        ----------
            **kwargs :
               See module testbench_common
        
        '''
        super().__init__(parent=parent,**kwargs)

    # Generating spice options string
    @property
    def options(self):
        """String
        
        Spice options string parsed from self.spiceoptions -dictionary in the
        parent entity.
        """
        if not hasattr(self,'_options'):
            self._options = "%s Options\n" % self.parent.spice_simulator.commentchar
            for optname,optval in self.parent.spiceoptions.items():
                if optval != "":
                    self._options += self.parent.spice_simulator.option + ' ' + optname + "=" + optval + "\n"
                else:
                    self._options += ".option " + optname + "\n"
        return self._options
    @options.setter
    def options(self,value):
        self._options=value
    @options.deleter
    def options(self,value):
        self._options=None

    @property
    def libcmd(self):
        """str : Library inclusion string. Parsed from self.spicecorner -dictionary in
        the parent entity, as well as 'ELDOLIBFILE' or 'SPECTRELIBFILE' global
        variables in TheSDK.config.
        """
        if not hasattr(self,'_libcmd'):
            libfile = ""
            corner = "top_tt"
            temp = "27"
            for optname,optval in self.parent.spicecorner.items():
                if optname == "temp":
                    temp = optval
                if optname == "corner":
                    corner = optval
            try:
                libfile = thesdk.GLOBALS['ELDOLIBFILE']
                if libfile == '':
                    raise ValueError
                else:
                    self._libcmd = "*** Eldo device models\n"
                    self._libcmd += ".lib " + libfile + " " + corner + "\n"
            except:
                self.print_log(type='W',msg='Global TheSDK variable ELDOLIBFILE not set.')
                self._libcmd = "*** Eldo device models (undefined)\n"
                self._libcmd += "*.lib " + libfile + " " + corner + "\n"
            self._libcmd += ".temp " + str(temp) + "\n"
        return self._libcmd
    @libcmd.setter
    def libcmd(self,value):
        self._libcmd=value
    @libcmd.deleter
    def libcmd(self,value):
        self._libcmd=None

    @property
    def dcsourcestr(self):
        """String
        
        DC source definitions parsed from spice_dcsource objects instantiated
        in the parent entity.
        """
        if not hasattr(self,'_dcsourcestr'):
            self._dcsourcestr = "%s DC sources\n" % self.parent.spice_simulator.commentchar
            for name, val in self.dcsources.Members.items():
                value = val.value if val.paramname is None else val.paramname
                supply = '%s%s' % (val.sourcetype.upper(),val.name.upper())
                if val.ramp == 0:
                    self._dcsourcestr += "%s %s %s %s %s\n" % \
                            (supply,val.pos,val.neg,value, \
                            'NONOISE' if not val.noise else '')
                else:
                    self._dcsourcestr += "%s %s %s %s %s\n" % \
                            (supply,val.pos,val.neg, \
                            'pulse(0 %g 0 %g)' % (value,abs(val.ramp)), \
                            'NONOISE' if not val.noise else '')
        return self._dcsourcestr

    @dcsourcestr.setter
    def dcsourcestr(self,value):
        self._dcsourcestr=value
    @dcsourcestr.deleter
    def dcsourcestr(self,value):
        self._dcsourcestr=None

