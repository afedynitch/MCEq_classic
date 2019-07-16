cmake_minimum_required(VERSION 3.11.0)
project(nrlmsis00)
find_package(PythonExtensions REQUIRED)

add_library(nrlmsis00 MODULE nrlmsis00/nrlmsise-00_data.c nrlmsis00/nrlmsise-00.c nrlmsis00/nrlmsise-00.h)
python_extension_module(nrlmsis00)
install(TARGETS nrlmsis00 LIBRARY DESTINATION nrlmsis00)