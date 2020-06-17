"""
========================
Spice Simulation Command
========================

Class for spice simulation commands.

Initially written for eldo-module by Okko Järvinen, okko.jarvinen@aalto.fi, 9.1.2020

Last modification by Okko Järvinen, 29.05.2020 19:06

"""

import os
import sys
from abc import * 
from thesdk import *
from thesdk.iofile import iofile
import numpy as np
import pandas as pd
import pdb

class spice_simcmd(thesdk):
    """
    Class to provide DC source definitions to ELDO testbench.
    When instantiated in the parent class, this class automatically
    attaches eldo_simcmd objects to simcmd_bundle -bundle in testbench.

    Example
    -------
    Initiated in parent as: 
        _=eldo_simcmd(self,type='tran',tprint=1e-12,tstop='10n',uic=True,noise=True,fmin=1,fmax=5e9,seed=0)

    For a simple transient:
        _=eldo_simcmd(self,type='tran')
    
    Parameters
    -----------
    parent : object 
        The parent object initializing the 
        eldo_simcmd instance. Default None
    
    **kwargs :  
            sim : str  
                Simulation type. Currently only 'tran' supported.
            tprint : float/str  
                Print interval. Default '1p' or 1e-12.
            tstop : float/str  
                Transient simulation duration. When not defined, the simulation time
                is the duration of the longest input signal.
            uic : bool
                Use initial conditions flag. Default False.
            noise : bool
                Noise transient flag. Default False.
            fmin : float/str
                Minimum noise frequency. Default 1 (Hz).
            fmax : float/str
                Maximum noise frequency. Default 5e9.
            seed : int
                Random generator seed for noise transient. Default None (random).
    """

    @property
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    def __init__(self,parent,**kwargs):
        try:  
            self.parent = parent
            self._sim=kwargs.get('sim','tran')
            self._tprint=kwargs.get('tprint','1p')
            self._tstop=kwargs.get('tstop',None)
            self._uic=kwargs.get('uic',False)
            self._noise=kwargs.get('noise',False)
            self._fmin=kwargs.get('fmin',1)
            self._fmax=kwargs.get('fmax',5e9)
            self._seed=kwargs.get('seed',None)

        except:
            self.print_log(type='F', msg="Eldo simulation command definition failed.")

        if hasattr(self.parent,'simcmd_bundle'):
            # This limits it to 1 of each simulation type. Is this ok?
            self.parent.simcmd_bundle.new(name=self.sim,val=self)

    @property
    def sim(self):
        if hasattr(self,'_sim'):
            return self._sim
        else:
            self._sim='tran'
        return self._sim
    @sim.setter
    def sim(self,value):
        self._sim=value

    @property
    def tprint(self):
        if hasattr(self,'_tprint'):
            return self._tprint
        else:
            self._tprint='1p'
        return self._tprint
    @tprint.setter
    def tprint(self,value):
        self._tprint=value

    @property
    def tstop(self):
        if hasattr(self,'_tstop'):
            return self._tstop
        else:
            self._tstop=None
        return self._tstop
    @tstop.setter
    def tstop(self,value):
        self._tstop=value

    @property
    def uic(self):
        if hasattr(self,'_uic'):
            return self._uic
        else:
            self._uic=False
        return self._uic
    @uic.setter
    def uic(self,value):
        self._uic=value

    @property
    def noise(self):
        if hasattr(self,'_noise'):
            return self._noise
        else:
            self._noise=False
        return self._noise
    @noise.setter
    def noise(self,value):
        self._noise=value

    @property
    def fmin(self):
        if hasattr(self,'_fmin'):
            return self._fmin
        else:
            self._fmin=1
        return self._fmin
    @fmin.setter
    def fmin(self,value):
        self._fmin=value

    @property
    def fmax(self):
        if hasattr(self,'_fmax'):
            return self._fmax
        else:
            self._fmax=5e9
        return self._fmax
    @fmax.setter
    def fmax(self,value):
        self._fmax=value

    @property
    def seed(self):
        if hasattr(self,'_seed'):
            return self._seed
        else:
            self._seed=None
        return self._seed
    @seed.setter
    def seed(self,value):
        self._seed=value

