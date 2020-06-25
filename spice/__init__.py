"""
=======
Spice
=======
Analog simulation interface package for The System Development Kit 

Provides utilities to import spice-like modules to python environment and
automatically generate testbenches for the most common simulation cases.

Initially written by Okko Järvinen, 2019

Release 1.4 , Jun 2020 supports Eldo and Spectre
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
    for vhdl simulations in the subclasses.
    
    """

    #These need to be converted to abstact properties
    def __init__(self):
        pass

    @property
    def syntaxdict(self):
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
                    "subckt" : '.subckt',
                    "lastline" : '.end',
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
                    "subckt" : 'subckt',
                    "lastline" : '///', #needed?
                    "csvskip" : 0
                    }
        return self._syntaxdict
    @syntaxdict.setter
    def syntaxdict(self,value):
        self._syntaxdict=value
    #Name derived from the file

    @property
    @abstractmethod
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    @property
    def preserve_iofiles(self):  
        """True | False (default)

        If True, do not delete file IO files after 
        simulations. Useful for debugging the file IO"""

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

        If True, do not delete generated Eldo files (testbench, subcircuit, etc.)
        after simulations. Useful for debugging."""

        if hasattr(self,'_preserve_spicefiles'):
            return self._preserve_spicefiles
        else:
            self._preserve_spicefiles=False
        return self._preserve_spicefiles
    @preserve_spicefiles.setter
    def preserve_spicefiles(self,value):
        self._preserve_spicefiles=value

    @property
    def load_state(self):  
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
        if hasattr(self,'_spiceoptions'):
            return self._spiceoptions
        else:
            self._spiceoptions={}
        return self._spiceoptions
    @spiceoptions.setter
    def spiceoptions(self,value):
        self._spiceoptions=value

    @property
    def runname(self):
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
        
        Launch simulator in local machine with GUI."""

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
        if hasattr(self,'_errpreset'):
            return self._errpreset
        else:
            self._errpreset='moderate'
        return self._errpreset
    @errpreset.setter
    def errpreset(self,value):
        self._errpreset=value

    @property
    def iofile_bundle(self):
        """ 
        Property of type thesdk.Bundle.
        This property utilises eldo_iofile class to maintain list of IO-files
        that  are automatically assigned as arguments to eldocmd.
        when eldo.eldo_iofile.eldo_iofile(name='<filename>,...) is used to define an IO-file, created file object is automatically
        appended to this Bundle property as a member. Accessible with self.iofile_bundle.Members['<filename>']
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
        if (not self.preserve_iofiles):
            if self.interactive_spice:
                simpathname = self.spicesimpath
            else:
                simpathname = self.spicesimpath
            try:
                shutil.rmtree(simpathname)
                self.print_log(type='I',msg='Removing %s.' % simpathname)
            except:
                self.print_log(type='W',msg='Could not remove %s.' % simpathname)
        #self._iofile_bundle=None

    @property
    def dcsource_bundle(self):
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
    def spice_submission(self):
        """
        Defines spice submioddion prefix from thesdk.GLOBALS['LSFSUBMISSION']

        Usually something like 'bsub -K'
        """
        if not hasattr(self, '_spice_submission'):
            try:
                #self._spice_submission=thesdk.GLOBALS['LSFSUBMISSION']+' '

                #temporary fix
                #self._spice_submission=' '
                #self._spice_submission='sleep 10;'+thesdk.GLOBALS['LSFSUBMISSION']+' -q "CentOS6" -o %s/bsublog.txt ' %self.spicesimpath
                self._spice_submission=thesdk.GLOBALS['LSFSUBMISSION']+' -q "CentOS7" -o %s/bsublog.txt ' %self.spicesimpath
            except:
                self.print_log(type='W',msg='Variable thesdk.GLOBALS incorrectly defined. _spice_submission defaults to empty string and simulation is ran in localhost.')
                self._spice_submission=''

        if hasattr(self,'_interactive_spice'):
            return self._spice_submission

        return self._spice_submission

    @property
    def spiceparameters(self): 
        if not hasattr(self, '_spiceparameters'):
            self._spiceparameters =dict([])
        return self._spiceparameters
    @spiceparameters.setter
    def spiceparameters(self,value): 
            self._spiceparameters = value
    @spiceparameters.deleter
    def spiceparameters(self): 
            self._spiceparameters = None

    @property
    def eldocorner(self): 
        if not hasattr(self, '_eldocorner'):
            self._eldocorner =dict([])
        return self._eldocorner
    @eldocorner.setter
    def eldocorner(self,value): 
            self._eldocorner = value
    @eldocorner.deleter
    def eldocorner(self): 
            self._eldocorner = None

    @property
    def eldooptions(self): 
        if not hasattr(self, '_eldooptions'):
            self._eldooptions =dict([])
        return self._eldooptions
    @eldooptions.setter
    def eldooptions(self,value): 
            self._eldooptions = value
    @eldooptions.deleter
    def eldooptions(self): 
            self._eldooptions = None

    @property
    def eldoiofiles(self): 
        if not hasattr(self, '_eldoiofiles'):
            self._eldoiofiles =dict([])
        return self._eldoiofiles
    @eldoiofiles.setter
    def eldoiofiles(self,value): 
            self._eldoiofiles = value
    @eldoiofiles.deleter
    def eldoiofiles(self): 
            self._eldoiofiles = None

    @property
    def plotlist(self): 
        if not hasattr(self, '_plotlist'):
            self._plotlist = []
        return self._plotlist
    @plotlist.setter
    def plotlist(self,value): 
            self._plotlist = value
    @plotlist.deleter
    def plotlist(self): 
            self._plotlist = None

    @property
    def spicemisc(self): 
        if not hasattr(self, '_spicemisc'):
            self._spicemisc = []
        return self._spicemisc
    @spicemisc.setter
    def spicemisc(self,value): 
            self._spicemisc = value
    @spicemisc.deleter
    def spicemisc(self): 
            self._spicemisc = None
    @property
    def ahdlpath(self): 
        if not hasattr(self, '_ahdlpath'):
            self._ahdlpath = []
        return self._ahdlpath
    @ahdlpath.setter
    def ahdlpath(self,value): 
            self._ahdlpath = value
    @ahdlpath.deleter
    def ahdlpath(self): 
            self._ahdlpath = None

    @property
    def name(self):
        if not hasattr(self, '_name'):
            self._name=os.path.splitext(os.path.basename(self._classfile))[0]
        return self._name
    #No setter, no deleter.

    @property
    def entitypath(self):
        if not hasattr(self, '_entitypath'):
            self._entitypath= os.path.dirname(os.path.dirname(self._classfile))
        return self._entitypath
    #No setter, no deleter.

    @property
    def spicesrcpath(self):
        self._spicesrcpath  =  self.entitypath + '/spice'
        try:
            if not (os.path.exists(self._spicesrcpath)):
                os.makedirs(self._spicesrcpath)
                self.print_log(type='I',msg='Creating %s.' % self._spicesrcpath)
        except:
            self.print_log(type='E',msg='Failed to create %s.' % self._spicesrcpath)
        return self._spicesrcpath
    #No setter, no deleter.

    @property
    def spicesrc(self):
        if not hasattr(self, '_spicesrc'):
            self._spicesrc=self.spicesrcpath + '/' + self.name + self.syntaxdict["cmdfile_ext"]

            if not os.path.exists(self._spicesrc):
                self.print_log(type='W',msg='No source circuit found in %s.' % self._spicesrc)
        return self._spicesrc

    @property
    def spicetbsrc(self):
        if not hasattr(self, '_spicetbsrc'):

            if self.interactive_spice:
                self._spicetbsrc=self.spicesrcpath + '/tb_' + self.name + self.syntaxdict["cmdfile_ext"]
            else:
                self._spicetbsrc=self.spicesimpath + '/tb_' + self.name + self.syntaxdict["cmdfile_ext"]
        return self._spicetbsrc

    @property
    def eldowdbsrc(self):
        if not hasattr(self, '_eldowdbsrc'):
            if self.interactive_spice:
                self._eldowdbsrc=self.spicesrcpath + '/tb_' + self.name + '.wdb'
            else:
                self._eldowdbsrc=self.spicesimpath + '/tb_' + self.name + '.wdb'
        return self._eldowdbsrc

    @property
    def eldochisrc(self):
        if not hasattr(self, '_eldochisrc'):
            if self.interactive_spice:
                self._eldochisrc=self.spicesrcpath + '/tb_' + self.name + '.chi'
            else:
                self._eldochisrc=self.spicesimpath + '/tb_' + self.name + '.chi'
        return self._eldochisrc

    @property
    def spicesubcktsrc(self):
        if not hasattr(self, '_spicesubcktsrc'):
            if self.interactive_spice:
                self._spicesubcktsrc=self.spicesrcpath + '/subckt_' + self.name + self.syntaxdict["cmdfile_ext"]
            else:
                self._spicesubcktsrc=self.spicesimpath + '/subckt_' + self.name + self.syntaxdict["cmdfile_ext"]
        return self._spicesubcktsrc

    @property
    def spicesimpath(self):
        #self._eldosimpath  = self.entitypath+'/Simulations/eldosim'
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
        if (not self.interactive_spice) and (not self.preserve_spicefiles):
            # Removing generated files
            filelist = [
                #self.eldochisrc,
                #self.eldowdbsrc,
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
            if not self.preserve_iofiles:
                # I need to save this here to prevent the directory from being re-created
                simpathname = self._spicesimpath
                try:
                    # This fails now because of .nfs files
                    shutil.rmtree(simpathname)
                    self.print_log(type='I',msg='Removing %s.' % simpathname)
                except:
                    self.print_log(type='W',msg='Could not remove %s.' % simpathname)
        else:
            # Using the private variable here to prevent the re-creation of the dir?
            self.print_log(type='I',msg='Preserving spice files in %s.' % self._spicesrcpath)


    @property
    def spicecmd(self):
        if self.interactive_spice:
            if self.model=='eldo':
                plottingprogram = "-ezwave"
            elif self.model=='spectre':
                #plottingprogram = "-ezwave"
                plottingprogram = ''
            submission=""
        else:
            plottingprogram = ""
            submission=self.spice_submission

        if self.nproc:
            nprocflag = "%s%d" % (self.syntaxdict["nprocflag"],self.nproc)
        else:
            nprocflag = ""

        if self.tb.postlayout:
            plflag = '+postlayout=upa'
        else:
            plflag = ''

        if self.model=='eldo':
            spicesimcmd = "eldo -64b %s %s " % (plottingprogram,nprocflag)
        elif self.model=='spectre':
            #spicesimcmd = "\"sleep 10; spectre %s %s \"" % (plottingprogram,nprocflag)
            #spicesimcmd = "spectre %s %s " % (plottingprogram,nprocflag)
            spicesimcmd = "spectre -64 ++aps=%s %s %s %s " % (self.errpreset,plflag,plottingprogram,nprocflag)
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
    @spicecmd.deleter
    def spicecmd(self):
        self._spicecmd=None

    def connect_inputs(self):
        for ioname,io in self.IOS.Members.items():
            if ioname in self.iofile_bundle.Members:
                val=self.iofile_bundle.Members[ioname]
                # File type inputs are driven by the file.Data, not the input field
                if not isinstance(self.IOS.Members[val.name].Data,spice_iofile) \
                        and val.dir is 'in':
                    # Data must be properly shaped
                    self.iofile_bundle.Members[ioname].Data=self.IOS.Members[ioname].Data

    def connect_outputs(self):
        for name,val in self.iofile_bundle.Members.items():
            if val.dir is 'out':
                self.IOS.Members[name].Data=self.iofile_bundle.Members[name].Data

    # This writes infiles
    def write_infile(self):
        for name, val in self.iofile_bundle.Members.items():
            if val.dir.lower()=='in' or val.dir.lower()=='input':
                self.iofile_bundle.Members[name].write()

    # Reading output files
    def read_outfile(self):
        for name, val in self.iofile_bundle.Members.items():
            if val.dir.lower()=='out' or val.dir.lower()=='output':
                 self.iofile_bundle.Members[name].read()
    
    def execute_spice_sim(self):
        # Call spice here
        self.print_log(type='I', msg="Running external command %s\n" %(self.spicecmd) )
    
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

    def extract_powers(self):
        self.powers = {}
        self.currents = {}
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
                            self.currents[sourcename] = extval
                        elif powermatch.search(line):
                            words = line.split()
                            sourcename = words[1].replace('POWER_','')
                            extval = float(words[3])
                            self.powers[sourcename] = extval
            elif self.model == 'spectre':
                for name, val in self.tb.dcsources.Members.items():
                    # Read transient power consumption of the extracted source
                    if val.extract and val.sourcetype.lower() == 'v':
                        arr = genfromtxt(val._extfile,delimiter=', ',skip_header=self.syntaxdict["csvskip"])
                        if val.ext_start is not None:
                            arr = arr[np.where(arr[:,0] >= val.ext_start)[0],1]
                        if val.ext_stop is not None:
                            arr = arr[np.where(arr[:,0] <= val.ext_stop)[0],1]
                        meancurr = np.mean(np.abs(arr))
                        meanpwr = meancurr*val.value
                        sourcename = '%s%s' % (val.sourcetype.upper(),val.name.upper())
                        self.currents[sourcename] = meancurr
                        self.powers[sourcename] = meanpwr
            self.print_log(type='I',msg='Extracted power consumption from transient:')
            # This is newer Python syntax
            maxlen = len(max([*self.powers,'total'],key=len))
            for name,val in self.currents.items():
                self.print_log(type='I',msg='%s%s current = %.06f mA'%(name,' '*(maxlen-len(name)),1e3*val))
            if len(self.currents.items()) > 0:
                self.print_log(type='I',msg='Total%s current = %.06f mA'%(' '*(maxlen-5),1e3*sum(self.currents.values())))
            for name,val in self.powers.items():
                self.print_log(type='I',msg='%s%s power   = %.06f mW'%(name,' '*(maxlen-len(name)),1e3*val))
            if len(self.powers.items()) > 0:
                self.print_log(type='I',msg='Total%s power   = %.06f mW'%(' '*(maxlen-5),1e3*sum(self.powers.values())))
        except:
            self.print_log(type='W',msg=traceback.format_exc())
            self.print_log(type='W',msg='Something went wrong while extracting power consumptions.')

    def run_spice(self):
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
            self.extract_powers()
            self.read_outfile()
            self.connect_outputs()

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
            except:
                self.print_log(type='I',msg=traceback.format_exc())
                self.print_log(type='F',msg='Failed while loading results from %s.' % self._spicesimpath)

