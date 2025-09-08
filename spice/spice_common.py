"""
============
Spice Common
============

Mix-in class of common properties and methods for spice simulator classes

"""

import os
import sys
import subprocess
import shlex
import fileinput
from thesdk import *
from spice.spice_methods import spice_methods
import pdb


class spice_common(spice_methods, thesdk):
    """
    Common properties and methods for spice simulator tool classes.
    Most of these are overloaded in __init__.py

    """

    @property
    def extracts(self):
        """Bundle

        A thesdk.Bundle containing extracted quantities.
        """
        if not hasattr(self, "_extracts"):
            self._extracts = Bundle()
        return self._extracts

    @extracts.setter
    def extracts(self, value):
        self._extracts = value
