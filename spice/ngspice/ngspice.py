"""
=======
Ngspice
=======

Mixin class for Ngspice for TheSyDeKick.

Initially written by Okko Järvinen, 2019
"""
import os
import sys
from abc import * 
from thesdk import *
import numpy as np

class ngspice(thesdk,metaclass=abc.ABCMeta):
    @property
    def ngspice_spicecmd(self):
        """String

        Simulation command string to be executed on the command line.
        Automatically generated.
        """
        if not hasattr(self,'_ngspice_spicecmd'):
            
            if self.nproc:
                nprocflag = "%s%d" % (self.langmodule.nprocflag,self.nproc)
                self.print_log(type='I',msg='Multithreading \'%s\'.' % nprocflag)
                self.print_log(type='I',msg='Multithreading for Ngspice handled in testbench.')
            else:
                nprocflag = ""

            # How is this defined and where. Comes out of the blue
            if self.tb.postlayout:
                self.print_log(type='W',msg='Post-layout optimization not suported for Ngspice')

            self._ngspice_spicecmd = self.spice_submission+self.langmodule.simulatorcmd+' '+self.spicetbsrc
        return self._ngspice_spicecmd
