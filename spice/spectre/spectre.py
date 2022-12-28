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

    @property
    def spectre_spicecmd(self):
        """String

        Simulation command string to be executed on the command line.
        Automatically generated.
        """
        if not hasattr(self,'_spectre_spicecmd'):
            if self.nproc:
                nprocflag = "%s%d" % (self.langmodule.nprocflag,self.nproc)
                self.print_log(type='I',msg='Enabling multithreading \'%s\'.' % nprocflag)
            else:
                nprocflag = ""

            if self.tb.postlayout:
                plflag=self.langmodule.postlayout_flag
                self.print_log(type='I',msg='Enabling post-layout optimization \'%s\'.' % plflag)
            else:
                plflag = ''

            spicesimcmd = (self.langmodule.simulatorcmd + " ++aps=%s %s %s -outdir %s " 
                    % (self.errpreset,plflag,nprocflag,self.spicesimpath))
            self._spectre_spicecmd = self.spice_submission+spicesimcmd+self.spicetbsrc

        return self._spectre_spicecmd

