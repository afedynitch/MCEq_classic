# -*- coding: utf-8 -*-
"""
:mod:`MCEq.data` --- data management
====================================

This module includes code for bookkeeping, interfacing and
validating data structures:

- :class:`InteractionYields` manages particle interactions, obtained
  from sampling of various interaction models
- :class:`DecayYields` manages particle decays, obtained from
  sampling PYTHIA8 Monte Carlo
- :class:`HadAirCrossSections` keeps information about the inelastic,
  cross-section of hadrons with air. Typically obtained from Monte Carlo.
"""

import numpy as np
import h5py
from collections import defaultdict
from mceq_config import config
from os.path import join
from misc import normalize_hadronic_model_name, is_charm_pdgid, info

equivalences = {
    'SIBYLL': {
        130: 310,
        3212: 3122,
        -3212: -3122
    },
    'QGSJET': {
        -2212: 2212,
        -2112: 2212,
        -211: 211,
        -321: 321,
        130: 321,
        310: 321,
        2112: 2212
    }
}


class HDF5Backend(object):
    """Provides access to tabulated data stored in an HDF5 file.

    The file contains all necessary ingredients to run MCEq, i.e. no
    other files are required. This database is not maintained in git
    and it will change infrequently.
    """

    def __init__(self):

        info(2, 'Opening HDF5 file', config['mceq_db_fname'])
        self.h5fname = join(config['data_dir'], config['mceq_db_fname'])
        with h5py.File(self.h5fname, 'r') as mceq_db:
            from MCEq.misc import energy_grid
            ca = mceq_db['common'].attrs
            self.min_idx, self.max_idx, self._cuts = self._eval_energy_cuts(ca['e_grid'])
            self._energy_grid = energy_grid(ca['e_grid'][self._cuts],
                                            ca['e_bins'][self.min_idx:self.max_idx + 1],
                                            ca['widths'][self._cuts],
                                            self.max_idx - self.min_idx)
            self.dim_full = ca['e_dim']

    @property
    def energy_grid(self):
        return self._energy_grid

    def _eval_energy_cuts(self, e_centers):
        min_idx, max_idx = 0, len(e_centers)
        slice0, slice1 = None, None
        if config['e_min'] is not None:
            min_idx = slice0 = np.argmin(np.abs(e_centers - config['e_min']))
        if config['e_max'] is not None:
            max_idx = slice1 = np.argmin(np.abs(e_centers - config['e_max']))
        return min_idx, max_idx, slice(slice0,slice1)

    def _gen_db_dictionary(self, hdf_root, indptrs, equivalences={}):

        from scipy.sparse import csr_matrix
        index_d = {}
        relations = defaultdict(lambda: [])
        particle_list = []
        if 'description' in hdf_root.attrs:
            description = hdf_root.attrs['description']
        else:
            description = None
        mat_data = hdf_root[:, :]
        indptr_data = indptrs[:]
        len_data = hdf_root.attrs['len_data']

        exclude = config['adv_set']["disabled_particles"]
        read_idx = 0

        for tupidx, tup in enumerate(hdf_root.attrs['tuple_idcs']):

            if len(tup) == 4:
                parent_pdg, child_pdg = tuple(tup[:2]), tuple(tup[2:])
            elif len(tup) == 2:
                parent_pdg, child_pdg = (tup[0], 0), (tup[1], 0)
            else:
                raise Exception('Failed decoding parent-child relation.')

            if (abs(parent_pdg[0]) in exclude) or (abs(
                    child_pdg[0]) in exclude):
                read_idx += len_data[tupidx]
                continue

            particle_list.append(parent_pdg)
            particle_list.append(child_pdg)

            index_d[(parent_pdg, child_pdg)] = (csr_matrix(
                (mat_data[0, read_idx:read_idx + len_data[tupidx]],
                 mat_data[1, read_idx:read_idx + len_data[tupidx]],
                 indptr_data[tupidx, :]),
                shape=(self.dim_full,
                       self.dim_full))[self._cuts, self.
                                       min_idx:self.max_idx]).toarray()

            relations[parent_pdg].append(child_pdg)

            # Link equivalent interactions
            if parent_pdg in equivalences:
                info(20, 'Applying equivalent interaction matrices to',
                     parent_pdg)
                particle_list.append(equivalences[parent_pdg])
                index_d[(equivalences[parent_pdg],
                         child_pdg)] = index_d[(parent_pdg, child_pdg)]
                relations[equivalences[parent_pdg]] = relations[parent_pdg]

            read_idx += len_data[tupidx]

        return {
            'parents': sorted(relations.keys()),
            'particles': sorted(list(set(particle_list))),
            'relations': dict(relations),
            'index_d': dict(index_d),
            'description': description
        }

    def _check_subgroup_exists(self, subgroup, mname):
        available_models = subgroup.keys()
        if mname not in available_models:
            info(0, 'Invalid choice/model', mname)
            info(0, 'Choose from:\n', '\n'.join(available_models))
            raise Exception('Unknown selections.')

    def interaction_db(self, interaction_model_name):

        mname = normalize_hadronic_model_name(interaction_model_name)
        with h5py.File(self.h5fname, 'r') as mceq_db:
            self._check_subgroup_exists(mceq_db['hadronic_interactions'],
                                        mname)
            if 'SIBYLL' in mname:
                eqv = equivalences['SIBYLL']
            elif 'QGSJET' in mname:
                eqv = equivalences['QGSJET']
            int_index = self._gen_db_dictionary(
                mceq_db['hadronic_interactions'][mname],
                mceq_db['hadronic_interactions'][mname + '_indptrs'],
                equivalences=eqv)

            # Append electromagnetic interaction matrices from EmCA
            if config['enable_em']:
                info(2, 'Injecting EmCA matrices into interaction_db.')
                self._check_subgroup_exists(mceq_db, 'electromagnetic')
                em_index = self._gen_db_dictionary(
                    mceq_db['electromagnetic']['emca_mats'],
                    mceq_db['electromagnetic']['emca_mats' + '_indptrs'])
                int_index['parents'] = sorted(int_index['parents'] +
                                              em_index['parents'])
                int_index['particles'] = sorted(
                    list(set(int_index['particles'] + em_index['particles'])))
                int_index['relations'].update(em_index['relations'])
                int_index['index_d'].update(em_index['index_d'])
        
        if int_index['description'] is not None:
            int_index['description'] += '\nInteraction model name: ' + mname
        else:
            int_index['description'] = 'Interaction model name: ' + mname

        return int_index

    def decay_db(self, decay_dset_name):

        with h5py.File(self.h5fname, 'r') as mceq_db:
            self._check_subgroup_exists(mceq_db['decays'], decay_dset_name)
            dec_index = self._gen_db_dictionary(
                mceq_db['decays'][decay_dset_name],
                mceq_db['decays'][decay_dset_name + '_indptrs'])

            if config["muon_helicity_dependence"]:
                info(2, 'Using helicity dependent decays.')
                custom_index = self._gen_db_dictionary(
                    mceq_db['decays']['custom_decays'],
                    mceq_db['decays']['custom_decays' + '_indptrs'])
                # for tup in custom_index['index_d']:
                # if tup not in dec_index['index_d']:
                #     info(2, tup, 'was not in normal decay_db.')
                #     continue

                info(2, 'Replacing decay from custom decay_db.')
                dec_index['index_d'].update(custom_index['index_d'])

                # Remove manually TODO: Kaon decays to muons assumed only two-body
                _ = dec_index['index_d'].pop(((211, 0), (-13, 0)))
                _ = dec_index['index_d'].pop(((-211, 0), (13, 0)))
                _ = dec_index['index_d'].pop(((321, 0), (-13, 0)))
                _ = dec_index['index_d'].pop(((-321, 0), (13, 0)))
                # _ = dec_index['index_d'].pop(((211,0),(14,0)))
                # _ = dec_index['index_d'].pop(((-211,0),(-14,0)))
                # _ = dec_index['index_d'].pop(((321,0),(14,0)))
                # _ = dec_index['index_d'].pop(((-321,0),(-14,0)))

                dec_index['relations'] = defaultdict(lambda: [])
                dec_index['particles'] = []

                for idx_tup in dec_index['index_d']:
                    parent, child = idx_tup
                    dec_index['relations'][parent].append(child)
                    dec_index['particles'].append(parent)
                    dec_index['particles'].append(child)

                dec_index['parents'] = sorted(dec_index['relations'].keys())
                dec_index['particles'] = sorted(
                    list(set(dec_index['particles'])))

        return dec_index

    def cs_db(self, interaction_model_name):

        mname = normalize_hadronic_model_name(interaction_model_name)
        with h5py.File(self.h5fname, 'r') as mceq_db:
            self._check_subgroup_exists(mceq_db['cross_sections'], mname)
            cs_db = mceq_db['cross_sections'][mname]
            cs_data = cs_db[:]
            index_d = {}
            parents = list(cs_db.attrs['projectiles'])
            for ip, p in enumerate(parents):
                index_d[p] = cs_data[self._cuts, ip]

            # Append electromagnetic interaction cross sections from EmCA
            if config["enable_em"]:
                self._check_subgroup_exists(mceq_db, 'electromagnetic')
                em_cs = mceq_db["electromagnetic"]['cs'][:]
                em_parents = list(
                    mceq_db["electromagnetic"]['cs'].attrs['projectiles'])
                for ip, p in enumerate(em_parents):
                    if p in index_d:
                        raise Exception(
                            'EM cross sections already in database?')

                    index_d[p] = em_cs[ip, self._cuts]
                parents += em_parents

        return {'parents': parents, 'index_d': index_d}

    def continuous_loss_db(self, medium='air'):

        with h5py.File(self.h5fname, 'r') as mceq_db:
            self._check_subgroup_exists(mceq_db['continuous_losses'], medium)
            cl_db = mceq_db['continuous_losses'][medium]

            index_d = {}
            for pstr in cl_db.keys():
                for hel in [0, 1, -1]:
                    index_d[(int(pstr),
                             hel)] = cl_db[pstr][self._cuts]
            if config['enable_em']:
                self._check_subgroup_exists(mceq_db, 'electromagnetic')
                for hel in [0, 1, -1]:
                    index_d[(11, hel)] = mceq_db["electromagnetic"]['dEdX 11'][
                        self._cuts]
                    index_d[(-11, hel)] = mceq_db["electromagnetic"][
                        'dEdX -11'][self._cuts]

        return {'parents': sorted(index_d.keys()), 'index_d': index_d}


class Interactions(object):
    """Class for managing the dictionary of interaction yield matrices.

    The class unpickles a dictionary, which contains the energy grid
    and :math:`x` spectra, sampled from hadronic interaction models.



    A list of available interaction model keys can be printed by::

        $ print yield_obj

    Args:
      interaction_model (str): name of the interaction model
      charm_model (str, optional): name of the charm model

    """

    def __init__(self, mceq_hdf_db):
        from collections import defaultdict

        #: MCEq HDF5Backend reference
        self.mceq_db = mceq_hdf_db
        #: reference to energy grid
        self.energy_grid = mceq_hdf_db.energy_grid
        #: List of active parents
        self.parents = None
        #: List of all known particles
        self.particles = None
        #: Dictionary parent/child relations
        self.relations = None
        #: Dictionary containing the distribuiton matrices
        self.index_d = None
        #: String containing the desciption of the model
        self.description = None

        #: (str) Interaction Model name
        self.iam = None
        # #: (tuple) selection of a band of coeffictients (in xf)
        # self.band = None
        #: (tuple) modified particle combination for error prop.
        self.mod_pprod = defaultdict(lambda: {})

    def load(self, interaction_model, parent_list=None):
        from MCEq.misc import is_charm_pdgid
        self.iam = normalize_hadronic_model_name(interaction_model)
        # Load tables and index from file
        index = self.mceq_db.interaction_db(self.iam)

        self.parents = index['parents']
        self.particles = index['particles']
        self.relations = index['relations']
        self.index_d = index['index_d']
        self.description = index['description']

        # Advanced options
        regenerate_index = False
        if parent_list is not None:
            self.parents = [p for p in self.parents if p in parent_list]
            regenerate_index = True
        if (config['adv_set']['disable_charm_pprod']):
            self.parents = [
                p for p in self.parents if not is_charm_pdgid(p[0])
            ]
            regenerate_index = True
        if (config['adv_set']['disable_interactions_of_unstable']):
            self.parents = [
                p for p in self.parents
                if p[0] not in [2212, 2112, -2212, -2112]
            ]
            regenerate_index = True
        if (config['adv_set']['allowed_projectiles']):
            self.parents = [
                p for p in self.parents
                if p in config['adv_set']['allowed_projectiles']
            ]
            regenerate_index = True
        if regenerate_index:
            self.particles = []
            for p in self.relations.keys():
                if p not in self.parents:
                    _ = self.relations.pop(p, None)
                    continue
                self.particles.append(p)
                self.particles += self.relations[p]
            self.particles = sorted(list(set(self.particles)))

        if config['adv_set']['disable_direct_leptons'] or 'DPMJET' in self.iam:
            info(5, 'Hotfix for DPMJET, no direct leptons')
            for p in self.relations.keys():
                self.relations[p] = [
                    c for c in self.relations[p] if not 10 < abs(c[0]) < 20
                ]

    def __getitem__(self, key):
        return self.get_matrix(*key)

    def __contains__(self, key):
        """Defines the `in` operator to look for particles"""
        return key in self.parents

    def _gen_mod_matrix(self, x_func, *args):
        """Creates modification matrix using an (x,E)-dependent function.

        :math:`x = \\frac{E_{\\rm primary}}{E_{\\rm secondary}}` is the
        fraction of secondary particle energy. ``x_func`` can be an
        arbitrary function modifying the :math:`x_\\text{lab}` distribution.
        Run this method each time you change ``x_func``, or its parameters,
        not each time you change modified particle.
        The ``args`` are passed to the function.

        Args:
          x_func (object): reference to function
          args (tuple): arguments of `x_func`

        Returns:
          (numpy.array): modification matrix
        """
        from MCEq.misc import gen_xmat
        info(2, 'Generating modification matrix for', x_func.__name__, args)

        xmat = gen_xmat(self.energy_grid)

        # select the relevant slice of interaction matrix
        modmat = x_func(xmat, self.energy_grid.c, *args)
        # Set lower triangular indices to 0. (should be not necessary)
        modmat[np.tril_indices(self.energy_grid.d, -1)] = 0.

        return modmat

    def _set_mod_pprod(self, prim_pdg, sec_pdg, x_func, args):
        """Sets combination of parent/secondary for error propagation.

        The production spectrum of ``sec_pdg`` in interactions of
        ``prim_pdg`` is modified according to the function passed to
        :func:`InteractionYields.init_mod_matrix`

        Args:
          prim_pdg (int): interacting (primary) particle PDG ID
          sec_pdg (int): secondary particle PDG ID
        """

        # Short cut for the pprod list
        mpli = self.mod_pprod
        pstup = (prim_pdg, sec_pdg)

        if config['use_isospin_sym'] and prim_pdg not in [2212, 2112]:
            raise Exception('Unsupported primary for isospin symmetries.')

        if (x_func.__name__, args) in mpli[(pstup)]:
            info(
                5, ' no changes to particle production' +
                ' modification matrix of {0}/{1} for {2},{3}'.format(
                    prim_pdg, sec_pdg, x_func.__name__, args))
            return False

        # Check function with same mode but different parameter is supplied
        for (xf_name, fargs) in mpli[pstup].keys():
            if (xf_name == x_func.__name__) and (fargs[0] == args[0]):
                info(1, 'Warning. If you modify only the value of a function,',
                     'unset and re-apply all changes')
                return False

        info(
            2, 'modifying modify particle production' +
            ' matrix of {0}/{1} for {2},{3}').format(prim_pdg, sec_pdg,
                                                     x_func.__name__, args)

        kmat = self._gen_mod_matrix(x_func, *args)
        mpli[pstup][(x_func.__name__, args)] = kmat

        info(5, 'modification "strength"',
             np.sum(kmat) / np.count_nonzero(kmat, dtype=np.float))

        if not config['use_isospin_sym']:
            return True

        prim_pdg, symm_pdg = 2212, 2112
        if prim_pdg == 2112:
            prim_pdg = 2112
            symm_pdg = 2212

        # p->pi+ = n-> pi-, p->pi- = n-> pi+
        if abs(sec_pdg) == 211:
            # Add the same mod to the isospin symmetric particle combination
            mpli[(symm_pdg, -sec_pdg)][('isospin', args)] = kmat

            # Assumption: Unflavored production coupled to the average
            # of pi+ and pi- production

            if np.any([p in self.parents for p in [221, 223, 333]]):

                unflv_arg = None
                if (prim_pdg, -sec_pdg) not in mpli:
                    # Only pi+ or pi- (not both) have been modified
                    unflv_arg = (args[0], 0.5 * args[1])

                if (prim_pdg, -sec_pdg) in mpli:
                    # Compute average of pi+ and pi- modification matrices
                    # Save the 'average' argument (just for meaningful printout)
                    for arg_name, arg_val in mpli[(prim_pdg, -sec_pdg)]:
                        if arg_name == args[0]:
                            unflv_arg = (args[0], 0.5 * (args[1] + arg_val))

                unflmat = self._gen_mod_matrix(x_func, *unflv_arg)

                # modify eta, omega, phi, 221, 223, 333
                for t in [(prim_pdg, 221), (prim_pdg, 223), (prim_pdg, 333),
                          (symm_pdg, 221), (symm_pdg, 223), (symm_pdg, 333)]:
                    mpli[t][('isospin', unflv_arg)] = unflmat

        # Charged and neutral kaons
        elif abs(sec_pdg) == 321:
            # approx.: p->K+ ~ n-> K+, p->K- ~ n-> K-
            mpli[(symm_pdg, sec_pdg)][('isospin', args)] = kmat
            k0_arg = (args[0], 0.5 * args[1])
            if (prim_pdg, -sec_pdg) in mpli:
                # Compute average of K+ and K- modification matrices
                # Save the 'average' argument (just for meaningful printout)
                for arg_name, arg_val in mpli[(prim_pdg, -sec_pdg)]:
                    if arg_name == args[0]:
                        k0_arg = (args[0], 0.5 * (args[1] + arg_val))

            k0mat = self._gen_mod_matrix(x_func, *k0_arg)

            # modify K0L/S
            for t in [(prim_pdg, 310), (prim_pdg, 130), (symm_pdg, 310),
                      (symm_pdg, 130)]:
                mpli[t][('isospin', k0_arg)] = k0mat

        elif abs(sec_pdg) == 411:
            ssec = np.sign(sec_pdg)
            mpli[(prim_pdg, ssec * 421)][('isospin', args)] = kmat
            mpli[(prim_pdg, ssec * 431)][('isospin', args)] = kmat
            mpli[(symm_pdg, sec_pdg)][('isospin', args)] = kmat
            mpli[(symm_pdg, ssec * 421)][('isospin', args)] = kmat
            mpli[(symm_pdg, ssec * 431)][('isospin', args)] = kmat

        # Leading particles
        elif abs(sec_pdg) == prim_pdg:
            mpli[(symm_pdg, symm_pdg)][('isospin', args)] = kmat
        elif abs(sec_pdg) == symm_pdg:
            mpli[(symm_pdg, prim_pdg)][('isospin', args)] = kmat
        else:
            raise Exception('No isospin relation found for secondary' +
                            str(sec_pdg))

        # Tell MCEqRun to regenerate the matrices if something has changed
        return True

    def print_mod_pprod(self):
        """Prints the active particle production modification.
        """

        for i, (prim_pdg, sec_pdg) in enumerate(sorted(self.mod_pprod)):
            for j, (argname, argv) in enumerate(self.mod_pprod[(prim_pdg,
                                                                sec_pdg)]):
                info(
                    2,
                    '{0}: {1} -> {2}, func: {3}, arg: {4}'.format(
                        i + j, prim_pdg, sec_pdg, argname, argv),
                    no_caller=True)

    def get_matrix(self, parent, child):
        """Returns a ``DIM x DIM`` yield matrix.

        Args:
          parent (int): PDG ID of parent particle
          child (int): PDG ID of final state child/secondary particle
        Returns:
          numpy.array: yield matrix

        Note:
          In the current version, the matrices have to be multiplied by the
          bin widths. In later versions they will be stored with the multiplication
          carried out.
        """
        info(20, 'entering with', parent, child)
        if child not in self.relations[parent]:
            raise Exception(("trying to get empty matrix {0} -> {1}").format(
                parent, child))

        m = self.index_d[(parent, child)]

        if config['adv_set']['disable_leading_mesons'] and abs(child) < 2000 \
                and (parent, -child) in self.index_d.keys():
            m_anti = self.index_d[(parent, -child)]
            ie = 50
            info(2, 'sum in disable_leading_mesons',
                 (np.sum(m[:, ie - 30:ie]) - np.sum(m_anti[:, ie - 30:ie])))

            if (np.sum(m[:, ie - 30:ie]) - np.sum(m_anti[:, ie - 30:ie])) > 0:
                info(2, 'inverting meson due to leading particle veto.', child,
                     '->', -child)
                m = m_anti
            else:
                info(2, 'no inversion since child not leading', child)
        else:
            info(20, 'no meson inversion in leading particle veto.', parent,
                 child)

        if (parent, child) in self.mod_pprod.keys():
            info(
                2, 'using modified particle production for {0}/{1}'.format(
                    parent, child))
            i = 0
            for args, mmat in self.mod_pprod[(parent, child)].items():
                info(10, i, (parent, child), args, np.sum(mmat), np.sum(m))
                i += 1
                return m * mmat

        return m


class Decays(object):
    """Class for managing the dictionary of decay yield matrices.

    The class un-pickles a dictionary, which contains :math:`x`
    spectra of decay products/childs, sampled from PYTHIA 8
    Monte Carlo.

    Args:
      parent_list (list, optional): list of particle parents from
                                    interaction model
    """

    def __init__(self, mceq_hdf_db, default_decay_dset='full_decays'):

        #: MCEq HDF5Backend reference
        self.mceq_db = mceq_hdf_db
        #: reference to energy grid
        self.energy_grid = mceq_hdf_db.energy_grid
        #: (list) List of particles in the decay matrices
        self.parent_list = []
        self._default_decay_dset = default_decay_dset

    def load(self, parent_list=None, decay_dset=None):
        # Load tables and index from file
        if decay_dset is None:
            decay_dset = self._default_decay_dset

        index = self.mceq_db.decay_db(decay_dset)

        self.parents = index['parents']
        self.particles = index['particles']
        self.relations = index['relations']
        self.index_d = index['index_d']
        self.description = index['description']
        # Advanced options
        regenerate_index = False
        if (parent_list):
            # Take only the parents provided by the list
            self.parents = [p for p in self.parents if p in parent_list]
            # Add the decay products, which can become new parents
            self.parents += sorted(
                list(
                    set([p for p in self.parents for p in self.relations[p]])))
            regenerate_index = True

        if (config['adv_set']['disable_decays']):
            self.parents = [
                p for p in self.parents
                if p[0] not in config['adv_set']['disable_decays']
            ]
            regenerate_index = True
        if regenerate_index:
            self.particles = []
            for p in self.relations.keys():
                if p not in self.parents:
                    _ = self.relations.pop(p, None)
                    continue
                self.particles.append(p)
                self.particles += self.relations[p]
            self.particles = sorted(list(set(self.particles)))

    def __getitem__(self, key):
        return self.get_matrix(*key)

    def __contains__(self, key):
        """Defines the `in` operator to look for particles"""
        return key in self.parents

    def children(self, parent_pdg):

        if parent_pdg not in self.relations:
            raise Exception(
                'Parent {0} not in decay database.'.format(parent_pdg))

        return self.relations[parent_pdg]

    def get_matrix(self, parent, child):
        """Returns a ``DIM x DIM`` decay matrix.
        Args:
          parent (int): PDG ID of parent particle
          child (int): PDG ID of final state child particle
        Returns:
          numpy.array: decay matrix
        Note:
          In the current version, the matrices have to be multiplied by the
          bin widths. In later versions they will be stored with the multiplication
          carried out.
        """
        info(20, 'entering with', parent, child)
        if child not in self.relations[parent]:
            raise Exception(("trying to get empty matrix {0} -> {1}").format(
                parent, child))

        return self.index_d[(parent, child)]


class InteractionCrossSections(object):
    """Class for managing the dictionary of hadron-air cross-sections.

    The class unpickles a dictionary, which contains proton-air,
    pion-air and kaon-air cross-sections tabulated on the common
    energy grid.

    Args:
      interaction_model (str): name of the interaction model
    """
    #: unit - :math:`\text{GeV} \cdot \text{fm}`
    GeVfm = 0.19732696312541853
    #: unit - :math:`\text{GeV} \cdot \text{cm}`
    GeVcm = GeVfm * 1e-13
    #: unit - :math:`\text{GeV}^2 \cdot \text{mbarn}`
    GeV2mbarn = 10.0 * GeVfm**2
    #: unit conversion - :math:`\text{mbarn} \to \text{cm}^2`
    mbarn2cm2 = GeVcm**2 / GeV2mbarn

    def __init__(self, mceq_hdf_db, interaction_model='SIBYLL2.3c'):

        #: MCEq HDF5Backend reference
        self.mceq_db = mceq_hdf_db
        #: reference to energy grid
        self.energy_grid = mceq_hdf_db.energy_grid
        #: List of active parents
        self.parents = None
        #: Dictionary containing the distribuiton matrices
        self.index_d = None
        #: (str) Interaction Model name
        self.iam = normalize_hadronic_model_name(interaction_model)
        # Load defaults
        self.load(interaction_model)

    def __getitem__(self, parent):
        """Return the cross section in :math:`\\text{cm}^2` as a dictionary lookup."""
        return self.get_cs(parent)

    def __contains__(self, key):
        """Defines the `in` operator to look for particles"""
        return key in self.parents

    def load(self, interaction_model):
        #: (str) Interaction Model name
        self.iam = normalize_hadronic_model_name(interaction_model)
        # Load tables and index from file
        index = self.mceq_db.cs_db(self.iam)

        self.parents = index['parents']
        self.index_d = index['index_d']

    def get_cs(self, parent, mbarn=False):
        """Returns inelastic ``parent``-air cross-section
        :math:`\\sigma_{inel}^{proj-Air}(E)` as vector spanned over
        the energy grid.

        Args:
          parent (int): PDG ID of parent particle
          mbarn (bool,optional): if ``True``, the units of the cross-section
                                 will be :math:`mbarn`, else :math:`\\text{cm}^2`

        Returns:
          numpy.array: cross-section in :math:`mbarn` or :math:`\\text{cm}^2`
        """

        message_templ = 'HadAirCrossSections(): replacing {0} with {1} cross-section'
        scale = 1.0
        if not mbarn:
            scale = self.mbarn2cm2
        if parent in self.index_d.keys():
            return scale * self.index_d[parent]
        elif abs(parent) in [411, 421, 431]:
            info(15, message_templ.format('D', 'K+-'))
            return scale * self.index_d[321]
        elif abs(parent) in [4332, 4232, 4132]:
            info(15, message_templ.format('charmed baryon', 'nucleon'))
            return scale * self.index_d[2212]
        elif abs(parent) > 2000 and abs(parent) < 5000:
            info(15, message_templ.format(parent, 'nucleon'))
            return scale * self.index_d[2212]
        elif 5 < abs(parent) < 23:
            info(15, 'returning 0 cross-section for lepton', parent)
            return np.zeros_like(self.index_d[2212])
        else:
            info(15, message_templ.format(parent, 'pion'))
            return scale * self.index_d[211]


class ContinuousLosses(object):
    """Class for managing the dictionary of hadron-air cross-sections.

    The class unpickles a dictionary, which contains proton-air,
    pion-air and kaon-air cross-sections tabulated on the common
    energy grid.

    Args:
      interaction_model (str): name of the interaction model
    """

    def __init__(self, mceq_hdf_db, material='air'):

        #: MCEq HDF5Backend reference
        self.mceq_db = mceq_hdf_db
        #: reference to energy grid
        self.energy_grid = mceq_hdf_db.energy_grid
        #: List of active parents
        self.parents = None
        #: Dictionary containing the distribuiton matrices
        self.index_d = None
        # Load defaults
        self.load_db(material)

    def __getitem__(self, parent):
        """Return the cross section in :math:`\\text{cm}^2` as a dictionary lookup."""
        return self.index_d[parent]

    def __contains__(self, key):
        """Defines the `in` operator to look for particles"""
        return key in self.parents

    def load_db(self, material):
        # Load tables and index from file
        index = self.mceq_db.continuous_loss_db(material)

        self.parents = index['parents']
        self.index_d = index['index_d']