"""
=================
Spectre Testbench
=================

Simulators sepecific testbench generation class for Spectre.

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

class spectre_testbench(testbench_common):
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
            if self.parent.postlayout and 'savefilter' not in self.parent.spiceoptions:
                self.print_log(type='I', msg='Consider using option savefilter=rc for post-layout netlists to reduce output file size!')
            if self.parent.postlayout and 'save' not in self.parent.spiceoptions:
                self.print_log(type='I', msg='Consider using option save=none and specifiying saves with plotlist for post-layout netlists to reduce output file size!')
            i=0
            for optname,optval in self.parent.spiceoptions.items():
                self._options += "Option%d " % i # spectre options need unique names
                i+=1
                if optval != "":
                    self._options += self.parent.spice_simulator.option + ' ' + optname + "=" + optval + "\n"
                else:
                    self._options += ".option " + optname + "\n"

        return self._options
    @options.setter
    def options(self,value):
        self._options=value

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
                libfile = thesdk.GLOBALS['SPECTRELIBFILE']
                if libfile == '':
                    raise ValueError
                else:
                    self._libcmd = "// Spectre device models\n"
                    files = libfile.split(',')
                    if len(files)>1:
                        if isinstance(corner,list) and len(files) == len(corner):
                            for path,corn in zip(files,corner):
                                if not isinstance(corn, list):
                                    corn = [corn]
                                for c in corn:
                                    self._libcmd += 'include "%s" section=%s\n' % (path,c)
                        else:
                            self.print_log(type='W',msg='Multiple entries in SPECTRELIBFILE but spicecorner wasn\'t a list or contained different number of elements!')
                            self._libcmd += 'include "%s" section=%s\n' % (files[0], corner)
                    else:
                        self._libcmd += 'include "%s" section=%s\n' % (files[0], corner)
            except:
                self.print_log(type='W',msg='Global TheSDK variable SPECTRELIBPATH not set.')
                self._libcmd = "// Spectre device models (undefined)\n"
                self._libcmd += "//include " + libfile + " " + corner + "\n"
            self._libcmd += 'tempOption options temp=%s\n' % str(temp)
        return self._libcmd
    @libcmd.setter
    def libcmd(self,value):
        self._libcmd=value
    @libcmd.deleter
    def libcmd(self,value):
        self._libcmd=None

    @property
    def dcsourcestr(self):
        """str : DC source definitions parsed from spice_dcsource objects instantiated
        in the parent entity.
        """
        if not hasattr(self,'_dcsourcestr'):
            self._dcsourcestr = "%s DC sources\n" % self.parent.spice_simulator.commentchar
            for name, val in self.dcsources.Members.items():
                value = val.value if val.paramname is None else val.paramname
                supply = '%s%s' % (val.sourcetype.upper(),val.name.upper())
                if val.ramp == 0:
                    self._dcsourcestr += "%s %s %s %s%s\n" % \
                            (supply,self.esc_bus(val.pos),self.esc_bus(val.neg),\
                            ('%ssource dc=' % val.sourcetype.lower()),value)
                else:
                    self._dcsourcestr += "%s %s %s %s type=pulse val0=0 val1=%s rise=%g\n" % \
                            (supply,self.esc_bus(val.pos),self.esc_bus(val.neg),\
                            ('%ssource' % val.sourcetype.lower()),value,val.ramp)
        return self._dcsourcestr

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
                            if val.pos and val.neg:
                                self._inputsignals += "%s%s %s %s %ssource type=pwl file=\"%s\"\n" % \
                                        (val.sourcetype.upper(),self.esc_bus(val.ionames[i].lower()),
                                        self.esc_bus(val.pos), self.esc_bus(val.neg),val.sourcetype.lower(),val.file[i])
                            else:
                                self._inputsignals += "%s%s %s 0 %ssource type=pwl file=\"%s\"\n" % \
                                        (val.sourcetype.upper(),self.esc_bus(val.ionames[i].lower()),
                                        self.esc_bus(val.ionames[i]),val.sourcetype.lower(),val.file[i])
                    # Sample signals are digital
                    # Presumably these are already converted to bitstrings
                    elif val.iotype.lower()=='sample':
                        for i in range(len(val.ionames)):
                            # This is a lazy way to handle non-list val.Data
                            try:
                                if float(self._trantime) < len(val.Data)/val.rs:
                                    self._trantime = len(val.Data)/val.rs
                                    self._trantime_name = name
                            except:
                                pass
                            self._inputsignals += 'vec_include "%s"\n' % val.file[i]
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
                if val.mc:
                    self._simcmdstr += 'mc montecarlo donominal=no variations=all %snumruns=1 {\n' \
                            % ('' if val.mc_seed is None else 'seed=%d '%val.mc_seed)
                if str(sim).lower() == 'tran':
                    simtime = val.tstop if val.tstop is not None else self._trantime
                    if val.tstop is None:
                        self.print_log(type='D',msg='Inferred transient duration is %g s from \'%s\'.' % (simtime,self._trantime_name))
                    #TODO initial conditions
                    self._simcmdstr += 'TRAN_analysis %s pstep=%s stop=%s %s ' % \
                            (sim,str(val.tprint),str(simtime),'UIC' if val.uic else '')
                    if val.noise:
                        if val.seed==0:
                            self.print_log(type='W',msg='Spectre disables noise if seed=0.')
                        self._simcmdstr += 'trannoisemethod=default noisefmin=%s noisefmax=%s %s ' % \
                                (str(val.fmin),str(val.fmax),'noiseseed=%d'%(val.seed) if val.seed is not None else '')
                    if val.method is not None:
                        self._simcmdstr += 'method=%s ' %  (str(val.method))
                    if val.cmin is not None:
                        self._simcmdstr += 'cmin=%s ' %  (str(val.cmin))
                    if val.maxstep is not None:
                        self._simcmdstr += 'maxstep=%s ' % (str(val.maxstep))
                    if val.step is not None:
                        self._simcmdstr += 'step=%s ' % (str(val.step))
                    if val.strobeperiod is not None:
                        self._simcmdstr += 'strobeperiod=%s strobeoutput=strobeonly ' % (str(val.strobeperiod))
                    if val.strobedelay is not None:
                        self._simcmdstr += 'strobedelay=%s' % (str(val.strobedelay))
                    if val.skipstart is not None:
                        self._simcmdstr += 'skipstart=%s' % (str(val.skipstart))
                    self._simcmdstr += '\n\n' 

                elif str(sim).lower() == 'dc':
                    if len(val.sweep) == 0: # This is not a sweep analysis
                        self._simcmdstr+='oppoint dc\n\n'
                    else:
                        if self.parent.distributed_run:
                            distributestr = 'distribute=lsf numprocesses=%d' % self.parent.num_processes 
                        else:
                            distributestr = ''
                        if len(val.subcktname) != 0: # Sweep subckt parameter
                            length=len(val.subcktname)
                            if any(len(lst) != length for lst in [val.sweep, val.swpstart, val.swpstop, val.swpstep]):
                                self.print_log(type='F', msg='Mismatch in length of simulation parameters.\nEnsure that sweep points and subcircuit names have the same number of elements!')
                            for i in range(len(val.subcktname)):
                                self._simcmdstr+='Sweep%d sweep param=%s sub=%s start=%s stop=%s step=%s %s { \n' \
                                    % (i, val.sweep[i], val.subcktname[i], val.swpstart[i], val.swpstop[i], val.swpstep[i], distributestr)
                        elif len(val.devname) != 0: # Sweep device parameter
                            length=len(val.devname)
                            if any(len(lst) != length for lst in [val.sweep, val.swpstart, val.swpstop, val.swpstep]):
                                self.print_log(type='F', msg='Mismatch in length of simulation parameters.\nEnsure that sweep points and device names have the same number of elements!')
                            for i in range(len(val.devname)):
                                self._simcmdstr+='Sweep%d sweep param=%s dev=%s start=%s stop=%s step=%s %s { \n' \
                                    % (i, val.sweep[i], val.devname[i], val.swpstart[i], val.swpstop[i], val.swpstep[i], distributestr)
                        else: # Sweep top-level netlist parameter
                            length=len(val.sweep)
                            if any(len(lst) != length for lst in [val.swpstart, val.swpstop, val.swpstep]):
                                self.print_log(type='F', msg='Mismatch in length of simulation parameters.\nEnsure that sweep points and parameter names have the same number of elements!')
                            for i in range(len(val.sweep)):
                                self._simcmdstr+='Sweep%d sweep param=%s start=%s stop=%s step=%s %s { \n' \
                                    % (i, val.sweep[i], val.swpstart[i], val.swpstop[i], val.swpstep[i], distributestr)
                        self._simcmdstr+='oppoint dc\n'
                        # Closing brackets
                        for j in range(i, -1, -1):
                            self._simcmdstr+='}\n'
                        self._simcmdstr+='\n'
                elif str(sim).lower() == 'ac':
                    if val.fscale.lower()=='log':
                        if val.fpoints != 0:
                            pts_str='log=%d' % val.fpoints
                        elif val.fstepsize != 0:
                            pts_str='dec=%d' % val.fstepsize
                        else:
                            self.print_log(type='F', msg='Set either fpoints or fstepsize for AC simulation!')
                    elif val.fscale.lower()=='lin':
                        if val.fpoints != 0:
                            pts_str='lin=%d' % val.fpoints
                        elif val.fstepsize != 0:
                            pts_str='step=%d' % val.fstepsize
                        else:
                            self.print_log(type='F', msg='Set either fpoints or fstepsize for AC simulation!')
                    else:
                        self.print_log(type='F', msg='Unsupported frequency scale %s for AC simulation!' % val.fscale)
                    self._simcmdstr += 'AC_analysis %s start=%s stop=%s %s' % \
                            (sim,str(val.fmin),str(val.fmax),pts_str)
                    self._simcmdstr += '\n\n'

                else:
                    self.print_log(type='E',msg='Simulation type \'%s\' not yet implemented.' % str(sim))
                if val.mc:
                    self._simcmdstr += '}\n\n'
            if val.model_info:
                self._simcmdstr += 'element info what=inst where=rawfile \nmodelParameter info what=models where=rawfile\n\n'
        return self._simcmdstr
    @simcmdstr.setter
    def simcmdstr(self,value):
        self._simcmdstr=value
    @simcmdstr.deleter
    def simcmdstr(self,value):
        self._simcmdstr=None

    @property
    def plotcmd(self):
        """str : All output IOs are mapped to plot or print statements in the testbench.
        Also manual plot commands through `spice_simcmd.plotlist` are handled here.

        """

        if not hasattr(self,'_plotcmd'):
            self._plotcmd = "" 
            for name, val in self.simcmds.Members.items():
                # Manual probes
                if len(val.plotlist) > 0 and name.lower() != 'dc':
                    self._plotcmd = "%s Manually probed signals\n" % self.parent.spice_simulator.commentchar
                    self._plotcmd += 'save ' 

                    for i in val.plotlist:
                        self._plotcmd += self.esc_bus(i) + " "
                    self._plotcmd += "\n\n"
                #DC probes
                if len(val.plotlist) > 0 and name.lower() == 'dc':
                    self._plotcmd = "%s DC operating points to be captured:\n" % self.parent.spice_simulator.commentchar
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
                                        if first:
                                            savestr += 'save %s' % self.esc_bus(trig)
                                            plotstr += '.print v(%s)' % (trig)
                                            first=False
                                        else:
                                            savestr += ' %s' % self.esc_bus(trig) 
                                            plotstr += ' v(%s)' % (trig)
                                    for j in busrange:
                                        if buswidth == 1 and '<' not in val.ionames[i]:
                                            bitname = signame[0]
                                        else:
                                            bitname = '%s<%d>' % (signame[0],j)
                                        # If not already, add the bit voltage to iofile_eventdict
                                        if bitname not in self.parent.iofile_eventdict:
                                            self.parent.iofile_eventdict[bitname] = None
                                            if first:
                                                savestr += 'save %s' % self.esc_bus(bitname)
                                                plotstr += '.print %s(%s)' % (val.sourcetype, bitname)
                                                first=False
                                            else:
                                                savestr += ' %s' % self.esc_bus(bitname)
                                                plotstr += ' %s(%s)' % (val.sourcetype, bitname)
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
                                        if first:
                                            savestr += 'save %s' % signame
                                            plotstr += '.print %s(%s)' % (val.sourcetype, val.ionames[i])
                                            first=False
                                        else:
                                            savestr += ' %s' % signame
                                            plotstr += ' %s(%s)' % (val.sourcetype, val.ionames[i])
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
                            if first:
                                savestr += 'save %s:pwr %s:p' % (supply,supply)
                                plotstr += '.print I(%s)' % (supply)
                                first=False
                            else:
                                savestr += ' %s:pwr %s:p' % (supply,supply)
                                plotstr += ' I(%s)' % (supply)
                    # Output accumulated save and print statement to plotcmd
                    savestr += '\n'
                    plotstr += '\n'
                    self._plotcmd += savestr
                    self._plotcmd += 'simulator lang=spice\n'
                    self._plotcmd += '.option ingold 2\n'
                    # Format the output to same "table", 15 bits per column
                    self._plotcmd += '.option co=%d\n' % (self.num_cols)
                    self._plotcmd += plotstr
                    self._plotcmd += 'simulator lang=spectre\n'
        return self._plotcmd
    @plotcmd.setter
    def plotcmd(self,value):
        self._plotcmd=value
    @plotcmd.deleter
    def plotcmd(self,value):
        self._plotcmd=None

    @property
    def num_cols(self):
        '''
        Number of columns in the output file, when using Spectre.
        Each signal takes 1 column (unless it is complex, then two).
        Each column is 15 bit wide, hence number of columns is multiplied by 15.
        '''
        if not hasattr(self, '_num_cols'):
            self._num_cols=0
            pdb.set_trace()
            for name, val in self.iofiles.Members.items():
                if val.dir.lower() == 'out':
                    if val.datatype.lower() == 'complex':
                        self._num_cols += 2
                    else:
                        self._num_cols += 1
        self._num_cols *= 15
        return self._num_cols

    @num_cols.setter
    def num_cols(self, val):
        self._num_cols=val

