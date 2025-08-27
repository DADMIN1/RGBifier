MAKEFLAGS += --warn-undefined-variables --no-implicit-rules --no-builtin-rules --no-builtin-variables
#MAKEFLAGS += --warn-undefined-variables --no-implicit-rules --no-builtin-rules --no-builtin-variables --print-data-base --dry-run
# compiler version: GCC13

CXXFLAGS := -std=c++23 -fdiagnostics-color=always
CXXFLAGS += -march=native -mtune=native -O3
LDFLAGS := -lMagickCore-6.Q16 -lMagick++-6.Q16
WARNFLAGS := -Wall -Wextra -Wpedantic -fmax-errors=1

# INCLUDEFLAGS := -isystem /usr/include/ImageMagick-6/ -isystem /usr/include/x86_64-linux-gnu/ImageMagick-6/
# "magick-baseconfig.h" is literally the only file under the second path
# /usr/include/x86_64-linux-gnu/ImageMagick-6/magick/magick-baseconfig.h

INCLUDEFLAGS := -isystem ImageMagick6_headers/

# magick-config.h says "fix your makefile" if these aren't defined
MAGICKFLAGS := -DMAGICKCORE_QUANTUM_DEPTH=16 -DMAGICKCORE_HDRI_ENABLE=0

OBJECTFILE_DIR := build/objectfiles
SHARED_OBJECTFILE_DIR := build/shared_objfiles
SUBDIRS := ${OBJECTFILE_DIR} ${SHARED_OBJECTFILE_DIR}
.PHONY: subdirs
subdirs: ${SUBDIRS}
${SUBDIRS}:
	@mkdir --verbose --parents $@
# '--parents' also prevents errors if it already exists

# ------------------------------------------------ #
# executable
# ------------------------------------------------ #
${OBJECTFILE_DIR}/%.o: %.cpp
	g++ ${CXXFLAGS} ${INCLUDEFLAGS} ${WARNFLAGS} ${MAGICKFLAGS} -c $< -o $@

runtest: ${OBJECTFILE_DIR}/test.o
	g++ ${CXXFLAGS} ${WARNFLAGS} $< -o $@ ${LDFLAGS}
	@echo "built executable: $@"

# ------------------------------------------------ #
# dynamic library
# ------------------------------------------------ #
${SHARED_OBJECTFILE_DIR}/%.o: %.cpp
	g++ -fpic -shared ${CXXFLAGS} ${INCLUDEFLAGS} ${WARNFLAGS} ${MAGICKFLAGS} -DIS_LIBRARY_BUILD -c $< -o $@
# object files must be compiled with '-fpic'

libRGBmagick.so: ${SHARED_OBJECTFILE_DIR}/test.o
	g++ -fpic -shared ${CXXFLAGS} ${WARNFLAGS} $< -o $@ ${LDFLAGS} -Wl,--trace
	@echo "built library: $@"
# '--trace' (linker option) prints each file that's being linked in


# ------------------------------------------------ #
# adding this Makefile as prerequisite (bonus: not included in automatic variables like '$^')
# and subdirs as an order-only prerequsite, of course
.EXTRA_PREREQS := Makefile | ${SUBDIRS}
# global definition is added to all targets

.DEFAULT_GOAL := all
.PHONY: all
all: runtest libRGBmagick.so
#	@echo "built libaries: $?" # always prints


# ------------------------------------------------ #

.PHONY: clean
clean:
	@-rm --verbose ${OBJECTFILE_DIR}/*.o 2> /dev/null || true
	@-rm --verbose ${SHARED_OBJECTFILE_DIR}/*.o 2> /dev/null || true
	@-rm --verbose runtest 2> /dev/null || true
	@-rm --verbose libRGBmagick.so 2> /dev/null || true

