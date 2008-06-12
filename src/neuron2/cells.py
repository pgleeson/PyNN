# ==============================================================================
# Standard cells for neuron
# $Id: cells.py 191 2008-01-29 10:36:00Z apdavison $
# ==============================================================================

from pyNN import common
import neuron
from math import pi

ExpISyn   = neuron.new_point_process('ExpISyn')
AlphaISyn = neuron.new_point_process('AlphaISyn')
AlphaSyn  = neuron.new_point_process('AlphaSyn') # note that AlphaSynapse exists in NEURON now
ResetRefrac = neuron.new_point_process('ResetRefrac')
VecStim = neuron.new_hoc_class('VecStim')

def _new_property(obj_hierarchy, attr_name):
    """
    Returns a new property, mapping attr_name to obj_hierarchy.attr_name.
    
    For example, suppose that an object of class A has an attribute b which
    itself has an attribute c which itself has an attribute d. Then placing
      e = _new_property('b.c', 'd')
    in the class definition of A makes A.e an alias for A.b.c.d
    """
    def set(self, value):
        obj = reduce(getattr, [self] + obj_hierarchy.split('.'))
        setattr(obj, attr_name, value)
    def get(self):
        obj = reduce(getattr, [self] + obj_hierarchy.split('.'))
        return getattr(obj, attr_name)
    return property(fset=set, fget=get)

class StandardIF(neuron.nrn.Section):
    """docstring"""
    
    synapse_models = {
        'current':      { 'exp': ExpISyn,        'alpha': AlphaISyn },
        'conductance' : { 'exp': neuron.ExpSyn,  'alpha': AlphaSyn },
    }
    
    def __init__(self, syn_type, syn_shape, tau_m=20, cm=1.0, v_rest=-65,
                 v_thresh=-55, t_refrac=2, i_offset=0, v_reset=None,
                 v_init=None, tau_e=5, tau_i=5, e_e=0, e_i=-70):

        # initialise Section object with 'pas' mechanism
        neuron.nrn.Section.__init__(self)
        self.seg = self(0.5)
        self.L = 100
        self.seg.diam = 1000/pi # gives area = 1e-3 cm2
        self.insert('pas')
        
        # insert synapses
        assert syn_type in ('current', 'conductance'), "syn_type must be either 'current' or 'conductance'"
        assert syn_shape in ('alpha', 'exp'), "syn_type must be either 'alpha' or 'exp'"
        synapse_model = StandardIF.synapse_models[syn_type][syn_shape]
        self.esyn = synapse_model(self, 0.5)
        self.isyn = synapse_model(self, 0.5)

        # insert current source
        self.stim = neuron.IClamp(self, 0.5, delay=0, dur=1e12, amp=i_offset)
        
        # insert spike reset mechanism
        self.spike_reset = ResetRefrac(self, 0.5)
        self.spike_reset.vspike = 40 # (mV) spike height
        self.source = self.spike_reset
        
        # process arguments
        for name in ('tau_m', 'cm', 'v_rest', 'v_thresh', 't_refrac',
                     'i_offset', 'v_reset', 'v_init', 'tau_e', 'tau_i'):
            setattr(self, name, locals()[name])
        if self.v_reset is None:
            self.v_reset = self.v_rest
        if self.v_init is None:
            self.v_init = self.v_rest
        if syn_type == 'conductance':
            self.e_e = e_e
            self.e_i = e_i
            
        # need to deal with FinitializeHandler for v_init?
        #self.fih = neuron.FInitializeHandler("memb_init()", obj=self)
        self.fih2 = neuron.FInitializeHandler('print "kjyuyv"', obj=self)
        #neuron.h('objref fih3')
        #neuron.h('fih3 = new FInitializeHandler("reslugis")')
        #fih4 = neuron.h.new_FInitializeHandler(1, "kurh")
        #neuron.h('obfunc foobar() { return new FInitializeHandler(1, "kuauw") }')
        #fih5 = neuron.h.foobar()
    
    def __set_tau_m(self, value):
        self.seg.pas.g = 1e-3*self.seg.cm/value # cm(nF)/tau_m(ms) = G(uS) = 1e-6G(S). Divide by area (1e-3) to get factor of 1e-3
        
    def __get_tau_m(self):
        return 1e-3*self.seg.cm/self.seg.pas.g
    
    tau_m    = property(fget=__get_tau_m, fset=__set_tau_m)
    cm       = _new_property('seg', 'cm')
    i_offset = _new_property('stim', 'amp')
    tau_e    = _new_property('esyn', 'tau')
    tau_i    = _new_property('isyn', 'tau')
    e_e      = _new_property('esyn', 'e')
    e_i      = _new_property('isyn', 'e')
    v_rest   = _new_property('seg.pas', 'e')
    v_thresh = _new_property('spike_reset', 'vthresh')
    v_reset  = _new_property('spike_reset', 'vreset')
    t_refrac = _new_property('spike_reset', 'trefrac')
    
    # what about v_init?

    def record(self, active):
        if active:
            rec = NetCon(self.source, None)
            rec.record(self.spiketimes)
    
    def record_v(self, active):
        if active:
            self.vtrace = neuron.Vector()
            self.vtrace.record(self, 'v')
        else:
            self.vtrace = None
    
    def memb_init(self, v_init=None):
        if v_init:
            self.v_init = v_init
        self.v = v_init
        

class SpikeSource(object):
    
    def __init__(self, source_type, spiketimes=[]):
        self.source = source_type()
        if spiketimes:
            self.spiketimes = neuron.Vector(spiketimes)
            self.source.play(self.spiketimes.hoc_obj)
            self.do_not_record = True
        else:
            self.spiketimes = neuron.Vector()
            self.do_not_record = False

    def record(self, active):
        if not self.do_not_record: # for VecStims, etc, recording doesn't make sense as we already have the spike times
            if active:
                rec = NetCon(self.source, None)
                rec.record(self.spiketimes)
            

class IF_curr_alpha(StandardIF, common.IF_curr_alpha):
    """Leaky integrate and fire model with fixed threshold and alpha-function-
    shaped post-synaptic current."""
    
    translations = common.build_translations(
        ('tau_m',      'tau_m'),
        ('cm',         'cm'),
        ('v_rest',     'v_rest'),
        ('v_thresh',   'v_thresh'),
        ('v_reset',    'v_reset'),
        ('tau_refrac', 't_refrac'),
        ('i_offset',   'i_offset'),
        ('tau_syn_E',  'tau_e'),
        ('tau_syn_I',  'tau_i'),
        ('v_init',     'v_init'),
    )
    #hoc_name = "StandardIF"
    
    def __init__(self, parameters):
        common.IF_curr_alpha.__init__(self, parameters) # checks supplied parameters and adds default
                                                       # values for not-specified parameters.
        self.parameters = self.translate(self.parameters)
        #self.parameters['syn_type']  = 'current'
        #self.parameters['syn_shape'] = 'alpha'
        StandardIF.__init__(self, 'current', 'alpha', **self.parameters)

class IF_curr_exp(common.IF_curr_exp):
    """Leaky integrate and fire model with fixed threshold and
    decaying-exponential post-synaptic current. (Separate synaptic currents for
    excitatory and inhibitory synapses."""
    
    translations = common.build_translations(
        ('tau_m',      'tau_m'),
        ('cm',         'cm'),
        ('v_rest',     'v_rest'),
        ('v_thresh',   'v_thresh'),
        ('v_reset',    'v_reset'),
        ('tau_refrac', 't_refrac'),
        ('i_offset',   'i_offset'),
        ('tau_syn_E',  'tau_e'),
        ('tau_syn_I',  'tau_i'),
        ('v_init',     'v_init'),
    )
    hoc_name = "StandardIF"
    
    def __init__(self, parameters):
        common.IF_curr_exp.__init__(self, parameters)
        self.parameters = self.translate(self.parameters)
        self.parameters['syn_type']  = 'current'
        self.parameters['syn_shape'] = 'exp'


class IF_cond_alpha(common.IF_cond_alpha):
    """Leaky integrate and fire model with fixed threshold and alpha-function-
    shaped post-synaptic conductance."""
    
    translations = common.build_translations(
        ('tau_m',      'tau_m'),
        ('cm',         'cm'),
        ('v_rest',     'v_rest'),
        ('v_thresh',   'v_thresh'),
        ('v_reset',    'v_reset'),
        ('tau_refrac', 't_refrac'),
        ('i_offset',   'i_offset'),
        ('tau_syn_E',  'tau_e'),
        ('tau_syn_I',  'tau_i'),
        ('v_init',     'v_init'),
        ('e_rev_E',    'e_e'),
        ('e_rev_I',    'e_i')
    )
    hoc_name = "StandardIF"
    
    def __init__(self, parameters):
        common.IF_cond_alpha.__init__(self, parameters) # checks supplied parameters and adds default
                                                       # values for not-specified parameters.
        self.parameters = self.translate(self.parameters)
        self.parameters['syn_type']  = 'conductance'
        self.parameters['syn_shape'] = 'alpha'


class IF_cond_exp(common.IF_cond_exp):
    """Leaky integrate and fire model with fixed threshold and 
    exponentially-decaying post-synaptic conductance."""
    
    translations = common.build_translations(
        ('tau_m',      'tau_m'),
        ('cm',         'cm'),
        ('v_rest',     'v_rest'),
        ('v_thresh',   'v_thresh'),
        ('v_reset',    'v_reset'),
        ('tau_refrac', 't_refrac'),
        ('i_offset',   'i_offset'),
        ('tau_syn_E',  'tau_e'),
        ('tau_syn_I',  'tau_i'),
        ('v_init',     'v_init'),
        ('e_rev_E',    'e_e'),
        ('e_rev_I',    'e_i')
    )
    hoc_name = "StandardIF"
    
    def __init__(self, parameters):
        common.IF_cond_exp.__init__(self, parameters) # checks supplied parameters and adds default
                                                       # values for not-specified parameters.
        self.parameters = self.translate(self.parameters)
        self.parameters['syn_type']  = 'conductance'
        self.parameters['syn_shape'] = 'exp'


class IF_facets_hardware1(common.IF_facets_hardware1):
    """Leaky integrate and fire model with conductance-based synapses and fixed
    threshold as it is resembled by the FACETS Hardware Stage 1. For further
    details regarding the hardware model see the FACETS-internal Wiki:
    https://facets.kip.uni-heidelberg.de/private/wiki/index.php/WP7_NNM
    """

    translations = common.build_translations(
        ('cm',         'cm'),
        ('v_rest',     'v_rest'),
        ('v_thresh',   'v_thresh'),
        ('v_reset',    'v_reset'),
        ('tau_refrac', 't_refrac'),
        ('g_leak',     'tau_m',    "cm*1000.0/g_leak", "CM*1000.0/tau_m"),
        ('tau_syn_E',  'tau_e'),
        ('tau_syn_I',  'tau_i'),
        ('e_rev_E',    'e_e'),
        ('e_rev_I',    'e_i'),
    ) # v_init?
    hoc_name = "StandardIF"

    def __init__(self, parameters):
        common.IF_facets_hardware1.__init__(self, parameters)
        self.parameters = self.translate(self.parameters)
        self.parameters['syn_type']  = 'conductance'
        self.parameters['syn_shape'] = 'exp'
        self.parameters['i_offset']  = 0.0


class SpikeSourcePoisson(common.SpikeSourcePoisson):
    """Spike source, generating spikes according to a Poisson process."""

    translations = common.build_translations(
        ('start',    'start'),
        ('rate',     'interval',  "1000.0/rate",  "1000.0/interval"),
        ('duration', 'number',    "int(rate/1000.0*duration)", "number*interval"), # should there be a +/1 here?
    )
    hoc_name = 'SpikeSource'
   
    def __init__(self, parameters):
        common.SpikeSourcePoisson.__init__(self, parameters)
        self.parameters = self.translate(self.parameters)
        self.parameters['source_type'] = 'NetStim'    
        self.parameters['noise'] = 1
        

class SpikeSourceArray(SpikeSource, common.SpikeSourceArray):
    """Spike source generating spikes at the times given in the spike_times array."""

    translations = common.build_translations(
        ('spike_times', 'spiketimes'),
    )
    #hoc_name = 'SpikeSource'
    
    def __init__(self, parameters):
        common.SpikeSourceArray.__init__(self, parameters)
        self.parameters = self.translate(self.parameters)  
        #self.parameters['source_type'] = 'VecStim'
        SpikeSource.__init__(self, source_type=VecStim, spiketimes=self.parameters['spiketimes'])
        
        
class EIF_cond_alpha_isfa_ista(common.EIF_cond_alpha_isfa_ista):
    """
    Exponential integrate and fire neuron with spike triggered and sub-threshold
    adaptation currents (isfa, ista reps.) according to:
    
    Brette R and Gerstner W (2005) Adaptive Exponential Integrate-and-Fire Model as
    an Effective Description of Neuronal Activity. J Neurophysiol 94:3637-3642

    See also: IF_cond_exp_gsfa_grr
    """
    
    translations = (
        ('v_init',     'v_init'),
        ('w_init',     'w_init'),
        ('cm',         'cm'),
        ('tau_refrac', 'Ref'), 
        ('v_spike',    'Vspike'),
        ('v_reset',    'Vbot'),
        ('v_rest',     'EL'),
        ('tau_m',      'GL',       "cm/tau_m", "CM/GL"), # uS
        ('i_offset',   'i_offset'), 
        ('a',          'a',        0.001), # nS --> uS
        ('b',          'b'),
        ('delta_T',    'delta'), 
        ('tau_w',      'tau_w'), 
        ('v_thresh',   'Vtr'), 
        ('e_rev_E',    'e_e'),
        ('tau_syn_E',  'tau_e'), 
        ('e_rev_I',    'e_i'), 
        ('tau_syn_I',  'tau_i'),
    )
    hoc_name = "IF_BG_alpha"
    
    def __init__(self, parameters):
        common.EIF_cond_alpha_isfa_ista.__init__(self, parameters)
        self.parameters = self.translate(self.parameters)
        self.parameters['syn_type']  = 'conductance'
        self.parameters['syn_shape'] = 'alpha'