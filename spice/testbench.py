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
from abc import * 
from thesdk import *
from spice import *
from spice.spice_module import spice_module
import pdb

import numpy as np
import pandas as pd
from functools import reduce
import textwrap
from datetime import datetime

class testbench(spice_module):
    """
    This class generates all testbench contents.
    This class is utilized by the main spice class.

    """
    @property
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    def __init__(self, parent=None, **kwargs):
        if parent==None:
            self.print_log(type='F', msg="Parent of spice testbench not given.")
        else:
            self.parent=parent
        try:  
            # This attribute holds duration of longest input vector after reading input files
            self._trantime=0
        except:
            self.print_log(type='F', msg="Spice Testbench file definition failed.")
        
        #The methods for these are derived from spice_module
        self._name=''
        self.iofiles=Bundle()
        self.dcsources=Bundle()
        self.simcmds=Bundle()
        self.dut=spice_module(file=self.parent.spicesrc)
        #This is mandatory until the refactoring is done
        self.dut.parent=parent
        

    # Generating spice options string
    @property
    def options(self):
        """String
        
        Spice options string parsed from self.spiceoptions -dictionary in the
        parent entity.
        """
        if not hasattr(self,'_options'):
            self._options = "%s Options\n" % self.parent.syntaxdict["commentchar"]
            i=0
            if self.parent.model == 'spectre':
                if self.parent.postlayout and 'savefilter' not in self.parent.spiceoptions:
                    self.print_log(type='I', msg='Consider using option savefilter=rc for post-layout netlists to reduce output file size!')
                if self.parent.postlayout and 'save' not in self.parent.spiceoptions:
                    self.print_log(type='I', msg='Consider using option save=none and specifiying saves with plotlist for post-layout netlists to reduce output file size!')
            for optname,optval in self.parent.spiceoptions.items():
                if self.parent.model=='spectre':
                    self._options += "Option%d " % i # spectre options need unique names
                    i+=1
                if optval != "":
                    self._options += self.parent.syntaxdict["option"] + optname + "=" + optval + "\n"
                else:
                    self._options += ".option " + optname + "\n"
        return self._options
    @options.setter
    def options(self,value):
        self._options=value
    @options.deleter
    def options(self,value):
        self._options=None

    # Generating eldo/spectre parameters string
    @property
    def parameters(self):
        """String
        
        Spice parameters string parsed from self.spiceparameters -dictionary in
        the parent entity.
        """
        if not hasattr(self,'_parameters'):
            self._parameters = "%s Parameters\n" % self.parent.syntaxdict["commentchar"]
            for parname,parval in self.parent.spiceparameters.items():
                self._parameters += self.parent.syntaxdict["parameter"] + str(parname) + "=" + str(parval) + "\n"
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
        """String
        
        Library inclusion string. Parsed from self.spicecorner -dictionary in
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
            if self.parent.model == 'eldo':
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
            if self.parent.model == 'spectre':
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
            if self.parent.model == 'ngspice':
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

    # Generating netlist inclusion string
    @property
    def includecmd(self):
        """String
        
        Subcircuit inclusion string pointing to generated subckt_* -file.
        """
        if not hasattr(self,'_includecmd'):
            self._includecmd = "%s Subcircuit file\n"  % self.parent.syntaxdict["commentchar"]
            self._includecmd += "%s \"%s\"\n" % (self.parent.syntaxdict["include"],self.parent.spicesubcktsrc)
        return self._includecmd
    @includecmd.setter
    def includecmd(self,value):
        self._includecmd=value
    @includecmd.deleter
    def includecmd(self,value):
        self._includecmd=None

    # DSPF include commands
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
                                        print(line.replace(self._origcellname,self.parent.name.upper()),end='')
                            self.print_log(type='I',msg='Including DSPF-file: %s' % dspfpath)
                            self._dspfincludecmd += "%s \"%s\"\n" % (self.parent.spice_simulator.dspfinclude,dspfpath)
                    except:
                        self.print_log(type='F',msg='DSPF-file did not contain matching desing for %s' % self.parent.name)
                        self.print_log(type='F',msg=traceback.format_exc())
                else:
                    self.postlayout = False
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
            self._misccmd="%s Manual commands\n" % (self.parent.syntaxdict["commentchar"])
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

    # Generating spice dcsources string
    @property
    def dcsourcestr(self):
        """String
        
        DC source definitions parsed from spice_dcsource objects instantiated
        in the parent entity.
        """
        if not hasattr(self,'_dcsourcestr'):
            self._dcsourcestr = "%s DC sources\n" % self.parent.syntaxdict["commentchar"]
            for name, val in self.dcsources.Members.items():
                value = val.value if val.paramname is None else val.paramname
                supply = '%s%s' % (val.sourcetype.upper(),val.name.upper())
                if self.parent.model == 'eldo':
                    if val.ramp == 0:
                        self._dcsourcestr += "%s %s %s %s %s\n" % \
                                (supply,val.pos,val.neg,value, \
                                'NONOISE' if not val.noise else '')
                    else:
                        self._dcsourcestr += "%s %s %s %s %s\n" % \
                                (supply,val.pos,val.neg, \
                                'pulse(0 %g 0 %g)' % (value,abs(val.ramp)), \
                                'NONOISE' if not val.noise else '')
                elif self.parent.model == 'spectre':
                    if val.ramp == 0:
                        self._dcsourcestr += "%s %s %s %s%s\n" % \
                                (supply,self.esc_bus(val.pos),self.esc_bus(val.neg),\
                                ('%ssource dc=' % val.sourcetype.lower()),value)
                    else:
                        self._dcsourcestr += "%s %s %s %s type=pulse val0=0 val1=%s rise=%g\n" % \
                                (supply,self.esc_bus(val.pos),self.esc_bus(val.neg),\
                                ('%ssource' % val.sourcetype.lower()),value,val.ramp)
                elif self.parent.model == 'ngspice':
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

    # Generating inputsignals string
    @property
    def inputsignals(self):
        """String
        
        Input signal definitions parsed from spice_iofile objects instantiated
        in the parent entity.
        """
        if not hasattr(self,'_inputsignals'):
            self._inputsignals = "%s Input signals\n" % self.parent.syntaxdict["commentchar"]
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
                            if self.parent.model=='eldo':
                                self._inputsignals += "%s%s %s 0 pwl(file=\"%s\")\n" % \
                                        (val.sourcetype.upper(),val.ionames[i].lower(),val.ionames[i].upper(),val.file[i])
                            elif self.parent.model=='spectre':
                                if val.pos and val.neg:
                                    self._inputsignals += "%s%s %s %s %ssource type=pwl file=\"%s\"\n" % \
                                            (val.sourcetype.upper(),self.esc_bus(val.ionames[i].lower()),
                                            self.esc_bus(val.pos), self.esc_bus(val.neg),val.sourcetype.lower(),val.file[i])
                                else:
                                    self._inputsignals += "%s%s %s 0 %ssource type=pwl file=\"%s\"\n" % \
                                            (val.sourcetype.upper(),self.esc_bus(val.ionames[i].lower()),
                                            self.esc_bus(val.ionames[i]),val.sourcetype.lower(),val.file[i])
                            elif self.parent.model=='ngspice':
                                self._inputsignals += "a%s %%vd[%s 0] filesrc%s\n" % \
                                        (self.esc_bus(val.ionames[i].lower()),
                                        self.esc_bus(val.ionames[i].upper()),self.esc_bus(val.ionames[i].lower()))
                                self._inputsignals += ".model filesrc%s filesource (file=\"%s\"\n" % \
                                        (self.esc_bus(val.ionames[i].lower()),os.path.basename(val.file[i]).lower())
                                self._inputsignals += "+ amploffset=[0 0] amplscale=[1 1] timeoffset=0 timescale=1 timerelative=false amplstep=false)\n"
                    # Sample signals are digital
                    # Presumably these are already converted to bitstrings
                    elif val.iotype.lower()=='sample':
                        if self.parent.model == 'eldo':
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
                        elif self.parent.model == 'spectre':
                            for i in range(len(val.ionames)):
                                # This is a lazy way to handle non-list val.Data
                                try:
                                    if float(self._trantime) < len(val.Data)/val.rs:
                                        self._trantime = len(val.Data)/val.rs
                                        self._trantime_name = name
                                except:
                                    pass
                                self._inputsignals += 'vec_include "%s"\n' % val.file[i]
                        elif self.parent.model == 'ngspice':
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
                                    # Ngsim assumes lowercase filenames
                                    self._inputsignals += (
                                            '.model input_vector_%s d_source(input_file = %s)\n'
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

    # Generating simcmds string
    @property
    def simcmdstr(self):
        """String
        
        Simulation command definition parsed from spice_simcmd object
        instantiated in the parent entity.
        """
        if not hasattr(self,'_simcmdstr'):
            self._simcmdstr = "%s Simulation commands\n" % self.parent.syntaxdict["commentchar"]
            for sim, val in self.simcmds.Members.items():
                if val.mc and self.parent.model=='spectre':
                    self._simcmdstr += 'mc montecarlo donominal=no variations=all %snumruns=1 {\n' \
                            % ('' if val.mc_seed is None else 'seed=%d '%val.mc_seed)
                if str(sim).lower() == 'tran':
                    simtime = val.tstop if val.tstop is not None else self._trantime
                    if val.tstop is None:
                        self.print_log(type='D',msg='Inferred transient duration is %g s from \'%s\'.' % (simtime,self._trantime_name))
                    #TODO could this if-else be avoided?
                    if self.parent.model=='eldo':
                        self._simcmdstr += '.%s %s %s %s\n' % \
                                (sim,str(val.tprint),str(simtime),'UIC' if val.uic else '')
                        if val.noise:
                            self._simcmdstr += '.noisetran fmin=%s fmax=%s nbrun=1 NONOM %s\n' % \
                                    (str(val.fmin),str(val.fmax),'seed=%d'%(val.seed) if val.seed is not None else '')
                    elif self.parent.model=='spectre':
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
                    elif self.parent.model=='ngspice':
                        self._simcmdstr += '.%s %s %s %s\n' % \
                                (sim,str(val.tprint),str(simtime),'uic' if val.uic else '')
                        if val.noise:
                            self.print_log(type='E', 
                                    msg= ( 'Noise transient not available for Ngsim. Running regular transient.'))

                elif str(sim).lower() == 'dc':
                    if self.parent.model=='eldo':
                        self._simcmdstr='.op'
                    elif self.parent.model=='spectre':
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
                    else:
                        self.print_log(type='E',msg='Unsupported model %s.' % self.parent.model)
                elif str(sim).lower() == 'ac':
                    if self.parent.model=='eldo':
                        print_log(type='F', msg='AC simulation for eldo not yet implemented')
                    elif self.parent.model=='spectre':
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
                    elif self.parent.model=='ngspice':
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
                if val.mc and self.parent.model=='spectre':
                    self._simcmdstr += '}\n\n'
            if val.model_info and self.parent.model=='spectre':
                self._simcmdstr += 'element info what=inst where=rawfile \nmodelParameter info what=models where=rawfile\n\n'
        return self._simcmdstr
    @simcmdstr.setter
    def simcmdstr(self,value):
        self._simcmdstr=value
    @simcmdstr.deleter
    def simcmdstr(self,value):
        self._simcmdstr=None
    
    def esc_bus(self,name, esc_colon=True):
        """
        Helper function to escape bus characters for Spectre simulations::

            self.esc_bus('bus<3:0>') 
            # Returns 'bus\<3\:0\>'
        """
        if self.parent.model == 'spectre':
            if esc_colon:
                return name.replace('<','\\<').replace('>','\\>').replace('[','\\[').replace(']','\\]').replace(':','\\:')
            else: # Cannot escape colon for DC analyses..
                return name.replace('<','\\<').replace('>','\\>').replace('[','\\[').replace(']','\\]')
        else:
            return name

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
                    self._plotcmd = "%s Manually probed signals\n" % self.parent.syntaxdict["commentchar"]
                    if self.parent.model == 'eldo': 
                        self._plotcmd += '.plot ' 
                    else:
                        self._plotcmd += 'save ' 

                    for i in val.plotlist:
                        self._plotcmd += self.esc_bus(i) + " "
                    self._plotcmd += "\n\n"
                #DC probes
                if len(val.plotlist) > 0 and name.lower() == 'dc':
                    self._plotcmd = "%s DC operating points to be captured:\n" % self.parent.syntaxdict["commentchar"]
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
                    self._plotcmd += "%s Output signals\n" % self.parent.syntaxdict["commentchar"]
                    if self.parent.model=='ngspice':
                        self._plotcmd += ".control\nset wr_singlescale\nset wr_vecnames\nset appendwrite\n"
                        if self.parent.nproc: 
                            self._plotcmd +="%s%d\n" % (self.parent.syntaxdict["nprocflag"],self.parent.nproc)
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

    def export_subckts(self,**kwargs):
        """
        Function to write the parsed DUT subcircuit definitions
        to a tempory file defined by self.parent.spicesubcktsrc.
        """
        if not os.path.isfile(self.parent.spicesubcktsrc):
            self.print_log(type='D',msg='Exporting spice subcircuit to %s' %(self.parent.spicesubcktsrc))
            with open(self.parent.spicesubcktsrc, "w") as module_file:
                module_file.write(self.dut.subckt)

        elif os.path.isfile(self.parent.spicesubcktsrc) and not kwargs.get('force'):
            self.print_log(type='F', msg=('Export target file %s exists.\n Force overwrite with force=True.' %(self.parent.spicesubcktsrc)))

        elif kwargs.get('force'):
            self.print_log(type='I',msg='Forcing overwrite of spice subcircuit to %s.' %(self.parent.spicesubcktsrc))
            with open(self.parent.spicesubcktsrc, "w") as module_file:
                module_file.write(self.dut.subckt)

    def generate_contents(self):
        """
        Internally called function to generate testbench contents.
        """
        date_object = datetime.now()
        headertxt = self.parent.syntaxdict["commentline"] +\
                    "%s Testbench for %s\n" % (self.parent.syntaxdict["commentchar"],self.parent.name) +\
                    "%s Generated on %s \n" % (self.parent.syntaxdict["commentchar"],date_object) +\
                    self.parent.syntaxdict["commentline"]
        libcmd = self.libcmd
        includecmd = self.includecmd
        subinst = self.dut.instance
        dspfincludecmd = self.dspfincludecmd
        options = self.options
        params = self.parameters
        dcsourcestr = self.dcsourcestr
        inputsignals = self.inputsignals
        misccmd = self.misccmd
        simcmd = self.simcmdstr
        plotcmd = self.plotcmd
        self.contents = (headertxt + "\n" +
                        libcmd + "\n" +\
                        includecmd + "\n" +
                        dspfincludecmd + "\n" +
                        options + "\n" +\
                        params + "\n" +
                        subinst + "\n\n" +\
                        misccmd + "\n" +
                        dcsourcestr + "\n" +\
                        inputsignals + "\n" +\
                        simcmd + "\n" +\
                        plotcmd + "\n" +\
                        self.parent.syntaxdict["lastline"])

    def export(self,**kwargs):
        """
        Write the testbench to a file defined by self.parent.spicetbsrc.

        """
        if not os.path.isfile(self.parent.spicetbsrc):
            self.print_log(type='D',msg='Exporting spice testbench to %s' %(self.parent.spicetbsrc))
            with open(self.parent.spicetbsrc, "w") as module_file:
                module_file.write(self.contents)

        elif os.path.isfile(self.parent.spicetbsrc) and not kwargs.get('force'):
            self.print_log(type='F', msg=('Export target file %s exists.\n Force overwrite with force=True.' %(self.parent.spicetbsrc)))

        elif kwargs.get('force'):
            self.print_log(type='I',msg='Forcing overwrite of spice testbench to %s.' %(self.parent.spicetbsrc))
            with open(self.parent.spicetbsrc, "w") as module_file:
                module_file.write(self.contents)
if __name__=="__main__":
    pass
