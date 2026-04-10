cmake_minimum_required(VERSION 3.14)
project(EngLabServer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ─── httplib (header-only HTTP library) ───
include(FetchContent)
FetchContent_Declare(httplib
    GIT_REPOSITORY https://github.com/yhirose/cpp-httplib.git
    GIT_TAG        v0.18.3
)
FetchContent_MakeAvailable(httplib)

add_executable(englab_server main.cpp)
target_link_libraries(englab_server PRIVATE httplib::httplib)

# Windows-specific: link ws2_32
if(WIN32)
    target_link_libraries(englab_server PRIVATE ws2_32)
endif()
