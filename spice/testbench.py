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
                        with open(dspfpath) as dspffile:
                            lines = dspffile.readlines()
                            for line in lines:
                                if origcellmatch.search(line) != None:
                                    words = line.split()
                                    cellname = words[-1].replace('\"','')
                                    if cellname.lower() == self.parent.name.lower():
                                        self.print_log(type='I',msg='Found DSPF cell name matching to original top-level cell name.')
                                        rename = True
                                        self._origcellname=cellname
                                    break
                            if rename:
                                self.print_log(type='I',msg='Renaming DSPF top cell name accordingly from "%s" to "%s".' % (cellname,self.parent.name))
                                with fileinput.FileInput(dspfpath,inplace=True,backup='.bak') as f:
                                    for line in f:
                                        print(line.replace(self._origcellname,self.parent.name),end='')
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
        """String
        
        All output IOs are mapped to plot or print statements in the testbench.
        Also manual plot commands through `spice_simcmd.plotlist` are handled here.

        """
        if not hasattr(self,'_plotcmd'):
            self._plotcmd = "" 
            for name, val in self.simcmds.Members.items():
                # Manual probes
                if len(val.plotlist) > 0 and name.lower() != 'dc':
                    self._plotcmd = "%s Manually probed signals\n" % self.parent.spice_simulator.commentchar
                    if self.parent.model == 'eldo': 
                        self._plotcmd += '.plot ' 
                    else:
                        self._plotcmd += 'save ' 

                    for i in val.plotlist:
                        self._plotcmd += self.esc_bus(i) + " "
                    self._plotcmd += "\n\n"
                #DC probes
                if len(val.plotlist) > 0 and name.lower() == 'dc':
                    self._plotcmd = "%s DC operating points to be captured:\n" % self.parent.spice_simulator.commentchar
                    if self.parent.model == 'eldo': 
                        self._plotcmd += '.plot ' 
                    else:
                        self._plotcmd += 'save ' 

                    for i in val.plotlist:
                        self._plotcmd += self.esc_bus(i, esc_colon=False) + " "
                    if val.excludelist != []:
                        self._plotcmd += 'exclude=[ '
                        for i in val.excludelist:
                            self._plotcmd += i + ' '
                        self._plotcmd += ']'
                    self._plotcmd += "\n\n"

                if name.lower() == 'tran' or name.lower() == 'ac' :
                    self._plotcmd += "%s Output signals\n" % self.parent.spice_simulator.commentchar
                    if self.parent.model=='ngspice':
                        self._plotcmd += ".control\nset wr_singlescale\nset wr_vecnames\nset appendwrite\n"
                        if self.parent.nproc: 
                            self._plotcmd +="%s%d\n" % (self.parent.spice_simulator.nprocflag,self.parent.nproc)
                        self._plotcmd += "run\n"

                    # Parsing output iofiles
                    savestr=''
                    plotstr=''
                    first=True
                    for name, val in self.iofiles.Members.items():
                        # Output iofile becomes a plot/print command
                        if val.dir.lower()=='out' or val.dir.lower()=='output':
                            if val.iotype=='event':
                                for i in range(len(val.ionames)):
                                    signame = self.esc_bus(val.ionames[i])
                                    if self.parent.model=='eldo':
                                        self._plotcmd += '.printfile %s(%s) file=%s\n' % (val.sourcetype,signame,val.file[i])
                                    elif self.parent.model=='spectre':
                                        if first:
                                            savestr += 'save %s' % signame
                                            if val.datatype.lower() == 'complex':
                                                plotstr += '.print %sr(%s) %si(%s)' % \
                                                        (val.sourcetype, val.ionames[i], val.sourcetype, val.ionames[i])
                                            else:
                                                plotstr += '.print %s(%s)' % (val.sourcetype, val.ionames[i])
                                            first=False
                                        else:
                                            if val.datatype.lower() == 'complex':
                                                if f'{val.sourcetype}({val.ionames[i]})' not in plotstr.split(' '):
                                                    savestr += ' %s' % signame
                                                    plotstr += ' %sr(%s) %si(%s)' % \
                                                            (val.sourcetype, val.ionames[i], val.sourcetype, val.ionames[i])
                                            else:
                                                if f'{val.sourcetype}({val.ionames[i]})' not in plotstr.split(' '):
                                                    savestr += ' %s' % signame
                                                    plotstr += ' %s(%s)' % (val.sourcetype, val.ionames[i])
                                    elif self.parent.model=='ngspice':
                                        # Plots in tb only for interactive. Does not work in batch
                                        if self.parent.interactive_spice:
                                            self._plotcmd += "plot %s(%s)\n" % \
                                                    (val.sourcetype,val.ionames[i].upper())
                                        self._plotcmd += "wrdata %s %s(%s)\n" % \
                                                (val.file[i], val.sourcetype,val.ionames[i].upper())
                            elif val.iotype=='sample':
                                for i in range(len(val.ionames)):
                                    # Checking the given trigger(s)
                                    if isinstance(val.trigger,list):
                                        if len(val.trigger) == len(val.ionames):
                                            trig = val.trigger[i]
                                        else:
                                            trig = val.trigger[0]
                                            self.print_log(type='W',
                                                    msg='%d triggers given for %d ionames. Using the first trigger for all ionames.' 
                                                    % (len(val.trigger),len(val.ionames)))
                                    else:
                                        trig = val.trigger
                                    # Extracting the bus width
                                    signame = val.ionames[i]
                                    busstart,busstop,buswidth,busrange = self.parent.get_buswidth(signame)
                                    signame = signame.replace('<',' ').replace('>',' ').replace('[',' ').replace(']',' ').replace(':',' ').split(' ')
                                    # If not already, add the respective trigger signal voltage to iofile_eventdict
                                    if trig not in self.parent.iofile_eventdict:
                                        self.parent.iofile_eventdict[trig] = None
                                        if self.parent.model=='spectre':
                                            if first:
                                                savestr += 'save %s' % self.esc_bus(trig)
                                                plotstr += '.print v(%s)' % (trig)
                                                first=False
                                            else:
                                                savestr += ' %s' % self.esc_bus(trig) 
                                                plotstr += ' v(%s)' % (trig)
                                        elif self.parent.model=='eldo':
                                            self._plotcmd += '.printfile %s(%s) file=%s\n' % (val.sourcetype,self.esc_bus(trig),val.file[i])
                                        elif self.parent.model=='ngspice':
                                            # Plots in tb only for interactive. Does not work in batch
                                            if self.parent.interactive_spice:
                                                self._plotcmd += "plot %s(%s)\n" % \
                                                    (val.sourcetype,trig.upper())
                                            self._plotcmd += "wrdata %s %s(%s)\n" % \
                                                    (val.file[i],val.sourcetype,trig.upper())
                                    for j in busrange:
                                        if buswidth == 1 and '<' not in val.ionames[i]:
                                            bitname = signame[0]
                                        else:
                                            bitname = '%s<%d>' % (signame[0],j)
                                        # If not already, add the bit voltage to iofile_eventdict
                                        if bitname not in self.parent.iofile_eventdict:
                                            self.parent.iofile_eventdict[bitname] = None
                                            if self.parent.model=='spectre':
                                                if first:
                                                    savestr += 'save %s' % self.esc_bus(bitname)
                                                    plotstr += '.print %s(%s)' % (val.sourcetype, bitname)
                                                    first=False
                                                else:
                                                    savestr += ' %s' % self.esc_bus(bitname)
                                                    plotstr += ' %s(%s)' % (val.sourcetype, bitname)
                                            elif self.parent.model=='eldo':
                                                self._plotcmd += '.printfile %s(%s) file=%s\n' % (val.sourcetype,self.esc_bus(bitname),val.file[i])
                                            elif self.parent.model=='ngspice':
                                                self._plotcmd += "plot %s(%s)\n" % \
                                                        (val.sourcetype,bitname.upper())
                                                self._plotcmd += "wrdata %s %s(%s)\n" % \
                                                        (val.file[i],val.sourcetype,bitname.upper())
                            elif val.iotype=='time':
                                # For time IOs, the node voltage is saved as
                                # event and the time information is later
                                # parsed in Python
                                for i in range(len(val.ionames)):
                                    signame = self.esc_bus(val.ionames[i])
                                    # Check if this same node was already saved as event type
                                    if val.ionames[i] not in self.parent.iofile_eventdict:
                                        # Requested node was not saved as event
                                        # -> add to eventdict + save to output database
                                        self.parent.iofile_eventdict[val.ionames[i]] = None
                                        if self.parent.model == 'spectre':
                                            if first:
                                                savestr += 'save %s' % signame
                                                plotstr += '.print %s(%s)' % (val.sourcetype, val.ionames[i])
                                                first=False
                                            else:
                                                savestr += ' %s' % signame
                                                plotstr += ' %s(%s)' % (val.sourcetype, val.ionames[i])
                                        elif self.parent.model == 'eldo':
                                            self._plotcmd += '.printfile %s(%s) file=%s\n' % (val.sourcetype,signame,val.file[i])
                                        elif self.parent.model == 'ngspice':
                                            # Plots in tb only for interactive. Does not work in batch
                                            if self.parent.interactive_spice:
                                                self._plotcmd += "plot %s(%s)\n" % \
                                                        (val.sourcetype,signame.upper())
                                            self._plotcmd += "wrdata %s %s(%s)\n" % \
                                                    (val.file[i],val.sourcetype,signame.upper())
                            elif val.iotype=='vsample':
                                self.print_log(type='O',msg='IO type \'vsample\' is obsolete. Please use type \'sample\' and set ioformat=\'volt\'.')
                                self.print_log(type='F',msg='Please do it now :)')
                            else:
                                self.print_log(type='W',msg='Output filetype incorrectly defined.')

                    # Parsing supply currents here as well (I think ngspice
                    # plots need to be grouped like this)
                    for name, val in self.dcsources.Members.items():
                        if val.extract:
                            supply = '%s%s' % (val.sourcetype.upper(),val.name.upper())
                            if supply not in self.parent.iofile_eventdict:
                                self.parent.iofile_eventdict[supply] = None
                            if self.parent.model == 'eldo':
                                # Plotting power and current waveforms for this supply
                                self._plotcmd += '.plot POW(%s)\n' % supply
                                self._plotcmd += '.plot I(%s)\n' % supply
                                # Writing source current consumption to a file
                                self._plotcmd += '.printfile I(%s) file=%s\n' % (supply,val.ext_file)
                            elif self.parent.model == 'spectre':
                                if first:
                                    savestr += 'save %s:pwr %s:p' % (supply,supply)
                                    plotstr += '.print I(%s)' % (supply)
                                    first=False
                                else:
                                    savestr += ' %s:pwr %s:p' % (supply,supply)
                                    plotstr += ' I(%s)' % (supply)
                            elif self.parent.model == 'ngspice':
                                # Plots in tb only for interactive. Does not work in batch
                                if self.parent.interactive_spice:
                                    self._plotcmd += "plot I(%s)\n" % supply
                                self._plotcmd += "wrdata %s I(%s)\n" % (val.ext_file,supply)
                    # Output accumulated save and print statement to plotcmd
                    if self.parent.model=='spectre':
                        savestr += '\n'
                        plotstr += '\n'
                        self._plotcmd += savestr
                        self._plotcmd += 'simulator lang=spice\n'
                        self._plotcmd += '.option ingold 2\n'
                        self._plotcmd += plotstr
                        self._plotcmd += 'simulator lang=spectre\n'
            if self.parent.model=='ngspice':
                self._plotcmd += ".endc\n"
        return self._plotcmd
    @plotcmd.setter
    def plotcmd(self,value):
        self._plotcmd=value
    @plotcmd.deleter
    def plotcmd(self,value):
        self._plotcmd=None

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
if __name__=="__main__":
    pass
