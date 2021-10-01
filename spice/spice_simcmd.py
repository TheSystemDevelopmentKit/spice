"""
========================
Spice Simulation Command
========================

Class for spice simulation commands.

Initially written by Okko Järvinen, 9.1.2020

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
    
    Attributes
    ----------
    parent : object 
        The parent object initializing the spice_simcmd instance. Default None.
    sim : 'tran' or 'dc'
        Simulation type.
    plotlist : list(str)
        List of node names or operating points to be plotted. Node names follow
        simulator syntax.  For Eldo, the voltage/current specifier is expected::

            self.plotlist = ['v(OUT)','v(CLK)']
        
        For Spectre, the node name is enough::

            self.plotlist = ['OUT','CLK']
        
        .. NOTE:: Below applies only for Spectre!

        When capturing operating point information with Spectre, adding the
        instance name to plotlist saves all operating points for the device,
        e.g::
            
            self.plotlist = [XTB_NAME.XSUBCKT/M0]
        
        saves all operating points defined by the model for the device M0 in
        subckt XSUBCKT.
        
        Wildcards are supported, but should be used with caution as the output
        file can quickly become excessively large. For example to capture the
        gm of all transistor use::

            self.plotlist = [*:gm]

        It is highly recommended to exclude the devices that are not needed
        from the output to reduce file size. Examples of such devices are
        RC-parasitics (include option savefilter='rc' in self.spiceoptions to
        exclude them) and dummy transistors. See excludelist below. 
    excludelist : list(str)
        Applies for Spectre only! List of device names NOT to be included in
        the output report. Wildcards are supported. Exclude list is especially
        useful for DC simulations when specifiying outputs with wildcards. 

        For example, when capturing gm for all transistors, use exclude list to
        exclude all dummy transistors with::
            
            self.excludelist = [XTB_NAME*DUMMY_ID*],

        where DUMMY_ID is extraction tool / runset specific dummy identifier.
    sweep : str
        DC & Spectre models only. If given, sweeps the top-level parameter
        given as value. For example::
        
            _spice_simcmd(sim='dc',sweep='temp',swpstart=27,swpstop=87)
        
        sweeps the top-level parameter temp (temperature) from 27 to 87 at 10
        degree increments.
    subcktname : str
        If given, sweeps the parameter defined by property sweep from the
        subcircuit given by this property. For example::
        
            _=spice_simcmd(sim='dc',sweep='Vb',subcktname='XSUBCKT',
                           swpstart=0.1,swpstop=1.5,step=0.05)
        
        sweeps the Vb parameter from subcircuit XSUBCKT from 0.1 volts to 1.5
        volts with 0.05 volt increments.
    devname : str
        If given, sweeps the parameter defined by property sweep from the
        device given by this property. For example::
        
            _=spice_simcmd(sim='dc', sweep='w', deviceswp='XSUBCKT.XNMOS',
                           swpstart='10u', swpstop='14u', step='0.1u')
        
        sweeps the width of transistor XNMOS of subckt XSUBCKT from 10u to 14u
        in 0.1u increments.
    swpstart : int, float or str
        Starting point of DC sweep. Default 0.
    swpstop : int, float or str
        Stop point of DC sweep. Default 0.
    swpstep : int, float or str
        Step size of the sweep simulation. Default 10.
    tprint : float or str
        Print interval. Default 1e-12 (same as '1p').
    tstop : float or str
        Transient simulation duration. When not defined, the simulation time is
        the duration of the longest input signal.
    uic : bool
        Use initial conditions flag. Default False.
    noise : bool
        Noise transient flag. Default False.
    fmin : float or str
        Minimum noise frequency. Default 1 (Hz).
    fmax : float or str
        Maximum noise frequency. Default 5e9.
    fscale : 'log' or 'lin'
        Logarithmic or linear scale for frequency. Default 'log'.
    fpoints : int
        Number of points for frequency analysis. Default 0.
    fstepsize : int 
        Step size for AC analysis, if scale if 'lin'. If fscale is 'log', this
        parameter gives number of points per decade. Default 0.
    seed : int
        Random generator seed for noise transient. Default None (random).
    method : str
        Transient integration method. Default None (Spectre takes
        method from errpreset).
    cmin : float
        Spectre cmin parameter: this much cap from each node to ground.
        Might speed up simulation. Default None (not used).
    mc : bool
        Enable Monte Carlo simulation. This flag will enable Monte Carlo
        modeling for a single simulation. It will NOT execute multiple runs
        or do any statistical analysis. Intended use case is to generate a
        group of entities in the testbench with each having mc=True,
        simulating them in parallel (see run_parallel() of thesdk-class),
        post-processing results in Python.
    mc_seed : int
        Random seed for the Monte Carlo instance. Default None (random seed).

    Examples
    --------
    Initiated in parent as:: 

        _=spice_simcmd(self,sim='tran',tprint=1e-12,tstop='10n',
                       uic=True,noise=True,fmin=1,fmax=5e9)

    For a simple transient with inferred simulation duration::

        _=spice_simcmd(self,sim='tran')

    """

    @property
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    def __init__(self,parent,**kwargs):
        try:
            self.parent = parent
            self.sim = kwargs.get('sim','tran')
            self.plotlist = kwargs.get('plotlist',[])
            self.excludelist = kwargs.get('excludelist',[])
            self.sweep = kwargs.get('sweep','')
            self.subcktname = kwargs.get('subcktname','')
            self.devname = kwargs.get('devname','')
            self.swpstart = kwargs.get('swpstart',0)
            self.swpstop = kwargs.get('swpstop',0)
            self.swpstep = kwargs.get('swpstep',10)
            self.tprint = kwargs.get('tprint',1e-12)
            self.tstop = kwargs.get('tstop',None)
            self.uic = kwargs.get('uic',False)
            self.noise = kwargs.get('noise',False)
            self.fmin = kwargs.get('fmin',1)
            self.fmax = kwargs.get('fmax',5e9)
            self.fscale = kwargs.get('fscale','log')
            self.fpoints = kwargs.get('fpoints',0)
            self.fstepsize = kwargs.get('fstepsize',0)
            self.seed = kwargs.get('seed',None)
            self.method = kwargs.get('method',None)
            self.cmin = kwargs.get('cmin',None)
            self.mc = kwargs.get('mc',False)
            self.mc_seed = kwargs.get('mc_seed',None)
        except:
            self.print_log(type='F', msg="Simulation command definition failed.")
        if hasattr(self.parent,'simcmd_bundle'):
            # This limits it to 1 of each simulation type. Is this ok?
            self.parent.simcmd_bundle.new(name=self.sim,val=self)
        if self.subcktname != '' and self.devname != '':
            self.print_log(type='F', msg='Cannot specify subckt sweep and device sweep in the same simcmd instance!')

