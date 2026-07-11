cmake_minimum_required(VERSION 3.14)

set(REQUIRED_VARIABLES
    ARTIFACT_PATH
    MANIFEST_PATH
    BUILD_CONFIG
    HTTPLIB_REPOSITORY
    HTTPLIB_VERSION
    HTTPLIB_COMMIT
)
foreach(REQUIRED_VARIABLE IN LISTS REQUIRED_VARIABLES)
    if(NOT DEFINED ${REQUIRED_VARIABLE} OR "${${REQUIRED_VARIABLE}}" STREQUAL "")
        message(FATAL_ERROR "Missing required verification value: ${REQUIRED_VARIABLE}")
    endif()
endforeach()

if(NOT EXISTS "${ARTIFACT_PATH}")
    message(FATAL_ERROR "Build artifact does not exist: ${ARTIFACT_PATH}")
endif()
if(NOT EXISTS "${MANIFEST_PATH}")
    message(FATAL_ERROR "Build manifest does not exist: ${MANIFEST_PATH}")
endif()

file(SHA256 "${ARTIFACT_PATH}" ARTIFACT_SHA256)
file(SIZE "${ARTIFACT_PATH}" ARTIFACT_SIZE)
get_filename_component(ARTIFACT_NAME "${ARTIFACT_PATH}" NAME)
file(READ "${MANIFEST_PATH}" MANIFEST_CONTENT)

function(require_manifest_fragment FRAGMENT LABEL)
    string(FIND "${MANIFEST_CONTENT}" "${FRAGMENT}" FRAGMENT_INDEX)
    if(FRAGMENT_INDEX EQUAL -1)
        message(FATAL_ERROR "Build manifest mismatch for ${LABEL}: ${FRAGMENT}")
    endif()
endfunction()

require_manifest_fragment("\"schema_version\": 1" "schema version")
require_manifest_fragment("\"name\": \"${ARTIFACT_NAME}\"" "artifact name")
require_manifest_fragment("\"size_bytes\": ${ARTIFACT_SIZE}" "artifact size")
require_manifest_fragment("\"sha256\": \"${ARTIFACT_SHA256}\"" "artifact SHA-256")
require_manifest_fragment("\"build_config\": \"${BUILD_CONFIG}\"" "build config")
require_manifest_fragment("\"repository\": \"${HTTPLIB_REPOSITORY}\"" "dependency repository")
require_manifest_fragment("\"version\": \"${HTTPLIB_VERSION}\"" "dependency version")
require_manifest_fragment("\"commit\": \"${HTTPLIB_COMMIT}\"" "dependency commit")

message(STATUS "Verified build manifest: ${MANIFEST_PATH}")
