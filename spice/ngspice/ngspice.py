"""
=======
Ngspice
=======

Simulator specific definitions for Ngspice

Initially written by Marko Kosunen, 2021
"""
import os
import sys
from abc import * 
from thesdk import *
import numpy as np

class ngspice(thesdk,metaclass=abc.ABCMeta):
    """This class is used as instance in simulatormodule property of 
    spice class. Contains language dependent definitions.

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
        """ Dictionary
        
        Internally used dictionary for syntax conversions
        """
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
        """str : Extension of the command file
        """
        return '.ngcir'
    @property
    def resultfile_ext(self):
        """str : Extension of the result file
        """
        return ''
    @property
    def commentchar(self):
        """str : Comment character of the simulator
        """
        return '*'
    @property
    def commentline(self):
        """str : Comment line for the simulator
        """
        return '***********************\n'
    @property
    def nprocflag(self):
        """str : String for defining multithread execution
        """
        return 'set num_threads='
    @property
    def simulatorcmd(self):
        """str : Simulator execution command 
            (Default: 'ngspice')
        """
        return 'ngspice'
    @property
    def dcsource_declaration(self):
        """str : DC source declaration
        """
        #self.print_log(type='F', msg='DC source declaration not defined for ngspice')
        return ''
    @property
    def parameter(self):
        """str : Netlist parameter definition string
        """
        return '.param'
    @property
    def option(self):
        """str : Netlist option definition string
        """
        return '.option'
    @property
    def include(self):
        """str : Netlist include string
        """
        return '.include'
    @property
    def dspfinclude(self):
        """str : Netlist dspf-file include string
        """
        return '.include'
    @property
    def subckt(self):
        """str : Subcircuit include string
        """
        return '.subckt'
    @property
    def lastline(self):
        """str : Last line of the simulator command file
        """
        return '.end'
    @property
    def eventoutdelim(self):
        """str : Delimiter for the events
        """
        return '  ' #Two spaces
    @property
    def csvskip(self):
        """Needs documentation. Lines skipped in result file : int
        """
        return 1

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
        """str : Simulation command string to be executed on the command line.
        Automatically generated.
        """
        if not hasattr(self,'_ngspice_spicecmd'):
            
            if self.parent.nproc:
                nprocflag = "%s%d" % (self.nprocflag,self.parent.nproc)
                self.print_log(type='I',msg='Multithreading \'%s\'.' % nprocflag)
                self.print_log(type='I',msg='Multithreading for Ngspice handled in testbench.')
            else:
                nprocflag = ""

            # How is this defined and where. Comes out of the blue
            if self.parent.postlayout:
                self.print_log(type='W',msg='Post-layout optimization not suported for Ngspice')

            if self.parent.interactive_spice:
                self._ngspice_spicecmd = self.spice_submission+self.langmodule.simulatorcmd+' '+self.spicetbsrc
            else:
                self._ngspice_spicecmd = self.parent.spice_submission + self.simulatorcmd + ' -b '+self.parent.spicetbsrc
        return self._ngspice_spicecmd

    def run_plotprogram(self):
        ''' Starting a parallel process for waveform viewer program.

        The plotting program command can be set with 'plotprogram'.
        Tested for spectre and eldo.
        '''
        self.print_log(type='W',msg='Interactive plotting not implemented for ngspice.')
        return 0


