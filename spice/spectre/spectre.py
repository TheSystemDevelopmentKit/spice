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
import numpy as np

class spectre(thesdk,metaclass=abc.ABCMeta):
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
            self._plflag="upa"
        return self._plflag

    @plflag.setter
    def plflag(self, val):
        if val in ["upa", "hpa"]:
            self._plflag=val
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
        if hasattr(self,'_errpreset'):
            return self._errpreset
        else:
            self._errpreset='moderate'
        return self._errpreset
    @errpreset.setter
    def errpreset(self,value):
        self._errpreset=value

    @property
    def spectre_spicecmd(self):
        """String

        Simulation command string to be executed on the command line.
        Automatically generated.
        """
        if not hasattr(self,'_spectre_spicecmd'):
            if self.parent.nproc:
                nprocflag = "%s%d" % (self.nprocflag,self.parent.nproc)
                self.print_log(type='I',msg='Enabling multithreading \'%s\'.' % nprocflag)
            else:
                nprocflag = ""

            if self.parent.tb.postlayout:
                plflag=self.plflag
                self.print_log(type='I',msg='Enabling post-layout optimization \'%s\'.' % plflag)
            else:
                plflag = ''

            spicesimcmd = (self.simulatorcmd + " ++aps=%s %s %s -outdir %s " 
                    % (self.errpreset,plflag,nprocflag,self.parent.spicesimpath))
            self._spectre_spicecmd = self.parent.spice_submission+spicesimcmd+self.parent.spicetbsrc

        return self._spectre_spicecmd

    def run_plotprogram(self):
        ''' Starting a parallel process for waveform viewer program.

        The plotting program command can be set with 'plotprogram' property.
        '''
        tries = 0
        while tries < 100:
            if os.path.exists(self.parent.spicedbpath):
                # More than just the logfile exists
                if len(os.listdir(self.parent.picedbpath)) > 1:
                    # Database file has something written to it
                    filesize = []
                    for f in os.listdir(self.parent.spicedbpath):
                        filesize.append(os.stat('%s/%s' % (self.parent.spicedbpath,f)).st_size)
                    if all(filesize) > 0:
                        break
            else:
                time.sleep(2)
                tries += 1
        cmd=self.parent.plotprogcmd
        self.print_log(type='I', msg='Running external command: %s' % cmd)
        try:
            ret=os.system(cmd)
            if ret != 0:
                self.print_log(type='W', msg='%s returned with exit status %d.' % (self.parent.plotprogram, ret))
        except: 
            self.print_log(type='W',msg='Something went wrong while launcing %s.' % self.parent.plotprogram)
            self.print_log(type='W',msg=traceback.format_exc())

