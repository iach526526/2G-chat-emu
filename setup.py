from setuptools import setup
from Cython.Build import cythonize

setup(
    name="switch_data",
    ext_modules=cythonize("switch_data/**/*.py"),
    zip_safe=False,
)
