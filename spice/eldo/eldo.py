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
        """ dict : Internally used dictionary for syntax conversions
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
        return '.cir'
    @property
    def resultfile_ext(self):
        """str : Extension of the result file
        """
        return '.wdb'
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
        return '-use_proc '
    @property
    def simulatorcmd(self):
        """str : Simulator execution command
            (Default: 'ngspice')
        """
        return 'eldo -64b'
    @property
    def dcsource_declaration(self):
        """str : DC source declaration
        """
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
        return ' '
    @property
    def csvskip(self):
        """Needs documentation. Lines skipped in result file : int
        """
        return 2

    @property
    def plflag_simcmd_prefix(self):
        """
        Simulator specific prefix for enabling postlayout optimization
        Postfix comes from self.plflag (user defined)
        """
        if not hasattr(self, '_plflag_simcmd_prefix'):
            self.print_log(type='I', msg='Postlayout prefix unsupported for %s' %(self.parent.model))
            self._plflag_simcmd_prefix=""
        return self._plflag_simcmd_prefix

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
    def plotprogram(self):
        """ str : Sets the program to be used for visualizing waveform databases.

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
        """str : Simulation command string to be executed on the command line.
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
            if os.path.exists(self.parent.spicedbpath):
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

    def read_sp_result(self,**kwargs):
        """ Internally called function to read the S-parameter simulation results
        """
        read_type=kwargs.get('read_type')
        if 'sp' in self.parent.simcmd_bundle.Members.keys():
            self.print_log(type='W', msg='S-Parameters unsupported for %s' %(self.parent.model))

    def read_noise_result(self,**kwargs):
        """ Internally called function to read the noise simulation results
        """
        if 'noise' in self.parent.simcmd_bundle.Members.keys():
            self.print_log(type='F', msg='Noise analysis unsupported for %s' %(self.parent.model))
        return None, None

    def create_nested_sweepresult_dict(self, level, fileptr, sweeps_ran_dict,
            files,read_type):
        """Documentation missing
        """
        self.print_log(type='F', msg='create_nested_sweepresulsts unsupported for %s' %(self.parent.model))
        return None, None

    def read_oppts(self):
        """ Internally called function to read the DC operating points of the circuit
        """

        try:
            if 'dc' in self.parent.simcmd_bundle.Members.keys():
                self.print_log(type='F', msg='DC analysis unsupported for %s' %(self.parent.model))
                raise Exception('DC optpoint extraction not supported for Eldo.')
            else: # DC analysis not in simcmds, oppts is empty
                self.extracts.Members.update({'oppts' : {}})
        except:
            self.print_log(type='W', msg=traceback.format_exc())
            self.print_log(type='W',msg='Something went wrong while extracting DC operating points.')

