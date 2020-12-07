"""
========================
Spice Simulation Command
========================

Class for spice simulation commands.

Initially written by Okko Järvinen, okko.jarvinen@aalto.fi, 9.1.2020

Last modification by Okko Järvinen, 03.12.2020 19:10

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
    Class to provide simulation command parameters to spice testbench.
    When instantiated in the parent class, this class automatically
    attaches spice_simcmd objects to simcmd_bundle -bundle in testbench.

    Examples
    --------
    Initiated in parent as:: 

        _=spice_simcmd(self,sim='tran',tprint=1e-12,tstop='10n',
                       uic=True,noise=True,fmin=1,fmax=5e9)

    For a simple transient with inferred simulation duration:

        _=spice_simcmd(self,sim='tran')
    
    Parameters
    -----------
    parent : object 
        The parent object initializing the spice_simcmd instance. Default None
    
    **kwargs :  
            sim: str
                Simulation type. Currently only 'tran' and 'dc' supported.
            plotlist: list(str)
                List of node names to be plotted. Node names follow simulator
                syntax.  For Eldo, the voltage/current specifier is expected::

                    self.plotlist = ['v(OUT)','v(CLK)']
                
                For Spectre, the node name is enough::

                    self.plotlist = ['OUT','CLK']
            sweep: str
                DC & Spectre models only. If given, sweeps the top-level
                parameter given as value. For example::
                
                    _spice_simcmd(sim='dc',sweep='temp',swpstart=27,swpstop=87)
                
                sweeps the top-level parameter temp (temperature) from 27 to 87
                at 10 degree increments.
            subcktname: str
                If given, sweeps the parameter defined by property sweep from
                the subcircuit given by this property.  For example::
                
                    _=spice_simcmd(sim='dc',sweep='Vb',subcktname='XSUBCKT',
                                   swpstart=0.1,swpstop=1.5,step=0.05)
                
                sweeps the Vb parameter from subcircuit XSUBCKT from 0.1 volts
                to 1.5 volts with 0.05 volt increments.
            devname: str
                If given, sweeps the parameter defined by property sweep from
                the device given by this property.  For example::
                
                    _=spice_simcmd(sim='dc', sweep='w', deviceswp='XSUBCKT.XNMOS',
                                   swpstart=10u, swpstop=14u, step=0.1u)
                
                sweeps the width of transistor XNMOS of subckt XSUBCKT from 10u
                to 14u in 0.1u increments.
            swpstart: union(int, float, str)
                Starting point of DC sweep. Default: 0.
            swpstop: union(int, float, str)
                Stop point of DC sweep. Default: 0.
            swpstep: union(int, float, str)
                Step size of the sweep simulation. Default: 10  
            tprint: float/str
                Print interval. Default '1p' or 1e-12.
            tstop: float/str
                Transient simulation duration. When not defined, the simulation
                time is the duration of the longest input signal.
            uic: bool
                Use initial conditions flag. Default False.
            noise: bool
                Noise transient flag. Default False.
            fmin: float/str
                Minimum noise frequency. Default 1 (Hz).
            fmax: float/str
                Maximum noise frequency. Default 5e9.
            seed: int
                Random generator seed for noise transient. Default None (random).
            method: str
                Transient integration method. Default None (spectre takes
                method from errpreset).
            cmin: float
                Spectre cmin parameter: this much cap from each node to ground.
                Might speed up simulation. Default None (not used).

    """

    @property
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    def __init__(self,parent,**kwargs):
        try:
            self.parent = parent
            self._sim=kwargs.get('sim','tran')
            self._plotlist=kwargs.get('plotlist', [])
            self._sweep=kwargs.get('sweep', '')
            self._subcktname=kwargs.get('subcktname', '')
            self._devname=kwargs.get('devname', '')
            self._swpstart=kwargs.get('swpstart', 0)
            self._swpstop=kwargs.get('swpstop', 0)
            self._swpstep=kwargs.get('swpstep', 10)
            self._tprint=kwargs.get('tprint','1p')
            self._tstop=kwargs.get('tstop',None)
            self._uic=kwargs.get('uic',False)
            self._noise=kwargs.get('noise',False)
            self._fmin=kwargs.get('fmin',1)
            self._fmax=kwargs.get('fmax',5e9)
            self._seed=kwargs.get('seed',None)
            self._method=kwargs.get('method',None)
            self._cmin=kwargs.get('cmin',None)
        except:
            self.print_log(type='F', msg="Simulation command definition failed.")
        if hasattr(self.parent,'simcmd_bundle'):
            # This limits it to 1 of each simulation type. Is this ok?
            self.parent.simcmd_bundle.new(name=self.sim,val=self)
        if self.subcktname != '' and self.devname != '':
            self.print_log(type='F', msg='Cannot specify subckt sweep and device sweep in the same simcmd instance!')

    @property
    def sim(self):
        """Set by argument 'sim'."""
        if hasattr(self,'_sim'):
            return self._sim
        else:
            self._sim='tran'
        return self._sim
    @sim.setter
    def sim(self,value):
        self._sim=value

    @property
    def plotlist(self):
        """Set by argument 'plotlist'."""
        if hasattr(self,'_plotlist'):
            return self._plotlist
        else:
            self._plotlist=[]
        return self._plotlist
    @plotlist.setter
    def plotlist(self,value):
        self._plotlist=value

    @property
    def sweep(self):
        """Set by argument 'sweep'."""
        if hasattr(self,'_sweep'):
            return self._sweep
        else:
            self._sweep=''
        return self._sweep
    @sweep.setter
    def sweep(self,value):
        self._sweep=value

    @property
    def subcktname(self):
        """Set by argument 'subcktname'."""
        if hasattr(self,'_subcktname'):
            return self._subcktname
        else:
            self._subcktname=''
        return self._subcktname
    @subcktname.setter
    def subcktname(self,value):
        self._subcktname=value

    @property
    def devname(self):
        """Set by argument 'devname'."""
        if hasattr(self,'_devname'):
            return self._devname
        else:
            self._devname=''
        return self._devname
    @devname.setter
    def devname(self,value):
        self._devname=value

    @property
    def swpstart(self):
        """Set by argument 'swpstart'."""
        if hasattr(self,'_swpstart'):
            return self._swpstart
        else:
            self._swpstart=0
        return self._swpstart
    @swpstart.setter
    def swpstart(self,value):
        self._swpstart=value

    @property
    def swpstop(self):
        """Set by argument 'swpstop'."""
        if hasattr(self,'_swpstop'):
            return self._swpstop
        else:
            self._swpstop=0
        return self._swpstop
    @swpstop.setter
    def swpstop(self,value):
        self._swpstop=value

    @property
    def swpstep(self):
        """Set by argument 'swpstep'."""
        if hasattr(self,'_swpstep'):
            return self._swpstep
        else:
            self._swpstep=10
        return self._swpstep
    @swpstep.setter
    def swpstep(self,value):
        self._swpstep=value

    @property
    def tprint(self):
        """Set by argument 'tprint'."""
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
        """Set by argument 'tstop'."""
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
        """Set by argument 'uic'."""
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
        """Set by argument 'noise'."""
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
        """Set by argument 'fmin'."""
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
        """Set by argument 'fmax'."""
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
        """Set by argument 'seed'."""
        if hasattr(self,'_seed'):
            return self._seed
        else:
            self._seed=None
        return self._seed
    @seed.setter
    def seed(self,value):
        self._seed=value

    @property
    def method(self):
        """Set by argument 'method'."""
        if hasattr(self,'_method'):
            return self._method
        else:
            self._method=None
        return self._method
    @method.setter
    def method(self,value):
        self._method=value

    @property
    def cmin(self):
        """Set by argument 'cmin'."""
        if hasattr(self,'_cmin'):
            return self._cmin
        else:
            self._cmin=None
        return self._cmin
    @cmin.setter
    def cmin(self,value):
        self._cmin=value
