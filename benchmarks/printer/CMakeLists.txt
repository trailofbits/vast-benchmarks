cmake_minimum_required(VERSION 3.5)

project(example)

add_library(printer STATIC
    src/printer.c
)

target_include_directories(printer
    PUBLIC
        ${PROJECT_SOURCE_DIR}/include
)

add_executable(example
    src/main.c
)

target_link_libraries(example printer)