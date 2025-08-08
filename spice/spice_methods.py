"""
Spice methods

Collection of methods provided as a mixin class

Initially restructured to this package Marko Kosunen 2022
"""


import os
import sys
from abc import * 
from thesdk import *
import subprocess
import multiprocessing
import pandas as pd

class spice_methods(metaclass=abc.ABCMeta):

    def filter_strobed(self, key,ioname):
        """
        Helper function to read in the strobed simulation results. Only for spectre.

        TODO:
        this is because the strobeoutput
        parameter for some reason still outputs
        all the data points, even when it is in mode
        strobeonly
        If solution is found to this later from simulator
        remove this.
        """
        if len(self.strobe_indices)==0:
            tvals=self.iofile_eventdict[ioname.upper()][:,0]
            maxtime = np.max(tvals)
            mintime = np.min(tvals)
            for simulationcommand, simulationoption in self.simcmd_bundle.Members.items():
                strobeperiod = simulationoption.strobeperiod
                strobedelay = simulationoption.strobedelay
                skipstart = simulationoption.skipstart
            if not skipstart:
                skipstart=0
            if not strobedelay:
                strobedelay=0
            strobetimestamps = np.arange(mintime,maxtime,strobeperiod)+strobedelay+skipstart
            self.strobe_indices=np.zeros(len(strobetimestamps)) # indexes to take the values
            seg=min(300, len(strobetimestamps)) # length of a segment in the for loop (how many samples at a time)
            idxmin=0
            l=len(strobetimestamps)
            nseg=l//seg # number of segments, rounded down (how many loops required)
            idxmax=0
            i = 0
            for i in np.arange(1,nseg):
                idxmax=(i-1)*seg+np.argmin(abs(tvals[(i-1)*seg:]-strobetimestamps[i*seg])) # find index of the received signal which corresponds to the largest value in reference
                ind=idxmin+abs(strobetimestamps[seg*(i-1):seg*(i),None]-tvals[None,idxmin:idxmax]).argmin(axis=-1) # take index for the seg's values
                idxmin=idxmax
                self.strobe_indices[seg*(i-1):seg*i]=ind  
            # again just in case that the loop does not overflow to take the final samples into account
            idxmax=len(tvals)-1
            ind=idxmin+abs(strobetimestamps[seg*(i):,None]-tvals[None,idxmin:idxmax]).argmin(axis=-1)
            idxmin=idxmax
            self.strobe_indices[seg*(i):]=ind
            self.strobe_indices=self.strobe_indices.astype(int)
            if self.iofile_bundle.Members[key].strobe:
                new_array =self.iofile_eventdict[ioname.upper()][self.strobe_indices]
                if len(strobetimestamps)!=len(new_array):
                    self.print_log(type='W',
                            msg='Oh no, something went wrong while reading the strobeperiod data')
                    self.print_log(type='W',
                            msg='Check data lenghts!')
            else:
                new_array =self.iofile_eventdict[ioname.upper()]
        else: # We already know the strobe indices, use them!
            if self.iofile_bundle.Members[key].strobe:
                new_array =self.iofile_eventdict[ioname.upper()][self.strobe_indices]
            else:
                new_array =self.iofile_eventdict[ioname.upper()]
        return new_array

    def check_output_accuracy(self):
        '''
        Helper function to check output accuracy
        '''
        keys = list(self.iofile_eventdict.keys())
        if len(keys) > 0:
            try:
                key = keys[0]
                tdiff = np.diff(self.iofile_eventdict[key.upper()][:,0])
                if np.any(tdiff == 0.0):
                        self.print_log(type='W', msg='Accuracy of output file is insufficient. Increase value of \'digits\' parameter and re-run simulation!')
            except: # Requested output wasn't in output file, do nothing
                self.print_log(type='W',msg='Couldn\'t check output file accuracy')
                self.print_log(type='W',msg=traceback.format_exc())
        else:
            self.print_log(type='I',msg='Output file has no lines or was not read before checking output accuracy.')

    def parse_io_from_file(self,filepath,start,stop,dtype,labels,queue):
        """ Parse specific lines from a spectre/ngspice print file.

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

    def read_output_file(self,file,dtype):
        '''
        Function which reads output file. This is called only once after the simulation has finished.
        The datapoints read from the iofile are populated into self.iofile_eventdict, from which
        they can be obtained later on.
        '''
        label_match=re.compile(r'\(([^)]+)\)') # Match one or more characters that are not ) and capture.
        if self.model in ['spectre','ngspice']:
            os.system('sync %s' % self.spicesimpath)
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
                                self.iofile_eventdict[item[0].upper()]=item[1]
                            self.print_log(type='I',msg=f'IO reading complete')
                    for i,p in enumerate(procs):
                        try:
                            ret = queues[i].get()
                            for item in ret:
                                self.iofile_eventdict[item[0].upper()]=item[1]
                            p.join()
                        except KeyError:
                            self.print_log(type='W', msg='Failed reading %s' % (ret[0]))
            else:
                self.print_log(type='W', msg='Couldn\'t read IOs from file %s. Missing ioname?' % file)
        elif self.model == 'eldo':
            # Parse signal headers
            with open(file,'r') as f:
                for line in f.readlines():
                    if line.startswith('# TIME') or line.startswith('# FREQ'):
                        header = line.replace('# ','').replace('\n','').split(' ')
                        break
            arr = np.genfromtxt(file)
            if len(header) != len(arr[0,:]):
                self.print_log(type='E', msg='Signal name and array column mismatch while reading event outputs.')
            for col_idx,sname in enumerate(header[1:]):
                label=label_match.search(sname)
                if label:
                    label = label.group(1)
                    # Add to the event dictionary
                    self.iofile_eventdict[label.upper()]=np.hstack((arr[:,0].reshape(-1,1),arr[:,col_idx+1].reshape(-1,1))).reshape(-1,2)
                else:
                    self.print_log(type='W', msg='Label format mismatch with \'%s\'.' %  (label))

    def get_buswidth(self,signame):
        """ Extract buswidth from signal name.
        
        Little-endian example::
                
            start,stop,width,busrange = get_buswidth('BUS<10:0>')
            # start = 10
            # stop = 0
            # width = 11
            # busrange = range(10,-1,-1)

        Big-endian example::
                
            start,stop,width,busrange = get_buswidth('BUS<0:8>')
            # start = 0
            # stop = 8
            # width = 9
            # busrange = range(0,9)
            
        """
        signame = signame.replace('<',' ').replace('>',' ').replace('[',' ').replace(']',' ').replace(':',' ').split(' ')
        if '' in signame:
            signame.remove('')
        if len(signame) == 1:
            busstart = 0
            busstop = 0
        elif len(signame) == 2:
            busstart = int(signame[1])
            busstop = int(signame[1])
        else:
            busstart = int(signame[1])
            busstop = int(signame[2])
        if busstart > busstop:
            buswidth = busstart-busstop+1
            busrange = range(busstart,busstop-1,-1)
        else:
            buswidth = busstop-busstart+1
            busrange = range(busstart,busstop+1)
        return busstart,busstop,buswidth,busrange
    
    def si_string_to_float(self, strval):
        """ Convert SI-formatted string to float
            
        E.g. self.si_string_to_float('3 mV') returns 3e-3.
        """
        parts = strval.split()
        if len(parts) == 2:
            val = float(parts[0])
            if len(parts[1]) == 1: # No prefix
                mult = 1
            else:
                try:
                    mult = self.si_prefix_mult[parts[1][0]]
                except KeyError: # Could not convert, just return the text value
                    self.print_log(type='W', msg='Invalid SI-prefix %s, failed to convert.' % parts[1][0])
                    return strval
            return val*mult
        else:
            return strval # Was a text value



    def sorter(self,val,index=0):
        '''
        Function for sorting the files in correct order
        Files that are output from simulation are of form

        SweepN-<integer>_SweepN-1-<integer>_ ... _oppoint.dc

        Strategy: Extract the innermost sweep (e.g. Sweep0) string, find the sweep number
        and sort based on that. If the sweep is nested, run this algorithm N times with increasing
        index to sort the outer sweep results.

        '''
        base=os.path.basename(val)
        sweeps=list(reversed(base.split('_')[:-1]))
        key = sweeps[index].split('-')[-1]
        return int(key)
