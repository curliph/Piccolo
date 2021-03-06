#!/usr/bin/python3

# Copyright (c) 2018 Bluespec, Inc.
# See LICENSE for license details

usage_line = \
"Usage:\n" \
"    $ CMD    <simulation_executable>  <root-dir-for-ISA-tests>  <logs_dir>  <optional_verbosity>\n"

help_lines = \
"  Runs the RISC-V simulation executable with ELF files from root-dir and its sub-directories.\n" \
"  Runs it only on those ELF files that are relevant to the architecture implemented by the simulator.\n" \
"      The architecture must be somewhere in the simulation executable pathname (see example below).\n" \
"  For each ELF file FOO, saves simulation output in <logs_dir>/FOO.log. \n" \
"  The optional verbosity flag is:\n" \
"      v1:    Print instruction trace during simulation\n" \
"      v2:    Print pipeline stage state during simulation\n" \
"\n" \
"  Example:\n" \
"      $ CMD ../builds/RV32IMU_verilator/exe_HW_sim  ./isa  ./Logs  v1\n" \
"    will run the verilator simulation executable on the following RISC-V ISA tests:\n" \
"            isa/rv32ui-p*\n"    \
"            isa/rv32mi-p*\n"    \
"            isa/rv32um-p*\n"    \
"    which are relevant for architecture RV32IMU (taken from the simulation executable path)\n" \
"    and will leave a transcript of each test's simulation output in files like ./Logs/rv32ui-p-add.log\n" \
"    Each log will contain an instruction trace (because of the 'v1' arg).\n"

import sys
import os
import stat
import subprocess

# ================================================================

elf_to_hex_exe = "./elf_to_hex/elf_to_hex"

num_executed = 0
num_passed   = 0

# ================================================================

def main (argv = None):
    print ("Use flag --help  or --h for a help message")
    if ((len (argv) <= 1) or
        (argv [1] == '-h') or (argv [1] == '--help') or
        ((len (argv) != 4) and (len (argv) != 5))):

        sys.stdout.write (usage_line.replace ("CMD", argv [0]))
        sys.stdout.write ("\n")
        sys.stdout.write (help_lines.replace ("CMD", argv [0]))
        sys.stdout.write ("\n")
        return 0

    sim_path = os.path.abspath (os.path.normpath (argv [1]))
    if not (os.path.exists (sim_path)):
        sys.stderr.write ("ERROR: The given simulation path does not seem to exist?\n")
        sys.stderr.write ("    Simulation path: " + sim_path + "\n")
        sys.exit (1)

    arch_string = extract_arch_string (sim_path)

    test_families = select_test_families (arch_string)
    print ("Testing the following families of ISA tests")
    for tf in test_families:
        print ("    " + tf)

    elfs_path = os.path.abspath (os.path.normpath (argv [2]))

    logs_path = os.path.abspath (os.path.normpath (argv [3]))
    if not (os.path.exists (logs_path) and os.path.isdir (logs_path)):
        print ("Creating dir: " + logs_path)
        os.mkdir (logs_path)

    verbosity = 0
    if (len (argv) == 5):
        if (argv [4] == "v1"):
            verbosity = 1
        elif (argv [4] == "v2"):
            verbosity = 2
        else:
            sys.stdout.write ("Unknown command-line argument: {0}\n".format (argv [4]))
            print ("Use flag --help  or --h for a help message")
            return -1

    # Perform the recursive traversal
    max_level = 20
    traverse (max_level, 0, sim_path, test_families, elfs_path, logs_path, verbosity)

    # Write final statistics
    sys.stdout.write ("Executed: {0} tests\n".format (num_executed))
    sys.stdout.write ("PASS:     {0} tests\n".format (num_passed))


# ================================================================
# Extract the architecture string (e.g., RV64AIMSU) from the simulation path

def extract_arch_string (sim_path):
    s = sim_path.upper()
    j_rv32 = s.find ("RV32")
    j_rv64 = s.find ("RV64")

    if (j_rv32 >= 0):
        j = j_rv32
    elif (j_rv64 >= 0):
        j = j_rv64
    else:
        sys.stderr.write ("ERROR: cannot find architecture string beginning with RV32 or RV64 in simulator path\n")
        sys.stderr.write ("    Simulator path: " + s + "\n")
        sys.exit (1)

    k = j + 4
    rv = s [j:k]

    extns = ""
    while (k < len (s)):
        ch = s [k]
        if (ch < "A") or (ch > "Z"): break
        extns = extns + s [k]
        k     = k + 1

    arch = rv + extns
    sys.stdout.write ("Architecture is: {0}\n".format (arch))
    return arch

# ================================================================
# Select ISA test families based on provided arch string

def select_test_families (arch):
    arch = arch.lower ()
    families = []

    if arch.find ("32") != -1:
        rv = 32
        families = ["rv32ui-p", "rv32mi-p"]
    else:
        rv = 64
        families = ["rv64ui-p", "rv64mi-p"]

    if (arch.find ("s") != -1):
        s = True
        if rv == 32:
            families.extend (["rv32ui-v", "rv32si-p"])
        else:
            families.extend (["rv64ui-v", "rv64si-p"])
    else:
        s = False

    def add_family (extension):
        if (arch.find (extension) != -1):
            if rv == 32:
                families.append ("rv32u" + extension + "-p")
                if s:
                    families.append ("rv32u" + extension + "-v")
            else:
                families.append ("rv64u" + extension + "-p")
                if s:
                    families.append ("rv64u" + extension + "-v")

    add_family ("m")
    add_family ("a")
    add_family ("f")
    add_family ("d")
    add_family ("c")

    return families

# ================================================================
# Recursively traverse the dir tree below elf_path and process each file

def traverse (max_level, level, sim_path, test_families, elfs_path, logs_path, verbosity):
    st = os.stat (elfs_path)
    is_dir = stat.S_ISDIR (st.st_mode)
    is_regular = stat.S_ISREG (st.st_mode)
    do_foreachfile_function (level, is_dir, is_regular, sim_path, test_families, elfs_path, logs_path, verbosity)
    if is_dir and level < max_level:
        for entry in os.listdir (elfs_path):
            elfs_path1 = os.path.join (elfs_path, entry)
            traverse (max_level, level + 1, sim_path, test_families, elfs_path1, logs_path, verbosity)
    return 0

# ================================================================
# This function is applied to every path in the
# recursive traversal

def do_foreachfile_function (level, is_dir, is_regular, sim_path, test_families, elfs_path, logs_path, verbosity):
    prefix = ""
    for j in range (level): prefix = "  " + prefix

    # directories
    if is_dir:
        print ("%s%d dir %s" % (prefix, level, elfs_path))

    # regular files
    elif is_regular:
        dirname  = os.path.dirname (elfs_path)
        basename = os.path.basename (elfs_path)
        # print ("%s%d %s" % (prefix, level, elfs_path))
        do_regular_file_function (level, dirname, basename, sim_path, test_families, logs_path, verbosity)

    # other files
    else:
        print ("%s%d Unknown file type: %s" % (prefix, level, os.path.basename (elfs_path)))

# ================================================================
# For each ELF file, execute it in the RISC-V simulator

def do_regular_file_function (level, dirname, basename, sim_path, test_families, logs_path, verbosity):
    global num_executed
    global num_passed

    full_filename = os.path.join (dirname, basename)

    # Ignore filename if has .dump extension (not an ELF file)
    if basename.find (".dump") != -1: return

    # Ignore filename if does not match test_families
    ignore = True
    for x in test_families:
        if basename.find (x) != -1: ignore = False
    if ignore:
        # print ("Ignoring file: " + full_filename)
        return

    # For debugging only
    # prefix = ""
    # for j in range (level): prefix = "  " + prefix
    # sys.stdout.write ("{0}{1} ACTION:    {2}\n".format (prefix, level, full_filename))

    # Construct the commands for sub-process execution
    command1 = [elf_to_hex_exe, full_filename, "Mem.hex"]

    command2 = [sim_path,  "+tohost"]
    if (verbosity == 1): command2.append ("+v1")
    elif (verbosity == 2): command2.append ("+v2")

    sys.stdout.write ("Test {0}\n".format (basename))

    sys.stdout.write ("    Exec:")
    for x in command1:
        sys.stdout.write (" {0}".format (x))
    sys.stdout.write ("\n")

    sys.stdout.write ("    Exec:")
    for x in command2:
        sys.stdout.write (" {0}".format (x))
    sys.stdout.write ("\n")

    # Run command as a sub-process
    completed_process1 = run_command (command1)
    completed_process2 = run_command (command2)
    num_executed = num_executed + 1
    passed = completed_process2.stdout.find ("PASS") != -1
    if passed:
        sys.stdout.write ("    PASS")
        num_passed = num_passed + 1
    else:
        sys.stdout.write ("    FAIL")

    # Save stdouts in log file
    log_filename = os.path.join (logs_path, basename + ".log")
    sys.stdout.write ("      Writing log: {0}.log\n".format (basename))

    fd = open (log_filename, 'w')
    fd.write (completed_process1.stdout)
    fd.write (completed_process2.stdout)
    fd.close ()

    # If Tandem Verification trace file was created, save it as well
    if os.path.exists ("./trace_out.dat"):
        trace_filename = os.path.join (logs_path, basename + ".trace_data")
        os.rename ("./trace_out.dat", trace_filename)
        sys.stdout.write ("    Trace output saved in: {0}\n".format (trace_filename))

    return

# ================================================================
# This is a wrapper around 'subprocess.run' because of an annoying
# incompatible change in moving from Python 3.5 to 3.6

def run_command (command):
    python_minor_version = sys.version_info [1]
    if python_minor_version < 6:
        # Python 3.5 and earlier
        result = subprocess.run (args = command,
                                 bufsize = 0,
                                 stdout = subprocess.PIPE,
                                 stderr = subprocess.STDOUT,
                                 universal_newlines = True)
    else:
        # Python 3.6 and later
        result = subprocess.run (args = command,
                                 bufsize = 0,
                                 stdout = subprocess.PIPE,
                                 stderr = subprocess.STDOUT,
                                 encoding='utf-8')
    return result

# ================================================================
# For non-interactive invocations, call main() and use its return value
# as the exit code.
if __name__ == '__main__':
  sys.exit (main (sys.argv))
