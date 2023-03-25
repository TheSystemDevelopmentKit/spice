"""
============
Spice Module
============

Class for Spice netlist parsing.

"""
import os
import pdb
import shutil
import fileinput
import sys
from thesdk import *
from spice import *
from copy import deepcopy
import traceback

class spice_module(thesdk):
    """
    This class parses source netlist for subcircuits and handles the generation
    of a separate pruned subckt_* -file. This class is internally utilized by
    the spice_testbench module.

    """

    def __init__(self, **kwargs):
        # No need to propertize these yet
        self._file=kwargs.get('file','')
        self._name=kwargs.get('name','')
        self.parent=kwargs.get('parent') # There should be no need for parent in this module
        if not self.file and not self._name:
            self.print_log(type='F', msg='Either name or file must be defined')

    @property
    def file(self):
        """String
        
        Filepath to the entity's spice netlist source file (i.e. './spice/entityname.scs').
        """
        if not hasattr(self,'_file'):
            self._file=None
        return self._file
    @file.setter
    def file(self,value):
            self._file=value
    
    @property
    def name(self):
        """String
        
        Entity name."""
        if not self._name:
            self._name=os.path.splitext(os.path.basename(self.file))[0]
        return self._name

    @property
    def postlayout(self):
        """Boolean
        
        Enables post-layout optimizations in the simulator command options. 

        """
        if not hasattr(self,'_postlayout'):
            if len(self.dspf) > 0:
                self.print_log(type='I', msg = 'Setting postlayout to True due to given dspf-files')
                self._postlayout = True
            else:
                self.print_log(type='O', 
                               msg='In release v1.9, automatic postlayout simulation detection from netlist has been removed. This warning will be removed in comming releases.')
                self.print_log(type='W', 
                               msg='Postlayout attribute accessed before defined. Defaulting to False.')
                self._postlayout=False
        return self._postlayout
    @postlayout.setter
    def postlayout(self,value):
        self._postlayout=value
    @postlayout.deleter
    def postlayout(self,value):
        self._postlayout=None

    @property
    def subckt(self):
        """String
        
        String containing the contents of the subcircuit definition file of the entity.
        Extract the definitions form the source netlist. The source netlist when accessed. 
        Can be written to the subckt_file with export_subckt method. 

        """
        if not hasattr(self,'_subckt'):
            self._subckt="%s Subcircuit definitions\n\n" % self.parent.syntaxdict["commentchar"]
            # Extract the module definition
            if os.path.isfile(self.file):
                try:
                    self.print_log(type='D',msg='Parsing source netlist %s' % self.file)
                    self._subckt += subprocess.check_output('sed -n \'/\.*[sS][uU][bB][cC][kK][tT]\s\s*/,/\.*[eE][nN[dD][sS]/p\' %s' % self.file, shell=True).decode('utf-8')
                except:
                    self.print_log(type='E',msg='Something went wrong while parsing %s.' % self.file)
                    self.print_log(type='E',msg=traceback.format_exc())
            else:
                self.print_log(type='W',msg='File %s not found.' % self.file)
        return self._subckt
    @subckt.setter
    def subckt(self,value):
        self._subckt=value
    @subckt.deleter
    def subckt(self,value):
        self._subckt=None

    @property
    def instance(self):
        """String
        
        String containing the subcircuit instance to be placed in the
        testbench. Parsed from the subckt property
        """
        try:
            if not hasattr(self,'_instance'):
                subckt = self.subckt.split('\n')
                startmatch=re.compile(r"%s %s " %(self.parent.syntaxdict["subckt"], self.parent.name)
                        ,re.IGNORECASE)

                if len(subckt) <= 3:
                    self.print_log(type='W',msg='No subcircuit found.')
                    self._instance = "%s Empty subcircuit\n" % (self.parent.syntaxdict["commentchar"])

                else:
                    self._instance = "%s Subcircuit instance\n" % (self.parent.syntaxdict["commentchar"])
                    startfound = False
                    endfound = False
                    lastline = False
                    for line in subckt:
                        if startmatch.search(line) != None:
                            startfound = True
                            # For spectre we need to process the statline as potential endline
                            if self.parent.model == 'spectre':
                                if startfound and len(line) > 0:
                                    if lastline:
                                        endfound = True
                                        startfound = False
                                    if not line[-1] == '\\':
                                        lastline = True
                        elif startfound and len(line) > 0:
                            if self.parent.model == 'eldo':
                                if line[0] != '+':
                                    endfound = True
                                    startfound = False
                            elif self.parent.model == 'spectre':
                                if lastline:
                                    endfound = True
                                    startfound = False
                                if not line[-1] == '\\':
                                    lastline = True
                            # For consistency, even though identical to eldo
                            elif self.parent.model == 'ngspice':
                                if line[0] != '+':
                                    endfound = True
                                    startfound = False
                        if startfound and not endfound:
                            words = line.split(" ")
                            if words[0].lower() == self.parent.syntaxdict["subckt"]:
                                if self.parent.model == 'eldo':
                                    words[0] = "X%s%s" % (self.parent.name,'')  
                                elif self.parent.model == 'spectre':
                                    words[0] = "X%s%s" % (self.parent.name, ' (')
                                elif self.parent.model == 'ngspice':
                                    words[0] = "X%s%s" % (self.parent.name,'')  
                                words.pop(1)
                                line = ' '.join(words)
                            self._instance += line + "%s\n" % (' \\' if lastline else '')
                    if self.parent.model == 'eldo':
                        self._instance += ('+')  + self.parent.name
                    elif self.parent.model == 'spectre':
                        self._instance += (') ' )  + self.parent.name
                    elif self.parent.model == 'ngspice':
                        self._instance += ('+')  + self.parent.name
                return self._instance
        except:
            self.print_log(type='E',msg='Something went wrong while generating subcircuit instance.')
            self.print_log(type='E',msg=traceback.format_exc())
    @instance.setter
    def instance(self,value):
        self._instance=value
    @instance.deleter
    def instance(self,value):
        self._instance=None

    def export_subckt(self,**kwargs):
        """
        Internally called function to write the parsed subcircuit definitions
        to a file.

        Parameters
        ----------
        file : str
            Path to file where to write.
        force : Bool, False
            Force writing
        """
        file = kwargs.get('file')
        force = kwargs.get('force', False)
        if not os.path.isfile(file):
            self.print_log(type='D',msg='Exporting spice subcircuit to %s' %(file))
            with open(file, "w") as module_file:
                module_file.write(self.subckt)
        elif os.path.isfile(file) and not force:
            self.print_log(type='F', msg=('Export target file %s exists.\n Force overwrite with force=True.' %(file)))
        elif force:
            self.print_log(type='I',msg='Forcing overwrite of spice subcircuit to %s.' %(file))
            with open(file, "w") as module_file:
                module_file.write(self.subckt)

if __name__=="__main__":
    pass
