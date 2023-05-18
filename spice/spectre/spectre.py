"""
=======
Spectre
=======
Spectre simulation interface package for Spectre for TheSyDeKick.

Initially written by Okko Järvinen, 2019
"""
import os
import sys
from abc import * 
from thesdk import *
from spice.spice_common import *
import numpy as np

class spectre(spice_common):
    """This class is used as instance in spice_simulatormodule property of 
    spice class. Contains simulator dependent definitions.

    Parameters
    ----------
    parent: object, None (mandatory to define). TheSyDeKick parent entity object for this simulator class.

    **kwargs :
       None

    
    """

    def __init__(self, parent=None,**kwargs):

            if parent==None:
                self.print_log(type='F', msg="Parent of simulator module not given")
            else:
                self.parent=parent

    @property
    def syntaxdict(self):
        self.print_log(type='O', msg='Syntaxdict is obsoleted. Access properties directly')
        self._syntaxdict = {
                "cmdfile_ext" : self.cmdfile_ext,
                "resultfile_ext" : self.resultfile_ext,
                "commentchar" : self.commentchar,
                "commentline" : self.commentline,
                "nprocflag" : self.nprocflag,
                "simulatorcmd" : self.simulatorcmd, 
                "dcsource_declaration" : self.dcsource_declaration,
                "parameter" : self.parameter,
                "option" : self.option,
                "include" : self.include,
                "dspfinclude" : self.dspfinclude,
                "subckt" : self.subckt,
                "lastline" : self.lastline,
                "eventoutdelim" : self.eventoutdelim, # Two spaces
                "csvskip" : self.csvskip
                }
        return self._syntaxdict
    @syntaxdict.setter
    def syntaxdict(self,value):
        self._syntaxdict=value

    @property
    def cmdfile_ext(self):
        """Extension of the command file : str
        """
        return '.scs'
    @property
    def resultfile_ext(self):
        """Extension of the result file : str
        """
        return '.raw'
    @property
    def commentchar(self):
        """Comment character of the simulator : str
        """
        return '//'
    @property
    def commentline(self):
        """Comment line for the simulator : str
        """
        return '///////////////////////\n'
    @property
    def nprocflag(self):
        """String for defining multithread execution : str
        """
        return '+mt='
    @property
    def simulatorcmd(self):
        """Simulator execution command : str
        """
        return 'spectre -64 +lqtimeout=0 ++aps=%s' %(self.errpreset)
    @property
    def dcsource_declaration(self):
        """DC source declaration : str
        """
        #self.print_log(type='F', msg='DC source declaration not defined for ngspice')
        return 'vsource type=dc dc='
    @property
    def parameter(self):
        """Netlist parameter definition string : str
        """
        return 'parameters'
    @property
    def option(self):
        """Netlist option definition string : str
        """
        return 'options'
    @property
    def include(self):
        """Netlist include string : str
        """
        return 'include'
    @property
    def dspfinclude(self):
        """Netlist dspf-file include string : str
        """
        return 'dspf_include'
    @property
    def subckt(self):
        """Subcircuit include string : str
        """
        return 'subckt'
    @property
    def lastline(self):
        """Last line of the simulator command file : str
        """
        return '///'
    @property
    def eventoutdelim(self):
        """Delimiter for the events : str
        """
        return ','
    @property
    def csvskip(self):
        """Needs documentation. Lines skipped in result file : int
        """
        return 0

    @property
    def plflag(self):
        '''
        Postlayout simulation accuracy/RC reduction flag.
        See: https://community.cadence.com/cadence_blogs_8/b/cic/posts/spectre-optimizing-spectre-aps-performance 
        '''
        if not hasattr(self, '_plflag'):
            self._plflag="+postlayout=upa"
        return self._plflag

    @plflag.setter
    def plflag(self, val):
        if val in ["upa", "hpa"]:
            self._plflag="+postlayout=%s" %(val)
        else:
            self.print_log(type='W', msg='Unsupported postlayout flag: %s' % val)

    @property
    def errpreset(self):
        """ String
        
        Global accuracy parameter for Spectre simulations. Options include
        'liberal', 'moderate' and 'conservative', in order of rising accuracy.
        You can set this by accesssing spice langmodule

        Example
        -------
        self.spice_langmodule.errpreset='conservative'

        """
        if not hasattr(self,'_errpreset'):
            self._errpreset='moderate'
        return self._errpreset
    @errpreset.setter
    def errpreset(self,value):
        self._errpreset=value

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
        if value not in  [ 'ezwave', 'viva' ]:  
            self.print_log(type='F', 
                    msg='%s not supported for plotprogram, only ezvave and viva are supported')
        else:
            self._plotprogram = value

    @property
    def plotprogcmd(self):
        """ str : Command to be run for interactive simulations.
        """
        if not hasattr(self, '_plotprogcmd'):
            if self.plotprogram == 'ezwave':
                self._plotprogcmd='%s -MAXWND -LOGfile %s/ezwave.log %s &' % \
                        (self.plotprogram,self.parent.spicesimpath,self.parent.spicedbpath)
            elif self.plotprogram == 'viva':
                self._plotprogcmd='%s -datadir %s -nocdsinit &' % \
                        (self.plotprogram,self.parent.spicedbpath)
            else:
                self.print_log(type='F',msg='Unsupported plot program \'%s\'.' % self.plotprogram)
        return self._plotprogcmd
    @plotprogcmd.setter
    def plotprogcmd(self, value):
        self._plotprogcmd=value


    @property
    def spicecmd(self):
        """String

        Simulation command string to be executed on the command line.
        Automatically generated.
        """
        if not hasattr(self,'_spicecmd'):
            if self.parent.nproc:
                nprocflag = "%s%d" % (self.nprocflag,self.parent.nproc)
                self.print_log(type='I',msg='Enabling multithreading \'%s\'.' % nprocflag)
            else:
                nprocflag = ""

            if self.parent.postlayout:
                plflag=self.plflag
                self.print_log(type='I',msg='Enabling post-layout optimization \'%s\'.' % plflag)
            else:
                plflag = ''

            spicesimcmd = (self.simulatorcmd + " %s %s -outdir %s " 
                    % (plflag,nprocflag,self.parent.spicesimpath))
            self._spicecmd = self.parent.spice_submission+spicesimcmd+self.parent.spicetbsrc

        return self._spicecmd

    def run_plotprogram(self):
        ''' Starting a parallel process for waveform viewer program.

        The plotting program command can be set with 'plotprogram' property.
        '''
        tries = 0
        while tries < 100:
            if os.path.exists(self.parent.spicedbpath):
                # More than just the logfile exists
                if len(os.listdir(self.parent.spicedbpath)) > 1:
                    # Database file has something written to it
                    filesize = []
                    for f in os.listdir(self.parent.spicedbpath):
                        filesize.append(os.stat('%s/%s' % (self.parent.spicedbpath,f)).st_size)
                    if all(filesize) > 0:
                        break
            else:
                time.sleep(2)
                tries += 1
        cmd=self.plotprogcmd
        self.print_log(type='I', msg='Running external command: %s' % cmd)
        try:
            ret=os.system(cmd)
            if ret != 0:
                self.print_log(type='W', msg='%s returned with exit status %d.' % (self.plotprogram, ret))
        except: 
            self.print_log(type='W',msg='Something went wrong while launcing %s.' % self.plotprogram)
            self.print_log(type='W',msg=traceback.format_exc())

    def read_oppts(self):
        """ Internally called function to read the DC operating points of the circuit
            TODO: Implement for Eldo as well.
        """

        try:
            if 'dc' in self.parent.simcmd_bundle.Members.keys():
                self.extracts.Members.update({'oppts' : {}})
                # Get dc simulation file name
                for name, val in self.parent.simcmd_bundle.Members.items():
                    mc = val.mc
                    if name == 'dc':
                        fname=''
                        if len(val.sweep) != 0:
                            for i in range(0, len(val.sweep)):
                                fname += 'Sweep%d-[0-9]*_' % i
                            if mc:
                                fname+='mc_oppoint.dc'
                            else:
                                fname+='oppoint.dc'
                        else:
                            if mc:
                                fname = 'mc_oppoint*.dc'
                            else:
                                fname = 'oppoint*.dc'
                        break
                # For distributed runs
                if self.parent.distributed_run:
                    path=os.path.join(self.parent.spicesimpath,'tb_%s.raw' % self.parent.name, '[0-9]*', fname)
                    files = sorted(glob.glob(path),key=self.sorter)
                else:
                    path=os.path.join(self.parent.spicesimpath,'tb_%s.raw' % self.parent.name, fname)
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
        except:
            self.print_log(type='W', msg=traceback.format_exc())
            self.print_log(type='W',msg='Something went wrong while extracting DC operating points.')

