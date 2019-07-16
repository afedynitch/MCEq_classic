import sys
from skbuild import setup


# Require pytest-runner only when running tests
pytest_runner = (['pytest-runner>=2.0,<3dev']
                 if any(arg in sys.argv for arg in ('pytest', 'test'))
                 else [])

setup_requires = pytest_runner

setup(
    name='MCEq',
    version='1.0.0',
    description='Numerical cascade equation solver',
    author='Anatoli Fedynitch',
    author_email='afedynitch@gmail.com',
    url='https://github.com/afedynitch/MCEq',
    packages=[
        'MCEq','nrlmsis00'
    ],
    py_modules=['mceq_config'],
    requires=['numpy', 'scipy', 'numba', 'mkl', 'particletools', 'crflux'])