cmake_minimum_required(VERSION 3.14)
project(EngLabServer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" AND CMAKE_CXX_COMPILER_VERSION VERSION_LESS 9.1)
    message(FATAL_ERROR "englab_server requires GCC 9.1+ for complete C++17 filesystem support")
endif()

# ─── httplib (header-only HTTP library) ───
set(ASTRA_HTTPLIB_VERSION "0.18.3")
set(ASTRA_HTTPLIB_REPOSITORY "https://github.com/yhirose/cpp-httplib.git")
set(ASTRA_HTTPLIB_COMMIT "a7bc00e3307fecdb4d67545e93be7b88cfb1e186")
option(
    ASTRA_DEPENDENCIES_OFFLINE
    "Require an explicitly supplied, pre-populated and commit-verified dependency source"
    OFF
)

include(FetchContent)
if(ASTRA_DEPENDENCIES_OFFLINE)
    if(NOT FETCHCONTENT_SOURCE_DIR_HTTPLIB)
        message(FATAL_ERROR
            "ASTRA_DEPENDENCIES_OFFLINE=ON requires "
            "-DFETCHCONTENT_SOURCE_DIR_HTTPLIB=<verified cpp-httplib checkout>"
        )
    endif()
    get_filename_component(
        FETCHCONTENT_SOURCE_DIR_HTTPLIB
        "${FETCHCONTENT_SOURCE_DIR_HTTPLIB}"
        ABSOLUTE
    )
    if(NOT EXISTS "${FETCHCONTENT_SOURCE_DIR_HTTPLIB}/httplib.h"
       OR NOT EXISTS "${FETCHCONTENT_SOURCE_DIR_HTTPLIB}/CMakeLists.txt")
        message(FATAL_ERROR
            "Offline cpp-httplib source is incomplete: ${FETCHCONTENT_SOURCE_DIR_HTTPLIB}"
        )
    endif()
    set(FETCHCONTENT_FULLY_DISCONNECTED ON)
endif()

set(FETCHCONTENT_UPDATES_DISCONNECTED ON)
FetchContent_Declare(httplib
    GIT_REPOSITORY "${ASTRA_HTTPLIB_REPOSITORY}"
    GIT_TAG        "${ASTRA_HTTPLIB_COMMIT}"
    GIT_SUBMODULES ""
)
FetchContent_MakeAvailable(httplib)
FetchContent_GetProperties(httplib SOURCE_DIR ASTRA_HTTPLIB_SOURCE_DIR)

find_package(Git REQUIRED)
execute_process(
    COMMAND "${GIT_EXECUTABLE}" -C "${ASTRA_HTTPLIB_SOURCE_DIR}" rev-parse HEAD
    RESULT_VARIABLE ASTRA_HTTPLIB_GIT_RESULT
    OUTPUT_VARIABLE ASTRA_HTTPLIB_ACTUAL_COMMIT
    ERROR_VARIABLE ASTRA_HTTPLIB_GIT_ERROR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
if(NOT ASTRA_HTTPLIB_GIT_RESULT EQUAL 0)
    message(FATAL_ERROR
        "Unable to verify cpp-httplib checkout at ${ASTRA_HTTPLIB_SOURCE_DIR}: "
        "${ASTRA_HTTPLIB_GIT_ERROR}"
    )
endif()
if(NOT ASTRA_HTTPLIB_ACTUAL_COMMIT STREQUAL ASTRA_HTTPLIB_COMMIT)
    message(FATAL_ERROR
        "cpp-httplib commit mismatch: expected ${ASTRA_HTTPLIB_COMMIT}, "
        "got ${ASTRA_HTTPLIB_ACTUAL_COMMIT}"
    )
endif()
message(STATUS
    "cpp-httplib ${ASTRA_HTTPLIB_VERSION} verified at ${ASTRA_HTTPLIB_ACTUAL_COMMIT}"
)

add_executable(englab_server main.cpp)
target_link_libraries(englab_server PRIVATE httplib::httplib)

# Windows-specific: link ws2_32
if(WIN32)
    target_link_libraries(englab_server PRIVATE ws2_32)
endif()

set(ASTRA_BUILD_MANIFEST
    "$<TARGET_FILE_DIR:englab_server>/englab_server.build-manifest.json"
)
add_custom_command(
    TARGET englab_server
    POST_BUILD
    COMMAND "${CMAKE_COMMAND}"
        "-DARTIFACT_PATH=$<TARGET_FILE:englab_server>"
        "-DMANIFEST_PATH=${ASTRA_BUILD_MANIFEST}"
        "-DBUILD_CONFIG=$<CONFIG>"
        "-DCMAKE_TOOL_VERSION=${CMAKE_VERSION}"
        "-DCOMPILER_ID=${CMAKE_CXX_COMPILER_ID}"
        "-DCOMPILER_VERSION=${CMAKE_CXX_COMPILER_VERSION}"
        "-DHTTPLIB_REPOSITORY=${ASTRA_HTTPLIB_REPOSITORY}"
        "-DHTTPLIB_VERSION=${ASTRA_HTTPLIB_VERSION}"
        "-DHTTPLIB_COMMIT=${ASTRA_HTTPLIB_COMMIT}"
        -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/write_build_manifest.cmake"
    COMMENT "Writing englab_server dependency and artifact manifest"
    VERBATIM
)

add_custom_target(
    verify_build_manifest
    COMMAND "${CMAKE_COMMAND}"
        "-DARTIFACT_PATH=$<TARGET_FILE:englab_server>"
        "-DMANIFEST_PATH=${ASTRA_BUILD_MANIFEST}"
        "-DBUILD_CONFIG=$<CONFIG>"
        "-DHTTPLIB_REPOSITORY=${ASTRA_HTTPLIB_REPOSITORY}"
        "-DHTTPLIB_VERSION=${ASTRA_HTTPLIB_VERSION}"
        "-DHTTPLIB_COMMIT=${ASTRA_HTTPLIB_COMMIT}"
        -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/verify_build_manifest.cmake"
    DEPENDS englab_server
    COMMENT "Verifying englab_server dependency and artifact manifest"
    VERBATIM
)
