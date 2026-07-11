cmake_minimum_required(VERSION 3.14)

set(REQUIRED_VARIABLES
    ARTIFACT_PATH
    MANIFEST_PATH
    BUILD_CONFIG
    CMAKE_TOOL_VERSION
    COMPILER_ID
    COMPILER_VERSION
    HTTPLIB_REPOSITORY
    HTTPLIB_VERSION
    HTTPLIB_COMMIT
)
foreach(REQUIRED_VARIABLE IN LISTS REQUIRED_VARIABLES)
    if(NOT DEFINED ${REQUIRED_VARIABLE} OR "${${REQUIRED_VARIABLE}}" STREQUAL "")
        message(FATAL_ERROR "Missing required manifest value: ${REQUIRED_VARIABLE}")
    endif()
endforeach()

if(NOT EXISTS "${ARTIFACT_PATH}")
    message(FATAL_ERROR "Build artifact does not exist: ${ARTIFACT_PATH}")
endif()

function(json_escape INPUT_VALUE OUTPUT_VARIABLE)
    set(ESCAPED_VALUE "${INPUT_VALUE}")
    string(REPLACE "\\" "\\\\" ESCAPED_VALUE "${ESCAPED_VALUE}")
    string(REPLACE "\"" "\\\"" ESCAPED_VALUE "${ESCAPED_VALUE}")
    string(REPLACE "\n" "\\n" ESCAPED_VALUE "${ESCAPED_VALUE}")
    string(REPLACE "\r" "\\r" ESCAPED_VALUE "${ESCAPED_VALUE}")
    set(${OUTPUT_VARIABLE} "${ESCAPED_VALUE}" PARENT_SCOPE)
endfunction()

file(SHA256 "${ARTIFACT_PATH}" ARTIFACT_SHA256)
file(SIZE "${ARTIFACT_PATH}" ARTIFACT_SIZE)
get_filename_component(ARTIFACT_NAME "${ARTIFACT_PATH}" NAME)

json_escape("${ARTIFACT_NAME}" ARTIFACT_NAME_JSON)
json_escape("${BUILD_CONFIG}" BUILD_CONFIG_JSON)
json_escape("${CMAKE_TOOL_VERSION}" CMAKE_TOOL_VERSION_JSON)
json_escape("${COMPILER_ID}" COMPILER_ID_JSON)
json_escape("${COMPILER_VERSION}" COMPILER_VERSION_JSON)
json_escape("${HTTPLIB_REPOSITORY}" HTTPLIB_REPOSITORY_JSON)
json_escape("${HTTPLIB_VERSION}" HTTPLIB_VERSION_JSON)
json_escape("${HTTPLIB_COMMIT}" HTTPLIB_COMMIT_JSON)

file(WRITE "${MANIFEST_PATH}"
    "{\n"
    "  \"schema_version\": 1,\n"
    "  \"artifact\": {\n"
    "    \"name\": \"${ARTIFACT_NAME_JSON}\",\n"
    "    \"size_bytes\": ${ARTIFACT_SIZE},\n"
    "    \"sha256\": \"${ARTIFACT_SHA256}\"\n"
    "  },\n"
    "  \"toolchain\": {\n"
    "    \"cmake\": \"${CMAKE_TOOL_VERSION_JSON}\",\n"
    "    \"compiler_id\": \"${COMPILER_ID_JSON}\",\n"
    "    \"compiler_version\": \"${COMPILER_VERSION_JSON}\",\n"
    "    \"build_config\": \"${BUILD_CONFIG_JSON}\"\n"
    "  },\n"
    "  \"dependencies\": {\n"
    "    \"cpp_httplib\": {\n"
    "      \"repository\": \"${HTTPLIB_REPOSITORY_JSON}\",\n"
    "      \"version\": \"${HTTPLIB_VERSION_JSON}\",\n"
    "      \"commit\": \"${HTTPLIB_COMMIT_JSON}\"\n"
    "    }\n"
    "  }\n"
    "}\n"
)

message(STATUS "Wrote build manifest: ${MANIFEST_PATH}")
