"""
=====
Spice
=====

Analog simulation interface package for The System Development Kit 

Provides utilities to import spice-like modules to python environment and
automatically generate testbenches for the most common simulation cases.

Initially written by Okko Järvinen, 2019

Last modification by Okko Järvinen, 08.04.2021 19:55

Release 1.6, Jun 2020 supports Eldo and Spectre
"""
import os
import sys
import subprocess
import shlex
import pdb
import shutil
import time
import traceback
from datetime import datetime
from abc import * 
from thesdk import *
import numpy as np
from numpy import genfromtxt
import pandas as pd
from functools import reduce
from spice.testbench import testbench as stb
from spice.spice_iofile import spice_iofile as spice_iofile
from spice.spice_dcsource import spice_dcsource as spice_dcsource
from spice.spice_simcmd import spice_simcmd as spice_simcmd
from spice.module import spice_module

class spice(thesdk,metaclass=abc.ABCMeta):
    """Adding this class as a superclass enforces the definitions 
    for Spice simulations in the subclasses.
    
    """

    #These need to be converted to abstact properties
    def __init__(self):
        pass

    @property
    @abstractmethod
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    @property
    def si_prefix_mult(self):
        """ Dictionary mapping SI-prefixes to multipliers """
        if hasattr(self, '_si_prefix_mult'):
            return self._si_prefix_mult
        else:
            self._si_prefix_mult = {
                    'E':1e18,
                    'P':1e15,
                    'T':1e12,
                    'G':1e9,
                    'M':1e6,
                    'k':1e3,
                    'm':1e-3,
                    'u':1e-6,
                    'n':1e-9,
                    'p':1e-12,
                    'f':1e-15,
                    'a':1e-18,
                    }
        return self._si_prefix_mult

    @property
    def syntaxdict(self):
        """Internally used dictionary for common syntax conversions between
        Spectre, Eldo, and Ngspice."""
        if self.model=='eldo':
            self._syntaxdict = {
                    "cmdfile_ext" : '.cir',
                    "resultfile_ext" : '.wdb',
                    'plotprog' : 'ezwave',
                    "commentchar" : '*',
                    "commentline" : '***********************\n',
                    "nprocflag" : '-use_proc ', #space required
                    "simulatorcmd" : 'eldo -64b',
                    "dcsource_declaration" : '',
                    "parameter" : '.param ',
                    "option" : '.option ',
                    "include" : '.include',
                    "dspfinclude" : '.include',
                    "subckt" : '.subckt',
                    "lastline" : '.end',
                    "eventoutdelim" : ' ',
                    "csvskip" : 2
                    }
        elif self.model=='spectre':
            self._syntaxdict = {
                    "cmdfile_ext" : '.scs',
                    'plotprog' : 'viva',
                    "resultfile_ext" : '.raw',
                    "commentchar" : '//',
                    "commentline" : '///////////////////////\n',
                    "nprocflag" : '+mt=', #space required??
                    "simulatorcmd" : 'spectre',
                    "dcsource_declaration" : 'vsource type=dc dc=',
                    "parameter" : 'parameters ',
                    "option" : 'options ',
                    "include" : 'include ',
                    "dspfinclude" : 'dspf_include ',
                    "subckt" : 'subckt',
                    "lastline" : '///', #needed?
                    "eventoutdelim" : ',',
                    "csvskip" : 0
                    }
        if self.model=='ngspice':
            self._syntaxdict = {
                    "cmdfile_ext" : '.ngcir',
                    "resultfile_ext" : '',
                    'plotprog' : '',
                    "commentchar" : '*',
                    "commentline" : '***********************\n',
                    "nprocflag" : 'set num_threads=', #Goes to .control section
                    "simulatorcmd" : 'ngspice -b', 
                    #"dcsource_declaration" : '',
                    "parameter" : '.param ',
                    "option" : '.option ',
                    "include" : '.include',
                    "dspfinclude" : '.include',
                    "subckt" : '.subckt',
                    "lastline" : '.end',
                    "eventoutdelim" : '  ', # Two spaces
                    "csvskip" : 1
                    }
        return self._syntaxdict
    @syntaxdict.setter
    def syntaxdict(self,value):
        self._syntaxdict=value
    #Name derived from the file

    @property
    def preserve_iofiles(self):  
        """True | False (default)

        If True, do not delete file IO files after simulations. Useful for
        debugging the file IO"""
        if hasattr(self,'_preserve_iofiles'):
            return self._preserve_iofiles
        else:
            self._preserve_iofiles=False
        return self._preserve_iofiles
    @preserve_iofiles.setter
    def preserve_iofiles(self,value):
        self._preserve_iofiles=value
        
    @property
    def preserve_spicefiles(self):  
        """True | False (default)

        If True, do not delete generated Spice files (testbench, subcircuit,
        etc.) after simulations.  Useful for debugging."""
        if hasattr(self,'_preserve_spicefiles'):
            return self._preserve_spicefiles
        else:
            self._preserve_spicefiles=False
        return self._preserve_spicefiles
    @preserve_spicefiles.setter
    def preserve_spicefiles(self,value):
        self._preserve_spicefiles=value

    @property
    def distributed_run(self):
        """ Boolean (default False)
            If True, distributes applicable simulations (currently DC sweep supported)
            into the LSF cluster. The number of subprocesses launched is
            set by self.num_processes.
        """
        if hasattr(self, '_distributed_run'):
            return self._distributed_run
        else:
            self._distributed_run=False
        return self.distributed_run
    @distributed_run.setter
    def distributed_run(self, value):
        self._distributed_run=value

    @property
    def num_processes(self):
        """ integer
            Maximum number of spawned child processes for distributed runs.
        """
        if hasattr(self, '_num_processes'):
            return self._num_processes
        else:
            self._num_processes=10
        return self.num_processes
    @num_processes.setter
    def num_processes(self, value):
        self._num_processes=int(value)

    @property
    def load_state(self):  
        """String (Default '')

        Feature for loading results of previous simulation.  The Spice
        simulation is not re-executed, but the outputs will be read from
        existing files.
        
        Example inputs::

            self.load_state = 'last' # load latest
            self.load_state = 'latest' # load latest
            self.load_state = '20201002103638_tmpdbw11nr4' # load results matching this name
            self.load_state = 'zzzz' (non-existent directory) # list available directories to load
        """
        if hasattr(self,'_load_state'):
            return self._load_state
        else:
            self._load_state=''
        return self._load_state
    @load_state.setter
    def load_state(self,value):
        self._load_state=value

    @property
    def spicecorner(self):  
        """Dictionary

        Feature for specifying the 'section' of the model library file and
        simulation temperature. The path to model libraries should be set in
        TheSDK.config as either ELDOLIBFILE, SPECTRELIBFILE or NGSPICELIBFILE variable.

        Example::

            self.spicecorner = {
                    'temp': 27,
                    'corner': 'top_tt'
                    }

        """
        if hasattr(self,'_spicecorner'):
            return self._spicecorner
        else:
            self._spicecorner= {
                    'temp': 27,
                    'corner': ''
                    }
        return self._spicecorner
    @spicecorner.setter
    def spicecorner(self,value):
        self._spicecorner=value

    @property
    def spiceoptions(self):  
        """Dictionary

        Feature for specifying options for spice simulation. The key is the
        name of the option (as in simulator manual specifies), and the value is
        the value given to said option. Valid key-value pairs can be found from
        the manual of the simulator (Eldo, Spectre or Ngspice).

        Example::

            self.spiceoptions = {
                       'save': 'lvlpub',
                       'nestlvl': '1',
                       'pwr': 'subckts',
                       'digits': '12'
                   }

        """
        if hasattr(self,'_spiceoptions'):
            return self._spiceoptions
        else:
            self._spiceoptions={}
        return self._spiceoptions
    @spiceoptions.setter
    def spiceoptions(self,value):
        self._spiceoptions=value

    @property
    def spiceparameters(self): 
        """Dictionary

        Feature for specifying simulation parameters for spice simulation. The
        key is the name of the parameter , and the value is the value given to
        said parameter.

        Example::

            self.spiceparameters = {
                       'nf_pmos': 8,
                       'nf_nmos': 4,
                       'ibias': 100e-6
                   }

        """
        if not hasattr(self, '_spiceparameters'):
            self._spiceparameters =dict([])
        return self._spiceparameters
    @spiceparameters.setter
    def spiceparameters(self,value): 
            self._spiceparameters = value

    @property
    def runname(self):
        """String 
        
        Automatically generated name for the simulation. 
        
        Formatted as timestamp_randomtag, i.e. '20201002103638_tmpdbw11nr4'.
        Can be overridden by assigning self.runname = 'myname'."""
        if hasattr(self,'_runname'):
            return self._runname
        else:
            self._runname='%s_%s' % \
                    (datetime.now().strftime('%Y%m%d%H%M%S'),os.path.basename(tempfile.mkstemp()[1]))
        return self._runname
    @runname.setter
    def runname(self,value):
        self._runname=value

    @property
    def interactive_spice(self):
        """ True | False (default)
        
        Launch simulator in interactive mode. For Eldo, opens also ezwave."""

        if hasattr(self,'_interactive_spice'):
            return self._interactive_spice
        else:
            self._interactive_spice=False
        return self._interactive_spice
    @interactive_spice.setter
    def interactive_spice(self,value):
        self._interactive_spice=value

    @property
    def nproc(self):
        """Integer
        
        Requested maximum number of threads for multithreaded simulations. For
        Eldo, maps to command line parameter '-nproc'. For Spectre, maps to
        command line parameter '+mt'."""
        if hasattr(self,'_nproc'):
            return self._nproc
        else:
            self._nproc=False
        return self._nproc
    @nproc.setter
    def nproc(self,value):
        self._nproc=value

    @property
    def errpreset(self):
        """String
        
        Global accuracy parameter for Spectre simulations. Options include
        'liberal', 'moderate' and 'conservative', in order of rising
        accuracy."""
        if hasattr(self,'_errpreset'):
            return self._errpreset
        else:
            self._errpreset='moderate'
        return self._errpreset
    @errpreset.setter
    def errpreset(self,value):
        self._errpreset=value

    # DSPF filenames
    @property
    def dspf(self):
        """List<String>
        
        List containing filenames for DSPF-files to be included for post-layout
        simulations. The names given in this list are matched to dspf-files in
        './spice/' -directory. A postfix '.pex.dspf' is automatically appended
        to the given names (this will probably change later).
        
        Example::

            self.dspf = ['inv_v2','switch_v3']

        would include files './spice/inv_v2.pex.dspf' and
        './spice/switch_v3.pex.dspf' as dspf-files in the testbench. If the
        dspf-file contains definition matching the original design name of the
        top-level netlist, it gets also renamed to match the module name
        (dspf-file for top-level instance is possible).
        """
        if not hasattr(self,'_dspf'):
            self._dspf = []
        return self._dspf
    @dspf.setter
    def dspf(self,value):
        self._dspf=value

    @property
    def iofile_bundle(self):
        """ 
        A thesdk.Bundle containing spice_iofile objects. The iofile objects
        are automatically added to this Bundle, nothing should be manually
        added.
        """
        if not hasattr(self,'_iofile_bundle'):
            self._iofile_bundle=Bundle()
        return self._iofile_bundle
    @iofile_bundle.setter
    def iofile_bundle(self,value):
        self._iofile_bundle=value
    @iofile_bundle.deleter
    def iofile_bundle(self):
        for name, val in self.iofile_bundle.Members.items():
            if val.preserve:
                self.print_log(type="I", msg="Preserving files for %s." % val.name)
            else:
                val.remove()
        if not self.preserve_iofiles:
            if self.interactive_spice:
                simpathname = self.spicesimpath
            else:
                simpathname = self.spicesimpath
            try:
                shutil.rmtree(simpathname)
                self.print_log(type='I',msg='Removing %s.' % simpathname)
            except:
                self.print_log(type='W',msg='Could not remove %s.' % simpathname)

    @property
    def dcsource_bundle(self):
        """ 
        A thesdk.Bundle containing spice_dcsource objects. The dcsource objects
        are automatically added to this Bundle, nothing should be manually
        added.
        """
        if not hasattr(self,'_dcsource_bundle'):
            self._dcsource_bundle=Bundle()
        return self._dcsource_bundle
    @dcsource_bundle.setter
    def dcsource_bundle(self,value):
        self._dcsource_bundle=value
    @dcsource_bundle.deleter
    def dcsource_bundle(self):
        for name, val in self.dcsource_bundle.Members.items():
            if self.preserve_iofiles:
                if val.extract:
                    self.print_log(type="I", msg="Preserving file %s." % val.extfile)
            else:
                val.remove()

    @property
    def simcmd_bundle(self):
        """ 
        A thesdk.Bundle containing spice_simcmd objects. The simcmd objects
        are automatically added to this Bundle, nothing should be manually
        added.
        """
        if not hasattr(self,'_simcmd_bundle'):
            self._simcmd_bundle=Bundle()
        return self._simcmd_bundle
    @simcmd_bundle.setter
    def simcmd_bundle(self,value):
        self._simcmd_bundle=value
    @simcmd_bundle.deleter
    def simcmd_bundle(self):
        for name, val in self.simcmd_bundle.Members.items():
            val.remove()

    @property
    def extracts(self):
        """ 
        A thesdk.Bundle containing extracted quantities.
        """
        if not hasattr(self,'_extracts'):
            self._extracts=Bundle()
        return self._extracts
    @extracts.setter
    def extracts(self,value):
        self._extracts=value

    @property 
    def has_lsf(self):
        """
        Returs True if LSF submissions are properly defined. Default False
        """
        if ( not thesdk.GLOBALS['LSFINTERACTIVE'] == '' ) and (not thesdk.GLOBALS['LSFINTERACTIVE'] == ''):
            self._has_lsf = True
        else:
            self._has_lsf = False
        return self._has_lsf

    @property 
    def spice_submission(self):
        """
        Defines spice submission prefix from thesdk.GLOBALS['LSFSUBMISSION']
        and thesdk.GLOBALS['LSFINTERACTIVE'] for LSF submissions.

        Usually something like 'bsub -K' and 'bsub -I'.
        """
        if not hasattr(self, '_spice_submission'):
            try:
                if not self.has_lsf:
                    self.print_log(type='I', msg='LSF not configured. Running locally')
                    self._spice_submission=''
                else:
                    if self.interactive_spice:
                        if not self.distributed_run:
                            self._spice_submission = thesdk.GLOBALS['LSFINTERACTIVE'] + ' '
                        else: # Spectre LSF doesn't support interactive queues
                            self.print_log(type='W', msg='Cannot run in interactive mode if distributed mode is on!')
                            self._spice_submission = thesdk.GLOBALS['LSFSUBMISSION'] + ' -o %s/bsublog.txt ' % (self.spicesimpath)
            except:
                self.print_log(type='W',msg='Error while defining spice submission command. Running locally.')
                self._spice_submission=''

        return self._spice_submission
    @spice_submission.setter
    def spice_submission(self,value):
        self._spice_submission=value

    @property
    def plotlist(self): 
        """
            OBSOLETE! RE-LOCATED TO SPICE_SIMCMD.PY
        """
        self.print_log(type='O', msg='Plotlist has been relocated as a parameter to spice_simcmd!') 
        if not hasattr(self,'_plotlist'):
            self._plotlist=[]
        return self._plotlist 
    @plotlist.setter
    def plotlist(self,value): 
        self.print_log(type='O', msg='Plotlist has been relocated as a parameter to spice_simcmd!') 
        self._plotlist=value

    @property
    def spicemisc(self): 
        """List<String>

        List of manual commands to be pasted to the testbench. The strings are
        pasted to their own lines (no linebreaks needed), and the syntax is
        unchanged.

        Example: setting initial voltages from testbench (Eldo)::

            self.spicemisc = []
            for i in range(nodes):
                self.spicemisc.append('.ic NODE<%d> 0' % i)
        """
        if not hasattr(self, '_spicemisc'):
            self._spicemisc = []
        return self._spicemisc
    @spicemisc.setter
    def spicemisc(self,value): 
            self._spicemisc = value

    @property
    def ahdlpath(self): 
        """List<String>

        List of strings containing file paths to Verilog-A files to be included
        into a Spectre simulation.
        """
        if not hasattr(self, '_ahdlpath'):
            self._ahdlpath = []
        return self._ahdlpath
    @ahdlpath.setter
    def ahdlpath(self,value): 
            self._ahdlpath = value

    @property
    def name(self):
        """String

        Name of the module.
        """
        if not hasattr(self, '_name'):
            self._name=os.path.splitext(os.path.basename(self._classfile))[0]
        return self._name

    @property
    def entitypath(self):
        """String

        Path to the entity root.
        """
        if not hasattr(self, '_entitypath'):
            self._entitypath= os.path.dirname(os.path.dirname(self._classfile))
        return self._entitypath

    @property
    def spicesrcpath(self):
        """String

        Path to the spice source of the entity ('./spice').
        """
        self._spicesrcpath  =  self.entitypath + '/spice'
        try:
            if not (os.path.exists(self._spicesrcpath)):
                os.makedirs(self._spicesrcpath)
                self.print_log(type='I',msg='Creating %s.' % self._spicesrcpath)
        except:
            self.print_log(type='E',msg='Failed to create %s.' % self._spicesrcpath)
        return self._spicesrcpath

    @property
    def spicesrc(self):
        """String

        Path to the source netlist (i.e. 'spice/entityname.scs').
        This shouldn't be set manually.

        .. note::

            Provided netlist name has to match entity name (entityname.scs or entityname.cir).

        .. note::
            
            Netlist has to contain the top-level design as a subcircuit definition.
        """
        if not hasattr(self, '_spicesrc'):
            self._spicesrc=self.spicesrcpath + '/' + self.name + self.syntaxdict["cmdfile_ext"]

            if not os.path.exists(self._spicesrc):
                self.print_log(type='W',msg='No source circuit found in %s.' % self._spicesrc)
        return self._spicesrc

    @property
    def spicetbsrc(self):
        """String

        Path to the spice testbench ('./spice/tb_entityname.<suffix>').
        This shouldn't be set manually.
        """
        if not hasattr(self, '_spicetbsrc'):

            if self.interactive_spice:
                self._spicetbsrc=self.spicesrcpath + '/tb_' + self.name + self.syntaxdict["cmdfile_ext"]
            else:
                self._spicetbsrc=self.spicesimpath + '/tb_' + self.name + self.syntaxdict["cmdfile_ext"]
        return self._spicetbsrc

    @property
    def eldowdbsrc(self):
        """String

        Path to the Eldo EZwave database ('./spice/tb_entityname.wdb').
        Only applies to Eldo simulations.
        This shouldn't be set manually.
        """
        if not hasattr(self, '_eldowdbsrc'):
            if self.interactive_spice:
                self._eldowdbsrc=self.spicesrcpath + '/tb_' + self.name + '.wdb'
            else:
                self._eldowdbsrc=self.spicesimpath + '/tb_' + self.name + '.wdb'
        return self._eldowdbsrc

    @property
    def eldochisrc(self):
        """String

        Path to the Eldo chi-file. ('./spice/tb_entityname.chi').
        Only applies to Eldo simulations.
        This shouldn't be set manually.
        """
        if not hasattr(self, '_eldochisrc'):
            if self.interactive_spice:
                self._eldochisrc=self.spicesrcpath + '/tb_' + self.name + '.chi'
            else:
                self._eldochisrc=self.spicesimpath + '/tb_' + self.name + '.chi'
        return self._eldochisrc

    @property
    def spicesubcktsrc(self):
        """String

        Path to the parsed subcircuit file. ('./spice/subckt_entityname.<suffix>').
        This shouldn't be set manually.
        """
        if not hasattr(self, '_spicesubcktsrc'):
            if self.interactive_spice:
                self._spicesubcktsrc=self.spicesrcpath + '/subckt_' + self.name + self.syntaxdict["cmdfile_ext"]
            else:
                self._spicesubcktsrc=self.spicesimpath + '/subckt_' + self.name + self.syntaxdict["cmdfile_ext"]
        return self._spicesubcktsrc

    @property
    def spicesimpath(self):
        """String

        Simulation path. (./Simulations/spicesim/<runname>)
        This shouldn't be set manually.
        """
        if not hasattr(self,'_spicesimpath'):
            self._spicesimpath = self.entitypath+'/Simulations/spicesim/'+self.runname
            try:
                if not (os.path.exists(self._spicesimpath)):
                    os.makedirs(self._spicesimpath)
                    self.print_log(type='I',msg='Creating %s.' % self._spicesimpath)
            except:
                self.print_log(type='E',msg='Failed to create %s.' % self._spicesimpath)
        return self._spicesimpath
    @spicesimpath.deleter
    def spicesimpath(self):
        if not self.interactive_spice and not self.preserve_spicefiles:
            # Removing generated files
            filelist = [
                self.spicetbsrc,
                self.spicesubcktsrc
                ]
            for f in filelist:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                        self.print_log(type='I',msg='Removing %s.' % f)
                except:
                    self.print_log(type='W',msg='Could not remove %s.' % f)
                    pass

            # Cleaning up extra files
            if os.path.exists(self.spicesimpath):
                remaining = os.listdir(self.spicesimpath)
                for f in remaining:
                    try:
                        fpath = '%s/%s' % (self.spicesimpath,f)
                        if f.startswith('tb_%s' % self.name):
                            os.remove(fpath)
                            self.print_log(type='I',msg='Removing %s.' % fpath)
                    except:
                        self.print_log(type='W',msg='Could not remove %s.' % fpath)

            #TODO currently always remove everything 
            # IO files were also removed -> remove the directory
            if os.path.exists(self.spicesimpath) and not self.preserve_iofiles:
                try:
                    # This fails sometimes because of .nfs files
                    shutil.rmtree(self.spicesimpath)
                    self.print_log(type='I',msg='Removing %s.' % self.spicesimpath)
                except:
                    self.print_log(type='W',msg='Could not remove %s.' % self.spicesimpath)
        else:
            self.print_log(type='I',msg='Preserving spice files in %s.' % self.spicesrcpath)


    @property
    def spicecmd(self):
        """String

        Simulation command string to be executed on the command line.
        Automatically generated.
        """
        if not hasattr(self,'_spicecmd'):
            if self.interactive_spice:
                if self.model=='eldo':
                    plottingprogram=self.syntaxdict['plotprog'] 
                elif self.model=='spectre':
                    plottingprogram = '' # Plotting for spectre handled differently. See self.plotprogcmd
                #submission=""
                submission=self.spice_submission
            else:
                plottingprogram = ""
                submission=self.spice_submission

            if self.nproc:
                nprocflag = "%s%d" % (self.syntaxdict["nprocflag"],self.nproc)
                self.print_log(type='I',msg='Enabling multithreading \'%s\'.' % nprocflag)
            else:
                nprocflag = ""

            if self.tb.postlayout:
                plflag = '+postlayout=upa'
                self.print_log(type='I',msg='Enabling post-layout optimization \'%s\'.' % plflag)
            else:
                plflag = ''

            if self.model=='eldo':
                # Shouldn't this use self.syntaxdict["simulatorcmd"] ?
                spicesimcmd = "eldo -64b %s %s " % (plottingprogram,nprocflag)
            elif self.model=='spectre':
                #spicesimcmd = "\"sleep 10; spectre %s %s \"" % (plottingprogram,nprocflag)
                #spicesimcmd = "spectre %s %s " % (plottingprogram,nprocflag)
                spicesimcmd = ("spectre -64 +lqtimeout=0 ++aps=%s %s %s %s -outdir %s " 
                        % (self.errpreset, plflag,plottingprogram,nprocflag,self.spicesimpath))
            elif self.model=='ngspice':
                spicesimcmd = self.syntaxdict["simulatorcmd"] + ' '

            #spicesimcmd = "%s %s %s " % (self.syntaxdict["simulatorcmd"],plottingprogram,nprocflag)
            spicetbfile = self.spicetbsrc
            self._spicecmd = submission +\
                            spicesimcmd +\
                            spicetbfile
        return self._spicecmd
    # Just to give the freedom to set this if needed
    @spicecmd.setter
    def spicecmd(self,value):
        self._spicecmd=value

    @property
    def plotprogcmd(self):
        """
        Sets the command to be run for interactive Spectre simulations.
        """
        if not hasattr(self, '_plotprogcmd') and self.model=='spectre':
            path=self.spicesrcpath + '/tb_' + self.name + self.syntaxdict["resultfile_ext"]
            self._plotprogcmd='%s -datadir %s &' % (self.syntaxdict['plotprog'], path)
        return self._plotprogcmd
    @plotprogcmd.setter
    def plotprogcmd(self, value):
        self._plotprogcmd=value

    def connect_inputs(self):
        """Automatically called function to connect iofiles (inputs) to top
        entity IOS Bundle items."""
        for ioname,io in self.IOS.Members.items():
            if ioname in self.iofile_bundle.Members:
                val=self.iofile_bundle.Members[ioname]
                # File type inputs are driven by the file.Data, not the input field
                if not isinstance(self.IOS.Members[val.name].Data,spice_iofile) \
                        and val.dir == 'in':
                    # Data must be properly shaped
                    self.iofile_bundle.Members[ioname].Data=self.IOS.Members[ioname].Data

    def connect_outputs(self):
        """Automatically called function to connect iofiles (outputs) to top
        entity IOS Bundle items."""
        for name,val in self.iofile_bundle.Members.items():
            if val.dir == 'out':
                self.IOS.Members[name].Data=self.iofile_bundle.Members[name].Data

    def write_infile(self):
        """Automatically called function to call write() functions of each
        iofile with direction 'input'."""
        for name, val in self.iofile_bundle.Members.items():
            if val.dir.lower()=='in' or val.dir.lower()=='input':
                self.iofile_bundle.Members[name].write()

    def read_outfile(self):
        """Automatically called function to call read() functions of each
        iofile with direction 'output'."""
        for name, val in self.iofile_bundle.Members.items():
            if val.dir.lower()=='out' or val.dir.lower()=='output':
                self.iofile_bundle.Members[name].read()
    
    def execute_spice_sim(self):
        """Automatically called function to execute spice simulation."""
        self.print_log(type='I', msg="Running external command %s" %(self.spicecmd) )
        if self.model == 'eldo':
            # This is some experimental stuff
            count = 0
            while True:
                status = int(os.system(self.spicecmd)/256)
                # Status code 9 seems to result from failed licensing in LSF runs
                # Let's not try to restart if in interactive mode
                if status != 9 or count == 10 or self.interactive_spice:
                    break
                else:
                    count += 1
                    self.print_log(type='W',msg='License error, trying again... (%d/10)' % count)
                    time.sleep(5)
            if status > 0:
                self.print_log(type='F',msg='Eldo encountered an error (%d).' % status)
        else:
            os.system(self.spicecmd)

    def run_viva(self):
        """ Run plotting program for interactive Spectre simulations
            NOTE: This feature is for Spectre simulations ONLY!
        """
        cmd=self.plotprogcmd
        self.print_log(type='I', msg='Running external command: %s' % cmd)
        try:
            ret=os.system(cmd)
            if ret != 0:
                self.print_log(type='W', msg='%s returned with exit status %d!' % (self.syntaxdict['plotprog'], ret))
        except: 
            self.print_log(type='W',msg='Something went wrong while launcing %s.' % self.syntaxdict['plotprog'])
            self.print_log(type='W',msg=traceback.format_exc())

    def extract_powers(self):
        """
        Automatically called function to extract transient power and current
        consumptions. The consumptions are extracted for spice_dcsource objects
        with the attribute extract=True.
        
        The extracted consumptions are accessible on the top-level after simulation as::
            
            self.extracts.Members['powers'] # Dictionary with averaged power consumptions of each supply + total
            self.extracts.Members['currents'] # Dictionary with averaged current consumptions of each supply + total
            self.extracts.Members['curr_tran'] # Dictionary with transient current consumptions of each supply

        """
        self.extracts.Members['powers'] = {}
        self.extracts.Members['currents'] = {}
        self.extracts.Members['curr_tran'] = {}
        try:
            if self.model == 'eldo':
                currentmatch = re.compile(r"\* CURRENT_")
                powermatch = re.compile(r"\* POWER_")
                with open(self.eldochisrc) as infile:
                    chifile = infile.readlines()
                    for line in chifile:
                        if currentmatch.search(line):
                            words = line.split()
                            sourcename = words[1].replace('CURRENT_','')
                            extval = float(words[3])
                            self.extracts.Members['currents'][sourcename] = extval
                        elif powermatch.search(line):
                            words = line.split()
                            sourcename = words[1].replace('POWER_','')
                            extval = float(words[3])
                            self.extracts.Members['powers'][sourcename] = extval
            elif self.model == 'spectre':
                for name, val in self.tb.dcsources.Members.items():
                    # Read transient power consumption of the extracted source
                    if val.extract and val.sourcetype.lower() == 'v':
                        arr = genfromtxt(val._extfile,delimiter=', ',skip_header=self.syntaxdict["csvskip"])
                        if val.ext_start is not None:
                            arr = arr[np.where(arr[:,0] >= val.ext_start)[0],:]
                        if val.ext_stop is not None:
                            arr = arr[np.where(arr[:,0] <= val.ext_stop)[0],:]
                        # The time points are non-uniform -> use deltas as weights
                        dt = np.diff(arr[:,0])
                        totaltime = arr[-1,0]-arr[0,0]
                        meancurr = np.sum(np.abs(arr[1:,1])*dt)/totaltime
                        meanpwr = meancurr*val.value
                        sourcename = '%s%s' % (val.sourcetype.upper(),val.name.upper())
                        self.extracts.Members['currents'][sourcename] = meancurr
                        self.extracts.Members['powers'][sourcename] = meanpwr
                        self.extracts.Members['curr_tran'][sourcename] = arr
            self.print_log(type='I',msg='Extracted power consumption from transient:')
            # This is newer Python syntax
            maxlen = len(max([*self.extracts.Members['powers'],'total'],key=len))
            for name,val in self.extracts.Members['currents'].items():
                self.print_log(type='I',msg='%s%s current = %.06f mA'%(name,' '*(maxlen-len(name)),1e3*val))
            if len(self.extracts.Members['currents'].items()) > 0:
                self.print_log(type='I',msg='Total%s current = %.06f mA'%(' '*(maxlen-5),1e3*sum(self.extracts.Members['currents'].values())))
            for name,val in self.extracts.Members['powers'].items():
                self.print_log(type='I',msg='%s%s power   = %.06f mW'%(name,' '*(maxlen-len(name)),1e3*val))
            if len(self.extracts.Members['powers'].items()) > 0:
                self.print_log(type='I',msg='Total%s power   = %.06f mW'%(' '*(maxlen-5),1e3*sum(self.extracts.Members['powers'].values())))
        except:
            self.print_log(type='W',msg=traceback.format_exc())
            self.print_log(type='W',msg='Something went wrong while extracting power consumptions.')
    
    def si_string_to_float(self, strval):
        """ Convert SI-formatted string to float
            
            E.g. self.si_string_to_float('3 mV') returns 3e-3.
        """
        parts = strval.split()
        if len(parts) == 2:
            val = float(parts[0])
            if len(parts[1]) == 1: # No prefix
                mult = 1
            else:
                try:
                    mult = self.si_prefix_mult[parts[1][0]]
                except KeyError: # Could not convert, just return the text value
                    self.print_log(type='W', msg='Invalid SI-prefix %s, failed to convert.' % parts[1][0])
                    return strval
            return val*mult
        else:
            return strval # Was a text value

    def read_oppts(self):
        """ Internally called function to read the DC operating points of the circuit
            TODO: Implement for Eldo as well.
        """
        try:
            if self.model=='spectre' and 'dc' in self.simcmd_bundle.Members.keys():
                self.extracts.Members.update({'oppts' : {}})
                # Get dc simulation file name
                for name, val in self.simcmd_bundle.Members.items():
                    if name == 'dc':
                        if val.sweep != '':
                            fname = '%sSweep*.dc' % val.sweep
                            break
                        else:
                            fname = 'oppoint*.dc'
                            break
                # Move to spicesim
                if self.distributed_run:
                    ## NOTA BENE: The pattern [0-9]* matches any path with the first character
                    # being integer in range 0-9 and any number of trailing characters. Glob doesn't
                    # support exactly matching ANY number of digits and there shouldn't be any files
                    # in the simulation result directory mathing this pattern so this is probably good enough.
                    fpath = os.path.join(self.entitypath, 'spice/tb_%s.raw' % self.name,
                            '[0-9]*', fname)
                else:
                    fpath = os.path.join(self.entitypath, 'spice/tb_%s.raw' % self.name, fname)
                destpath = os.path.join(self.entitypath, 'Simulations/spicesim', self.runname)
                files = glob.glob(fpath)
                for file in files:
                    os.rename(file, os.path.join(destpath, file.split('/')[-1]))
                valbegin = 'VALUE\n'
                eof = 'END\n'
                parsevals = False
                files = sorted(glob.glob(os.path.join(destpath, fname)))
                for file in files:
                    with open(file, 'r') as f:
                        for line in f:
                            if line == valbegin: # Scan file until unit descriptions end and values start
                                parsevals = True
                            elif line != eof and parsevals: # Scan values from output until EOF
                                line = line.replace('\"', '')
                                parts = line.split()
                                if len(parts) >= 3:
                                    if ':' in parts[0]: # This line contains op point parameter (e.g. vgs)
                                        dev, param = parts[0].split(':')
                                    elif ':' not in parts[0] and parts[1] == 'V': # This is a node voltage
                                        dev = parts[0]
                                        param = parts[1]
                                    val = float(parts[2])
                                    if dev not in self.extracts.Members['oppts']: # Found new device
                                        self.extracts.Members['oppts'].update({dev : {}}) 
                                    if param not in self.extracts.Members['oppts'][dev]: # Found new parameter for device
                                        self.extracts.Members['oppts'][dev].update({param : [val]})
                                    else: # Parameter already existed, just append value. This can occur in e.g. sweeps
                                        self.extracts.Members['oppts'][dev][param].append(val)
                            elif line == eof:
                                parsevals = False
            elif self.model == 'eldo' and 'dc' in self.simcmd_bundle.Members.keys():
                raise Exception('DC optpoint extraction not supported for Eldo.')
            elif 'dc' in self.simcmd_bundle.Members.keys(): # Unsupported model
                raise Exception('Unrecognized model %s.' % self.model)
            else: # DC analysis not in simcmds, oppts is empty
                self.extracts.Members.update({'oppts' : {}})
        except:
            self.print_log(type='W', msg=traceback.format_exc())
            self.print_log(type='W',msg='Something went wrong while extracting DC operating points.')
        
    def run_spice(self):
        """Externally called function to execute spice simulation."""
        if self.load_state == '': 
            # Normal execution of full simulation
            self.tb = stb(self)
            self.tb.iofiles = self.iofile_bundle
            self.tb.dcsources = self.dcsource_bundle
            self.tb.simcmds = self.simcmd_bundle
            self.connect_inputs()
            self.tb.generate_contents()
            self.tb.export_subckt(force=True)
            self.tb.export(force=True)
            self.write_infile()
            self.execute_spice_sim()
            if self.interactive_spice and self.model=='spectre':
                self.run_viva()
            self.extract_powers()
            self.read_outfile()
            self.connect_outputs()
            self.read_oppts()
            # Calling deleter of iofiles
            del self.dcsource_bundle
            del self.iofile_bundle
            # And eldo files (tb, subcircuit, wdb)
            del self.spicesimpath
        else:
            #Loading previous simulation results and not simulating again
            try:
                self.runname = self.load_state
                if self.runname == 'latest' or self.runname == 'last':
                    results = glob.glob(self.entitypath+'/Simulations/spicesim/*')
                    latest = max(results, key=os.path.getctime)
                    self.runname = latest.split('/')[-1]
                    simpath = latest
                else:
                    simpath = self.entitypath+'/Simulations/spicesim/'+self.runname
                simpath = self.entitypath+'/Simulations/spicesim/'+self.runname
                if not (os.path.exists(simpath)):
                    self.print_log(type='E',msg='Existing results not found in %s.' % simpath)
                    existing = os.listdir(self.entitypath+'/Simulations/spicesim/')
                    self.print_log(type='I',msg='Found results:')
                    for f in existing:
                        self.print_log(type='I',msg='%s' % f)
                else:
                    self.print_log(type='I',msg='Loading results from %s.' % simpath)
                    self.tb = stb(self)
                    self.tb.iofiles = self.iofile_bundle
                    self.tb.dcsources = self.dcsource_bundle
                    self.tb.simcmds = self.simcmd_bundle
                    self.connect_inputs()
                    self.read_outfile()
                    self.connect_outputs()
                    self.extract_powers()
                    self.read_oppts()
            except:
                self.print_log(type='I',msg=traceback.format_exc())
                self.print_log(type='F',msg='Failed while loading results from %s.' % self._spicesimpath)

