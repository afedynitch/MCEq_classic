import sys
from os.path import join
from setuptools import setup, Extension

# Require pytest-runner only when running tests
pytest_runner = (['pytest-runner>=2.0,<3dev'] if any(
    arg in sys.argv for arg in ('pytest', 'test')) else [])

setup_requires = pytest_runner

libnrlmsise00 = Extension(
    'MCEq/nrlmsise00/_libnrlmsise00',
    sources=[
        join('MCEq/nrlmsise00', sf)
        for sf in ['nrlmsise-00_data.c', 'nrlmsise-00.c']
    ],
    include_dirs=['MCEq/nrlmsise00'])

setup(name='MCEq',
      version='1.0.0',
      description='Numerical cascade equation solver',
      author='Anatoli Fedynitch',
      author_email='afedynitch@gmail.com',
      license='BSD 3-Clause License',
      url='https://github.com/afedynitch/MCEq',
      packages=['MCEq', 'MCEq.nrlmsise00', 'MCEq.geometry'],
      package_dir={
          'MCEq': 'MCEq',
          'MCEq.geometry': 'MCEq/geometry',
          'MCEq.nrlmsise00': 'MCEq/nrlmsise00'
      },
      package_data={'MCEq': ['data/README.md']},
      py_modules=['mceq_config'],
      requires=[
          'numpy', 'scipy', 'numba', 'mkl', 'particletools', 'crflux', 'h5py'
      ],
      ext_modules=[libnrlmsise00],
      extras_require={
          'MKL': ["mkl"],
          'CUDA': ["cupy"]
      })
