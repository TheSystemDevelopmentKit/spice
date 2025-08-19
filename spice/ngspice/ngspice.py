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
from spice.spice_common import *
import numpy as np

class ngspice(spice_common):
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
        self.print_log(type='W', msg='Postlayout flag unsupported for Ngspice')

    @property
    def plotprogram(self):
        """ str : Sets the program to be used for visualizing waveform databases.

        Default 'gnuplot'.
        """
        if not hasattr(self, '_plotprogram'):
            self._plotprogram='gnuplot'
        return self._plotprogram
    @plotprogram.setter
    def plotprogram(self, value):
        if value not in  [ 'gnuplot' ]:
            self.print_log(type='F',
                    msg='%s not supported for plotprogram, only gnuplot is  supported')
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
        if not hasattr(self,'_ngspice_spicecmd'):
            if self.parent.nproc:
                nprocflag = "%s%d" % (self.nprocflag,self.parent.nproc)
                self.print_log(type='I',msg='Enabling multithreading \'%s\'.' % nprocflag)
                self.print_log(type='I',msg='Multithreading for Ngspice handled in testbench.')
            else:
                nprocflag = ""

            if self.parent.postlayout:
                self.print_log(type='W',msg='Post-layout optimization not suported for Ngspice')

            if self.parent.interactive_spice:
                self._ngspice_spicecmd = self.parent.spice_submission+self.simulatorcmd+' '+self.parent.spicetbsrc
            else:
                self._ngspice_spicecmd = self.parent.spice_submission + self.simulatorcmd + ' -b '+self.parent.spicetbsrc
        return self._ngspice_spicecmd

    def run_plotprogram(self):
        ''' Starting a parallel process for waveform viewer program.

        The plotting program command can be set with 'plotprogram'.
        '''
        self.print_log(type='W',msg='Interactive plotting not implemented for ngspice.')
        return 0

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

    def read_stb_result(self,**kwargs):
        ''' Internally called function to read the stb simulation results
        '''

        if 'stb' in self.parent.simcmd_bundle.Members.keys():
            msg='STB analysis unsupported for %s' %(self.model) 
            self.print_log(type='F', msg=msg)

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
            if 'dc' in self.parent.simcmd_bundle.Members.keys(): # Unsupported model
                self.print_log(type='F', msg='DC analysis unsupported for %s' %(self.parent.model))
                raise Exception('DC optpoint extraction not supported for Eldo.')
            else: # DC analysis not in simcmds, oppts is empty
                self.extracts.Members.update({'oppts' : {}})
        except:
            self.print_log(type='W', msg=traceback.format_exc())
            self.print_log(type='W',msg='Something went wrong while extracting DC operating points.')


    def parse_io_from_file(self,filepath,start,stop,dtype,labels,queue):
        """ Parse specific lines from a ngspice print file.

        This is wrapped to a function to allow parallelism.
        """
        stack = [(label, None) for label in labels]
        try:
            nrows = stop - start
            if nrows<0:
                self.print_log(type='W', msg='Stop index smaller than start index in parse_io_from_file!')
                nrows=None
            arr=pd.read_csv(filepath,skiprows=start-1, nrows=nrows,
                    sep='\s+', encoding='utf-8',engine='c',
                    dtype='float',chunksize=1e6)
            arr=pd.concat(arr).to_numpy()
        except ValueError:
            # This may happen if the print file
            # does not round to zero, and the
            # scientific format exponent may become
            # over 100, where the space separators
            # move on top of eachother. This
            # adds the missing spacebars, which
            # may fix the crash
            try:
                cmd=f'sed -i -E "s/([0-9])+([eE][+-]?[0-9]+)?[+-]/\\1\\2 /g" {filepath}'
                self.print_log(type='I', msg="Running external command %s" %(cmd) )
                subprocess.check_output(cmd,shell=True)
                nrows = stop - start
                if nrows<0:
                    self.print_log(type='W', msg='Stop index smaller than start index in parse_io_from_file!')
                    nrows=None
                arr=pd.read_csv(filepath,skiprows=start-1, nrows=nrows,
                        sep='\s+', encoding='utf-8',engine='c',
                        dtype='float',chunksize=1e6)
                arr=pd.concat(arr).to_numpy()
            except: 
                self.print_log(type='E',msg=traceback.format_exc())
                self.print_log(type='F',msg='Failed while reading files for %s.' % self.name)
        except: 
            self.print_log(type='E',msg=traceback.format_exc())
            self.print_log(type='F',msg='Failed while reading files for %s.' % self.name)
        try:
            n = 0
            for i, label in enumerate(labels):
                self.print_log(type='D',msg='Reading event output %s' % label)
                if dtype=='complex': # Complex data has separate columns in file for real and imag parts
                    try:
                        temp=np.vstack((arr[:,0], arr[:,n+1]+1j*arr[:,n+2])).T
                        n += 2
                    except IndexError: # If the data isn't complex (might be the case if there is some real valued extract), parse as usual
                        self.print_log(type='W', msg='Index overrange when reading data for output %s. Inferred datatype incorrect?' % label)
                        temp = np.vstack((arr[:,0], arr[:,n+1])).T
                        n += 1
                else:
                    temp=np.vstack((arr[:,0], arr[:,n+1])).T
                    n += 1
                stack[i] = (label, temp)
            if queue!=None:
                queue.put(stack)
            else:
                return stack
        except:
            self.print_log(type='E',msg=traceback.format_exc())
            self.print_log(type='E',msg='Failed reading event output %s' % label)
            if queue!=None:
                queue.put(stack)
            else:
                return stack
    
    def read_output_file(self, file, dtype):
        '''
        Interfacing function to read in results from an output file
        '''
        os.system('sync %s' % self.parent.spicesimpath)
        block_count=subprocess.check_output('grep -n \"time\|freq\" %s | sed \'s/^\([0-9]\+\):/\\1|/\'' % file, shell=True).decode('utf-8')
        if not block_count: 
            # We couldn't find the block count, exit
            if os.path.isfile(file):
                self.print_log(type='F', msg='Missing header row(s) from .print file!')
            else:
                self.print_log(type='F', msg='.print file at %s doesn\'t exist!' % file)
        blocks=block_count.split('\n') 
        linenumbers=[]
        labels=[]
        # Parse linenumbers of header blocks
        for block in blocks:
            parts=block.split('|')
            if len(parts) > 1: # Line should now contain linenumber in first element, ioname in second
                line = 0
                try:
                    line=int(parts[0])
                    linenumbers.append(line)
                except ValueError:
                    self.print_log(type='W', msg='Couldn\'t decode linenumber from file %s' %  file)
                labelgrp=label_match.findall(parts[1]) # Parse IO labels (nodenames)
                if labelgrp:
                    tmp = list(dict.fromkeys(labelgrp))
                    labels.append(tmp)
                else:
                    self.print_log(type='W', msg='Couldn\'t find IO on line %d from file %s' %  (line,file))

        if len(labels) == len(linenumbers):
            try:
                numlines = int(subprocess.check_output("wc -l %s | awk '{print $1}'" % file,shell=True).decode('utf-8'))
            except FileNotFoundError as e:
                self.print_log(type='F', msg='Print-file doesn\'t exist! Invalid node names in saves statement?')
            except ValueError as e:
                self.print_log(type='F', msg='Print-file doesn\'t exist! Invalid node names in saves statement?')
            # Maximum number of concurrent open files. This may or may not help with "too many open files" -error.
            num_parallel = 50
            num_loops = int(np.ceil(len(linenumbers)/num_parallel))
            for it in range(num_loops):
                lnrange = range(num_parallel*it,min([num_parallel*(it+1),len(linenumbers)]))
                procs = []
                queues = []
                for k in lnrange:
                    start=linenumbers[k] # Indexing of line numbers starts from one
                    if k == len(linenumbers)-1:
                        stop=numlines-1
                    else:
                        stop=linenumbers[k+1]-6 # Previous data column ends 5 rows before start of next one
                    nrows=stop-start
                    if nrows<20e6:
                        self.print_log(type='I',msg=f'Number of lines: {nrows}, reading with multiprocessing')
                        queue = multiprocessing.Queue()
                        queues.append(queue)
                        proc = multiprocessing.Process(target=self.parse_io_from_file,args=(file,start,stop,dtype,labels[k],queue))
                        procs.append(proc)
                        proc.start() 
                    else:
                        self.print_log(type='I',msg=f'Number of lines: {nrows}, reading without multiprocessing')
                        queue=None
                        ret = self.parse_io_from_file(file,start,stop,dtype,labels[k],queue)
                        for item in ret:
                            self.parent.iofile_eventdict[item[0].upper()]=item[1]
                        self.print_log(type='I',msg=f'IO reading complete')
                for i,p in enumerate(procs):
                    try:
                        ret = queues[i].get()
                        for item in ret:
                            self.parent.iofile_eventdict[item[0].upper()]=item[1]
                        p.join()
                    except KeyError:
                        self.print_log(type='W', msg='Failed reading %s' % (ret[0]))
        else:
            self.print_log(type='W', msg='Couldn\'t read IOs from file %s. Missing ioname?' % file)
