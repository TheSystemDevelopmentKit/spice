"""
====
Eldo
====
Eldo simulation interface package for TheSyDeKick.

Initially written by Okko Järvinen, 2019
"""
import os
import sys
from abc import * 
from thesdk import *
from spice.spice_common import *
import numpy as np

class eldo(spice_common):
    """This class is used as instance in *spice_simulatormodule* property of 
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
        return '.cir'
    @property
    def resultfile_ext(self):
        """Extension of the result file : str
        """
        return '.wdb'
    @property
    def commentchar(self):
        """Comment character of the simulator : str
        """
        return '*'
    @property
    def commentline(self):
        """Comment line for the simulator : str
        """
        return '***********************\n'
    @property
    def nprocflag(self):
        """String for defining multithread execution : str
        """
        return '-use_proc '
    @property
    def simulatorcmd(self):
        """Simulator execution command : str
        """
        return 'eldo -64b'
    @property
    def dcsource_declaration(self):
        """DC source declaration : str
        """
        return ''
    @property
    def parameter(self):
        """Netlist parameter definition string : str
        """
        return '.param'
    @property
    def option(self):
        """Netlist option definition string : str
        """
        return '.option'
    @property
    def include(self):
        """Netlist include string : str
        """
        return '.include'
    @property
    def dspfinclude(self):
        """Netlist dspf-file include string : str
        """
        return '.include'
    @property
    def subckt(self):
        """Subcircuit include string : str
        """
        return '.subckt'
    @property
    def lastline(self):
        """Last line of the simulator command file : str
        """
        return '.end'
    @property
    def eventoutdelim(self):
        """Delimiter for the events : str
        """
        return ' '
    @property
    def csvskip(self):
        """Needs documentation. Lines skipped in result file : int
        """
        return 2

    @property
    def plflag(self):
        '''
        Postlayout simulation accuracy/RC reduction flag.
        
        '''
        self.print_log(type='W', msg='Postlayout flag unsupported for %s' %(self.parent.model))
        if not hasattr(self, '_plflag'):
            self._plflag=''
        return self._plflag

    @plflag.setter
    def plflag(self, val):
        self.print_log(type='W', msg='Postlayout flag unsupported for Eldo')


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
                self.print_log(type='W',msg='Post-layout optimization not suported for Eldo')

            spicesimcmd = "%s %s " % (self.simulatorcmd, nprocflag)
            self._spicecmd = self.parent.spice_submission+spicesimcmd+self.parent.spicetbsrc

        return self._spicecmd

    def run_plotprogram(self):
        ''' Starting a parallel process for waveform viewer program.

        The plotting program command can be set with 'plotprogram'.
        Tested for spectre and eldo.
        '''
        # Wait for database to appear.
        tries = 0
        while tries < 100:
            if os.path.exists(self.spicedbpath):
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
                raise Exception('DC optpoint extraction not supported for Eldo.')
            else: # DC analysis not in simcmds, oppts is empty
                self.extracts.Members.update({'oppts' : {}})
        except:
            self.print_log(type='W', msg=traceback.format_exc())
            self.print_log(type='W',msg='Something went wrong while extracting DC operating points.')

