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
    @property
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    def __init__(self, **kwargs):
        # No need to propertize these yet
        self.file=kwargs.get('file','')
        self._name=kwargs.get('name','')
        if not self.file and not self._name:
            self.print_log(type='F', msg='Either name or file must be defined')
    
    @property
    def name(self):
        """String
        
        Entity name."""
        if not self._name:
            self._name=os.path.splitext(os.path.basename(self.file))[0]
        return self._name

    @property
    def DEBUG(self):
        """ This fixes DEBUG prints in spice_iofile, by propagating the DEBUG
        flag of the parent entity.
        """
        return self.parent.DEBUG 

    @property
    def postlayout(self):
        """Boolean
        
        Flag for detected post-layout netlists. This will enable post-layout
        optimizations in the simulator command options. 

        """
        if not hasattr(self,'_postlayout'):
            self.print_log(type='F', 
                           msg='Postlayout attribute accessed before defined. This parameter is no longer automatically extracted. You must set it.')
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
        
        String containing the contents of the subcircuit definition of the entity.
        Extract the definition form the source netlist. the source netlist when accessed. 
        Can be written to the subckt_file with export_subckt method. 

        """
        if not hasattr(self,'_subckt'):
            self._subckt="%s Subcircuit definitions\n\n" % self.parent.syntaxdict["commentchar"]
            # Extract the module definition
            if os.path.isfile(self._dutfile):
                try:
                    self.print_log(type='D',msg='Parsing source netlist %s' % self._dutfile)
                    self._subckt += subprocess.check_output('sed -n \'/\.*[sS][uU][bB][cC][kK][tT]/,/\.*[eE][nD][sS]/p\' %s' % self._dutfile, shell=True).decode('utf-8')
                except:
                    self.print_log(type='E',msg='Something went wrong while parsing %s.' % self._dutfile)
                    self.print_log(type='E',msg=traceback.format_exc())
            else:
                self.print_log(type='W',msg='File %s not found.' % self._dutfile)
        return self._subckt
    @subckt.setter
    def subckt(self,value):
        self._subckt=value
    @subckt.deleter
    def subckt(self,value):
        self._subckt=None

    @property
    def subinst(self):
        """String
        
        String containing the subcircuit instance to be placed in the
        testbench. Parsed from the subckt property
        """
        try:
            if not hasattr(self,'_subinst'):
                subckt = self.subckt.split('\n')
                startmatch=re.compile(r"%s %s " %(self.parent.syntaxdict["subckt"], self.parent.name)
                        ,re.IGNORECASE)

                if len(subckt) <= 3:
                    self.print_log(type='W',msg='No subcircuit found.')
                    self._subinst = "%s Empty subcircuit\n" % (self.parent.syntaxdict["commentchar"])

                else:
                    self._subinst = "%s Subcircuit instance\n" % (self.parent.syntaxdict["commentchar"])
                    startfound = False
                    endfound = False
                    lastline = False
                    for line in subckt:
                        if self.postlayout:
                            if self.parent.model == 'spectre':
                                # Does this actually doe something?
                                # Replaces newlines on _line_ with space
                                line = line.replace('\n','')

                        if startmatch.search(line) != None:
                            startfound = True
                            #For spectre, for some reason we need to process this already on the first line
                            #if self.parent.model == 'spectre':
                            #    if startfound and len(line) > 0:
                            #        if lastline:
                            #            endfound = True
                            #            startfound = False
                            #        # If the last character of the line is not backslash
                            #        # escaping newline we are already at the end
                            #        if not line[-1] == '\\':
                            #            lastline = True
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
                            self._subinst += line + "%s\n" % (' \\' if lastline else '')
                    if self.parent.model == 'eldo':
                        self._subinst += ('+')  + self.parent.name
                    elif self.parent.model == 'spectre':
                        self._subinst += (') ' )  + self.parent.name
                    elif self.parent.model == 'ngspice':
                        self._subinst += ('+')  + self.parent.name
                return self._subinst
        except:
            self.print_log(type='E',msg='Something went wrong while generating subcircuit instance.')
            self.print_log(type='E',msg=traceback.format_exc())
            pdb.set_trace()
    @subinst.setter
    def subinst(self,value):
        self._subinst=value
    @subinst.deleter
    def subinst(self,value):
        self._subinst=None

if __name__=="__main__":
    pass
