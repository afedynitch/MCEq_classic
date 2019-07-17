# MCEq - Matrix cascade equations


This version was previously known as 'dev' branch.

This scientific package might be useful fo all who deal with high-energy inclusive atmospheric fluxes of muons and neutrinos. 
In particular it might be useful for astroparticle physics experiments, for example  `IceCube <https://icecube.wisc.edu>`_ or 
`MINOS <http://www-numi.fnal.gov/PublicInfo/index.html>`_, for calculations of systematic uncertainties and atmospheric backgrounds.

## Status (Updated)


This is release candiate of the final version 1.0. It has several new features including:
- extended energy range (1 GeV - 10^11 GeV)
- new interaction models, SIBYLL 2.3 + 2.3c, EPOS-LHC and DPMJET-III 17.1
- compact (=very fast) mode
- low-energy extension (with DPMJET-III) of high-energy interaction models
- computation of hadron and lepton yields along an air-shower trajectory (average air-shower)
- energy loss for muons
- a generalized target mode, with arbitrary density profiles of target material (experimental and physics is not yet accurate)

## [Documentation (updated)](http://mceq.readthedocs.org/en/latest/>)


The latest version of the documentation can be found [here](http://mceq.readthedocs.org/en/latest/).

## Please cite our work

If you are using this code in your scientific work, please cite the code **AND** the
physical models. A complete list of references can be found in the 
`Citations section of the docs <http://mceq.readthedocs.org/en/latest/citations.html>`_.

## System requirements

- Some kind of modern CPU with FPU unit
- 2GB (8GB of RAM is recommended)
- ~2GB of disk space
- OS: Linux, Mac or Windows 10

## Software requirements

The majority of the code is pure Python. Some functions are accelerated through Just-In-Time (JIT) compilation 
using `numba <http://numba.pydata.org>`_, which requires the `llvmlite` package.

Dependencies:

* python-2.7
* numpy
* scipy

## Installation

Fairly simple:

```bash
pip install MCEq
```

## Contributers

*Anatoli Fedynitch*

## Copyright and license

Code released under [the BSD 3-clause license (see LICENSE)](LICENSE).
