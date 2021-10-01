"""
=====
Spice
=====

Analog simulation interface package for TheSyDeKick.

Provides utilities to import spice-like modules to Python environment and
generate testbenches for the various simulation cases.

Initially written by Okko Järvinen, 2019

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
import threading
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
from spice.spice_module import spice_module as spice_module

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
        """ Dictionary
        
        Dictionary mapping SI-prefixes to multipliers.
        """
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
        """ Dictionary
        
        Internally used dictionary for common syntax conversions between
        Spectre, Eldo, and Ngspice.
        """
        if self.model=='eldo':
            self._syntaxdict = {
                    "cmdfile_ext" : '.cir',
                    "resultfile_ext" : '.wdb',
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
    def preserve_result(self):  
        """True | False (default)

        If True, do not delete result files after simulations.
        """
        if not hasattr(self,'_preserve_result'):
            self._preserve_result=False
        return self._preserve_result
    @preserve_result.setter
    def preserve_result(self,value):
        self._preserve_result=value

    @property
    def preserve_iofiles(self):  
        """True | False (default)

        If True, do not delete file IO files after simulations. Useful for
        debugging the file IO.
        
        .. note::
            Replaced by `preserve_result` in v1.7
        """
        if not hasattr(self,'_preserve_iofiles'):
            self._preserve_iofiles=False
        return self._preserve_iofiles
    @preserve_iofiles.setter
    def preserve_iofiles(self,value):
        self.print_log(type='O',msg='preserve_iofiles is replaced with preserve_result since v1.7')
        self._preserve_iofiles=value
        self.print_log(msg='Setting preserve_result to %s' % str(value))
        self._preserve_result=value
        
    @property
    def preserve_spicefiles(self):  
        """True | False (default)

        If True, do not delete generated Spice files (testbench, subcircuit,
        etc.) after simulations.  Useful for debugging.
        
        .. note::
            Replaced by `preserve_result` in v1.7
        """
        if not hasattr(self,'_preserve_spicefiles'):
            self._preserve_spicefiles=False
        return self._preserve_spicefiles
    @preserve_spicefiles.setter
    def preserve_spicefiles(self,value):
        self.print_log(type='O',msg='preserve_spicefiles is replaced with preserve_result since v1.7')
        self._preserve_spicefiles=value
        self.print_log(msg='Setting preserve_result to %s' % str(value))
        self._preserve_result=value

    @property
    def distributed_run(self):
        """ True | False (default)

        If True, distributes applicable simulations (currently DC sweep
        supported) into the LSF cluster. The number of subprocesses launched is
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
        """ Integer

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
        """ String (default '')

        Feature for loading results of previous simulation. The Spice
        simulation is not re-executed, but the outputs will be read from
        existing files. The string value should be the `runname` of the desired
        simulation.
        
        Loading the most recent result automatically::

            self.load_state = 'last'
            # or
            self.load_state = 'latest'

        Loading a specific past result using the `runname`::

            self.load_state = '20201002103638_tmpdbw11nr4'

        List available results by providing any non-existent `runname`::

            self.load_state = 'this_does_not_exist'
        """
        if not hasattr(self,'_load_state'):
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
        TheSDK.config as either ELDOLIBFILE, SPECTRELIBFILE or NGSPICELIBFILE
        variable.

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
        Can be overridden by assigning self.runname = 'myname'.

        Example::

            self.runname = 'test'

        would generate the simulation files in `Simulations/spicesim/test/`.

        """
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
        
        Launch simulator in interactive mode. A waveform viewer (ezwave by
        default) is opened during the simulation for debugging. See
        `plotprogram` for selecting waveform viewer program.
        """

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
        """ Integer
        
        Requested maximum number of threads for multithreaded simulations. For
        Eldo, maps to command line parameter '-nproc'. For Spectre, maps to
        command line parameter '+mt'.
        """
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
        """ String
        
        Global accuracy parameter for Spectre simulations. Options include
        'liberal', 'moderate' and 'conservative', in order of rising accuracy.
        """
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
        """ List of str
        
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
    def iofile_eventdict(self):
        """ Dictionary

        Dictionary to store event type output from the simulations. This should
        speed up reading the results.
        """
        if not hasattr(self, '_iofile_eventdict'):
            self._iofile_eventdict=dict()
            for name, val in self.iofile_bundle.Members.items():
                if (val.dir.lower()=='out' or val.dir.lower()=='output') and val.iotype=='event':
                    for key in val.ionames:
                        # Eldo seems to force output names to uppercase, let's
                        # uppercase everything here to avoid key mismatches
                        self._iofile_eventdict[key.upper()] = None
        return self._iofile_eventdict
    @iofile_eventdict.setter
    def iofile_eventdict(self,val):
        self._iofile_eventdict=val

    @property
    def iofile_bundle(self):
        """ Bundle

        A thesdk.Bundle containing `spice_iofile` objects. The `spice_iofile`
        objects are automatically added to this Bundle, nothing should be
        manually added.
        """
        if not hasattr(self,'_iofile_bundle'):
            self._iofile_bundle=Bundle()
        return self._iofile_bundle
    @iofile_bundle.setter
    def iofile_bundle(self,value):
        self._iofile_bundle=value

    @property
    def dcsource_bundle(self):
        """ Bundle

        A thesdk.Bundle containing `spice_dcsource` objects. The `spice_dcsource`
        objects are automatically added to this Bundle, nothing should be
        manually added.
        """
        if not hasattr(self,'_dcsource_bundle'):
            self._dcsource_bundle=Bundle()
        return self._dcsource_bundle
    @dcsource_bundle.setter
    def dcsource_bundle(self,value):
        self._dcsource_bundle=value

    @property
    def simcmd_bundle(self):
        """ Bundle

        A thesdk.Bundle containing `spice_simcmd` objects. The `spice_simcmd`
        objects are automatically added to this Bundle, nothing should be
        manually added.
        """
        if not hasattr(self,'_simcmd_bundle'):
            self._simcmd_bundle=Bundle()
        return self._simcmd_bundle
    @simcmd_bundle.setter
    def simcmd_bundle(self,value):
        self._simcmd_bundle=value

    @property
    def extracts(self):
        """ Bundle

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
        """ True | False (default)

        True if LSF submissions are properly defined.
        """
        if ( not thesdk.GLOBALS['LSFINTERACTIVE'] == '' ) and (not thesdk.GLOBALS['LSFSUBMISSION'] == ''):
            self._has_lsf = True
        else:
            self._has_lsf = False
        return self._has_lsf

    @property 
    def spice_submission(self):
        """ String

        Defines spice submission prefix from thesdk.GLOBALS['LSFSUBMISSION']
        and thesdk.GLOBALS['LSFINTERACTIVE'] for LSF submissions.

        Usually something like 'bsub -K' or 'bsub -I'.
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
                    else:
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
        """ List of str

        List of net names to be saved in the waveform database.

        .. note:: 
            Obsolete! Moved to `spice_simcmd` as a keyword argument.
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
        """ List of str

        List of manual commands to be pasted to the testbench. The strings are
        pasted to their own lines (no linebreaks needed), and the syntax is
        unchanged.

        For example, setting initial voltages from testbench (Eldo)::

            for i in range(nodes):
                self.spicemisc.append('.ic NODE<%d> 0' % i)

        The same example can be done in Spectre with::

            self.spicemisc.append('simulator lang=spice')
            for i in range(nodes):
                self.spicemisc.append('.ic NODE<%d> 0' % i)
            self.spicemisc.append('simulator lang=spectre')
        """
        if not hasattr(self, '_spicemisc'):
            self._spicemisc = []
        return self._spicemisc
    @spicemisc.setter
    def spicemisc(self,value): 
            self._spicemisc = value

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

        Path to the spice testbench ('./Simulations/spicesim/<runname>/tb_entityname.<suffix>').
        This shouldn't be set manually.
        """
        if not hasattr(self, '_spicetbsrc'):
            self._spicetbsrc=self.spicesimpath + '/tb_' + self.name + self.syntaxdict["cmdfile_ext"]
        return self._spicetbsrc

    @property
    def eldochisrc(self):
        """String

        Path to the Eldo chi-file. ('./Simulations/spicesim/<runname>/tb_entityname.chi').
        Only applies to Eldo simulations.
        This shouldn't be set manually.
        """
        if not hasattr(self, '_eldochisrc'):
            self._eldochisrc=self.spicesimpath + '/tb_' + self.name + '.chi'
        return self._eldochisrc

    @property
    def spicesubcktsrc(self):
        """String

        Path to the parsed subcircuit file. ('./Simulations/spicesim/<runname>/subckt_entityname.<suffix>').
        This shouldn't be set manually.
        """
        if not hasattr(self, '_spicesubcktsrc'):
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
        if os.path.exists(self.spicesimpath) and not self.preserve_result:
            self.print_log(msg='Cleaning ./%s/ (set preserve_result=True to prevent cleaning).' % os.path.relpath(self._spicesimpath,start='../'))
            keepdb = False
            for target in os.listdir(self.spicesimpath):
                targetpath = '%s/%s' % (self.spicesimpath,target)
                try:
                    if targetpath == self.spicedbpath and self.interactive_spice:
                        keepdb = True
                        self.print_log(msg='Preserving ./%s due to interactive_spice' % os.path.relpath(targetpath,start='../'))
                        continue
                    if os.path.isdir(targetpath):
                        shutil.rmtree(targetpath)
                    else:
                        os.remove(targetpath)
                    self.print_log(type='D',msg='Removing ./%s' % os.path.relpath(targetpath,start='../'))
                except:
                    self.print_log(type='W',msg='Could not remove ./%s' % os.path.relpath(targetpath,start='../'))
            if not keepdb:
                try:
                    # Eldo needs some time to disconnect from the jwdb server
                    # Another dirty hack to check that the process is dead before cleaning
                    # TODO: figure out if this can be prevented
                    if self.model == 'eldo':
                        self.print_log(type='I',msg='Waiting for Eldo to exit...')
                        waittime = 0
                        while os.system('pgrep \"easynch_64.exe\" >/dev/null') == 0:
                            time.sleep(1)
                            waittime += 1
                            if waittime > 60:
                                break
                    shutil.rmtree(self.spicesimpath)
                    self.print_log(type='D',msg='Removing ./%s/' % os.path.relpath(self.spicesimpath,start='../'))
                except:
                    self.print_log(type='W',msg='Could not remove ./%s/' % os.path.relpath(self.spicesimpath,start='../'))

    @property
    def spicecmd(self):
        """String

        Simulation command string to be executed on the command line.
        Automatically generated.
        """
        if not hasattr(self,'_spicecmd'):
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
                spicesimcmd = "eldo -64b %s " % (nprocflag)
            elif self.model=='spectre':
                spicesimcmd = ("spectre -64 +lqtimeout=0 ++aps=%s %s %s -outdir %s " 
                        % (self.errpreset,plflag,nprocflag,self.spicesimpath))
            elif self.model=='ngspice':
                spicesimcmd = self.syntaxdict["simulatorcmd"] + ' '
            self._spicecmd = self.spice_submission+spicesimcmd+self.spicetbsrc
        return self._spicecmd
    @spicecmd.setter
    def spicecmd(self,value):
        self._spicecmd=value

    @property
    def spicedbpath(self):
        """String

        Path to output waveform database. (./Simulations/spicesim/<runname>/tb_<entityname>.<resultfile_ext>)
        For now only for spectre.
        This shouldn't be set manually.
        """
        if not hasattr(self,'_spicedbpath'):
            self._spicedbpath=self.spicesimpath+'/tb_'+self.name+self.syntaxdict["resultfile_ext"]
        return self._spicedbpath
    @spicedbpath.setter
    def spicedbpath(self, value):
        self._spicedbpath=value

    @property
    def plotprogram(self):
        """ String

        Sets the program to be used for visualizing waveform databases.
        Options are ezwave (default) or viva.
        """
        if not hasattr(self, '_plotprogram'):
            self._plotprogram='ezwave'
        return self._plotprogram
    @plotprogram.setter
    def plotprogram(self, value):
        self._plotprogram=value

    @property
    def plotprogcmd(self):
        """ String

        Sets the command to be run for interactive simulations.
        """
        if not hasattr(self, '_plotprogcmd'):
            if self.plotprogram == 'ezwave':
                self._plotprogcmd='%s -MAXWND -LOGfile %s/ezwave.log %s &' % \
                        (self.plotprogram,self.spicesimpath,self.spicedbpath)
            elif self.plotprogram == 'viva':
                self._plotprogcmd='%s -datadir %s -nocdsinit &' % \
                        (self.plotprogram,self.spicedbpath)
            else:
                self._plotprogcmd = ''
                self.print_log(type='W',msg='Unsupported plot program \'%s\'.' % self.plotprogram)
        return self._plotprogcmd
    @plotprogcmd.setter
    def plotprogcmd(self, value):
        self._plotprogcmd=value

    def connect_spice_inputs(self):
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

    def connect_spice_outputs(self):
        """Automatically called function to connect iofiles (outputs) to top
        entity IOS Bundle items."""
        for name,val in self.iofile_bundle.Members.items():
            if val.dir == 'out':
                self.IOS.Members[name].Data=self.iofile_bundle.Members[name].Data

    def write_spice_inputs(self):
        """Automatically called function to call write() functions of each
        iofile with direction 'input'."""
        for name, val in self.iofile_bundle.Members.items():
            if val.dir.lower()=='in' or val.dir.lower()=='input':
                self.iofile_bundle.Members[name].write()

    def read_spice_outputs(self):
        """Automatically called function to call read() functions of each
        iofile with direction 'output'."""
        first=True
        for name, val in self.iofile_bundle.Members.items():
            if val.dir.lower()=='out' or val.dir.lower()=='output':
                if val.iotype=='event': # Event type outs are in same file, read only once to speed up things
                    if first:
                        self.iofile_bundle.Members[name].read()
                        first=False
                    if len(val.ionames) == 1:
                        try:
                            self.iofile_bundle.Members[name].Data=self.iofile_eventdict[val.ionames[0].upper()]
                        except KeyError:
                            self.print_log(type='W', msg='Invalid ioname %s for iofile %s' % (val.ionames[0], name))
                    else: # Iofile is a bus?
                        data=[]
                        for i, key in enumerate(val.ionames):
                            try:
                                if i == 0:
                                    data=self.iofile_eventdict[key.upper()]
                                else:
                                    try:
                                        data=np.r_['1', data, self.iofile_eventdict[key.upper()]]
                                    except ValueError:
                                        self.print_log(type='W', msg='Invalid dimensions for concatenating arrays for IO %s!' % name)
                            except KeyError:
                                self.print_log(type='W', msg='Invalid ioname %s for iofile %s' % (key, name))
                        self.iofile_bundle.Members[name].Data=data
                else:
                    self.iofile_bundle.Members[name].read()
    
    def execute_spice_sim(self):
        """Automatically called function to execute spice simulation."""
        self.print_log(type='I', msg="Running external command %s" %(self.spicecmd) )
        if os.system(self.spicecmd) > 0:
            self.print_log(type='E', msg="Simulator (%s) returned non-zero exit code." % (self.model))

    def run_plotprogram(self):
        ''' Starting a parallel process for waveform viewer program.

        The plotting program command can be set with 'plotprogram'.
        Tested for spectre and eldo.
        '''
        if self.model == 'ngspice':
            self.print_log(type='W',msg='Interactive plotting not implemented for ngspice.')
            return
        # This waiting method assumes spectre output.
        tries = 0
        while tries < 100:
            if os.path.exists(self.spicedbpath):
                if self.model == 'spectre':
                    # More than just the logfile exists
                    if len(os.listdir(self.spicedbpath)) > 1:
                        # Database file has something written to it
                        filesize = []
                        for f in os.listdir(self.spicedbpath):
                            filesize.append(os.stat('%s/%s' % (self.spicedbpath,f)).st_size)
                        if all(filesize) > 0:
                            break
                else:
                    break
            else:
                time.sleep(2)
                tries += 1
        cmd=self.plotprogcmd
        self.print_log(type='I', msg='Running external command: %s' % cmd)
        try:
            ret=os.system(cmd)
            if ret != 0:
                self.print_log(type='W', msg='%s returned with exit status %d!' % (self.plotprogram, ret))
        except: 
            self.print_log(type='W',msg='Something went wrong while launcing %s.' % self.plotprogram)
            self.print_log(type='W',msg=traceback.format_exc())

    def extract_powers(self):
        """
        Automatically called function to extract transient power and current
        consumptions. The consumptions are extracted for spice_dcsource objects
        with the attribute extract=True.
        
        The extracted consumptions are accessible on the top-level after
        simulation as::
            
            # Dictionary with averaged power of each supply + total
            self.extracts.Members['powers']
            # Dictionary with averaged current of each supply + total
            self.extracts.Members['currents']
            # Dictionary with transient current of each supply
            self.extracts.Members['curr_tran']

        The keys in the aforementioned dictionaries match the `name`-fields of
        the respective `spice_dcsource` objects.

        """
        self.extracts.Members['powers'] = {}
        self.extracts.Members['currents'] = {}
        self.extracts.Members['curr_tran'] = {}
        try:
            for name, val in self.tb.dcsources.Members.items():
                # Read transient power consumption of the extracted source
                if val.extract and val.sourcetype.lower() == 'v':
                    sourcename = '%s%s' % (val.sourcetype.upper(),val.name.upper())
                    if sourcename in self.iofile_eventdict:
                        arr = self.iofile_eventdict[sourcename]
                        if val.ext_start is not None:
                            arr = arr[np.where(arr[:,0] >= val.ext_start)[0],:]
                        if val.ext_stop is not None:
                            arr = arr[np.where(arr[:,0] <= val.ext_stop)[0],:]
                        # The time points are non-uniform -> use deltas as weights
                        dt = np.diff(arr[:,0])
                        totaltime = arr[-1,0]-arr[0,0]
                        meancurr = np.sum(np.abs(arr[1:,1])*dt)/totaltime
                        meanpwr = meancurr*val.value
                        self.extracts.Members['currents'][val.name] = meancurr
                        self.extracts.Members['powers'][val.name] = meanpwr
                        self.extracts.Members['curr_tran'][val.name] = arr
            if len(self.extracts.Members['powers'].keys()) > 0:
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

    def get_buswidth(self,signame):
        """ Extract buswidth from signal name.
        
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
        signame = signame.replace('<',' ').replace('>',' ').replace('[',' ').replace(']',' ').replace(':',' ').split(' ')
        if '' in signame:
            signame.remove('')
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
            buswidth = busstart-busstop+1
            busrange = range(busstart,busstop-1,-1)
        else:
            buswidth = busstop-busstart+1
            busrange = range(busstart,busstop+1)
        return busstart,busstop,buswidth,busrange
    
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
        def sorter(val):
            '''
            Function for sorting the files in correct order
            Files that are output from simulation are of form

            dcSweep-<integer>_oppoint.dc

            Strategy: extract integer from filename and sort based on the integer.

            '''
            key=val.split('-')[1].split('_')[0]
            return int(key)

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
                # For distributed runs
                if self.distributed_run:
                    path=os.path.join(self.spicesimpath,'tb_%s.raw' % self.name, '[0-9]*', fname)
                    files = sorted(glob.glob(path),key=sorter)
                else:
                    path=os.path.join(self.spicesimpath,'tb_%s.raw' % self.name, fname)
                    files = glob.glob(path)
                valbegin = 'VALUE\n'
                eof = 'END\n'
                parsevals = False
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
            self.connect_spice_inputs()
            self.tb.generate_contents()
            self.tb.export_subckt(force=True)
            self.tb.export(force=True)
            self.write_spice_inputs()
            if self.interactive_spice:
                plotthread = threading.Thread(target=self.run_plotprogram,name='plotting')
                plotthread.start()
            self.execute_spice_sim()
            self.read_spice_outputs()
            self.connect_spice_outputs()
            self.extract_powers()
            self.read_oppts()
            # Clean simulation results
            del self.spicesimpath
        else:
            #Loading previous simulation results and not simulating again
            try:
                self.runname = self.load_state
                if self.runname == 'latest' or self.runname == 'last':
                    results = glob.glob(self.entitypath+'/Simulations/spicesim/*')
                    latest = max(results, key=os.path.getctime)
                    self.runname = latest.split('/')[-1]
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
                    self.connect_spice_inputs()
                    self.read_spice_outputs()
                    self.connect_spice_outputs()
                    self.extract_powers()
                    self.read_oppts()
            except:
                self.print_log(type='I',msg=traceback.format_exc())
                self.print_log(type='F',msg='Failed while loading results from %s.' % self._spicesimpath)

