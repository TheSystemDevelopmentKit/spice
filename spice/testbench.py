"""
===============
Spice Testbench
===============

Testbench generation class for spice simulations.

"""
import os
import sys
import subprocess
import shlex
import fileinput
from thesdk import *
from spice.testbench_common import testbench_common
from spice.ngspice.ngspice_testbench import ngspice_testbench
from spice.eldo.eldo_testbench import eldo_testbench
from spice.spectre.spectre_testbench import spectre_testbench
from spice.spice_module import spice_module
import pdb

import numpy as np
import pandas as pd
from functools import reduce
import textwrap
from datetime import datetime

class testbench(testbench_common):
    """
    This class generates all testbench contents.
    This class is utilized by the main spice class.

    """
    def __init__(self, parent=None, **kwargs):
        """ Executes init of testbench_common, thus having the same attributes and 
        parameters.

        Parameters
        ----------
            **kwargs :
               See module testbench_common
        
        """

        #This should be language specific.
        super().__init__(parent=parent,**kwargs)
        self.parent=parent
        self.model=self.parent.model

    @property
    def DEBUG(self):
        """ This fixes DEBUG prints in spice_iofile, by propagating the DEBUG
        flag of the parent entity.
        """
        return self.parent.DEBUG 

    @property
    def testbench_simulator(self): 
        """ The simulator specific operation is defined with an instance of 
        simulator specific class. Properties and methods return values from that class.

        :type: ngspice_testbench 
        :type: eldo_testbench
        :type: spectre_testbench


        """
        if not hasattr(self,'_testbench_simulator'):
            if self.model == 'ngspice':
                self._testbench_simulator=ngspice_testbench(parent=self.parent)
            if self.model == 'eldo':
                self._testbench_simulator=eldo_testbench(parent=self.parent)
            if self.model == 'spectre':
                self._testbench_simulator=spectre_testbench(parent=self.parent)
        return self._testbench_simulator
       
    @property
    def dut(self):
        """ Design under test
        
        :type: spice_module

        """
        if not hasattr(self,'_dut'):
            self._dut = spice_module(file=self._dutfile,parent=self.parent)
        return self._dut

    # Generating eldo/spectre parameters string
    @property
    def parameters(self):
        """String
        
        Spice parameters string parsed from self.spiceparameters -dictionary in
        the parent entity.
        """
        if not hasattr(self,'_parameters'):
            self._parameters = "%s Parameters\n" % self.parent.spice_simulator.commentchar
            for parname,parval in self.parent.spiceparameters.items():
                self._parameters += self.parent.spice_simulator.parameter + ' ' + str(parname) + "=" + str(parval) + "\n"
        return self._parameters
    @parameters.setter
    def parameters(self,value):
        self._parameters=value
    @parameters.deleter
    def parameters(self,value):
        self._parameters=None

    # Generating eldo/spectre library inclusion string
    @property
    def libcmd(self):
        """str : Library inclusion string. Parsed from self.spicecorner -dictionary in
        the parent entity, as well as 'ELDOLIBFILE' or 'SPECTRELIBFILE' global
        variables in TheSDK.config.
        """

        return self.testbench_simulator.libcmd

    @libcmd.setter
    def libcmd(self,value):
        self.testbench_simulator.libcmd = value

    # Generating netlist inclusion string
    @property
    def includecmd(self):
        """String
        
        Subcircuit inclusion string pointing to generated subckt_* -file.
        """
        if not hasattr(self,'_includecmd'):
            self._includecmd = "%s Subcircuit file\n"  % self.parent.spice_simulator.commentchar
            self._includecmd += "%s \"%s\"\n" % (self.parent.spice_simulator.include,self._subcktfile)
        return self._includecmd
    @includecmd.setter
    def includecmd(self,value):
        self._includecmd=value
    @includecmd.deleter
    def includecmd(self,value):
        self._includecmd=None

    # DSPF include commands
    @property
    def dspfincludecmd(self):
        """String
        
        DSPF-file inclusion string pointing to files corresponding to self.dspf
        in the parent entity.
        """
        if not hasattr(self,'_dspfincludecmd'):
            if len(self.parent.dspf) > 0:
                self.print_log(type='I',msg='Including exctracted parasitics from DSPF.')
                self._dspfincludecmd = "%s Extracted parasitics\n"  % self.parent.spice_simulator.commentchar
                origcellmatch = re.compile(r"DESIGN")
                for cellname in self.parent.dspf:
                    dspfpath = '%s/%s.pex.dspf' % (self.parent.spicesrcpath,cellname)
                    try:    
                        rename = False
                        found = False # This is essentially same as rename, but included here for clarity
                        with open(dspfpath) as dspffile:
                            lines = dspffile.readlines()
                            for line in lines:
                                if origcellmatch.search(line) != None:
                                    words = line.split()
                                    cellname = words[-1].replace('\"','')
                                    if cellname.lower() == self.parent.name.lower():
                                        self.print_log(type='I',msg='Found DSPF cell name matching to original top-level cell name.')
                                        rename = True
                                        found = True
                                        self._origcellname=cellname
                                    elif cellname.lower() == self.dut.custom_subckt_name:
                                        self.print_log(type='I',msg='Found DSPF cellname matching to custom_subckt_name: %s.' % cellname)
                                        rename = True
                                        found = True
                                        self._origcellname=cellname
                                    break
                            if rename:
                                self.print_log(type='I',msg='Renaming DSPF top cell name accordingly from "%s" to "%s".' % (cellname,self.parent.name))
                                with fileinput.FileInput(dspfpath,inplace=True,backup='.bak') as f:
                                    for line in f:
                                        print(line.replace(self._origcellname,self.parent.name),end='')
                            # The below case is exactly same as else for the 'if rename'. However, renaming shouldn't be necessary if cellname matches self.parent.name??
                            if not found:
                                self.print_log(type='W',msg='Included DSPF file %s doesn\'t contain subckt definition with name %s!' % (dspfpath, self.parent.name))
                                self.print_log(type='W',msg='You may also rename the subckt by setting self.spice_tb.dut.custom_subckt_name in you testbench!')
                                self.print_log(type='W',msg='Included parasitics from file %s may NOT be visible to the simulator.' % (dspfpath))
                            self.print_log(type='I',msg='Including DSPF-file: %s' % dspfpath)
                            self._dspfincludecmd += "%s \"%s\"\n" % (self.parent.spice_simulator.dspfinclude,dspfpath)
                    except:
                        self.print_log(type='F',msg='DSPF-file did not contain matching design for %s' % self.parent.name)
                        self.print_log(type='F',msg=traceback.format_exc())
            else:
                self._dspfincludecmd = ''
            return self._dspfincludecmd
    @dspfincludecmd.setter
    def dspfincludecmd(self,value):
        self._dspfincludecmd=value
    @dspfincludecmd.deleter
    def dspfincludecmd(self,value):
        self._dspfincludecmd=None

    @property
    def misccmd(self):
        """String
        
        Miscellaneous command string corresponding to self.spicemisc -list in
        the parent entity.
        """
        if not hasattr(self,'_misccmd'):
            self._misccmd="%s Manual commands\n" % (self.parent.spice_simulator.commentchar)
            mcmd = self.parent.spicemisc
            for cmd in mcmd:
                self._misccmd += cmd + "\n"
        return self._misccmd
    @misccmd.setter
    def misccmd(self,value):
        self._misccmd=value
    @misccmd.deleter
    def misccmd(self,value):
        self._misccmd=None

    @property
    def dcsourcestr(self):
        """str : DC source definitions parsed from spice_dcsource objects instantiated
        in the parent entity.
        """

        return self.testbench_simulator.dcsourcestr

    @dcsourcestr.setter
    def dcsourcestr(self,value):
        self.testbench_simulator.dcsourcestr = value

    @property
    def inputsignals(self):
        """str : Input signal definitions parsed from spice_iofile objects instantiated
        in the parent entity.
        """

        return self.testbench_simulator.inputsignals

    @property
    def simcmdstr(self):
        """str : Simulation command definition parsed from spice_simcmd object
        instantiated in the parent entity.
        """
    
        return self.testbench_simulator.simcmdstr

    # Generating plot and print commands
    @property
    def plotcmd(self):
        """str : All output IOs are mapped to plot or print statements in the testbench.
        Also manual plot commands through `spice_simcmd.plotlist` are handled here.

        """

        return self.testbench_simulator.plotcmd

    def export(self,**kwargs):
        """
        Internally called function to write the testbench to a file.

        Parameters
        ----------
        force : Bool, False

        """
        force=kwargs.get('force', False)

        if len(self.parent.dspf) == 0 and self.parent.postlayout:
            self.print_log(type='I',msg='No dspf for postlayout simulation. Not exporting subcircuit.')
        else:
            self.dut.export_subckts(file=self._subcktfile, force=force)

        if not os.path.isfile(self.file):
            self.print_log(type='D',msg='Exporting spice testbench to %s' %(self.file))
            with open(self.file, "w") as module_file:
                module_file.write(self.contents)

        elif os.path.isfile(self.file) and not kwargs.get('force'):
            self.print_log(type='F', msg=('Export target file %s exists.\n Force overwrite with force=True.' %(self.file)))

        elif kwargs.get('force'):
            self.print_log(type='I',msg='Forcing overwrite of spice testbench to %s.' %(self.file))
            with open(self.file, "w") as module_file:
                module_file.write(self.contents)

    def generate_contents(self):
        """
        Internally called function to generate testbench contents.
        """

        self.contents = (self.header + "\n" +
                        self.libcmd + "\n" +
                        self.includecmd + "\n" +
                        self.dspfincludecmd + "\n" +
                        self.options + "\n" +
                        self.parameters + "\n" +
                        self.dut.instance + "\n\n" +
                        self.misccmd + "\n" +
                        self.dcsourcestr + "\n" +
                        self.inputsignals + "\n" +
                        self.simcmdstr + "\n" +
                        self.plotcmd + "\n" +
                        self.parent.spice_simulator.lastline+"\n")

