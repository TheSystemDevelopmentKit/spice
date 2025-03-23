"""
=======
Spectre
=======
Spectre simulation interface package for Spectre for TheSyDeKick.

Initially written by Okko Järvinen, 2019
"""
import os
import sys
import subprocess
import pandas as pd
from collections import defaultdict
from abc import * 
from thesdk import *
from spice.spice_common import *
import numpy as np
import psf_utils.psf_utils as psfu

class spectre(spice_common):
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
        return '.scs'
    @property
    def resultfile_ext(self):
        """str : Extension of the result file
        """
        return '.raw'
    @property
    def commentchar(self):
        """str : Comment character of the simulator
        """
        return '//'
    @property
    def commentline(self):
        """str : Comment line for the simulator
        """
        return '///////////////////////\n'
    @property
    def nprocflag(self):
        """str : String for defining multithread execution
        """
        return '+mt='
    @property
    def simulatorcmd(self):
        """str : Simulator execution command 
            (Default: 'ngspice')
        """
        return 'spectre -64 +lqtimeout=0 ++aps=%s' %(self.errpreset)
    @property
    def dcsource_declaration(self):
        """str : DC source declaration
        """
        #self.print_log(type='F', msg='DC source declaration not defined for ngspice')
        return 'vsource type=dc dc='
    @property
    def parameter(self):
        """str : Netlist parameter definition string
        """
        return 'parameters'
    @property
    def option(self):
        """str : Netlist option definition string
        """
        return 'options'
    @property
    def include(self):
        """str : Netlist include string
        """
        return 'include'
    @property
    def dspfinclude(self):
        """str : Netlist dspf-file include string
        """
        return 'dspf_include'
    @property
    def subckt(self):
        """str : Subcircuit include string
        """
        return 'subckt'
    @property
    def lastline(self):
        """str : Last line of the simulator command file
        """
        return '///'
    @property
    def eventoutdelim(self):
        """str : Delimiter for the events
        """
        return ','
    @property
    def csvskip(self):
        """Needs documentation. Lines skipped in result file : int
        """
        return 0

    @property
    def plflag_simcmd_prefix(self):
        """
        Simulator specific prefix for enabling postlayout optimization
        Postfix comes from self.plflag (user defined)
        """
        if not hasattr(self, '_plflag_simcmd_prefix'):
            self._plflag_simcmd_prefix="+postlayout"
        return self._plflag_simcmd_prefix

    @property
    def plflag(self):
        '''
        Postlayout simulation accuracy/RC reduction flag.
        See: https://community.cadence.com/cadence_blogs_8/b/cic/posts/spectre-optimizing-spectre-aps-performance 
        '''
        if not hasattr(self, '_plflag'):
            self._plflag=f"=upa"
        return self._plflag

    @plflag.setter
    def plflag(self, val):
        if val in ["upa", "hpa"]:
            self._plflag=f'={val}'
        elif val=='':
            self._plflag=''
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
        if not hasattr(self,'_errpreset'):
            self._errpreset='moderate'
        return self._errpreset
    @errpreset.setter
    def errpreset(self,value):
        self._errpreset=value

    @property
    def plotprogram(self):
        """ str : Sets the program to be used for visualizing waveform databases.

        Options are ezwave (default) or viva.
        """
        if not hasattr(self, '_plotprogram'):
            if hasattr(self.parent,'plotprogram'):
                self._plotprogram=self.parent.plotprogram
            else:
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
                plflag=f"{self.plflag_simcmd_prefix}{self.plflag}"
                self.print_log(type='I',msg='Enabling post-layout optimization \'%s\'.' % plflag)
            else:
                plflag = ''

            spicesimcmd = (self.simulatorcmd + " %s %s -outdir %s " 
                    % (plflag,nprocflag,self.parent.spicesimpath))
            self._spicecmd = self.parent.spice_submission+spicesimcmd+self.parent.spicetbsrc

        return self._spicecmd

    def run_plotprogram(self):
        ''' Starting a parallel process for waveform viewer program.

         The plotting program command can be set with 'plotprogram' property.
        '''
        tries = 0
        while tries < 100:
            if os.path.exists(self.parent.spicedbpath):
                # More than just the logfile exists
                if len(os.listdir(self.parent.spicedbpath)) > 1:
                    # Database file has something written to it
                    filesize = []
                    for f in os.listdir(self.parent.spicedbpath):
                        filesize.append(os.stat('%s/%s' % (self.parent.spicedbpath,f)).st_size)
                    if all(filesize) > 0:
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

    def read_sp_result(self,**kwargs):
        """ Internally called function to read the S-parameter simulation results
            TODO: Implement for Eldo as well.
        """
        read_type=kwargs.get('read_type')
        try:
            if 'sp' in self.parent.simcmd_bundle.Members.keys():
                self.extracts.Members.update({read_type: {}})
                sweep=False
                # Get sp simulation file name
                for name, val in self.parent.simcmd_bundle.Members.items():
                    mc=val.mc
                    if name=='sp':
                        fname=''
                        if len(val.sweep)!=0:
                            for i in range(0, len(val.sweep)):
                                sweep=True
                                fname+='Sweep%d-*_' % i
                            if mc:
                                # TODO: implement.
                                self.print_log(type='F',
                                        msg=f"Monte carlo currently not supported for \
                                                S-parameter simulations.")
                                fname+='mc_oppoint.dc'
                            else:
                                if 'sparams' in read_type:
                                    fname+=f'SPanalysis.sp'
                                elif 'sprobe' in read_type:
                                    fname+=f'SPanalysis.sprobe.sp'
                        else:
                            if mc:
                                # TODO: implement.
                                self.print_log(type='F',
                                        msg=f"Monte carlo currently not supported for \
                                                S-parameter simulations.")
                                fname+='mc_oppoint.dc'
                            else:
                                if 'sparams' in read_type:
                                    fname+=f'SPanalysis.sp'
                                elif 'sprobe' in read_type:
                                    fname+=f'SPanalysis.sprobe.sp'
                        break
                # For distributed runs
                if self.parent.distributed_run:
                    # TODO: check functionality and implement
                    self.print_log(type='F',
                            msg=f"Distributed runs not currently supported for \
                                    S-parameter analyses.")
                    path=os.path.join(self.parent.spicesimpath,'tb_%s.raw' % self.parent.name, '[0-9]*',
                            fname)
                else:
                    path=os.path.join(self.parent.spicesimpath,'tb_%s.raw' % self.parent.name,
                            fname)
                # Sort files such that the sweeps are in correct order.
                if sweep:
                    num_sweeps=len(val.sweep)
                    files=glob.glob(path)
                    for i in range(num_sweeps):
                        files=sorted(files,key=lambda x: self.sorter(x, i))
                    if len(files)>0:
                        rd, fileptr = self.create_nested_sweepresult_dict(0,0,
                                self.extracts.Members['sweeps_ran'],files,
                                read_type)
                else:
                    files=glob.glob(path)
                    if len(files)>1: # This should not happen
                        self.print_log(type='W',
                                msg="S-parameter analysis was not a sweep, but for \
                                        some reason multiple output files were found. \
                                        results may be in wrong order!")
                    result={}
                    if len(files)>0:
                        psf = psfu.PSF(files[0])
                        psfsweep=psf.get_sweep()
                        for signal in psf.all_signals():
                            result[signal.name]=np.vstack((psfsweep.abscissa, 
                                psf.get_signal(f'{signal.name}').ordinate)).T
                    rd={0:{'param':'nosweep', 'value':0, read_type:result}}
                self.extracts.Members[read_type].update({'results':rd})
        except:
            self.print_log(type='W',
                    msg=traceback.format_exc())
            self.print_log(type='W',
                    msg="Something went wrong while extracting S-parameters")


    def read_noise_result(self,**kwargs):
        """ Internally called function to read the noise simulation results
            TODO: Implement for Eldo as well.
        """
        try:
            if 'noise' in self.parent.simcmd_bundle.Members.keys():
                ocean_command = f"""
                openResults("{self.parent.spicedbpath}")
                selectResult('noise)
                ocnPrint(?output "{os.path.join(self.parent.spicesimpath, '%s_nf' % self.parent.name)}" ?numberNotation 'scientific getData("NF"))
                noiseSummary('integrated ?resultsDir "{self.parent.spicedbpath}" ?result 'noise ?output "{os.path.join(self.parent.spicesimpath, '%s_noisesum' % self.parent.name)}" ?sort '(name))
                exit
                """
                process = subprocess.Popen(
                        ["ocean", "-nograph"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                        )
                stdout, stderr = process.communicate(input=ocean_command)
                if stderr:
                    print(stderr, file=sys.stderr)

                df = pd.read_csv(f"{os.path.join(self.parent.spicesimpath, '%s_nf' % self.parent.name)}", delim_whitespace=True, header=None, skiprows=3)
                df.columns = ['Frequency', 'NF']
                freq = df['Frequency'].values
                NF = df['NF'].values

                df = pd.read_csv(f"{os.path.join(self.parent.spicesimpath, '%s_noisesum' % self.parent.name)}", sep='\s+', header=None, skipinitialspace=True, skipfooter=5, engine='python')
                noise_data = {}
                current_device = None
                for index, row in df.iterrows():
                    # Device row
                    if all(pd.notna(row[0:4])) and all(pd.isna(row[5:10])):
                        current_device = row[0]
                        noise_data[current_device] = {
                                'Contribution_percentage': float(row[1]),
                                'Input_referred': float(row[2]),
                                'Param': {}
                                }
                        noise_data[current_device]['Param'][row[3]] = float(row[4])
                    # Device param row
                    elif all(pd.notna(row[0:2])) and all(pd.isna(row[2:10])):
                        param_name = row[0].strip()
                        if param_name:
                            noise_data[current_device]['Param'][param_name] = float(row[1])

                analysis='noise'
                nodes=self.parent.simcmd_bundle.Members[analysis].nodes
                mc=self.parent.simcmd_bundle.Members[analysis].mc
                self.extracts.Members.update({analysis: {}})
                # Get simulation result file name
                fnames=[]
                for node in nodes:
                    if mc:
                        # TODO: implement.
                        self.print_log(type='F',
                                msg=f"Monte carlo currently not yet supported for \
                                        {analysis} simulations. Please implement.")
                    else:
                        if 'noise' in analysis:
                            fnames.append(f'noise_analysis_{node}.noise')

                # For distributed runs
                for i in range(len(fnames)):
                    if self.parent.distributed_run:
                        # TODO: check functionality and implement
                        self.print_log(type='F',
                                msg=f"Distributed runs not currently supported for \
                                        PSF file read analyses.")
                        path=os.path.join(self.parent.spicesimpath,'tb_%s.raw' % self.parent.name, '[0-9]*',
                                fnames[i])
                    else:
                        path=os.path.join(self.parent.spicesimpath,'tb_%s.raw' % self.parent.name,
                                fnames[i])
                    files=glob.glob(path)
                    if 'noise' in analysis:
                        self.extracts.Members[analysis].update({
                            f'{nodes[i]}_freq':freq,
                            f'{nodes[i]}_NF':NF,
                            f'{nodes[i]}_noise_contributions':noise_data,
                            })
        except:
            self.print_log(type='W',
                    msg=traceback.format_exc())
            self.print_log(type='W',
                    msg="Something went wrong while extracting S-parameters")

    def create_nested_sweepresult_dict(self, level, fileptr, sweeps_ran_dict,
            files,read_type):
        """Documentation missing
        """
        rd={} # Return this to upper level
        if level < len(sweeps_ran_dict)-1:
            for v in np.arange(len(sweeps_ran_dict[level]['values'])):
                result={}
                psf = psfu.PSF(files[fileptr])
                fileptr += 1
                psfsweep=psf.get_sweep()
                for signal in psf.all_signals():
                    result[signal.name]=np.vstack((psfsweep.abscissa,
                        psf.get_signal(f'{signal.name}').ordinate)).T
                    rd.update({v:{'param':sweeps_ran_dict[level]['param'],
                        'value':sweeps_ran_dict[level]['values'][v],
                        read_type:result}})
        return rd, fileptr

    def read_oppts(self):
        """ Internally called function to read the DC operating points of the circuit
            TODO: Implement for Eldo as well.
        """

        try:
            if 'dc' in self.parent.simcmd_bundle.Members.keys():
                self.extracts.Members.update({'oppts' : {}})
                sweep=False
                # Get dc simulation file name
                for name, val in self.parent.simcmd_bundle.Members.items():
                    mc = val.mc
                    if name == 'dc':
                        fname=''
                        if len(val.sweep) != 0:
                            for i in range(0, len(val.sweep)):
                                sweep=True
                                fname += 'Sweep%d-[0-9]*_' % i
                            if mc:
                                fname+='mc_oppoint.dc'
                            else:
                                fname+='oppoint.dc'
                        else:
                            if mc:
                                fname = 'mc_oppoint*.dc'
                            else:
                                fname = 'oppoint*.dc'
                        break
                # For distributed runs
                if self.parent.distributed_run:
                    path=os.path.join(self.parent.spicesimpath,'tb_%s.raw' % self.parent.name, '[0-9]*',
                            fname)
                else:
                    path=os.path.join(self.parent.spicesimpath,'tb_%s.raw' % self.parent.name, fname)
                # Sort files so that sweeps are in correct order
                if sweep:
                    num_sweeps = len(val.sweep)
                    files = glob.glob(path)
                    for i in range(num_sweeps):
                        files = sorted(files,key=lambda x: self.sorter(x, i))
                else:
                    files = glob.glob(path)
                    if len(files)>1:# This shoudln't happen
                        self.print_log(type='W', msg='DC analysis was not a sweep, but multiple output files were found! Results may be in incorrect order!')
                valbegin = 'VALUE\n'
                eof = 'END\n'
                parsevals = False
                for file in files:
                    with open(file, 'r') as f:
                        for line in f:
                            if line == valbegin: # Scan file until unit descriptions end and values start
                                parsevals = True
                            elif line != eof and parsevals: # Scan values from output until EOF
                                line = line.replace('\"', '')
                                parts = line.split()
                                if len(parts) >= 3:
                                    if ':' in parts[0]: # This line contains op point parameter (e.g. vgs)
                                        dev, param = parts[0].split(':')
                                    elif ':' not in parts[0] and parts[1] == 'V': # This is a node voltage
                                        dev = parts[0]
                                        param = parts[1]
                                    val = float(parts[2])
                                    if dev not in self.extracts.Members['oppts']: # Found new device
                                        self.extracts.Members['oppts'].update({dev : {}}) 
                                    if param not in self.extracts.Members['oppts'][dev]: # Found new parameter for device
                                        self.extracts.Members['oppts'][dev].update({param : [val]})
                                    else: # Parameter already existed, just append value. This can occur in e.g. sweeps
                                        self.extracts.Members['oppts'][dev][param].append(val)
                            elif line == eof:
                                parsevals = False
        except:
            self.print_log(type='W', msg=traceback.format_exc())
            self.print_log(type='W',msg='Something went wrong while extracting DC operating points.')

