# -*- coding: utf-8 -*-
"""
:mod:`MCEq.data_utils` --- file operations on MCEq databases
============================================================

This module contains function to convert and manage data files
for MCEq.

- :func:`convert_to_compact` converts an interaction model file
  into "compact" mode
- :func:`extend_to_low_energies` extends an interaction model file
  with an low energy interaction model using interpolation
"""

import numpy as np
from mceq_config import config, standard_particles
import MCEq.data
from MCEq.particlemanager import _pdata
from MCEq.misc import is_charm_pdgid, info

def create_compact_low_e_db(mceq_db):
    pass

def convert_to_compact(fname):
    r"""Converts an interaction model dictionary to "compact" mode.

    This function takes a compressed yield file, where all secondary
    particle types known to the particular model are expected to be
    final state particles (set stable in the MC), and converts it
    to a new compressed yield file which contains only production channels
    to the most important particles (for air-shower and inclusive lepton
    calculations).

    The production of short lived particles and resonances is taken into
    account by executing the convolution with their decay distributions into
    more stable particles, until only final state particles are left. The list
    of "important" particles is defined in the standard_particles variable below.
    This results in a feed-down corretion, for example the process (chain)
    :math:`p + A \to \rho + X \to \pi + \pi + X` becomes simply
    :math:`p + A \to \pi + \pi + X`.
    The new interaction yield file obtains the suffix `_compact` and it
    contains only those final state secondary particles:

    .. math::

        \pi^+, K^+, K^0_{S,L}, p, n, \bar{p}, \bar{n}, \Lambda^0,
        \bar{\Lambda^0}, \eta, \phi, \omega, D^0, D^+, D^+_s +
        {\rm c.c.} + {\rm leptons}

    The compact mode has the advantage, that the production spectra stored in
    this dictionary are directly comparable to what accelerators consider as
    stable particles, defined by a minimal life-time requirement. Using the
    compact mode is recommended for most applications, which use
    :func:`MCEq.core.MCEqRun.set_mod_pprod` to modify the spectrum of secondary
    hadrons.

    For some interaction models, the performance advantage can be around 50\%.
    The precision loss is negligible at energies below 100 TeV, but can increase
    up to a few \% at higher energies where prompt leptons dominate. This is
    because also very short-lived charmed mesons and baryons with small branching
    ratios into leptons can interact with the atmosphere and lose energy before
    decay.

    For `QGSJET`, compact and normal mode are identical, since the model does not
    produce resonances or rare mesons by design.


    Args:
      fname (str): name of compressed yield (.bz2) file
    """

    import os
    import cPickle as pickle
    from bz2 import BZ2File

    dpm_di = None
    if fname.endswith('_ledpm.bz2'):

        info(1,"Low energy extension requested", fname)

        dpmpath = os.path.join(
            config['data_dir'],
            config['low_energy_extension']['le_model'].translate(
                None, "-.").upper() + '_yields_compact.bz2')

        info(2,"convert_to_compact(): looking for file", dpmpath)

        if not os.path.isfile(dpmpath):
            convert_to_compact(dpmpath)
        try:
            dpm_di = pickle.load(BZ2File(dpmpath))
        except IOError:
            raise Exception(
                "convert_to_compact(): Error, low-energy model file expected but"
                + "not found.\n", dpmpath)

    # If file name is supplied as ppd or with compact including, modify to
    # expected format
    fn_he = fname.replace('.ppd', '.bz2').replace('_compact', '').replace(
        '_ledpm', '')
    if not os.path.isfile(fn_he):
        fn_he = os.path.join(config["data_dir"], fn_he)

    info(1, "Attempting conversion of", fn_he)

    # Load the yield dictionary (without multiplication with bin widths)
    mdi = pickle.load(BZ2File(fn_he))

    # Load the decay dictionary (with bin widths and index)
    try:
        ddi = pickle.load(
            open(
                os.path.join(config["data_dir"], config["decay_fname"]), 'rb'))
    except IOError:
        # In case the ppd file is not yet created, use the DecayYields class to
        # decompress, rotate and weight the yield files
        from MCEq.data import DecayYields
        ds = DecayYields(fname=config["decay_fname"])
        ddi = ds.decay_dict

    # projectiles
    allowed_projectiles = [2212, 2112, 211, 321, 130, 3122]

    part_d = _pdata
    ctau_pr = part_d.ctau(310)

    # Create new dictionary for the compact model version
    compact_di = {}

    def create_secondary_dict(yield_dict):
        """This is a replica of function
        :func:`MCEq.data.InteractionYields._gen_index`."""
        info(10, 'entering...')

        secondary_dict = {}
        for key, mat in sorted(yield_dict.iteritems()):
            try:
                proj, sec = key
            except ValueError:
                info(10, 'Skip additional info', key)
                continue

            if proj not in secondary_dict:
                secondary_dict[proj] = []
                info(10, proj, 'added.')

            if np.sum(mat) > 0:
                assert (sec not in secondary_dict[proj]), (
                    "Error in construction of index array: {0} -> {1}".format(
                        proj, sec))
                secondary_dict[proj].append(sec)
            else:
                info(10, 'Zeros for', proj, sec)

        return secondary_dict

    def follow_chained_decay(real_mother, mat, interm_mothers, reclev):
        """Follows the chain of decays down to the list of stable particles.

        The function follows the list of daughters of an unstable parrticle
        and computes the feed-down contribution by evaluating the convolution
        of production spectrum and decay spectrum using the formula (24)

        ..math::
            \mathbf{C}^M^p = D^\rho \cdot \ 
        :func:`MCEq.data.InteractionYields._gen_index`."""

        tab = 3 * reclev * '--' + '> '

        info(10, 'start recursion with', real_mother, interm_mothers, np.sum(
                mat),  condition=reclev == 0)
        info(30, 'enter with', real_mother, interm_mothers, np.sum(mat))

        if np.sum(mat) < 1e-30:
            info(30, 'zero matrix for', real_mother, interm_mothers,condition=np.sum(mat) < 1e-30)
        if interm_mothers[-1] not in dec_di or interm_mothers[
                -1] in standard_particles:
            info(30, tab, 'no further decays of', interm_mothers)
            return

        for d in dec_di[interm_mothers[-1]]:
            # Decay matrix
            dmat = ddi[(interm_mothers[-1], d)]
            # Matrix product D x C from the left (convolution)
            mprod = dmat.dot(mat)

            if np.sum(mprod) < 1e-40:
                info(30, tab, 'cancel recursion in', real_mother, interm_mothers, d, \
                    'since matrix is zero', np.sum(mat), np.sum(dmat), np.sum(mprod))
                continue

            if d not in standard_particles:
                info(30, tab, 'Recurse', real_mother, interm_mothers, d, np.sum(
                        mat))

                follow_chained_decay(real_mother, mprod, interm_mothers + [d],
                                     reclev + 1)
            else:
                # Track prompt leptons in prompt category
                if abs(d) in [12, 13, 14, 16]:
                    # is_prompt = bool(np.sum([(part_d.ctau(mo) <= ctau_pr or
                    #     4000 < abs(mo) < 7000 or 400 < abs(mo) < 500)
                    #     for mo in interm_mothers]))
                    is_prompt = sum(
                        [part_d.ctau(mo) <= ctau_pr
                         for mo in interm_mothers]) > 0
                    if is_prompt:
                        d = np.sign(d) * (7000 + abs(d))

                info(10, tab, 'contribute to', real_mother, interm_mothers, d)

                if (real_mother, d) in compact_di.keys():
                    info(10, tab, '+=', (real_mother, d), np.sum(mprod))
                    compact_di[(real_mother, d)] += mprod
                else:
                    info(10, tab, 'new', (real_mother, d), interm_mothers)
                    compact_di[(real_mother, d)] = mprod

        return

    # Create index of entries
    pprod_di = create_secondary_dict(mdi)
    dec_di = create_secondary_dict(ddi)

    info(10, 'Int   dict:\n', sorted(pprod_di))
    info(10, 'Decay dict:\n', sorted(dec_di))

    for proj, lsecs in sorted(pprod_di.iteritems()):

        if abs(proj) not in allowed_projectiles:
            continue

        for sec in lsecs:
            if (config['adv_set']['disable_dpmjet_charm'] and 'DPMJET' in fname
                    and is_charm_pdgid(sec)):
                info(5, 'Skip charm secodaries for DPMJET')
                continue
            # Copy all direct production in first iteration
            if sec in standard_particles:
                compact_di[(proj, sec)] = np.copy(mdi[(proj, sec)])

                info(5, 'copied', proj, '->', sec)

        for sec in lsecs:
            #Iterate over all remaining secondaries
            if sec in standard_particles:
                continue
            if (config['adv_set']['disable_dpmjet_charm'] and 'DPMJET' in fname
                    and is_charm_pdgid(sec)):
                info(5, 'Skip charm secodaries for DPMJET')
                continue

            info(10, proj, '->', sec, '->', dec_di[sec])
            #Enter recursion and calculate contribution from decay
            follow_chained_decay(proj, mdi[(proj, sec)], [sec], 0)

    # Copy metadata
    compact_di['ebins'] = np.copy(mdi['ebins'])
    compact_di['evec'] = np.copy(mdi['evec'])
    compact_di['mname'] = mdi['mname']

    if dpm_di:
        compact_di = extend_to_low_energies(compact_di, dpm_di)

    pickle.dump(compact_di, BZ2File(fname, 'wb'), protocol=-1)

    # Delete cached version if it exists
    if os.path.isfile(fname.replace('.bz2', '.ppd')):
        os.unlink(fname.replace('.bz2', '.ppd'))


def extend_to_low_energies(he_di=None, le_di=None, fname=None):
    """Interpolates between a high-energy and a low-energy interaction model.

    Theis function takes either two yield dictionaries or a file name
    of the high energy model and interpolates the matrices at the energy
    specified in `:mod:mceq_config` in the low_energy_extension section.
    The interpolation is linear in energy grid index.

    In 'compact' mode all particles should be supported by the low energy
    model. However if you don't use compact mode, some rare or exotic
    secondaries might be not supported by the low energy model. In this
    case the config option "use_unknown_cs" decides if only the high energy
    part is used or if to raise an excption.

    Args:
      he_di (dict,optional): yield dictionary of high-energy model
      le_di (dict,optional): yield dictionary of low-energy model
      fname (str,optional): file name of high-energy model yields
    """

    import cPickle as pickle
    from bz2 import BZ2File
    import os

    if (he_di and le_di) and fname:
        raise Exception(
            "extend_to_low_energies(): either dictionaries or a file name " +
            "should be specified, but not both.")

    if fname:
        info(5, "Low energy extension requested:", fname)

        # Load the yield dictionary (without multiplication with bin widths ".bz2")
        he_di = pickle.load(
            BZ2File(fname.replace('_ledpm', '').replace('.ppd', '.bz2')))

        # Load low energy model yields
        le_di = pickle.load(
            BZ2File(
                os.path.join(
                    config['data_dir'],
                    config['low_energy_extension']['le_model'].translate(
                        None, "-.").upper() + '_yields.bz2')))

    he_le_trasition = config['low_energy_extension']['he_le_transition']
    nbins_interp = config['low_energy_extension']['nbins_interp']

    egr = he_di['evec']  # will throw error

    # Find the index of transition in the energy grid
    transition_idx = np.count_nonzero(egr < he_le_trasition)
    info(5, "transition_idx={0}, transition_energy={1}".format(
            transition_idx, egr[transition_idx]))

    # Indices of the transition region (+2 because 0 and 1 are included)
    intp_indices = np.arange(
        transition_idx - nbins_interp / 2 - 1,
        transition_idx + nbins_interp / 2 + 1.1,
        1,
        dtype='int32')
    intp_scales = np.linspace(0, 1, len(intp_indices))
    intp_array = np.ones((len(egr), len(intp_scales)))
    he_int_array = intp_scales * intp_array
    le_int_array = intp_scales[::-1] * intp_array
    info(5, "int. arrays", intp_scales, intp_indices, egr[intp_indices])

    ext_di = {}

    for k in he_di.keys():
        if type(k) is not tuple:
            ext_di[k] = he_di[k]
            continue

        he_mat = np.copy(he_di[k])

        new_mat = he_mat

        if k not in le_di:
            # Use only he model cross sections if le model doesn't
            # know the process
            if config["low_energy_extension"]["use_unknown_cs"]:
                info(5, "skipping particle", k)
                ext_di[k] = new_mat
                continue
            else:
                raise Exception('High energy model contains unknown cs.')
        else:
            le_mat = np.copy(le_di[k])
            try:
                new_mat[:, :intp_indices[0]] *= 0.
                new_mat[:, intp_indices] *= he_int_array
                le_mat[:, intp_indices[-1]:] *= 0
                le_mat[:, intp_indices] *= le_int_array

            except IndexError:
                info(0, "problems indexing model transition")
                info(0,  k, intp_indices)
                info(0,  he_mat)
                info(0,  le_mat)

            new_mat += le_mat

            ext_di[k] = new_mat

    ext_di['le_ext'] = config["low_energy_extension"]

    if fname:
        info(5, "Saving", fname)
        pickle.dump(ext_di, BZ2File(fname, 'wb'), protocol=-1)

    return ext_di
