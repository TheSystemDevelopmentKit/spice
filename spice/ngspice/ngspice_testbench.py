"""
=================
Ngspice Testbench
=================

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

class ngspice_testbench(testbench_common):
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
                self._options += self.parent.spice_simulator.option + optname + "=" + optval + "\n"
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
                libfile = thesdk.GLOBALS['NGSPICELIBFILE']
                if libfile == '':
                    raise ValueError
                else:
                    self._libcmd = "*** Ngspice device models\n"
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
    def portsrcstr(self):
        """
        Port source defintions parsed from from self.parent.spice_ports
        """
        if not hasattr(self, '_portsrcstr'):
            self.portsrcstr=''
            self.print_log(type='W', msg='Port support not yet implemented for ngspice!')
        return self._portsrcstr
    @portsrcstr.setter
    def portsrcstr(self, val):
        self._portsrcstr=val
    @portsrcstr.deleter
    def portsrcstr(self, val):
        self._portsrcstr=None

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
                    self._dcsourcestr += "%s %s %s %s %s\n" % \
                            (supply,val.pos,val.neg,value, \
                            'NONOISE' if not val.noise else '')
                else:
                    self._dcsourcestr += "%s %s %s %s %s\n" % \
                            (supply,val.pos,val.neg, \
                            'pulse(0 %g 0 %g)' % (value,abs(val.ramp)), \
                            'NONOISE' if not val.noise else '')
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
                            self._inputsignals += "a%s %%vd[%s 0] filesrc%s\n" % \
                                    (self.esc_bus(val.ionames[i].lower()),
                                    self.esc_bus(val.ionames[i].upper()),self.esc_bus(val.ionames[i].lower()))
                            self._inputsignals += ".model filesrc%s filesource (file=\"%s\"\n" % \
                                    (self.esc_bus(val.ionames[i].lower()),os.path.basename(val.file[i]).lower())
                            self._inputsignals += "+ amploffset=[0 0] amplscale=[1 1] timeoffset=0 timescale=1 timerelative=false amplstep=false)\n"

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
                            if (('<' not in val.ionames[i]) 
                                    and ('>' not in val.ionames[i]) 
                                    and len(str(val.Data[0,i])) == 1):
                                self._inputsignals += ( 'a%s [ %s_d ] input_vector_%s\n'
                                        % ( val.ionames[i], val.ionames[i], val.ionames[i]) )
                                # Ngsim assumes lowercase filenames, filenames must be quoted
                                self._inputsignals += (
                                        '.model input_vector_%s d_source(input_file = \"%s\")\n'
                                        % ( val.ionames[i], os.path.basename(val.file[i]).lower() )) 
                                self._inputsignals += (
                                        'adac_%s [ %s_d ] [ %s ] dac_%s\n' % ( val.ionames[i],
                                            val.ionames[i], val.ionames[i], val.ionames[i])
                                            )
                                self._inputsignals += (
                                    '.model dac_%s dac_bridge(out_low = %s out_high = %s out_undef = %s input_load = 5.0e-16 t_rise = %s t_fall = %s\n' %
                                    (val.ionames[i], val.vlo, val.vhi, (val.vhi+val.vlo)/2,
                                        val.trise, val.tfall )
                                    )
                            elif (('<' in val.ionames[i]) 
                                    and ('>' in val.ionames[i])):
                                signame = val.ionames[i]
                                signame = signame.replace('<',' ').replace('>',' ').replace('[',' ').replace(']',' ').replace(':',' ').split(' ')
                                busstart = int(signame[1])
                                busstop = int(signame[2])
                                loopstart=np.amin([busstart,busstop])
                                loopstop=np.amax([busstart,busstop])
                                self._inputsignals += ( 'a%s [ '
                                        % ( signame[0])
                                        )

                                for index in range(loopstart,loopstop+1):
                                    self._inputsignals += ( '%s_%s_d '
                                        % ( signame[0], index)
                                        )

                                self._inputsignals += ( '] input_vector_%s\n'
                                        % ( signame[0])
                                        )

                                # Ngsim assumes lowercase filenames
                                self._inputsignals += (
                                        '.model input_vector_%s d_source(input_file = %s)\n'
                                        % ( signame[0], os.path.basename(val.file[i]).lower() )
                                        ) 

                                # DAC
                                self._inputsignals += ( 'adac_%s [ ' % ( signame[0]) )

                                for index in range(loopstart,loopstop+1):
                                    self._inputsignals += ( '%s_%s_d '
                                            % ( signame[0], index))
                                self._inputsignals += ( '] [ ' )

                                for index in range(loopstart,loopstop+1):
                                    self._inputsignals += (
                                                '%s_%s_ ' % ( signame[0], index)
                                            )
                                self._inputsignals += (
                                            '] dac_%s\n' % ( signame[0])
                                        )
                                self._inputsignals += (
                                    '.model dac_%s dac_bridge(out_low = %s out_high = %s out_undef = %s input_load = 5.0e-16 t_rise = %s t_fall = %s' %
                                    (signame[0], val.vlo, val.vhi, (val.vhi+val.vlo)/2,
                                        val.trise, val.tfall )
                                    )
                            else:
                                busname = val.ionames[i]
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
        """String
        
        Simulation command definition parsed from spice_simcmd object
        instantiated in the parent entity.
        """
        if not hasattr(self,'_simcmdstr'):
            self._simcmdstr = "%s Simulation commands\n" % self.parent.spice_simulator.commentchar
            for sim, val in self.simcmds.Members.items():
                if str(sim).lower() == 'tran':
                    simtime = val.tstop if val.tstop is not None else self._trantime
                    if val.tstop is None:
                        self.print_log(type='D',msg='Inferred transient duration is %g s from \'%s\'.' % (simtime,self._trantime_name))
                    #TODO could this if-else be avoided?
                    self._simcmdstr += '.%s %s %s %s\n' % \
                            (sim,str(val.tprint),str(simtime),'uic' if val.uic else '')
                    if val.noise:
                        self.print_log(type='E', 
                                msg= ( 'Noise transient not available for Ngsim. Running regular transient.'))

                elif str(sim).lower() == 'dc':
                    self.print_log(type='E',msg='Unsupported model %s.' % self.parent.model)
                elif str(sim).lower() == 'ac':
                    if val.fscale.lower()=='dec':
                        if val.fpoints != 0:
                            pts_str='dec %d' % val.fpoints
                        else:
                            self.print_log(type='F', msg='Set fpoints for ngspice AC simulation!')
                    elif val.fscale.lower()=='lin':
                        if val.fpoints != 0:
                            pts_str='lin=%d' % val.fpoints
                        else:
                            self.print_log(type='F', msg='Set fpoints for ngspice AC simulation!')
                    else:
                        self.print_log(type='F', msg='Unsupported frequency scale %s for AC simulation!' % val.fscale)
                    self._simcmdstr += '.ac %s %s %s' % \
                            (pts_str,val.fmin,val.fmax)
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
                            # Plots in tb only for interactive. Does not work in batch
                            if self.parent.interactive_spice:
                                self._plotcmd += "plot I(%s)\n" % supply
                            self._plotcmd += "wrdata %s I(%s)\n" % (val.ext_file,supply)
            self._plotcmd += ".endc\n"
        return self._plotcmd
    @plotcmd.setter
    def plotcmd(self,value):
        self._plotcmd=value
    @plotcmd.deleter
    def plotcmd(self,value):
        self._plotcmd=None

