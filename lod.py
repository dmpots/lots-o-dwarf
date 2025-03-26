#!/usr/bin/env python3
import argparse
import os
import subprocess
from typing import List
import math
import re

SCRIPT_DIR=os.path.dirname(os.path.realpath(__file__))

def parse_args():
    parser = argparse.ArgumentParser(description='My Script')
    parser.add_argument('--count-of-leaf-source-files', type=int, default=10,
                        help='The number of object files to generate')
    parser.add_argument('--library_object_count', type=int, default=1000,
                        help='The number of object files to include in a library')
    parser.add_argument('--output-directory',
                        default=os.path.join(SCRIPT_DIR, 'build'),
                        help='The directory used to hold generated contents')
    parser.add_argument('--skip-generate', dest="generate", default=True,
                        action='store_false',
                         help='Do not re-generate the source files')
    parser.add_argument('--build', action='store_true', default=False,
                        help='Compile and link everything into a final executable')
    parser.add_argument('--run', choices=["both", "lldb", "gdb"],
                        help='Run the executable with lldb or gdb')
    parser.add_argument('--clang', default="/opt/llvm/bin/clang++",
                        help='Path to clang++')
    parser.add_argument('--gdb', default="gdb",
                        help='Path to gdb')
    parser.add_argument('--lldb', default="lldb",
                        help='Path to lldb')
    parser.add_argument('--stats',  action='store_true', default=False,
                        help='Collect stats about the build')
    parser.add_argument('--cflags', default="",
                        help='Extra flags to pass to clang')
    options = parser.parse_args()
    if options.run and options.run == "both":
        options.run = ["gdb", "lldb"]
    return options

def get_src_name_padding(options):
    return len(str(options.count_of_leaf_source_files))

def get_lib_name_padding(options):
    return len(str(get_num_libraries_to_build(options)))

def get_num_libraries_to_build(options) -> int:
    return math.ceil(options.count_of_leaf_source_files / options.library_object_count)

def get_build_directory(options):
    return options.output_directory

def get_src_directory(options):
    return os.path.join(get_build_directory(options), "src")

def get_obj_directory(options):
    return os.path.join(get_build_directory(options), "obj")

def get_lib_directory(options):
    return os.path.join(get_build_directory(options), "lib")

def get_bin_directory(options):
    return os.path.join(get_build_directory(options), "bin")

def get_source_file_path(options, file_index: int, prefix="src") -> str:
    src = get_src_directory(options)
    padding = get_src_name_padding(options)
    src_file = f"{prefix}_{file_index:0{padding}}.cpp"
    return os.path.join(src, src_file)

def get_obj_file_path(options, src_file):
    obj = get_obj_directory(options)
    obj_file = os.path.basename(src_file.replace(".cpp", ".o"))
    return os.path.join(obj, obj_file)

def get_lib_file_path(options, lib_index):
    lib = get_lib_directory(options)
    padding = get_lib_name_padding(options)
    lib_file = f"lib_{lib_index:0{padding}}.a"
    return os.path.join(lib, lib_file)

def get_get_bin_file_path(options, name):
    bin = get_bin_directory(options)
    return os.path.join(bin, name)

def get_main_exe(options):
    return get_get_bin_file_path(options, "lod")

def get_ninja_file_path(options) -> str:
    return os.path.join(get_build_directory(options), 'build.ninja')

def create_output_dirs(options):
    os.makedirs(get_build_directory(options), exist_ok=True)
    os.makedirs(get_src_directory(options), exist_ok=True)
    os.makedirs(get_obj_directory(options), exist_ok=True)
    os.makedirs(get_lib_directory(options), exist_ok=True)
    os.makedirs(get_bin_directory(options), exist_ok=True)

def get_lib_src_indices(options, lib_index):
    src_start = lib_index * options.library_object_count
    src_end = src_start + options.library_object_count
    return src_start, min(src_end, options.count_of_leaf_source_files)

def generate_obj_source_file(options, src_index):
    padding = get_src_name_padding(options)
    source_path = get_source_file_path(options, src_index)
    with open(source_path, 'w') as f:
        contents = f'''
        #include <vector>
        #include <set>
        #include <list>
        #include <map>
        #include <unordered_map>
        #include <unordered_set>
        #include <deque>
        #include <string>
        #include <bitset>
        #include <tuple>

        int src_{src_index:0{padding}}() {{
            std::set<int> s;
            s.insert(1);

            std::list<int> l;
            l.emplace_back(1);

            std::map<int, int> m;
            m[1] = 1;

            std::unordered_map<int, bool> um;
            um[1] = false;

            std::unordered_set<double> us;
            us.insert(1.0);

            std::deque<int> d;
            d.push_front(1);

            std::bitset<8> b8;
            b8.set(1);

            std::bitset<16> b16;
            b16.set(1);

            std::string str = "hello";

            std::tuple<int, int, int> t = std::make_tuple(1, 2, 3);
            std::get<0>(t);

            std::vector<int> v;
            v.push_back((1));
            return v.back();
        }}
        '''
        f.write(contents)
    return source_path

def generate_obj_source_files(options):
    num_object_files = options.count_of_leaf_source_files
    padding = get_src_name_padding(options)
    sources = []
    print(f'Generating {num_object_files} source files in {get_src_directory(options)}')
    for i in range(num_object_files):
        print(f"\r[{i+1:{padding}}/{num_object_files:{padding}}]", end="")
        sources.append(generate_obj_source_file(options, i))
    print("\r", end="")
    return sources

def generate_lib_source_file(options, lib_index):
    lib_padding = get_lib_name_padding(options)
    src_padding = get_src_name_padding(options)
    source_path = get_source_file_path(options, lib_index, prefix="lib")
    with open(f'{source_path}', 'w') as f:
        # Generate prototypes for all the source files in this library
        start, end = get_lib_src_indices(options, lib_index)
        for src in range(start, end):
            f.write(f'int src_{src:0{src_padding}}();\n')

        f.write("\n")
        # Generate library function that sums all the source files
        f.write(f'int lib_{lib_index:0{lib_padding}}() {{\n')
        f.write(f'  int ret = 0;\n')
        for src in range(start, end):
            f.write(f'  ret += src_{src:0{src_padding}}();\n')
        f.write(f'  return ret;\n')
        f.write('}\n')
    return source_path

def generate_lib_source_files(options):
    num_lib_files = get_num_libraries_to_build(options)
    padding = get_lib_name_padding(options)
    sources = []
    print(f'Generating {num_lib_files} library source files in {get_src_directory(options)}')
    for i in range(num_lib_files):
        print(f"\r[{i+1:{padding}}/{num_lib_files:{padding}}]", end="")
        sources.append(generate_lib_source_file(options, i))
    print("\r", end="")
    return sources

def generate_main_source_file(options):
    num_lib_files = get_num_libraries_to_build(options)
    padding = get_lib_name_padding(options)
    source_path = get_source_file_path(options, 0, prefix="main")
    with open(f'{source_path}', 'w') as f:
        # Generate prototypes for all the lib files in this binary
        for src in range(num_lib_files):
            f.write(f'int lib_{src:0{padding}}();\n')

        f.write("\n")
        # Generate main function that sums all the library files
        f.write(f'int main() {{\n')
        f.write(f'  int ret = 0;\n')
        for src in range(num_lib_files):
            f.write(f'  ret += lib_{src:0{padding}}();\n')
        f.write(f'  return ret;\n')
        f.write('}\n')
    return source_path

def generate_main_source_files(options):
    print(f'Generating 1 main source files in {get_src_directory(options)}')
    main = generate_main_source_file(options)
    return [main]

def generate_source_files(options):
    obj_sources = generate_obj_source_files(options)
    lib_sources = generate_lib_source_files(options)
    main_sources = generate_main_source_files(options)
    return obj_sources, lib_sources, main_sources

# Split the object files into libraries.
def split_object_files_into_libraries(options, obj_src, lib_src):
    # Split the object files into libraries.
    libraries = []
    for i in range(0, get_num_libraries_to_build(options)):
        lib_name = get_lib_file_path(options, i)
        src_start, src_end = get_lib_src_indices(options, i)
        lib_sources = obj_src[src_start:src_end] + [lib_src[i]]
        libraries.append((lib_name, lib_sources))
    return libraries

def generate_ninja_file(options, obj_src, lib_src, main_src):
    c = options.clang
    cflags = "-Wall -Wextra -O0 -g -gsplit-dwarf " + options.cflags
    linker = options.clang
    linkflags = "-g"
    libraries = split_object_files_into_libraries(options, obj_src, lib_src)

    # Create the Ninja file
    ninja_file_path = get_ninja_file_path(options)
    print(f"Writing Ninja file to {ninja_file_path}")
    with open(ninja_file_path, "w") as f:
        def puts(s=""):
            print(s, file=f)
        def section(name):
            puts()
            puts("#")
            puts(f"# {name}")
            puts("#")

        section("Variables")
        puts(f"c = {c}")
        puts(f"cflags = {cflags}")
        puts(f"linker = {linker}")
        puts(f"linkflags = {linkflags}")

        # Compile command
        section("Rules")
        puts("rule cc")
        puts("  command = $c $cflags -c $in -o $out")

        puts("rule archive")
        puts("  command = ar rcs $out $in")

        puts("rule link")
        puts("  command = $linker $linkflags -o $out $in")

        section("Build object files")
        for src_file in obj_src + lib_src + main_src:
            obj_file = get_obj_file_path(options, src_file)
            puts(f"build {obj_file}: cc {src_file}")

        section("Build libraries")
        for lib_name, lib_sources in libraries:
            obj_files = [get_obj_file_path(options, src_file) for src_file in lib_sources]
            puts(f"build {lib_name}: archive {' '.join(obj_files)}")

        section("Build main executable")
        main_obj_files = [get_obj_file_path(options, src) for src in main_src]
        main_lib_files = [lib_name for lib_name, lib_sources in libraries]
        main_link_inputs = main_obj_files + main_lib_files
        main_exe = get_get_bin_file_path(options, "lod")
        puts(f"build {main_exe}: link " + " ".join(main_link_inputs))

        # Default target
        section("Define the default target")
        puts(f"default {main_exe}")

def build(options):
    build_dir = get_build_directory(options)
    cmd = ['ninja', '-C', build_dir]
    print(" ".join(cmd))
    subprocess.run(cmd)

def run(options):
    def time_cmd(cmd):
        cmd = ["time", "-v"] + cmd
        print(" ".join(cmd))
        subprocess.run(cmd)

    main_exe = get_main_exe(options)
    if "gdb" in options.run:
        time_cmd([options.gdb, main_exe, "-ex", "quit"])
    if "lldb" in options.run:
        time_cmd([options.lldb, main_exe, "-o", "quit"])

def sizeof_fmt(num, suffix="B"):
    # https://stackoverflow.com/questions/1094841/get-a-human-readable-version-of-a-file-size
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"

def get_file_sizes(directory, pattern):
    regex = re.compile(pattern)
    file_sizes = 0
    file_count = 0
    for filename in os.listdir(directory):
        if regex.match(filename):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                file_sizes += os.path.getsize(filepath)
                file_count += 1
    return file_sizes, file_count

def stats(options):
    exe_size, exe_count = get_file_sizes(get_bin_directory(options), os.path.basename(get_main_exe(options)))
    dwo_size, dwo_count = get_file_sizes(get_obj_directory(options), ".*[.]dwo$")
    obj_size, obj_count = get_file_sizes(get_obj_directory(options), ".*[.]o$")
    lib_size, lib_count = get_file_sizes(get_lib_directory(options), ".*[.]a$")

    print("===================== Stats =====================")
    print(f"Executable size: {sizeof_fmt(exe_size):>8} count: {exe_count}")
    print(f"ObjectFile size: {sizeof_fmt(obj_size):>8} count: {obj_count}")
    print(f"Library    size: {sizeof_fmt(lib_size):>8} count: {lib_count}")
    print(f"DebugInfo  size: {sizeof_fmt(dwo_size):>8} count: {dwo_count}")

def main():
    options = parse_args()

    if options.generate:
        create_output_dirs(options)
        obj, lib, main = generate_source_files(options)
        generate_ninja_file(options, obj, lib, main)

    if options.build:
        build(options)

    if options.run:
        run(options)

    if options.stats:
        stats(options)

if __name__ == '__main__':
    main()
