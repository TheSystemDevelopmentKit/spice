"""
===============
Spice Testbench
===============

Testbench generation class for spice simulations.
Generates testbenches for eldo and spectre.


"""
import os
import sys
import subprocess
import shlex
import fileinput
from abc import * 
from thesdk import *
from spice import *
from spice.module import spice_module
import pdb

import numpy as np
import pandas as pd
from functools import reduce
import textwrap
from datetime import datetime

# Utilizes logging method from thesdk
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
            self.print_log(type='F', msg="Parent of spice testbench not given")
        else:
            self.parent=parent
        try:  
            if self.parent.interactive_spice:
                self._file=self.parent.spicesrcpath + '/tb_' + self.parent.name + self.parent.syntaxdict["cmdfile_ext"]
                self._subcktfile=self.parent.spicesrcpath + '/subckt_' + self.parent.name + self.parent.syntaxdict["cmdfile_ext"]
            else:
                self._file=self.parent.spicesimpath + '/tb_' + self.parent.name + self.parent.syntaxdict["cmdfile_ext"]
                #self._dutfile=self.parent.spicesimpath + '/subckt_' + self.parent.name + self.parent.syntaxdict["cmdfile_ext"]
                self._subcktfile=self.parent.spicesimpath + '/subckt_' + self.parent.name + self.parent.syntaxdict["cmdfile_ext"]
            self._dutfile=self.parent.spicesrcpath + '/' + self.parent.name + self.parent.syntaxdict["cmdfile_ext"]

            # This variable holds duration of longest input vector after reading input files
            self._trantime=0
        except:
            self.print_log(type='F', msg="Spice Testbench file definition failed")
        
        #The methods for these are derived from spice_module
        self._name=''
        self.iofiles=Bundle()
        self.dcsources=Bundle()
        self.simcmds=Bundle()
        
    @property
    def file(self):
        """String
        
        Filepath to the testbench file (i.e. './spice/tb_entityname.scs').
        """
        if not hasattr(self,'_file'):
            self._file=None
        return self._file
    @file.setter
    def file(self,value):
            self._file=value

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
                if self.postlayout and 'savefilter' not in self.parent.spiceoptions:
                    self.print_log(type='I', msg='Consider using option savefilter=rc for post-layout netlists to reduce output file size!')
                if self.postlayout and 'save' not in self.parent.spiceoptions:
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
                    self.print_log(type='W',msg='Global TheSDK variable ELDOLIBPATH not set.')
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
                        self._libcmd += 'include "%s" section=%s\n' % (libfile,corner)
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
                    self.print_log(type='W',msg='Global TheSDK variable ELDOLIBPATH not set.')
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
            self._includecmd += "%s \"%s\"\n" % (self.parent.syntaxdict["include"],self._subcktfile)
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
                self.postlayout = True
                self._dspfincludecmd = "%s Extracted parasitics\n"  % self.parent.syntaxdict["commentchar"]
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
                                    if cellname == self.origcellname:
                                        self.print_log(type='I',msg='Found DSPF cell name matching to original top-level cell name.')
                                        rename = True

                                    break
                        if rename:
                            self.print_log(type='I',msg='Renaming DSPF top cell name accordingly from "%s" to "%s".' % (cellname,self.parent.name))
                            with fileinput.FileInput(dspfpath,inplace=True,backup='.bak') as f:
                                for line in f:
                                    print(line.replace(self.origcellname,self.parent.name.upper()),end='')
                        self.print_log(type='I',msg='Including DSPF-file: %s' % dspfpath)
                        self._dspfincludecmd += "%s \"%s\"\n" % (self.parent.syntaxdict["dspfinclude"],dspfpath)
                    except:
                        self.print_log(type='W',msg='DSPF-file not found: %s' % dspfpath)
                        self.print_log(type='I',msg=traceback.format_exc())
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

    @property
    def ahdlincludecmd(self):
        """String
        
        Verilog-A inclusion string pointing to file-IO utility blocks, as well
        as manually added Verilog-A files defined in self.ahdlpath in the
        parent entity.
        """
        if not hasattr(self,'_ahdlincludecmd'):
            if self.parent.model == 'spectre':
                self._ahdlincludecmd="%s VerilogA block includes\n" % (self.parent.syntaxdict["commentchar"])
                self._ahdlincludecmd += 'ahdl_include "' + self.parent.entitypath + '/../spice/spice/veriloga_csv_write_edge.va"\n'
                self._ahdlincludecmd += 'ahdl_include "' + self.parent.entitypath + '/../spice/spice/veriloga_csv_write_allpoints.va"\n'
                self._ahdlincludecmd += 'ahdl_include "' + self.parent.entitypath + '/../spice/spice/veriloga_csv_write_allpoints_current.va"\n'
                ahldincludes = self.parent.ahdlpath
                for ahdlfile in ahldincludes:
                    self._ahdlincludecmd += 'ahdl_include' + ahdlfile + "\n"
            else:
                self._ahdlincludecmd = ''
        return self._ahdlincludecmd
    @ahdlincludecmd.setter
    def ahdlincludecmd(self,value):
        self._ahdlincludecmd=value
    @ahdlincludecmd.deleter
    def ahdlincludecmd(self,value):
        self._ahdlincludecmd=None

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
                if self.parent.model == 'eldo':
                    if val.ramp == 0:
                        self._dcsourcestr += "%s%s %s %s %g %s\n" % \
                                (val.sourcetype.upper(),val.name.lower(),val.pos,val.neg,val.value, \
                                'NONOISE' if not val.noise else '')
                    else:
                        self._dcsourcestr += "%s%s %s %s %s %s\n" % \
                                (val.sourcetype.upper(),val.name.lower(),val.pos,val.neg, \
                                'pulse(0 %g 0 %g)' % (val.value,abs(val.ramp)), \
                                'NONOISE' if not val.noise else '')
                    # If the DC source is a supply, the power consumption is extracted for it automatically
                    if val.extract:
                        supply = "%s%s"%(val.sourcetype.upper(),val.name.lower())
                        self._dcsourcestr += ".defwave p_%s=v(%s)*i(%s)\n" % \
                                (supply.lower(),supply,supply)
                        self._dcsourcestr += ".extract label=current_%s abs(average(i(%s),%s,%s))\n" % \
                                (supply.lower(),supply,val.ext_start,val.ext_stop)
                        self._dcsourcestr += ".extract label=power_%s abs(average(w(p_%s),%s,%s))\n" % \
                                (supply.lower(),supply.lower(),val.ext_start,val.ext_stop)
                elif self.parent.model == 'spectre':
                    if val.extract:
                        probenode = '_p'
                    else:
                        probenode = ''
                    if val.ramp == 0:
                        self._dcsourcestr += "%s%s %s%s %s %s%g\n" % \
                                (val.sourcetype.upper(),val.name.lower(),self.esc_bus(val.pos),
                                        probenode,self.esc_bus(val.neg),
                                ('%ssource dc=' % val.sourcetype.lower()),val.value)
                    else:
                        self._dcsourcestr += "%s%s %s%s %s %s type=pulse val0=0 val1=%g rise=%g\n" % \
                                (val.sourcetype.upper(),val.name.lower(),self.esc_bus(val.pos),probenode,
                                        self.esc_bus(val.neg),('%ssource' % val.sourcetype.lower()),val.value,val.ramp)
                    if val.extract:
                        # Plotting power and current waveforms for this supply
                        self._dcsourcestr += 'save %s%s:pwr\n' % (val.sourcetype.upper(),val.name.lower())
                        self._dcsourcestr += 'save %s%s:p\n' % (val.sourcetype.upper(),val.name.lower())
                        # Writing source current consumption to a file
                        self._dcsourcestr += "pwrout_%s%s (%s_p %s) veriloga_csv_write_allpoints_current filename=\"%s\"\n" % \
                            (val.sourcetype.lower(),val.name.lower().replace('.','_'),self.esc_bus(val.pos),self.esc_bus(val.pos),val._extfile)
                elif self.parent.model == 'ngspice':
                    if val.ramp == 0:
                        self._dcsourcestr += "%s%s %s %s %g %s\n" % \
                                (val.sourcetype.upper(),val.name.lower(),val.pos,val.neg,val.value, \
                                'NONOISE' if not val.noise else '')
                    else:
                        self._dcsourcestr += "%s%s %s %s %s %s\n" % \
                                (val.sourcetype.upper(),val.name.lower(),val.pos,val.neg, \
                                'pulse(0 %g 0 %g)' % (val.value,abs(val.ramp)), \
                                'NONOISE' if not val.noise else '')
                    # If the DC source is a supply, the power consumption is extracted for it automatically
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
                            maxtime = val.Data[-1,0]
                            if float(self._trantime) < float(maxtime):
                                self._trantime = maxtime
                                self._trantime_name = name
                            # Adding the source
                            if self.parent.model=='eldo':
                                self._inputsignals += "%s%s %s 0 pwl(file=\"%s\")\n" % \
                                        (val.sourcetype.upper(),val.ionames[i].lower(),val.ionames[i].upper(),val.file[i])
                            elif self.parent.model=='spectre':
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
                                        '.model dac_%s dac_bridge(out_low = %s out_high = %s out_undef = %s input_load = 5.0e-16 t_rise = %s t_fall = %s' %
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
                        self.print_log(type='I',msg='Inferred transient duration is %g s from \'%s\'.' % (simtime,self._trantime_name))
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
                        if val.sweep == '': # This is not a sweep analysis
                            self._simcmdstr+='oppoint dc\n\n'
                        else:
                            if self.parent.distributed_run:
                                distributestr = 'distribute=lsf numprocesses=%d' % self.parent.num_processes 
                            else:
                                distributestr = ''
                            if val.subcktname != '': # Sweep subckt parameter
                                self._simcmdstr+='%sSweep sweep param=%s sub=%s start=%s stop=%s step=%s %s { \n' \
                                    % (val.sweep, val.sweep, val.subcktname, val.swpstart, val.swpstop, val.swpstep, distributestr)
                            elif val.devname != '': # Sweep device parameter
                                self._simcmdstr+='%sSweep sweep param=%s dev=%s start=%s stop=%s step=%s %s { \n' \
                                    % (val.sweep, val.sweep, val.devname, val.swpstart, val.swpstop, val.swpstep, distributestr)
                            else: # Sweep top-level netlist parameter
                                self._simcmdstr+='%sSweep sweep param=%s start=%s stop=%s step=%s %s { \n' \
                                    % (val.sweep, val.sweep, val.swpstart, val.swpstop, val.swpstep, distributestr)
                            self._simcmdstr+='\toppoint dc\n}\n\n'

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

                else:
                    self.print_log(type='E',msg='Simulation type \'%s\' not yet implemented.' % str(sim))
                if val.mc and self.parent.model=='spectre':
                    self._simcmdstr += '}\n\n'
        return self._simcmdstr
    @simcmdstr.setter
    def simcmdstr(self,value):
        self._simcmdstr=value
    @simcmdstr.deleter
    def simcmdstr(self,value):
        self._simcmdstr=None
    
    def esc_bus(self,name, esc_colon=True):
        """
        Helper function to escape bus characters for Spectre simulations
        bus<3:0> --> bus\<3\:0\>.
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
        
        Manual plot commands corresponding to self.plotlist defined in the
        parent entity.

        
        Apparently, the there is no good way to save individual plots for individual analyses
        in Spectre. Thus all 'save' statements can be grouped into one. For Eldo, the situation
        is different and we need to figure out a way for this to work with Eldo also.
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
                        self._plotcmd += ".control\nset wr_singlescale\nset wr_vecnames\n"
                        if self.parent.nproc: 
                            self._plotcmd +="%s%d\n" % (self.parent.syntaxdict["nprocflag"],self.parent.nproc)
                        self._plotcmd += "run\n"

                    for name, val in self.iofiles.Members.items():
                        # Output iofile becomes an extract command
                        if val.dir.lower()=='out' or val.dir.lower()=='output':
                            if val.iotype=='event':
                                for i in range(len(val.ionames)):
                                    if self.parent.model=='eldo':
                                        self._plotcmd += ".printfile %s(%s) file=\"%s\"\n" % \
                                                (val.sourcetype,val.ionames[i],val.file[i])
                                    elif self.parent.model=='spectre':
                                        signame = self.esc_bus(val.ionames[i])
                                        self._plotcmd += 'save %s\n' % signame
                                        #self._plotcmd += "eventout_%s (%s) veriloga_csv_write_allpoints filename=\"%s\"\n" % \
                                        #        (val.ionames[i].replace('.','_').replace('<','').replace('>',''),signame,val.file[i])
                                        self._plotcmd += 'simulator lang=spice\n'
                                        self._plotcmd += '.option ingold 2\n'
                                        #self._plotcmd += ".print %s %s(%s) file=\"%s\"\n" % \
                                        #(name.lower(),val.sourcetype,val.ionames[i],val.file[i])
                                        # Implement complex value probing
                                        if val.datatype.lower() == 'complex':
                                            self._plotcmd += ".print %s %sr(%s) %si(%s) \n" % \
                                                    (name.lower(),val.sourcetype,val.ionames[i],
                                                            val.sourcetype,val.ionames[i])
                                        else:
                                            self._plotcmd += ".print %s %s(%s)\n" % \
                                                (name.lower(),val.sourcetype,val.ionames[i])
                                        self._plotcmd += 'simulator lang=spectre\n'
                                    elif self.parent.model=='ngspice':
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
                                    # Checking the polarity of the triggers (for now every trigger has to have same polarity)
                                    vthstr = ',%s' % str(val.vth)
                                    afterstr = ',%g' % float(val.after)
                                    beforestr = ',end'
                                    if val.edgetype.lower()=='falling':
                                        polarity = 'xdown'
                                    elif val.edgetype.lower()=='both':
                                        # Syntax for tcross is a bit different
                                        polarity = 'tcross'
                                        vthstr = ',vth=%s' % str(val.vth)
                                        afterstr = ',after=%g' % float(val.after)
                                        beforestr = ',before=end'
                                    else:
                                        polarity = 'xup'
                                    if self.parent.model=='eldo':
                                        self._plotcmd += ".extract file=\"%s\" vect label=%s yval(v(%s<*>),%s(v(%s)%s%s%s))\n" % (val.file[i],val.ionames[i],val.ionames[i].upper(),polarity,trig,vthstr,afterstr,beforestr)
                                    elif self.parent.model=='spectre':
                                        # Extracting the bus width from the ioname
                                        signame = val.ionames[i].upper()
                                        signame = signame.replace('<',' ').replace('>',' ').replace('[',' ').replace(']',' ').replace(':',' ').split(' ')
                                        if len(signame) == 1:
                                            busstart = 0
                                            busstop = 0
                                        else:
                                            busstart = int(signame[1])
                                            busstop = int(signame[2])
                                        if busstart > busstop:
                                            buswidth = busstart-busstop+1
                                        else:
                                            buswidth = busstop-busstart+1
                                        # Writing every individual bit of a bus to its own file (TODO: maybe to one file?)
                                        for j in range(buswidth):
                                            bitname = self.esc_bus('%s<%d>' % (signame[0],j))
                                            #self._plotcmd += 'save %s\n' % bitname
                                            self._plotcmd += "sampleout_%s_%d (%s %s) veriloga_csv_write_edge filename=\"%s\" vth=%g edgetype=%d\n" % \
                                                    (signame[0],j,self.esc_bus(trig),bitname,val.file[i].replace('.txt','_%d.txt'%j),val.vth,-1 if val.edgetype.lower() == 'falling' else 1)

                            elif val.iotype=='time':
                                for i in range(len(val.ionames)):
                                    if self.parent.model == 'eldo':
                                        self._plotcmd += ".printfile %s(%s) file=\"%s\"\n" % \
                                                (val.sourcetype,val.ionames[i].upper(),val.file[i])
                                        #for i in range(len(val.ionames)):
                                        #    vthstr = ',%s' % str(val.vth)
                                        #    if val.edgetype.lower()=='falling':
                                        #        edge = 'xdown'
                                        #    elif val.edgetype.lower()=='both':
                                        #        edge = 'tcross'
                                        #        vthstr = ',vth=%s' % str(val.vth)
                                        #    elif val.edgetype.lower()=='risetime':
                                        #        edge = 'trise'
                                        #        vthstr = ''
                                        #    elif val.edgetype.lower()=='falltime':
                                        #        edge = 'tfall'
                                        #        vthstr = ''
                                        #    else:
                                        #        edge = 'xup'
                                        #    self._plotcmd += ".extract file=\"%s\" vect label=%s %s(v(%s)%s)\n" % (val.file[i],val.ionames[i],edge,val.ionames[i].upper(),vthstr)
                                    elif self.parent.model == 'spectre':
                                        signame = self.esc_bus(val.ionames[i].upper())
                                        #self._plotcmd += 'save %s\n' % signame
                                        self._plotcmd += "timeout_%s_%s (%s) veriloga_csv_write_allpoints filename=\"%s\"\n" % \
                                                (val.edgetype.lower(),val.ionames[i].upper().replace('.','_').replace('<','').replace('>',''),signame,val.file[i])
                            elif val.iotype=='vsample':
                                for i in range(len(val.ionames)):
                                    # Checking the given trigger(s)
                                    if isinstance(val.trigger,list):
                                        if len(val.trigger) == len(val.ionames):
                                            trig = val.trigger[i]
                                        else:
                                            trig = val.trigger[0]
                                            self.print_log(type='W',msg='%d triggers given for %d ionames. Using the first trigger for all ionames.' % (len(val.trigger),len(val.ionames)))
                                    else:
                                        trig = val.trigger
                                    if self.parent.model=='eldo':
                                        self.print_log(type='F',msg='not yet done') #TODO
                                    elif self.parent.model=='spectre':
                                        #self._plotcmd += 'save %s\n' % val.ionames[i].upper()
                                        self._plotcmd += ("vsampleout_%s (%s %s) veriloga_csv_write_edge filename=\"%s\" vth=%g edgetype=%d\n" 
                                                %(val.ionames[i].upper().replace('.','_'),trig,val.ionames[i].upper(),
                                                    val.file[i],val.vth,-1 if val.edgetype.lower() == 'falling' else 1))
                                    elif self.parent.model=='ngspice':
                                        self.print_log(type='F',msg='Iotype vsample not implemented for Ngspice') #TODO
                            else:
                                self.print_log(type='W',msg='Output filetype incorrectly defined.')
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
        """
        if not os.path.isfile(self.file):
            self.print_log(type='I',msg='Exporting spice testbench to %s.' %(self.file))
            with open(self.file, "w") as module_file:
                module_file.write(self.contents)

        elif os.path.isfile(self.file) and not kwargs.get('force'):
            self.print_log(type='F', msg=('Export target file %s exists.\n Force overwrite with force=True.' %(self.file)))

        elif kwargs.get('force'):
            self.print_log(type='I',msg='Forcing overwrite of spice testbench to %s.' %(self.file))
            with open(self.file, "w") as module_file:
                module_file.write(self.contents)

    def export_subckt(self,**kwargs):
        """
        Internally called function to write the parsed subcircuit definitions
        to a file.
        """
        if len(self.parent.dspf) == 0 and self.postlayout:
            return
        if not os.path.isfile(self.parent.spicesubcktsrc):
            self.print_log(type='I',msg='Exporting spice subcircuit to %s.' %(self.parent.spicesubcktsrc))
            with open(self.parent.spicesubcktsrc, "w") as module_file:
                module_file.write(self.subckt)

        elif os.path.isfile(self.parent.spicesubcktsrc) and not kwargs.get('force'):
            self.print_log(type='F', msg=('Export target file %s exists.\n Force overwrite with force=True.' %(self.parent.spicesubcktsrc)))

        elif kwargs.get('force'):
            self.print_log(type='I',msg='Forcing overwrite of spice subcircuit to %s.' %(self.parent.spicesubcktsrc))
            with open(self.parent.spicesubcktsrc, "w") as module_file:
                module_file.write(self.subckt)

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
        subinst = self.subinst
        dspfincludecmd = self.dspfincludecmd
        ahdlincludecmd = self.ahdlincludecmd
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
                        ahdlincludecmd + "\n" +
                        options + "\n" +\
                        params + "\n" +
                        subinst + "\n\n" +\
                        misccmd + "\n" +
                        dcsourcestr + "\n" +\
                        inputsignals + "\n" +\
                        simcmd + "\n" +\
                        plotcmd + "\n" +\
                        self.parent.syntaxdict["lastline"])
if __name__=="__main__":
    pass
