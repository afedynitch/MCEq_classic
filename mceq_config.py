"""MCEq RC1 config file """

import sys
import platform
import os.path as path
base_path = path.dirname(path.abspath(__file__))
sys.path.append(base_path)
sys.path.append(base_path + "/CRFluxModels")
sys.path.append(base_path + "/ParticleDataTool")
sys.path.append(base_path + "/Python-NRLMSISE-00")
sys.path.append(base_path + "/c-NRLMSISE-00")

# determine shared library extension and MKL path
libext = None
mkl_default = path.join(sys.prefix, 'lib', 'libmkl_rt')

if platform.platform().find('Linux') != -1:
    libext = '.so'
elif platform.platform().find('Darwin') != -1:
    libext = '.dylib'
else:
    #Windows case
    mkl_default = path.join(sys.prefix, 'Library', 'bin', 'mkl_rt')
    libext = '.dll'

config = {

    # Debug flag for verbose printing, 0 silences MCEq entirely
    "debug_level": 1,
    # Print module name in debug output
    "print_module": True,
    #=========================================================================
    # Paths and library locations
    #=========================================================================

    # Directory where the data files for the calculation are stored
    "data_dir": path.join(base_path, 'data'),

    # File name of the MCEq database
    "mceq_db_fname": "mceq_db_fine.h5",

    # full path to libmkl_rt.[so/dylib] (only if kernel=='MKL')
    "MKL_path": mkl_default + libext,
    #=========================================================================
    # Atmosphere and geometry settings
    #=========================================================================

    # Atmospheric model in the format: (model, (arguments))
    "density_model": ('CORSIKA', ('BK_USStd', None)),
    # "density_model": ('MSIS00_IC',('SouthPole','January')),
    # "density_model": ('GeneralizedTarget', None),

    # Definition of prompt: default ctau < 0.123 cm (that of D0)
    "prompt_ctau": 0.123,

    # Average mass of target (for cross section calculations)
    # Change parameter only in combination with interaction model setting.
    # By default all inclusive cross sections are calculated for air targets
    # expect those with '_pp' suffix.
    "A_target": 14.5,  # <A> = 14.5 for air

    #parameters for EarthGeometry
    "r_E": 6391.e3,  # Earth radius in m
    "h_obs": 0.,  # observation level in m
    "h_atm": 112.8e3,  # top of the atmosphere in m

    #Default parameters for GeneralizedTarget
    "len_target": 1000.,  # Total length of the target [m]
    "env_density": 0.001225,  # density of default material in g/cm^3
    "env_name": "air",
    # Approximate value for the maximum density expected. Needed for the
    # resonance approximation.
    "max_density": 0.001225,

    #===========================================================================
    # Parameters of numerical integration
    #===========================================================================

    # Minimal energy for grid has to be > 1e-5 GeV
    "e_min" : 1.,#8.4e-2,

    # Maximal energy for grid has to be < 1e12 GeV
    "e_max" : 1e13,

    # Enable electromagnetic cascade with matrices from EmCA
    "enable_em" : True,

    # Selection of integrator (euler/odepack)
    "integrator": "euler",

    # euler kernel implementation (numpy/MKL/CUDA).
    # With serious nVidia GPUs CUDA a few times faster than MKL
    "kernel_config": "MKL",

    #Number of MKL threads (for sparse matrix multiplication the performance
    #advantage from using more than 1 thread is limited by memory bandwidth)
    "MKL_threads": 24,

    # Floating point precision: 32-bit results in speed-up with CUDA.
    # Do not use with MKL, it can result in false results and slow down.
    "FP_precision": 64,

    #parameters for the odepack integrator. More details at
    #http://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.ode.html#scipy.integrate.ode
    "ode_params": {
        'name': 'lsoda',
        'method': 'bdf',
        'nsteps': 1000,
        # 'max_step': 10.0,
        'rtol': 0.01
    },

    #=========================================================================
    # Advanced settings
    #=========================================================================

    # Compact mode: Create and use a compact version of the secondary particle
    # production, where most of the the exotic particles are integrated out, such
    # that only pions, kaons, nucleons, lambdas, lightest charm and leading
    # unflavored particles remain in the coupled system. Decay chains, for
    # example via rho -> pi pi are inlcuded in the p-> pi distribution by
    # analytical integration.
    # While the performace gain can be significant, with mostly very small
    # precision loss < 1% at low energies ~5% above PeV, the main purpose
    # is to have a clean interpretation definition of secondary particle
    # production, consitent with stable particle definitions of accelerator
    # experiments. Here, ctau => 2.5 cm (K0S).
    "compact_mode": True,

    # The leading process is can be either decay or interaction. This depends
    # on the target density and it is usually chosen automatically. For
    # advanced applications one can force "interactions" to be the dominant
    # process. Essentially this affects how the adaptive step size is computed.
    "leading_process" : "decays",   

    # Ratio of decay_length/interaction_length where particle interactions
    # are neglected and the resonance approximation is used
    # 0.5 ~ precision loss <+3% speed gain ~ factor 10
    # If smoothness and shape accuracy for prompt flux is crucial, use smaller
    # values around 0.1 or 0.05
    "hybrid_crossover": 0.5,

    # Muon energy loss according to Kokoulin et al.
    "enable_muon_energy_loss": True,

    # enable EM ionization loss
    "enable_em_ion" : True,
    
    # When using modified particle production matrices use
    # isospin symmetries to determine the corresponding
    # modification for neutrons and K0L/K0S
    "use_isospin_sym": True,

    # Helicity dependent muons decays from analytical expressions
    "muon_helicity_dependence":False,

    # All of the hadronic interaction models can simulate nucleon-air
    # interactions down to ~60 GeV (lab frame). This limits the
    # physically valid range of MCEq to E_lepton ~> 30 GeV. To fill this
    # gap, one shall extend the high energy model with a low energy model.
    # Currently the only choice is DPMJET-III-2017.1.
    # Around the transition energy, MCEq linearly interpolates between
    # neighboring energy bins of the two models, using the a number of
    # bins specified below.
    "low_energy_extension": {
        "enabled": True,
        "le_model": 'DPMJET-III-2017.1',
        # "le_model": 'DPMJET-III',
        "he_le_transition": 80,  # GeV (not recommended to go below 80)
        "nbins_interp": 3,
        # This flag controls what to do with processes, which are not
        # included in DPMJET, such as re-interactions of rare baryons
        # or charm particles. If set to true these processes will be
        # included in the merged model, but they will not be extended
        # in the low energy range. If False, these processes will be
        # simply ignored. In all normal cases there will be no
        # difference. In particular in combination with the compact
        # mode, this case doesn't even occur and output is identical.
        "use_unknown_cs": True,
    },

    # Advanced settings (some options might be obsolete/not working)
    "adv_set": {
        # Disable particle production by all hadrons, except nucleons
        "disable_interactions_of_unstable": False,

        # Disable particle production by charm *projectiles* (interactions)
        "disable_charm_pprod": False,

        # Disable production of charm *secondaries* for DPMJET-III
        "disable_dpmjet_charm": True,

        # Disable resonance/prompt contribution (this group of options
        # is either obsolete or needs maintenance.)
        # "disable_resonance_decay": False,

        # Allow only those particles to be projectiles (incl. anti-particles)
        # Faster initialization,
        # For inclusive lepton flux computations:
        # precision loss ~ 1%, for SIBYLL2.3.X with charm 5% above 10^7 GeV
        # Might be different for yields (set_single_primary_particle)
        # For full precision or if in doubt, use []
        "allowed_projectiles": [2212, 2112, 211, 321, 130, 11, 22],

        # Disable particle (production)
        "disabled_particles": [10313],

        # Disable leptons coming from prompt hadron decays at the vertex
        "disable_direct_leptons": False,

        # Difficult to explain parameter
        'disable_leading_mesons': False,

        # Do not apply mixing to these particles
        "exclude_from_mixing": [],

        # Switch off decays. E.g., disable muon decay with [13,-13]
        "disable_decays": [],

        # Force particles to be treated as resonance (astrophysical muons)
        "force_resonance": [15],

        # Disable mixing between resonance approx. and full propagation
        "no_mixing": False
    }
}

# Particles for compact mode
standard_particles = [
    11, 12, 13, 14, 16, 211, 321, 2212, 2112, 3122, 411, 421, 431
]

# Anti-particles
standard_particles += [-pid for pid in standard_particles]

# unflavored particles
# append 221, 223, 333, if eta, omega and phi needed directly
standard_particles += [22, 130, 310]  #, 221, 223, 333]


def mceq_config_without(key_list):
    r = dict(config)  # make a copy
    for key in key_list:
        del r[key]
    return r
