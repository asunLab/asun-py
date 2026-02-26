cmake_minimum_required(VERSION 3.15)
project(ason-py CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---- Find Python ----
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)

# ---- pybind11 ----
# Prefer system pybind11; fall back to vendored headers.
find_package(pybind11 CONFIG QUIET)
if(pybind11_FOUND)
    pybind11_add_module(ason MODULE src/ason_py.cpp)
else()
    # Use vendored headers (no pybind11 CMake infra needed — headers only)
    set(VENDOR_PBINC "${CMAKE_CURRENT_SOURCE_DIR}/vendor")
    if(NOT EXISTS "${VENDOR_PBINC}/pybind11/pybind11.h")
        message(FATAL_ERROR
            "pybind11 headers not found in vendor/pybind11/. "
            "Run: pip install pybind11  or  make  (which auto-vendors them).")
    endif()
    # Fall back to a plain shared library target
    add_library(ason MODULE src/ason_py.cpp)
    set_target_properties(ason PROPERTIES PREFIX "" SUFFIX "${Python3_EXT_SUFFIX}")
    target_include_directories(ason PRIVATE ${VENDOR_PBINC} ${Python3_INCLUDE_DIRS})
    target_link_libraries(ason PRIVATE ${Python3_LIBRARIES})
endif()

target_compile_options(ason PRIVATE -O2 -Wall -Wextra)

install(TARGETS ason DESTINATION .)
