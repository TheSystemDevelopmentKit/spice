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

    @property
    def inputsignals(self):
        """str : Input signal definitions parsed from spice_iofile objects instantiated
        in the parent entity.
        """
        if not hasattr(self,'_inputsignals'):
            self._inputsignals = "%s Input signals\n" % self.parent.spice_simulator.commentchar
            for name, val in self.iofiles.Members.items():
                # Input file becomes a source
                if val.dir.lower()=='in' or val.dir.lower()=='input':
                    # Event signals are analog
                    if val.iotype.lower()=='event':
                        for i in range(len(val.ionames)):
                            # Finding the max time instant
                            try:
                                maxtime = val.Data[-1,0]
                            except TypeError:
                                self.print_log(type='F', msg='Input data not assinged to IO %s! Terminating.' % name)
                            if float(self._trantime) < float(maxtime):
                                self._trantime_name = name
                                self._trantime = maxtime
                            # Adding the source
                            self._inputsignals += "%s%s %s 0 pwl(file=\"%s\")\n" % \
                                    (val.sourcetype.upper(),val.ionames[i].lower(),val.ionames[i].upper(),val.file[i])
                    # Sample signals are digital
                    # Presumably these are already converted to bitstrings
                    elif val.iotype.lower()=='sample':
                        for i in range(len(val.ionames)):
                            pattstr = ''
                            for d in val.Data[:,i]:
                                pattstr += '%s ' % str(d)
                            try:
                                if float(self._trantime) < len(val.Data)/val.rs:
                                    self._trantime = len(val.Data)/val.rs
                                    self._trantime_name = name
                            except:
                                pass
                            # Checking if the given bus is actually a 1-bit signal
                            if ('<' not in val.ionames[i]) and ('>' not in val.ionames[i]) and len(str(val.Data[0,i])) == 1:
                                busname = '%s_BUS' % val.ionames[i]
                                self._inputsignals += '.setbus %s %s\n' % (busname,val.ionames[i])
                            else:
                                busname = val.ionames[i]
                            # Adding the source
                            self._inputsignals += ".sigbus %s vhi=%s vlo=%s tfall=%s trise=%s thold=%s tdelay=%s base=%s PATTERN %s\n" % \
                                    (busname,str(val.vhi),str(val.vlo),str(val.tfall),str(val.trise),str(1/val.rs),'0','bin',pattstr)
                    else:
                        self.print_log(type='F',msg='Input type \'%s\' undefined.' % val.iotype)

            if self._trantime == 0:
                self._trantime = "UNDEFINED"
                self.print_log(type='I',msg='Transient time could not be inferred from input signals. Make sure to provide tstop argument to spice_simcmd.')
        return self._inputsignals
    @inputsignals.setter
    def inputsignals(self,value):
        self._inputsignals=value
    @inputsignals.deleter
    def inputsignals(self,value):
        self._inputsignals=None

    @property
    def simcmdstr(self):
        """str : Simulation command definition parsed from spice_simcmd object
        instantiated in the parent entity.
        """
        if not hasattr(self,'_simcmdstr'):
            self._simcmdstr = "%s Simulation commands\n" % self.parent.spice_simulator.commentchar
            for sim, val in self.simcmds.Members.items():
                if str(sim).lower() == 'tran':
                    simtime = val.tstop if val.tstop is not None else self._trantime
                    if val.tstop is None:
                        self.print_log(type='D',msg='Inferred transient duration is %g s from \'%s\'.' % (simtime,self._trantime_name))
                    self._simcmdstr += '.%s %s %s %s\n' % \
                            (sim,str(val.tprint),str(simtime),'UIC' if val.uic else '')
                    if val.noise:
                        self._simcmdstr += '.noisetran fmin=%s fmax=%s nbrun=1 NONOM %s\n' % \
                                (str(val.fmin),str(val.fmax),'seed=%d'%(val.seed) if val.seed is not None else '')
                elif str(sim).lower() == 'dc':
                    self._simcmdstr='.op'

                elif str(sim).lower() == 'ac':
                    print_log(type='F', msg='AC simulation for eldo not yet implemented')
                    self._simcmdstr += '\n\n'
                else:
                    self.print_log(type='E',msg='Simulation type \'%s\' not yet implemented.' % str(sim))
        return self._simcmdstr
    @simcmdstr.setter
    def simcmdstr(self,value):
        self._simcmdstr=value
    @simcmdstr.deleter
    def simcmdstr(self,value):
        self._simcmdstr=None

