import traceback

class spice_port():
    '''
    Class for providing port objects for spice simulations. When created,
    adds it self to the parents spice_ports dictionary and is accessible as
    parent.spice_ports['name'].

    Attributes
    ----------
    parent : object
        The parent object initializing the spice_port instance. Default None
    name: str
        Name of the port. Must be unique within top-level netlist. Default: "PORT<self.num>"
    pos: str
        Node to which the positive terminal of the port is to be attached
    neg: str
        Node to which the negative terminal of the port is to be attached
    res: float or int
        Series resistance of the port
    num: int
        Number of the port (for S-parameter analysis)
    type: str
        TODO: IS THIS NEEDED?
        Type of source, e.g. 'sine', 'dc'.
    freq: str
        TODO: IS THIS NEEDED?
        Point frequency of source.
    '''

    def __init__(self, parent=None, **kwargs):
        if parent == None:
            self.print_log(type='F', msg="Parent of spice input file not given")
        try:
            self.pos=kwargs.get('pos', None)
            self.neg=kwargs.get('neg', None)
            self.res=kwargs.get('res', 50)
            self.num=kwargs.get('num', 1)
            self.type=kwargs.get('type', 'sine')
            self.freq=kwargs.get('dc', 0)
            self.name=kwargs.get('name', f'PORT{self.num}')
            self.parent.spice_ports[self.name] = self
        except:
            self.print_log(type='W', msg="Something went wrong with defining a spice port.")
            self.print_log(type='W', msg=traceback.format_exc())
            self.print_log(type='F', msg="Exiting.")

