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
import numpy as np

class eldo(thesdk,metaclass=abc.ABCMeta):
    """This class is used as instance in simulatormodule property of 
    spice class.
    
    """

    @property
    def eldo_spicecmd(self):
        """String

        Simulation command string to be executed on the command line.
        Automatically generated.
        """
        if not hasattr(self,'_eldo_spicecmd'):
            if self.nproc:
                nprocflag = "%s%d" % (self.langmodule.nprocflag,self.nproc)
                self.print_log(type='I',msg='Enabling multithreading \'%s\'.' % nprocflag)
            else:
                nprocflag = ""

            if self.tb.postlayout:
                self.print_log(type='W',msg='Post-layout optimization not suported for Ngspice')

            spicesimcmd = "%s %s " % (self.langmodule.simulatorcmd, nprocflag)
            self._eldo_spicecmd = self.spice_submission+spicesimcmd+self.spicetbsrc

        return self._eldo_spicecmd
