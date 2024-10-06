"""
=====
Spice
=====

Analog simulation interface package for TheSyDeKick.

Provides utilities to import spice-like modules to Python environment and
generate testbenches for the various simulation cases.

Initially written by Okko Järvinen, 2019


Notes for developers
--------------------

There are now two ways to provide simulator dependent structures that are
(most of the time) followed:

    1. Simulator dependent *properties* are defined in packages 
    <simulator>/<simulator>.py that are used as `spice_simulator` instance
    in this spice class inside *spice_simulator* property. Properties and 
    attributed of instance of *this class* (i.e. all TheSyDeKick Entitites)
    are made visible to spice_simulators through passing the *self* as *parent* 
    argument in instance creation. Properties defined inside 
    *spice_simulator* are accessed and set through corresponding properties of
    this class.

    2. This is an interface package, generic spice simulation 
    related methods should be provided in *spice_methods* module.

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
import timeit
from datetime import datetime
from abc import * 
from thesdk import *
import numpy as np
from numpy import genfromtxt
import pandas as pd
from functools import reduce
from spice.spice_common import *
from spice.testbench import testbench as stb
from spice.spice_simcmd import spice_simcmd as spice_simcmd
from spice.spice_iofile import spice_iofile as spice_iofile
from spice.spice_dcsource import spice_dcsource as spice_dcsource
from spice.spice_module import spice_module as spice_module
# Simulator modules
from spice.ngspice.ngspice import ngspice
from spice.eldo.eldo import eldo
from spice.spectre.spectre import spectre

class spice(spice_common):

    @property
    def si_prefix_mult(self):
        """dict : Dictionary mapping SI-prefixes to multipliers.
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
    def spice_simulator(self): 
        """The simulator specific operation is defined with an instance of 
        simulator specific class. Properties and methods return values from that class.

        :type: ngspice
        :type: eldo
        :type: spectre

        """
        if not hasattr(self,'_spice_simulator'):
            if self.model == 'ngspice':
                self._spice_simulator=ngspice(parent=self)
            if self.model == 'eldo':
                self._spice_simulator=eldo(parent=self)
            if self.model == 'spectre':
                self._spice_simulator=spectre(parent=self)
        return self._spice_simulator
   

    @property
    def syntaxdict(self):
        """dict : Internally used dictionary for common syntax conversions between
        Spectre, Eldo, and Ngspice.
        """
        if not hasattr(self,'_syntaxdict'):
            self._syntaxdict = self.spice_simulator.syntaxdict
        return self._syntaxdict
    @syntaxdict.setter
    def syntaxdict(self,value):
        self._spice_simulator.syntaxdict=value

    @property
    def preserve_spicefiles(self):  
        """bool : If True, do not delete generated Spice files (testbench, subcircuit,
        etc.) after simulations.  Useful for debugging.

            (Default : False )
        
        """
        if not hasattr(self,'_preserve_spicefiles'):
            self._preserve_spicefiles=False
        return self._preserve_spicefiles
    @preserve_spicefiles.setter
    def preserve_spicefiles(self,value):
        self._preserve_spicefiles=value


    @property 
    def spicesimpath(self):
        """ str : Path to the directory where the simulation results are stored.

          ( Default : self.simpath )

        """
        if not hasattr(self,'_spicesimpath'):
            self._spicesimpath=self.simpath
        return self._spicesimpath

    def delete_spicesimpath(self):
        """ Method to clean up files from spicesimpath.

        """
        if os.path.exists(self.spicesimpath):
            # This is used to check if the waveform database would prevent the deletion of the directory
            keepdb = False
            # Collect iofile filepaths not to delete them
            iofilepaths = []
            for name,val in self.iofile_bundle.Members.items():
                for fpath in val.file:
                    iofilepaths.append(fpath)
            # Delete everything (conditionally skip iofiles or spicefiles)
            for target in os.listdir(self.spicesimpath):
                targetpath = '%s/%s' % (self.spicesimpath,target)
                try:
                    if targetpath not in iofilepaths:
                        # Target is a spicefile (anything that isn't an iofile)
                        if self.preserve_spicefiles:
                            self.print_log(type='I',msg='Preserving %s' % targetpath)
                        else:
                            if targetpath == self.spicedbpath and self.interactive_spice:
                                keepdb = True
                                self.print_log(type='I', msg='Preserving %s due to interactive_spice' % targetpath)
                                continue
                            if os.path.isdir(targetpath):
                                shutil.rmtree(targetpath)
                            else:
                                os.remove(targetpath)
                            self.print_log(type='D',msg='Removing %s' % targetpath)
                except:
                    self.print_log(type='W',msg='Could not remove %s' % targetpath)
            if not keepdb and not self.preserve_iofiles and not self.preserve_spicefiles:
                try:
                    # Eldo needs some time to disconnect from the jwdb server
                    # Another dirty hack to check that the process is dead before cleaning
                    # TODO: figure out if this can be prevented
                    # This is exceptionally here as eldo is the only deviation from the rule
                    # strictly it should be eldo's pecific module.
                    if self.model == 'eldo':
                        self.print_log(type='I',msg='Waiting for Eldo to exit...')
                        waittime = 0
                        while os.system('pgrep \"easynch_64.exe\" >/dev/null') == 0:
                            time.sleep(1)
                            waittime += 1
                            if waittime > 60:
                                break
                    shutil.rmtree(self.spicesimpath)
                    self.print_log(type='D',msg='Removing %s/' % self.spicesimpath)
                except:
                    self.print_log(type='W',msg='Could not remove %s/' % self.spicesimpath)


    @property
    def distributed_run(self):
        """bool : If True, distributes applicable simulations (currently DC sweep
        supported) into the LSF cluster. The number of subprocesses launched is
        set by self.num_processes.

            (Default False)

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
        """int :  Maximum number of spawned child processes for distributed runs.

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
        """str : Feature for loading results of previous simulation. The Spice
        simulation is not re-executed, but the outputs will be read from
        existing files. The string value should be the `runname` of the desired
        simulation.

            ( Default '' ) 
        
        Example
        -------

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
        """dict : Feature for specifying the 'section' of the model library file and
        simulation temperature. The path to model libraries should be set in
        TheSDK.config as either ELDOLIBFILE, SPECTRELIBFILE or NGSPICELIBFILE
        variable.

        Example
        -------
            ::

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
        """dict : Feature for specifying options for spice simulation. The key is the
        name of the option (as in simulator manual specifies), and the value is
        the value given to said option. Valid key-value pairs can be found from
        the manual of the simulator (Eldo, Spectre or Ngspice).

        Example
        -------
        ::

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
        """dict : Feature for specifying simulation parameters for spice simulation. The
        key is the name of the parameter , and the value is the value given to
        said parameter.

        Example
        -------
        ::

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
    def interactive_spice(self):
        """bool : Launch simulator in interactive mode. A waveform viewer (ezwave by
        default) is opened during the simulation for debugging. See
        `plotprogram` for selecting waveform viewer program.
         
            ( Default : False )

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
        """int : Requested maximum number of threads for multithreaded simulations.

        Eldo : maps to command line parameter '-nproc'

        Spectre :  maps to command line parameter '+mt'.

        Ngspice :  maps to 'set num_threads=' line in testbench.

        """
        if hasattr(self,'_nproc'):
            return self._nproc
        else:
            self._nproc=False
        return self._nproc
    @nproc.setter
    def nproc(self,value):
        self._nproc=value

    
    # DSPF filenames
    @property
    def postlayout_subckts(self):
        """[str] : List containing filenames for subcircuit DSPF-files to be included for 
        post-layout simulations. The names given in this list are matched to dspf-files in
        './spice/' -directory. A postfix '.pex.dspf' is automatically appended
        to the given names (this will probably change later).
        
        Example
        -------
        ::

            self.postlayout_subckts = ['inv_v2','switch_v3']

        would include files './spice/inv_v2.pex.dspf' and
        './spice/switch_v3.pex.dspf' as postlayout_subckts-files in the testbench. If top level 
        dspf (self.dspf) is given these are omitted. Otherwise simulator will replace 
        subcircuits with corresponding name with the postlayout netlist defined in the 
        dspf file. 
        """
        if not hasattr(self,'_postlayout_subckts'):
            self._postlayout_subckts = []
        return self._postlayout_subckts
    @postlayout_subckts.setter
    def postlayout_subckts(self,value):
        self._postlayout_subckts=value
    


    # DSPF filenames
    @property
    def dspf(self):
        """[str] : List containing filenames for DSPF-files to be included for post-layout
        simulations. The names given in this list are matched to dspf-files in
        './spice/' -directory. A postfix '.pex.dspf' is automatically appended
        to the given names (this will probably change later).
        
        Example
        -------
        ::

            self.dspf = ['adc_top_level']

        would include files './spice/adc_top_level.pex.dspf' as 
        a top level dspf-file in the testbench. If the
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
    def postlayout(self):
        """bool : Enables post-layout optimizations in the simulator command options. 
            (Default : False )

        """
        if not hasattr(self,'_postlayout'):
            if len(self.dspf) > 0:
                self.print_log(type='I', msg = 'Setting postlayout to True due to given dspf-files')
                self._postlayout = True
            else:
                self.print_log(type='W', 
                               msg='Postlayout attribute accessed before defined. Defaulting to False.')
                self._postlayout=False
        return self._postlayout
    @postlayout.setter
    def postlayout(self,value):
        self._postlayout=value
    @postlayout.deleter
    def postlayout(self,value):
        self._postlayout=None

    @property
    def iofile_eventdict(self):
        """dict : Dictionary to store event type output from the simulations. This should
        speed up reading the results.

        NOTE: Eldo seems to force output names to uppercase, let's
        uppercase everything here to avoid key mismatches. (This should be changed).

        """
        if not hasattr(self, '_iofile_eventdict'):
            self._iofile_eventdict=dict()
            for name, val in self.iofile_bundle.Members.items():
                if (val.dir.lower()=='out' or val.dir.lower()=='output') and val.iotype=='event':
                    for key in val.ionames:
                        self._iofile_eventdict[key.upper()] = None
        return self._iofile_eventdict
    @iofile_eventdict.setter
    def iofile_eventdict(self,val):
        self._iofile_eventdict=val

    @property
    def dcsource_bundle(self):
        """Bundle : A thesdk.Bundle containing `spice_dcsource` objects. The `spice_dcsource`
        objects are automatically added to this Bundle, nothing should be
        manually added.

        This is to automate biasing and operation conditions of the circuit.

        """
        if not hasattr(self,'_dcsource_bundle'):
            self._dcsource_bundle=Bundle()
        return self._dcsource_bundle
    @dcsource_bundle.setter
    def dcsource_bundle(self,value):
        self._dcsource_bundle=value

    @property
    def simcmd_bundle(self):
        """ Bundle : A thesdk.Bundle containing `spice_simcmd` objects. The `spice_simcmd`
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
        """ Bundle : A thesdk.Bundle containing extracted quantities.
        """

        return self.spice_simulator.extracts
    @extracts.setter
    def extracts(self,value):
        self.spice_simulator.extracts = value

    @property 
    def spice_submission(self):
        """str : Defines spice submission prefix from thesdk.GLOBALS['LSFSUBMISSION']
        and thesdk.GLOBALS['LSFINTERACTIVE'] for LSF submissions.

        Usually something like 'bsub -K' or 'bsub -I'.

        """
        if not hasattr(self, '_spice_submission'):
            try:
                if not self.has_lsf:
                    self.print_log(type='I', msg='LSF not configured, running locally.')
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
    def spicemisc(self): 
        """ [str] : List of manual commands to be pasted to the testbench. The strings are
        pasted to their own lines (no linebreaks needed), and the syntax is
        unchanged.

        Example
        -------
        Setting initial voltages from testbench (Eldo)::
        
            for i in range(nodes):

                self.spicemisc.append('.ic NODE<%d> 0' % i)

        The same example for Spectre::

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
        """str : Name of the module.
        """
        if not hasattr(self, '_name'):
            self._name=os.path.splitext(os.path.basename(self._classfile))[0]
        return self._name

    @property
    def spicesrcpath(self):
        """str : Path to the spice source of the entity. Can be set manually to desired location.
        This variable provides the dspf-parasitic netlist filepath.

            ( Default: <entity path>/spice )

        """
        if not hasattr(self, '_spicesrcpath'):
            self._spicesrcpath  =  self.entitypath + '/spice'
            try:
                if not (os.path.exists(self._spicesrcpath)):
                    os.makedirs(self._spicesrcpath)
                    self.print_log(type='I',msg='Creating %s.' % self._spicesrcpath)
            except:
                self.print_log(type='E',msg='Failed to create %s.' % self._spicesrcpath)
        return self._spicesrcpath
    @spicesrcpath.setter
    def spicesrcpath(self,val):
        self._spicesrcpath=val

    @property
    def spicesrc(self):
        """str : Path to the source netlist. Can be set manually to desired location.
        
            ( Default: 'spice/entityname.scs' )


        N.B!:
            Netlist has to contain the top-level design as a subcircuit definition!
        """
        if not hasattr(self, '_spicesrc'):
            self._spicesrc=self.spicesrcpath + '/' + self.name + self.spice_simulator.cmdfile_ext

            if not os.path.exists(self._spicesrc):
                self.print_log(type='W',msg='No source circuit found in %s.' % self._spicesrc)
        return self._spicesrc
    @spicesrc.setter
    def spicesrc(self,value): 
            self._spicesrc = value

    @property
    def spicetbsrc(self):
        """str : Path to the spice testbench ('<spicesimpath>/tb_entityname.<suffix>').
        This shouldn't be set manually.

        """
        if not hasattr(self, '_spicetbsrc'):
            self._spicetbsrc=self.spicesimpath + '/tb_' + self.name + self.spice_simulator.cmdfile_ext
        return self._spicetbsrc

    @property
    def spicesubcktsrc(self):
        """str : Path to the parsed subcircuit file. ('<spicesimpath>/subckt_entityname.<suffix>').
        This shouldn't be set manually.

        """
        if not hasattr(self, '_spicesubcktsrc'):
            self._spicesubcktsrc=self.spicesimpath + '/subckt_' + self.name + self.spice_simulator.cmdfile_ext
        return self._spicesubcktsrc

    
    @property
    def plflag(self):
        ''' str : Postlayout simulation accuracy/RC reduction flag.

        '''
        if not hasattr(self, '_plflag'):
            self._plflag=self.spice_simulator.plflag
        return self._plflag
    @plflag.setter
    def plflag(self, val):
        self.spice_simulator.plflag = val
        self._plflag = val
            
    @property
    def spicecmd(self):
        """str : Simulation command string to be executed on the command line.
        Automatically generated.

        """
        if not hasattr(self,'_spicecmd'):
                self._spicecmd = self.spice_simulator.spicecmd
        return self._spicecmd
    @spicecmd.setter
    def spicecmd(self,value):
        self.spice_simulator.spicecmd=value


    @property
    def spicedbpath(self):
        """str : Path to output waveform database. (<spicesimpath>/tb_<entityname>.<resultfile_ext>)
        (For now only for spectre. HOW? should work for Eldo too)

        """
        if not hasattr(self,'_spicedbpath'):
            self._spicedbpath=self.spicesimpath+'/tb_'+self.name+self.spice_simulator.resultfile_ext
        return self._spicedbpath
    @spicedbpath.setter
    def spicedbpath(self, value):
        self._spicedbpath=value

    ### To be relocated
    ### These are simuator related i.e. ezwave does not work for ngspice.
    @property
    def plotprogram(self):
        """str : Sets the program to be used for visualizing waveform databases.
        Options are ezwave (default) or viva.

        """
        if not hasattr(self, '_plotprogram'):
            self._plotprogram='ezwave'
        return self._plotprogram
    @plotprogram.setter
    def plotprogram(self, value):
        self._plotprogram=value
    ### End to be relocated

    @property
    def plotprogcmd(self):
        """ str : Command to be run for interactive simulations.

        """
        return self.spice_simulator.plotprogcmd

    @plotprogcmd.setter
    def plotprogcmd(self, value):
        self.spice_simulator.plotprogcmd = value

    @property
    def save_database(self): 
        """bool : Whether to save the waveform database (.wdb-file for eldo, raw-database
        for spectre), when save_state=True.

            ( Default : False)

        """
        if not hasattr(self,'_save_database'):
            self._save_database=False
        return self._save_database 
    @save_database.setter
    def save_database(self,value): 
        self._save_database=value


    @property
    def save_output_file(self):
        """bool : If True and save_state is True, copy the output file of simulator
        to entity statedir. Useful for scavenging results if simulator exited
        but state was not written to disk for some reason.

           ( Default : False)

        """
        if not hasattr(self, '_save_output_file'):
            self._save_output_file=False
        return self._save_output_file

    @save_output_file.setter
    def save_output_file(self, val):
        self._save_output_file=val


    @property
    def load_output_file(self): 
        """bool : Whether to load the outputs from simulator output file.
        This only works if the file exists in the state directory, i.e.
        the simulator was run with save_output_file=True.
        WARNING: This will read the IOS from the output file, and REWRITE
        THE ENTITY STATE on disk.

            ( Default : False )

        """
        if not hasattr(self,'_load_output_file'):
            self._load_output_file=False
        return self._load_output_file 
    @load_output_file.setter
    def load_output_file(self,value): 
        if value:
            self.print_log(type='W', msg='load_output_file set to True! This will rewrite the entity state on disk!')
        self._load_output_file=value

    def connect_spice_inputs(self):
        """Automatically called function to connect iofiles (inputs) to top
        entity IOS Bundle items.

        """
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
        entity IOS Bundle items.

        """
        for name,val in self.iofile_bundle.Members.items():
            if val.dir == 'out':
                self.IOS.Members[name].Data=self.iofile_bundle.Members[name].Data

    def write_spice_inputs(self):
        """Automatically called function to call write() functions of each
        iofile with direction 'input'.

        """
        for name, val in self.iofile_bundle.Members.items():
            if val.dir.lower()=='in':
                self.iofile_bundle.Members[name].write()
            elif val.dir.lower()=='input':
                self.print_log(type='F', 
                    msg='Direction indicator for %s of should be \'in\' and you are the one to fix your code.' 
                        %(self.iofile_bundle.Members[name]))


    def read_spice_outputs(self):
        """Automatically called function to call read() functions of each
        iofile with direction 'output'.

        """
        first=True
        for name, val in self.iofile_bundle.Members.items():
            if val.dir.lower()=='out' or val.dir.lower()=='output':
                if val.iotype=='event': # Event type outs are in same file, read only once to speed up things
                    if first:
                        self.iofile_bundle.Members[name].read()
                        first=False
                        self.check_output_accuracy(val.ionames[0]) # Time stamps are common to all, need to do only once
                    if len(val.ionames) == 1:
                        try:
                            if self.model == 'spectre':
                                if self.is_strobed:
                                    self.iofile_bundle.Members[name].Data=self.filter_strobed(val.name,val.ionames[0])
                                else:
                                    self.iofile_bundle.Members[name].Data=self.iofile_eventdict[val.ionames[0].upper()]
                            else:
                                self.iofile_bundle.Members[name].Data=self.iofile_eventdict[val.ionames[0].upper()]
                        except KeyError:
                            self.print_log(type='E',msg='Invalid ioname %s for iofile %s' % (val.ionames[0], name))
                    else: # Iofile is a bus?
                        data=[]
                        for i, key in enumerate(val.ionames):
                            try:
                                if i == 0:
                                    # Parse the first member of bus
                                    if self.model == 'spectre':
                                        if self.is_strobed:
                                            data=self.filter_strobed(val.name, key)
                                        else:
                                            data=self.iofile_eventdict[key.upper()]
                                    else:
                                        data=self.iofile_eventdict[key.upper()]
                                else:
                                    # Next members are concatenated to array
                                    if self.model == 'spectre' and self.is_strobed:
                                        next=self.filter_strobed(val.name, key)
                                    else:
                                        next=self.iofile_eventdict[key.upper()]
                                    try:
                                        data=np.r_['1', data, next]
                                    except ValueError:
                                        self.print_log(type='W',msg='Invalid dimensions for concatenating arrays for IO %s!' % name)
                            except KeyError:
                                self.print_log(type='E', msg='Invalid ioname %s for iofile %s' % (key, name))
                        self.iofile_bundle.Members[name].Data=data
                else:
                    self.iofile_bundle.Members[name].read()
            elif val.dir.lower()=='output':
                self.print_log(type='F', 
                    msg='Direction indicator for %s of should be \'out\' and you are the one to fix your code.' 
                        %(self.iofile_bundle.Members[name]))
    
    def execute_spice_sim(self):
        """Automatically called function to execute spice simulation.

        """
        self.print_log(type='I', msg="Running external command %s" %(self.spicecmd) )
        if os.system(self.spicecmd) > 0:
            self.print_log(type='E', msg="Simulator (%s) returned non-zero exit code." % (self.model))

    def run_plotprogram(self):
        ''' Starting a parallel process for waveform viewer program.

        The plotting program command can be set with 'plotprogram'.
        Tested for spectre and eldo.

        '''
        if not self.distributed_run:
            self.spice_simulator.run_plotprogram()
        else:
            self.print_log(type='I', msg='Waveform viewer %s not launched due to distributed run.' % self.plotprogram)

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
            for name, val in self.spice_tb.dcsources.Members.items():
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

    def read_oppts(self):
        """ Internally called function to read the DC operating points of the circuit
            TODO: Implement for Eldo as well.

        """

        self.spice_simulator.read_oppts()


    @property
    def spice_tb(self):
        """spice_module : Testbench instance. You can set the attributes of the testbench and dut below it before you execute run_spice.
        if 

        Example
        -------

        ::
            self.spice_tb.dut.custom_subckt_name='custom_inverter'
            self.run_spice()

        """
        if not hasattr(self,'_spice_tb'):
            if hasattr(self,'_tb'):
                self.print_log(type='O', 
                        msg='Propagating self.tb to self.spice_tb property. You should use spice_tb for spice simulations.')
                self._spice_tb = self.tb
            else:
                self._spice_tb = stb(self)
        return self._spice_tb
    @spice_tb.setter
    def spice_tb(self, value):
            self._spice_tb = value

    def run_spice(self):
        """Externally called function to execute spice simulation.

        """
        if self.load_state != '': 
            # Loading a previously stored state
            if self.load_output_file:
                self.read_spice_outputs()
                self.connect_spice_outputs()
                # Are these really something to be part of
                # default execution
                self.extract_powers()
                self.read_oppts()
                ###
                self._write_state()
            else:
                self._read_state()
        else:
            # Normal execution of full simulation
            self.connect_spice_inputs()
            self.spice_tb.generate_contents()
            self.spice_tb.export(force=True)
            self.write_spice_inputs()
            if self.interactive_spice:
                plotthread = threading.Thread(target=self.run_plotprogram,name='plotting')
                plotthread.start()
            self.execute_spice_sim()
            self.read_spice_outputs()
            self.connect_spice_outputs()
            # Are these really something to be part of
            # default execution
            self.extract_powers()
            self.read_oppts()
            ###
            # Save entity state
            if self.save_state:
                self._write_state()
                # If this is generic enough between simulators, it can be moved
                # to thesdk (basically if spicedbpath has an equivalent in
                # other simulators too)
                if self.save_database:
                    try:
                        dbname = self.spicedbpath.split('/')[-1]
                        if os.path.isdir(self.spicedbpath):
                            shutil.copytree(self.spicedbpath,'%s/%s' % (self.statedir,dbname))
                        else:
                            shutil.copyfile(self.spicedbpath,'%s/%s' % (self.statedir,dbname))
                        self.print_log(msg='Saving waveform database to %s/%s' % (self.statedir,dbname))
                    except:
                        self.print_log(type='E',msg='Failed saving waveform database to %s/%s' % (self.statedir,dbname))
                if self.save_output_file:
                    output_name = 'tb_%s.print' % self.name
                    filepath = self.spicesimpath
                    output_path = os.path.join(filepath, output_name)
                    targ_path = os.path.join(self.statedir, output_name)
                    shutil.copyfile(output_path, targ_path)
            # Clean simulation results
            self.delete_iofile_bundle()
            self.delete_spicesimpath()

    # Obsolete stuff
    @property
    def plotlist(self): 
        """ [ str ] : List of net names to be saved in the waveform database.

        .. note:: 
            Obsolete! Moved to `spice_simcmd` as a keyword argument.
        """
        self.print_log(type='O', msg='Plotlist has been relocated as an argument to spice_simcmd!') 
        if not hasattr(self,'_plotlist'):
            self._plotlist=[]
        return self._plotlist 
    @plotlist.setter
    def plotlist(self,value): 
        self.print_log(type='O', msg='Plotlist has been relocated as an argument to spice_simcmd!') 
        self._plotlist=value

    @property
    def errpreset(self):
        """str : Global accuracy parameter for Spectre simulations. Options include
        'liberal', 'moderate' and 'conservative', in order of rising accuracy.

        Example
        -------
        ::

            self.spice_simulator.errpreset='conservative'

        """
        if not hasattr(self,'_errpreset'):
            self._errpreset=self.spice_simulator.errpreset
        self.print_log(type='O', msg='Errpreset is obsoleted as spectre specific command line argument')
        self.print_log(type='O', msg='Alternative method for handling simulator specific command line arguments should be developed.')
        return self.spice_simulator.errpreset
    @errpreset.setter
    def errpreset(self,value):
        self.spice_simulator.errpreset=value

