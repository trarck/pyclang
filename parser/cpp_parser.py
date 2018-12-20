#!/usr/bin/env python
# generator.py
# simple C++ generator, originally targetted for Spidermonkey bindings
#
# Copyright (c) 2011 - Zynga Inc.

from clang import cindex
import sys
import os
from parser import *

class Parser(object):
    def __init__(self, opts):
        self.index = cindex.Index.create()
        self.clang_args = opts['clang_args']
        self.skip_classes = {}
        self.parsed_classes = {}
        self.win32_clang_flags = opts['win32_clang_flags']
        self.methods = []
        self.namespaces = []

        self.current_namespace = None
        self._parsing_file = None

        extend_clang_args = []

        for clang_arg in self.clang_args:
            if not os.path.exists(clang_arg.replace("-I", "")):
                pos = clang_arg.find("lib/clang/3.3/include")
                if -1 != pos:
                    extend_clang_arg = clang_arg.replace("3.3", "3.4")
                    if os.path.exists(extend_clang_arg.replace("-I", "")):
                        extend_clang_args.append(extend_clang_arg)

        if len(extend_clang_args) > 0:
            self.clang_args.extend(extend_clang_args)

        if sys.platform == 'win32' and self.win32_clang_flags != None:
            self.clang_args.extend(self.win32_clang_flags)

        # if opts['skip']:
        #     list_of_skips = re.split(",\n?", opts['skip'])
        #     for skip in list_of_skips:
        #         class_name, methods = skip.split("::")
        #         self.skip_classes[class_name] = []
        #         match = re.match("\[([^]]+)\]", methods)
        #         if match:
        #             self.skip_classes[class_name] = match.group(1).split(" ")
        #         else:
        #             raise Exception("invalid list of skip methods")

    @staticmethod
    def in_parse_file(cursor, parsing_file):
        if cursor.location and cursor.location.file:
            source_file = cursor.location.file.name
        elif cursor.extent and cursor.extent.start:
            source_file = cursor.extent.start.file.name

        source_file = source_file.replace("\\", "/")
        # print("%s=%s" % (source_file, parsing_file))
        return source_file == parsing_file

    def _check_diagnostics(self, diagnostics):
        errors = []
        for idx, d in enumerate(diagnostics):
            if d.severity > 2:
                errors.append(d)
        if len(errors) == 0:
            return
        print("====\nErrors in parsing headers:")
        severities = ['Ignored', 'Note', 'Warning', 'Error', 'Fatal']
        for idx, d in enumerate(errors):
            print "%s. <severity = %s,\n    location = %r,\n    details = %r>" % (
                idx + 1, severities[d.severity], d.location, d.spelling)
        print("====\n")

    # must read the yaml file first
    def parse_file(self, file_path):
        tu = self.index.parse(file_path, self.clang_args)
        if len(tu.diagnostics) > 0:
            self._check_diagnostics(tu.diagnostics)
            is_fatal = False
            for d in tu.diagnostics:
                if d.severity >= cindex.Diagnostic.Error:
                    is_fatal = True
            if is_fatal:
                print("*** Found errors - can not continue")
                raise Exception("Fatal error in parsing headers")
        self._parsing_file = file_path.replace("\\", "/")

        # the root cursor is TRANSLATION_UNIT,visitor children
        if tu.cursor.kind == cindex.CursorKind.TRANSLATION_UNIT:
            cd = Parser._get_children_array_from_iter(tu.cursor.get_children())
            for cursor in tu.cursor.get_children():
                self._traverse(cursor)

    @staticmethod
    def _get_children_array_from_iter(cursor_iter):
        children = []
        for child in cursor_iter:
            children.append(child)
        return children

    def _traverse(self, cursor):
        if not Parser.in_parse_file(cursor, self._parsing_file):
            return None

        if cursor.kind == cindex.CursorKind.CLASS_DECL:
            # print("find class")
            if cursor == cursor.type.get_declaration() and len(
                    Parser._get_children_array_from_iter(cursor.get_children())) > 0:

                if not self.parsed_classes.has_key(cursor.displayname):
                    nclass = ClassInfo(cursor)
                    self.parsed_classes[cursor.displayname] = nclass
                return
        elif cursor.kind == cindex.CursorKind.FUNCTION_DECL:
            # print("find function")
            fun = FunctionInfo(cursor)
            self.methods.append(fun)
        elif cursor.kind == cindex.CursorKind.CXX_METHOD:
            # print("find method")
            method = FunctionInfo(cursor)
            self.methods.append(method)
        elif cursor.kind == cindex.CursorKind.NAMESPACE:
            # print("find namespace")
            self.current_namespace = cursor.spelling
            for sub_cursor in cursor.get_children():
                self._traverse(sub_cursor)
            self.current_namespace = None
        elif cursor.kind == cindex.CursorKind.CONSTRUCTOR:
            # print("find CONSTRUCTOR")
            method = FunctionInfo(cursor)
            self.methods.append(method)
        elif cursor.kind == cindex.CursorKind.DESTRUCTOR:
            # print("find DESTRUCTOR")
            method = FunctionInfo(cursor)
            self.methods.append(method)
        elif cursor.kind == cindex.CursorKind.OBJC_INTERFACE_DECL:
            print("find objc define")

    def sorted_classes(self):
        """
        sorted classes in order of inheritance
        """
        sorted_list = []
        for class_name in self.parsed_classes.iterkeys():
            nclass = self.parsed_classes[class_name]
            sorted_list += self._sorted_parents(nclass)
        # remove dupes from the list
        no_dupes = []
        [no_dupes.append(i) for i in sorted_list if not no_dupes.count(i)]
        return no_dupes

    def _sorted_parents(self, nclass):
        """
        returns the sorted list of parents for a native class
        """
        sorted_parents = []
        for p in nclass.parents:
            if p.class_name in self.parsed_classes.keys():
                sorted_parents += self._sorted_parents(p)
        if nclass.class_name in self.parsed_classes.keys():
            sorted_parents.append(nclass.class_name)
        return sorted_parents

    # def should_skip(self, class_name, method_name, verbose=False):
    #     if class_name == "*" and self.skip_classes.has_key("*"):
    #         for func in self.skip_classes["*"]:
    #             if re.match(func, method_name):
    #                 return True
    #     else:
    #         for key in self.skip_classes.iterkeys():
    #             if key == "*" or re.match("^" + key + "$", class_name):
    #                 if verbose:
    #                     print "%s in skip_classes" % (class_name)
    #                 if len(self.skip_classes[key]) == 1 and self.skip_classes[key][0] == "*":
    #                     if verbose:
    #                         print "%s will be skipped completely" % (class_name)
    #                     return True
    #                 if method_name != None:
    #                     for func in self.skip_classes[key]:
    #                         if re.match(func, method_name):
    #                             if verbose:
    #                                 print "%s will skip method %s" % (class_name, method_name)
    #                             return True
    #     if verbose:
    #         print "%s will be accepted (%s, %s)" % (class_name, key, self.skip_classes[key])
    #     return False

# def main():
#     from optparse import OptionParser
#
#     parser = OptionParser("usage: %prog [options] {configfile}")
#     parser.add_option("-s", action="store", type="string", dest="section",
#                       help="sets a specific section to be converted")
#     parser.add_option("-t", action="store", type="string", dest="target",
#                       help="specifies the target vm. Will search for TARGET.yaml")
#     parser.add_option("-o", action="store", type="string", dest="outdir",
#                       help="specifies the output directory for generated C++ code")
#     parser.add_option("-n", action="store", type="string", dest="out_file",
#                       help="specifcies the name of the output file, defaults to the prefix in the .ini file")
#
#     (opts, args) = parser.parse_args()
#
#     # script directory
#     workingdir = os.path.dirname(inspect.getfile(inspect.currentframe()))
#
#     if len(args) == 0:
#         parser.error('invalid number of arguments')
#
#     userconfig = ConfigParser.SafeConfigParser()
#     userconfig.read('userconf.ini')
#     print 'Using userconfig \n ', userconfig.items('DEFAULT')
#
#     clang_lib_path = os.path.join(userconfig.get('DEFAULT', 'cxxgeneratordir'), 'libclang')
#     cindex.Config.set_library_path(clang_lib_path);
#
#     config = ConfigParser.SafeConfigParser()
#     config.read(args[0])
#
#     if (0 == len(config.sections())):
#         raise Exception("No sections defined in config file")
#
#     sections = []
#     if opts.section:
#         if (opts.section in config.sections()):
#             sections = []
#             sections.append(opts.section)
#         else:
#             raise Exception("Section not found in config file")
#     else:
#         print("processing all sections")
#         sections = config.sections()
#
#     # find available targets
#     targetdir = os.path.join(workingdir, "targets")
#     targets = []
#     if (os.path.isdir(targetdir)):
#         targets = [entry for entry in os.listdir(targetdir)
#                    if (os.path.isdir(os.path.join(targetdir, entry)))]
#     if 0 == len(targets):
#         raise Exception("No targets defined")
#
#     if opts.target:
#         if (opts.target in targets):
#             targets = []
#             targets.append(opts.target)
#
#     if opts.outdir:
#         outdir = opts.outdir
#     else:
#         outdir = os.path.join(workingdir, "gen")
#     if not os.path.exists(outdir):
#         os.makedirs(outdir)
#
#     for t in targets:
#         # Fix for hidden '.svn', '.cvs' and '.git' etc. folders - these must be ignored or otherwise they will be interpreted as a target.
#         if t == ".svn" or t == ".cvs" or t == ".git" or t == ".gitignore":
#             continue
#
#         print "\n.... Generating bindings for target", t
#         for s in sections:
#             print "\n.... .... Processing section", s, "\n"
#             gen_opts = {
#                 'prefix': config.get(s, 'prefix'),
#                 'headers': (config.get(s, 'headers', 0, dict(userconfig.items('DEFAULT')))),
#                 'replace_headers': config.get(s, 'replace_headers') if config.has_option(s,
#                                                                                          'replace_headers') else None,
#                 'classes': config.get(s, 'classes').split(' '),
#                 'classes_need_extend': config.get(s, 'classes_need_extend').split(' ') if config.has_option(s,
#                                                                                                             'classes_need_extend') else [],
#                 'clang_args': (config.get(s, 'extra_arguments', 0, dict(userconfig.items('DEFAULT'))) or "").split(" "),
#                 'target': os.path.join(workingdir, "targets", t),
#                 'outdir': outdir,
#                 'search_path': os.path.abspath(os.path.join(userconfig.get('DEFAULT', 'cocosdir'), 'cocos')),
#                 'remove_prefix': config.get(s, 'remove_prefix'),
#                 'target_ns': config.get(s, 'target_namespace'),
#                 'cpp_ns': config.get(s, 'cpp_namespace').split(' ') if config.has_option(s, 'cpp_namespace') else None,
#                 'classes_have_no_parents': config.get(s, 'classes_have_no_parents'),
#                 'base_classes_to_skip': config.get(s, 'base_classes_to_skip'),
#                 'abstract_classes': config.get(s, 'abstract_classes'),
#                 'skip': config.get(s, 'skip'),
#                 'field': config.get(s, 'field') if config.has_option(s, 'field') else None,
#                 'rename_functions': config.get(s, 'rename_functions'),
#                 'rename_classes': config.get(s, 'rename_classes'),
#                 'out_file': opts.out_file or config.get(s, 'prefix'),
#                 'script_control_cpp': config.get(s, 'script_control_cpp') if config.has_option(s,
#                                                                                                'script_control_cpp') else 'no',
#                 'script_type': t,
#                 'macro_judgement': config.get(s, 'macro_judgement') if config.has_option(s,
#                                                                                          'macro_judgement') else None,
#                 'hpp_headers': config.get(s, 'hpp_headers', 0, dict(userconfig.items('DEFAULT'))).split(
#                     ' ') if config.has_option(s, 'hpp_headers') else None,
#                 'cpp_headers': config.get(s, 'cpp_headers', 0, dict(userconfig.items('DEFAULT'))).split(
#                     ' ') if config.has_option(s, 'cpp_headers') else None,
#                 'win32_clang_flags': (
#                         config.get(s, 'win32_clang_flags', 0, dict(userconfig.items('DEFAULT'))) or "").split(
#                     " ") if config.has_option(s, 'win32_clang_flags') else None
#             }
#             parser = Parser(gen_opts)
#             parser.parse_file()
#
#
# if __name__ == '__main__':
#     try:
#         main()
#     except Exception as e:
#         traceback.print_exc()
#         sys.exit(1)
