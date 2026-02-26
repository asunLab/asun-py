# Makefile for ason-py C++ pybind11 extension
# Requires: g++ (C++17), python3-dev (Python.h)
#
# Build:
#   make
# Run tests:
#   make test
# Clean:
#   make clean

CXX      := g++
CXXFLAGS := -std=c++17 -O2 -Wall -Wextra -fPIC
PYINC    := $(shell python3 -c "import sysconfig; print(sysconfig.get_path('include'))" 2>/dev/null)
PYINC_UP := $(shell python3 -c "import sysconfig, os; print(os.path.dirname(sysconfig.get_path('include')))" 2>/dev/null)
PBINC    := vendor
SUFFIX   := $(shell python3 -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))" 2>/dev/null)
TARGET   := ason$(SUFFIX)

.PHONY: all test clean

all: $(TARGET)

$(TARGET): src/ason_py.cpp vendor/pybind11/pybind11.h
	$(CXX) $(CXXFLAGS) -shared \
	  -I$(PBINC) \
	  -I$(PYINC) \
	  -I$(PYINC_UP) \
	  src/ason_py.cpp \
	  -o $@
	@echo "Built $@"

test: $(TARGET)
	python3 -m pytest tests/ -v

clean:
	rm -f ason*.so ason*.pyd
