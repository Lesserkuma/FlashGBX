include(FetchContent)

# Modern versions of CMake do not support 3.5 projects; setting this
# suppresses the safety check
set(CMAKE_POLICY_VERSION_MINIMUM 3.5)

FetchContent_declare(
  mgba
  GIT_REPOSITORY https://github.com/mgba-emu/mgba.git
  GIT_TAG 26b7884bc25a5933960f3cdcd98bac1ae14d42e2 # 0.10.5
  EXCLUDE_FROM_ALL
)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(LIBMGBA_ONLY ON)
set(DISABLE_FRONTENDS ON)
set(DISABLE_DEPS ON)
set(M_CORE_GB OFF)

set(SKIP_GIT ON)
set(MINIMAL_CORE 2)
set(ENABLE_EXTRA OFF)
set(DISABLE_THREADING ON)
set(BUILD_LTO OFF)

# These *should* be auto-detected as off, but setting them explicitly:
# - makes the build faster
# - reduces log spam
# - avoids accidentally picking up the dependency if it happens to be present
set(USE_EPOXY OFF)
set(USE_LIBZIP OFF)
set(USE_PNG OFF)
set(USE_MINIZIP OFF)
set(USE_FFMPEG OFF)
set(USE_SQLITE3 OFF)
set(USE_ELF OFF)

FetchContent_MakeAvailable(mgba)

# `LIBMGBA_ONLY` ignores the BUILD_STATIC/BUILD_SHARED flags and forces a static build, so, make our own target
get_target_property(mgba_SOURCES mgba SOURCES)

# Match loader in Sintax.py
set(OS_NAME "${CMAKE_SYSTEM_NAME}")
if(WIN32)
  set(OS_NAME "windows")
elseif (APPLE)
  set(OS_NAME "macos")
elseif (LINUX)
  set(OS_NAME "linux")
endif ()

# Match loader in Sintax.py
#
# Annoyingly, values for the same architecture vary by both OS and toolchain
set(ARCH "${CMAKE_C_COMPILER_ARCHITECTURE_ID}")
if (ARCH STREQUAL "arm64e" OR ARCH STREQUAL "aarch64" OR ARCH STREQUAL "ARM64")
  set(ARCH "arm64")
elseif (ARCH MATCHES "^i.+86$" OR ARCH STREQUAL "X86")
  set(ARCH "x86")
elseif (ARCH STREQUAL "x64" OR ARCH STREQUAL "X64")
  set(ARCH "x86_64")
elseif (ARCH STREQUAL "ARM" AND CMAKE_SIZEOF_VOID_P EQUAL 8)
  set(ARCH "arm64")
endif()

add_library(mgba_shared MODULE "${mgba_SOURCES}")
add_dependencies(mgba_shared mgba-version-info)

get_target_property(mgba_C_FLAGS mgba C_FLAGS)
get_target_property(mgba_C_FLAGS_RELEASE mgba C_FLAGS_RELEASE)
get_target_property(mgba_LINK_LIBRARIES mgba LINK_LIBRARIES)
get_target_property(mgba_INCLUDE_DIRECTORIES mgba INCLUDE_DIRECTORIES)
set_target_properties(
  mgba_shared
  PROPERTIES
  C_STANDARD 11
  C_STANDARD_REQUIRED ON
  C_EXTENSIONS OFF
  OUTPUT_NAME "mgba-${OS_NAME}-${ARCH}"
  PREFIX lib
  WINDOWS_EXPORT_ALL_SYMBOLS ON
  C_FLAGS "${mgba_C_FLAGS}"
  C_FLAGS_RELEASE "${mgba_C_FLAGS_RELEASE}"
  LINK_LIBRARIES "${mgba_LINK_LIBRARIES}"
  INCLUDE_DIRECTORIES "${mgba_INCLUDE_DIRECTORIES}"
)
if (APPLE)
  set_target_properties(
    mgba_shared
    PROPERTIES
    # scikit-build defaults to `.so` on macOS
    SUFFIX ".dylib"
  )
endif ()

get_target_property(mgba_COMPILE_DEFINITIONS mgba COMPILE_DEFINITIONS)
list(REMOVE_ITEM mgba_COMPILE_DEFINITIONS BUILD_STATIC)
target_compile_definitions(
  mgba_shared
  PRIVATE
  "${mgba_COMPILE_DEFINITIONS}"
  MGBA_DLL
  MINIMAL_CORE=2
  DISABLE_THREADING
)

install(TARGETS mgba_shared DESTINATION FlashGBX)
