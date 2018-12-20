#!/usr/bin/env python
# generator.py
# simple C++ generator, originally targetted for Spidermonkey bindings
#
# Copyright (c) 2011 - Zynga Inc.

from clang import cindex
import sys
import re
import os

type_map = {
    cindex.TypeKind.VOID: "void",
    cindex.TypeKind.BOOL: "bool",
    cindex.TypeKind.CHAR_U: "unsigned char",
    cindex.TypeKind.UCHAR: "unsigned char",
    cindex.TypeKind.CHAR16: "char",
    cindex.TypeKind.CHAR32: "char",
    cindex.TypeKind.USHORT: "unsigned short",
    cindex.TypeKind.UINT: "unsigned int",
    cindex.TypeKind.ULONG: "unsigned long",
    cindex.TypeKind.ULONGLONG: "unsigned long long",
    cindex.TypeKind.CHAR_S: "char",
    cindex.TypeKind.SCHAR: "char",
    cindex.TypeKind.WCHAR: "wchar_t",
    cindex.TypeKind.SHORT: "short",
    cindex.TypeKind.INT: "int",
    cindex.TypeKind.LONG: "long",
    cindex.TypeKind.LONGLONG: "long long",
    cindex.TypeKind.FLOAT: "float",
    cindex.TypeKind.DOUBLE: "double",
    cindex.TypeKind.LONGDOUBLE: "long double",
    cindex.TypeKind.NULLPTR: "NULL",
    cindex.TypeKind.OBJCID: "id",
    cindex.TypeKind.OBJCCLASS: "class",
    cindex.TypeKind.OBJCSEL: "SEL",
    # cindex.TypeKind.ENUM        : "int"
}

INVALID_NATIVE_TYPE = "??"

default_arg_type_arr = [

    # An integer literal.
    cindex.CursorKind.INTEGER_LITERAL,

    # A floating point number literal.
    cindex.CursorKind.FLOATING_LITERAL,

    # An imaginary number literal.
    cindex.CursorKind.IMAGINARY_LITERAL,

    # A string literal.
    cindex.CursorKind.STRING_LITERAL,

    # A character literal.
    cindex.CursorKind.CHARACTER_LITERAL,

    # [C++ 2.13.5] C++ Boolean Literal.
    cindex.CursorKind.CXX_BOOL_LITERAL_EXPR,

    # [C++0x 2.14.7] C++ Pointer Literal.
    cindex.CursorKind.CXX_NULL_PTR_LITERAL_EXPR,

    cindex.CursorKind.GNU_NULL_EXPR,

    # An expression that refers to some value declaration, such as a function,
    # varible, or enumerator.
    cindex.CursorKind.DECL_REF_EXPR
]

stl_type_map = {
    'std_function_args': 1000,
    'std::unordered_map': 2,
    'std::unordered_multimap': 2,
    'std::map': 2,
    'std::multimap': 2,
    'std::vector': 1,
    'std::list': 1,
    'std::forward_list': 1,
    'std::priority_queue': 1,
    'std::set': 1,
    'std::multiset': 1,
    'std::unordered_set': 1,
    'std::unordered_multiset': 1,
    'std::stack': 1,
    'std::queue': 1,
    'std::deque': 1,
    'std::array': 1,

    'unordered_map': 2,
    'unordered_multimap': 2,
    'map': 2,
    'multimap': 2,
    'vector': 1,
    'list': 1,
    'forward_list': 1,
    'priority_queue': 1,
    'set': 1,
    'multiset': 1,
    'unordered_set': 1,
    'unordered_multiset': 1,
    'stack': 1,
    'queue': 1,
    'deque': 1,
    'array': 1
}

access_specifier_map = {
    cindex.AccessSpecifier.INVALID: "invalid",
    cindex.AccessSpecifier.PUBLIC: "public",
    cindex.AccessSpecifier.PROTECTED: "protected",
    cindex.AccessSpecifier.PRIVATE: "private",
    cindex.AccessSpecifier.NONE: "none"
}


def find_sub_string_count(s, start, end, substr):
    count = 0
    pos = s.find(substr, start, end)
    if pos != -1:
        next_count = find_sub_string_count(s, pos + 1, end, substr)
        count = next_count + 1
    return count


def split_container_name(name):
    name = name.strip()
    left = name.find('<')
    right = -1

    if left != -1:
        right = name.rfind('>')

    if left == -1 or right == -1:
        return [name]

    first = name[:left]
    results = [first]

    comma = name.find(',', left + 1, right)
    if comma == -1:
        results.append(name[left + 1:right].strip())
        return results

    left += 1
    while comma != -1:
        lt_count = find_sub_string_count(name, left, comma, '<')
        gt_count = find_sub_string_count(name, left, comma, '>')
        if lt_count == gt_count:
            results.append(name[left:comma].strip())
            left = comma + 1
        comma = name.find(',', comma + 1, right)

    if left < right:
        results.append(name[left:right].strip())
    name_len = len(name)
    if right < name_len - 1:
        results.append(name[right + 1:].strip())

    return results


def normalize_type_name_by_sections(sections):
    container_name = sections[0]
    suffix = ''

    index = len(sections) - 1
    while sections[index] == '*' or sections[index] == '&':
        suffix += sections[index]
        index -= 1

    name_for_search = container_name.replace('const ', '').replace('&', '').replace('*', '').strip()
    if name_for_search in stl_type_map:
        normalized_name = container_name + '<' + ', '.join(sections[1:1 + stl_type_map[name_for_search]]) + '>' + suffix
    else:
        normalized_name = container_name + '<' + ', '.join(sections[1:]) + '>'

    return normalized_name


def normalize_std_function_by_sections(sections):
    normalized_name = ''
    if sections[0] == 'std_function_args':
        normalized_name = '(' + ', '.join(sections[1:]) + ')'
    elif sections[0] == 'std::function' or sections[0] == 'function':
        normalized_name = 'std::function<' + sections[1] + ' ' + sections[2] + '>'
    else:
        assert (False)
    return normalized_name


def normalize_type_str(s, depth=1):
    if s.find('std::function') == 0 or s.find('function') == 0:
        start = s.find('<')
        assert (start > 0)
        sections = [s[:start]]  # std::function
        start += 1
        ret_pos = s.find('(', start)
        sections.append(s[start:ret_pos].strip())  # return type
        end = s.find(')', ret_pos + 1)
        sections.append('std_function_args<' + s[ret_pos + 1:end].strip() + '>')
    else:
        sections = split_container_name(s)
    section_len = len(sections)
    if section_len == 1:
        return sections[0]

    # for section in sections:
    #     print('>' * depth + section)

    if sections[0] == 'const std::basic_string' or sections[0] == 'const basic_string':
        last_section = sections[len(sections) - 1]
        if last_section == '&' or last_section == '*' or last_section.startswith('::'):
            return 'const std::string' + last_section
        else:
            return 'const std::string'

    elif sections[0] == 'std::basic_string' or sections[0] == 'basic_string':
        last_section = sections[len(sections) - 1]
        if last_section == '&' or last_section == '*' or last_section.startswith('::'):
            return 'std::string' + last_section
        else:
            return 'std::string'

    for i in range(1, section_len):
        sections[i] = normalize_type_str(sections[i], depth + 1)

    if sections[0] == 'std::function' or sections[0] == 'function' or sections[0] == 'std_function_args':
        normalized_name = normalize_std_function_by_sections(sections)
    else:
        normalized_name = normalize_type_name_by_sections(sections)
    return normalized_name


def native_name_from_type(type_cursor, underlying=False):
    kind = type_cursor.kind  # get_canonical().kind
    const = ""  # "const " if ntype.is_const_qualified() else ""
    if not underlying and kind == cindex.TypeKind.ENUM:
        decl = type_cursor.get_declaration()
        return get_fullname(decl)
    elif kind in type_map:
        return const + type_map[kind]
    elif kind == cindex.TypeKind.RECORD:
        # might be an std::string
        decl = type_cursor.get_declaration()
        parent = decl.semantic_parent
        cdecl = type_cursor.get_canonical().get_declaration()
        cparent = cdecl.semantic_parent
        if decl.spelling == "string" and parent and parent.spelling == "std":
            return "std::string"
        elif cdecl.spelling == "function" and cparent and cparent.spelling == "std":
            return "std::function"
        else:
            # print >> sys.stderr, "probably a function pointer: " + str(decl.spelling)
            return const + decl.spelling
    else:
        # name = ntype.get_declaration().spelling
        # print >> sys.stderr, "Unknown type: " + str(kind) + " " + str(name)
        return INVALID_NATIVE_TYPE
        # pdb.set_trace()


def build_fullname(cursor, namespaces=[]):
    """
    build the full namespace for a specific cursor
    """
    if cursor:
        parent = cursor.semantic_parent
        while parent and (parent.kind == cindex.CursorKind.NAMESPACE or parent.kind == cindex.CursorKind.CLASS_DECL):
            namespaces.append(parent.displayname)
            parent = parent.semantic_parent

        # if parent:
        #     if parent.kind == cindex.CursorKind.NAMESPACE or parent.kind == cindex.CursorKind.CLASS_DECL:
        #         namespaces.append(parent.displayname)
        #         build_fullname(parent, namespaces)

    return namespaces


def get_fullname(cursor):
    ns_list = build_fullname(cursor, [])
    ns_list.reverse()
    ns = "::".join(ns_list)
    display_name = cursor.displayname.replace("::__ndk1", "")
    if len(ns) > 0:
        ns = ns.replace("::__ndk1", "")
        return ns + "::" + display_name
    return display_name


def build_namespace_list(cursor, namespaces=[]):
    """
    build the full namespace for a specific cursor
    """
    if cursor:
        parent = cursor.semantic_parent
        while parent and (parent.kind == cindex.CursorKind.NAMESPACE or parent.kind == cindex.CursorKind.CLASS_DECL):
            if parent.kind == cindex.CursorKind.NAMESPACE:
                namespaces.append(parent.displayname)
            parent = parent.semantic_parent
        # if parent:
        #     if parent.kind == cindex.CursorKind.NAMESPACE or parent.kind == cindex.CursorKind.CLASS_DECL:
        #         if parent.kind == cindex.CursorKind.NAMESPACE:
        #             namespaces.append(parent.displayname)
        #         build_namespace_list(parent, namespaces)
    return namespaces


def get_namespace_name(cursor):
    ns_list = build_namespace_list(cursor, [])
    ns_list.reverse()
    ns = "::".join(ns_list)

    if len(ns) > 0:
        ns = ns.replace("::__ndk1", "")
        return ns

    return ""


class NativeType(object):
    def __init__(self, cursor=None):
        self.cursor = cursor
        self.is_object = False
        self.is_function = False
        self.is_enum = False
        self.is_numeric = False
        self.is_const = False
        self.is_pointer = False
        self.not_supported = False
        self.param_types = []
        self.ret_type = None
        self.fullname = ""  # with namespace and class name
        self.namespace_name = ""  # only contains namespace
        self.name = ""
        self.whole_name = None
        self.canonical_type = None

    @staticmethod
    def from_type(type_cursor):
        if type_cursor.kind == cindex.TypeKind.POINTER:
            nt = NativeType.from_type(type_cursor.get_pointee())

            if None != nt.canonical_type:
                nt.canonical_type.name += "*"
                nt.canonical_type.fullname += "*"
                nt.canonical_type.whole_name += "*"

            nt.name += "*"
            nt.fullname += "*"
            nt.whole_name = nt.fullname
            nt.is_enum = False
            nt.is_const = type_cursor.get_pointee().is_const_qualified()
            nt.is_pointer = True
            if nt.is_const:
                nt.whole_name = "const " + nt.whole_name
        elif type_cursor.kind == cindex.TypeKind.LVALUEREFERENCE:
            nt = NativeType.from_type(type_cursor.get_pointee())
            nt.is_const = type_cursor.get_pointee().is_const_qualified()
            nt.whole_name = nt.whole_name + "&"

            if nt.is_const:
                nt.whole_name = "const " + nt.whole_name

            if None != nt.canonical_type:
                nt.canonical_type.whole_name += "&"
        else:
            nt = NativeType(type_cursor)
            decl = type_cursor.get_declaration()

            nt.fullname = get_fullname(decl).replace('::__ndk1', '')

            if decl.kind == cindex.CursorKind.CLASS_DECL \
                    and not nt.fullname.startswith('std::function') \
                    and not nt.fullname.startswith('std::string') \
                    and not nt.fullname.startswith('std::basic_string'):
                nt.is_object = True
                displayname = decl.displayname.replace('::__ndk1', '')
                nt.name = normalize_type_str(displayname)
                nt.fullname = normalize_type_str(nt.fullname)
                nt.namespace_name = get_namespace_name(decl)
                nt.whole_name = nt.fullname
            else:
                if decl.kind == cindex.CursorKind.NO_DECL_FOUND:
                    nt.name = native_name_from_type(type_cursor)
                else:
                    nt.name = decl.spelling
                nt.namespace_name = get_namespace_name(decl)

                if len(nt.fullname) > 0:
                    nt.fullname = normalize_type_str(nt.fullname)

                if nt.fullname.startswith("std::function"):
                    nt.name = "std::function"

                if len(nt.fullname) == 0 or nt.fullname.find("::") == -1:
                    nt.fullname = nt.name

                nt.whole_name = nt.fullname
                nt.is_const = type_cursor.is_const_qualified()
                if nt.is_const:
                    nt.whole_name = "const " + nt.whole_name

                # Check whether it's a std::function typedef
                cdecl = type_cursor.get_canonical().get_declaration()
                if None != cdecl.spelling and 0 == cmp(cdecl.spelling, "function"):
                    nt.name = "std::function"

                if nt.name != INVALID_NATIVE_TYPE and nt.name != "std::string" and nt.name != "std::function":
                    if type_cursor.kind == cindex.TypeKind.UNEXPOSED or type_cursor.kind == cindex.TypeKind.TYPEDEF or type_cursor.kind == cindex.TypeKind.ELABORATED:
                        ret = NativeType.from_type(type_cursor.get_canonical())
                        if ret.name != "":
                            if decl.kind == cindex.CursorKind.TYPEDEF_DECL:
                                ret.canonical_type = nt
                            return ret

                nt.is_enum = type_cursor.get_canonical().kind == cindex.TypeKind.ENUM

                if nt.name == "std::function":
                    nt.is_object = False
                    lambda_display_name = get_fullname(cdecl)
                    lambda_display_name = lambda_display_name.replace("::__ndk1", "")
                    lambda_display_name = normalize_type_str(lambda_display_name)
                    nt.fullname = lambda_display_name
                    r = re.compile('function<([^\s]+).*\((.*)\)>').search(nt.fullname)
                    (ret_type, params) = r.groups()
                    params = filter(None, params.split(", "))

                    nt.is_function = True
                    nt.ret_type = NativeType.from_string(ret_type)
                    nt.param_types = [NativeType.from_string(string) for string in params]

        # mark argument as not supported
        if nt.name == INVALID_NATIVE_TYPE:
            nt.not_supported = True

        if re.search("(short|int|double|float|long|size_t)$", nt.name) is not None:
            nt.is_numeric = True

        return nt

    @staticmethod
    def from_string(displayname):
        displayname = displayname.replace(" *", "*")

        nt = NativeType()
        nt.name = displayname.split("::")[-1]
        nt.fullname = displayname
        nt.whole_name = nt.fullname
        nt.is_object = True
        return nt

    @property
    def lambda_parameters(self):
        params = ["%s larg%d" % (str(nt), i) for i, nt in enumerate(self.param_types)]
        return ", ".join(params)

    def __str__(self):
        return self.canonical_type.whole_name if None != self.canonical_type else self.whole_name


class FieldAttributes(object):
    Empty = 0
    Private = 1
    Protected = 2
    Public = 3

    BaseAttributeEnd = 15

    Static = 16


class NativeField(object):
    def __init__(self, cursor):
        cursor = cursor.canonical
        self.cursor = cursor
        self.name = cursor.displayname
        self.kind = cursor.type.kind
        self.location = cursor.location

        self.signature_name = self.name
        self.field_type = NativeType.from_type(cursor.type)
        self.attributes = FieldAttributes.Empty

        if self.cursor.access_specifier == cindex.AccessSpecifier.PRIVATE:
            self.set_attribute(FieldAttributes.Private)
        elif self.cursor.access_specifier == cindex.AccessSpecifier.PROTECTED:
            self.set_attribute(FieldAttributes.Protected)
        elif self.cursor.access_specifier == cindex.AccessSpecifier.PUBLIC:
            self.set_attribute(FieldAttributes.Public)

    def set_attribute(self, value):
        if value > FieldAttributes.BaseAttributeEnd:
            self.attributes = self.attributes | value
        else:
            self.attributes = (self.attributes ^ (self.attributes & FieldAttributes.BaseAttributeEnd)) | value

    @property
    def is_private(self):
        return self.attributes & FieldAttributes.BaseAttributeEnd == FieldAttributes.Private

    @property
    def is_protected(self):
        return self.attributes & FieldAttributes.BaseAttributeEnd == FieldAttributes.Protected

    @property
    def is_public(self):
        return self.attributes & FieldAttributes.BaseAttributeEnd == FieldAttributes.Public

    @property
    def is_static(self):
        return self.attributes & FieldAttributes.Static > 0

    @staticmethod
    def can_parse(type_cursor):
        native_type = NativeType.from_type(type_cursor)
        if type_cursor.kind == cindex.TypeKind.UNEXPOSED and native_type.name != "std::string":
            return False
        return True


# return True if found default argument.
def iterate_param_node(param_node, depth=1):
    for node in param_node.get_children():
        # print(">"*depth+" "+str(node.kind))
        if node.kind in default_arg_type_arr:
            return True

        if iterate_param_node(node, depth + 1):
            return True

    return False


class FunctionAttributes(object):
    Empty = 0
    Private = 1
    Protected = 2
    Public = 3

    BaseAttributeEnd = 15
    Static = 16
    Final = 32
    Virtual = 64
    Constructor = 128
    Destructor = 256
    Const = 512
    Implement = 1024


class NativeFunction(object):
    def __init__(self, cursor):
        self.cursor = cursor
        self.func_name = cursor.spelling
        self.signature_name = self.func_name
        self.arguments = []
        self.argumentTips = []
        self.implementations = []
        self.is_overloaded = False
        self.is_constructor = False
        self.not_supported = False
        self.is_override = False
        self.ret_type = NativeType.from_type(cursor.result_type)
        self.comment = self.get_comment(cursor.raw_comment)
        self.attributes = FunctionAttributes.Empty
        self.class_name = None

        self._parse()

    def _parse(self):
        # parse the arguments

        for arg in self.cursor.get_arguments():
            self.argumentTips.append(arg.spelling)

        for arg in self.cursor.type.argument_types():
            nt = NativeType.from_type(arg)
            self.arguments.append(nt)
            # mark the function as not supported if at least one argument is not supported
            if nt.not_supported:
                self.not_supported = True

        found_default_arg = False
        index = -1

        for arg_node in self.cursor.get_children():
            if arg_node.kind == cindex.CursorKind.CXX_OVERRIDE_ATTR:
                self.is_override = True
            if arg_node.kind == cindex.CursorKind.PARM_DECL:
                index += 1
                if iterate_param_node(arg_node):
                    found_default_arg = True
                    break

        self.min_args = index if found_default_arg else len(self.arguments)

        # set access specifier
        if self.cursor.access_specifier == cindex.AccessSpecifier.PRIVATE:
            self.set_attribute(FunctionAttributes.Private)
        elif self.cursor.access_specifier == cindex.AccessSpecifier.PROTECTED:
            self.set_attribute(FunctionAttributes.Protected)
        elif self.cursor.access_specifier == cindex.AccessSpecifier.PUBLIC:
            self.set_attribute(FunctionAttributes.Public)

        # check is static function
        if self.cursor.is_static_method():
            self.set_attribute(FunctionAttributes.Static)

        # check is virtual function
        if self.cursor.is_virtual_method():
            self.set_attribute(FunctionAttributes.Virtual)

        if self.cursor.is_const_method():
            self.set_attribute(FunctionAttributes.Const)

        # set class name
        if self.cursor.semantic_parent.kind == cindex.CursorKind.CLASS_DECL:
            self.class_name = get_fullname(self.cursor.semantic_parent)

        # check have implement
        if self._check_have_implement():
            self.set_attribute(FunctionAttributes.Implement)

    def _check_have_implement(self):
        have_implement = False

        for node in self.cursor.get_children():
            if node.kind == cindex.CursorKind.COMPOUND_STMT:
                have_implement = True
                break
        return have_implement

    def get_comment(self, comment):
        replace_str = comment

        if comment is None:
            return ""

        regular_replace_list = [
            ("(\s)*//!", ""),
            ("(\s)*//", ""),
            ("(\s)*/\*\*", ""),
            ("(\s)*/\*", ""),
            ("\*/", ""),
            ("\r\n", "\n"),
            ("\n(\s)*\*", "\n"),
            ("\n(\s)*@", "\n"),
            ("\n(\s)*", "\n"),
            ("\n(\s)*\n", "\n"),
            ("^(\s)*\n", ""),
            ("\n(\s)*$", ""),
            ("\n", "<br>\n"),
            ("\n", "\n-- ")
        ]

        for item in regular_replace_list:
            replace_str = re.sub(item[0], item[1], replace_str)

        return replace_str

    def set_attribute(self, value):
        if value > FunctionAttributes.BaseAttributeEnd:
            self.attributes = self.attributes | value
        else:
            self.attributes = (self.attributes ^ (self.attributes & FunctionAttributes.BaseAttributeEnd)) | value

    @property
    def is_private(self):
        return self.attributes & FunctionAttributes.BaseAttributeEnd == FunctionAttributes.Private

    @property
    def is_protected(self):
        return self.attributes & FunctionAttributes.BaseAttributeEnd == FunctionAttributes.Protected

    @property
    def is_public(self):
        return self.attributes & FunctionAttributes.BaseAttributeEnd == FunctionAttributes.Public

    @property
    def is_static(self):
        return self.attributes & FunctionAttributes.Static > 0

    @property
    def is_virtual(self):
        return self.attributes & FunctionAttributes.Virtual > 0

    @property
    def is_const(self):
        return self.attributes & FunctionAttributes.Const > 0

    @property
    def is_implement(self):
        return self.attributes & FunctionAttributes.Implement > 0

    def get_extent_start(self):
        if self.cursor is not None:
            return self.cursor.extent.start
        else:
            return None

    def get_extent_start_line(self):
        if self.cursor is not None:
            return self.cursor.extent.start.line
        else:
            return -1

    def get_extent_end(self):
        if self.cursor is not None:
            return self.cursor.extent.end
        else:
            return None

    def get_extent_end_line(self):
        if self.cursor is not None:
            return self.cursor.extent.end.line
        else:
            return -1


class NativeClass(object):
    def __init__(self, cursor):
        # the cursor to the implementation
        self.cursor = cursor
        self.class_name = cursor.displayname
        self.is_ref_class = self.class_name == "Ref"
        self.full_class_name = self.class_name
        self.parents = []
        self.fields = []
        self.public_fields = []
        self.static_fields = []
        self.methods = []
        self.static_methods = []
        self.is_abstract = False  # self.class_name in generator.abstract_classes
        self._current_visibility = cindex.AccessSpecifier.PRIVATE
        # for generate lua api doc
        self.override_methods = {}
        self.has_constructor = False
        self.namespace_name = ""

        self.full_class_name = get_fullname(cursor)
        self.namespace_name = get_namespace_name(cursor)

        self._parse()

    @property
    def underlined_class_name(self):
        return self.full_class_name.replace("::", "_")

    def _parse(self):
        """
        parse the current cursor, getting all the necesary information
        """
        # the root cursor is CLASS_DECL.
        for cursor in self.cursor.get_children():
            self._traverse(cursor)

    def methods_clean(self):
        """
        clean list of methods (without the ones that should be skipped)
        """
        ret = []
        for name, impl in self.methods.iteritems():
            should_skip = False
            if name == 'constructor':
                should_skip = True
            else:
                if self.generator.should_skip(self.class_name, name):
                    should_skip = True
            if not should_skip:
                ret.append({"name": name, "impl": impl})
        return ret

    def static_methods_clean(self):
        """
        clean list of static methods (without the ones that should be skipped)
        """
        ret = []
        for name, impl in self.static_methods.iteritems():
            should_skip = self.generator.should_skip(self.class_name, name)
            if not should_skip:
                ret.append({"name": name, "impl": impl})
        return ret

    def override_methods_clean(self):
        """
        clean list of override methods (without the ones that should be skipped)
        """
        ret = []
        for name, impl in self.override_methods.iteritems():
            should_skip = self.generator.should_skip(self.class_name, name)
            if not should_skip:
                ret.append({"name": name, "impl": impl})
        return ret

    def _traverse(self, cursor=None, depth=0):
        if cursor.kind == cindex.CursorKind.CXX_BASE_SPECIFIER:
            parent = cursor.get_definition()
            parent_name = parent.displayname

            # if not self.class_name in self.generator.classes_have_no_parents:
            #     if parent_name and parent_name not in self.generator.base_classes_to_skip:
            #         # if parent and self.generator.in_listed_classes(parent.displayname):
            #         if not self.generator.parsed_classes.has_key(parent.displayname):
            #             parent = NativeClass(parent, self.generator)
            #             self.generator.parsed_classes[parent.class_name] = parent
            #         else:
            #             parent = self.generator.parsed_classes[parent.displayname]
            #
            #         self.parents.append(parent)
            #
            # if parent_name == "Ref":
            #     self.is_ref_class = True

        elif cursor.kind == cindex.CursorKind.FIELD_DECL:
            self.fields.append(NativeField(cursor))
            if self._current_visibility == cindex.AccessSpecifier.PUBLIC and NativeField.can_parse(cursor.type):
                self.public_fields.append(NativeField(cursor))
        elif cursor.kind == cindex.CursorKind.VAR_DECL:
            self.static_fields.append(NativeField(cursor))
        elif cursor.kind == cindex.CursorKind.CXX_ACCESS_SPEC_DECL:
            self._current_visibility = cursor.access_specifier
        elif cursor.kind == cindex.CursorKind.CXX_METHOD:  # and cursor.availability != cindex.AvailabilityKind.DEPRECATED:
            # skip if variadic
            m = NativeFunction(cursor)
            registration_name = m.func_name  # self.generator.should_rename_function(self.class_name, m.func_name) or m.func_name
            # bail if the function is not supported (at least one arg not supported)
            if m.not_supported:
                return None

            self.methods.append(m)
        elif cursor.kind == cindex.CursorKind.CONSTRUCTOR and not self.is_abstract:
            # Skip copy constructor
            if cursor.displayname == self.class_name + "(const " + self.full_class_name + " &)":
                # print "Skip copy constructor: " + cursor.displayname
                return None

            m = NativeFunction(cursor)
            m.is_constructor = True
            m.set_attribute(FunctionAttributes.Constructor)
            self.has_constructor = True
            self.methods.append(m)
        elif cursor.kind == cindex.CursorKind.DESTRUCTOR:
            m = NativeFunction(cursor)
            m.set_attribute(FunctionAttributes.Destructor)
            self.methods.append(m)

        # else:
        # print >> sys.stderr, "unknown cursor: %s - %s" % (cursor.kind, cursor.displayname)

    @staticmethod
    def _is_method_in_parents(current_class, method_name):
        if len(current_class.parents) > 0:
            if method_name in current_class.parents[0].methods:
                return True
            return NativeClass._is_method_in_parents(current_class.parents[0], method_name)
        return False

    def _is_ref_class(self, depth=0):
        """
        Mark the class as 'cocos2d::Ref' or its subclass.
        """
        # print ">" * (depth + 1) + " " + self.class_name

        for parent in self.parents:
            if parent._is_ref_class(depth + 1):
                return True

        if self.is_ref_class:
            return True

        return False


class NativeNameSpace(object):
    def __init__(self, cursor):
        self.cursor = cursor


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
                    nclass = NativeClass(cursor)
                    self.parsed_classes[cursor.displayname] = nclass
                return
        elif cursor.kind == cindex.CursorKind.FUNCTION_DECL:
            # print("find function")
            fun = NativeFunction(cursor)
            self.methods.append(fun)
        elif cursor.kind == cindex.CursorKind.CXX_METHOD:
            # print("find method")
            method = NativeFunction(cursor)
            self.methods.append(method)
        elif cursor.kind == cindex.CursorKind.NAMESPACE:
            # print("find namespace")
            self.current_namespace = cursor.spelling
            for sub_cursor in cursor.get_children():
                self._traverse(sub_cursor)
            self.current_namespace = None
        elif cursor.kind == cindex.CursorKind.CONSTRUCTOR:
            # print("find CONSTRUCTOR")
            method = NativeFunction(cursor)
            self.methods.append(method)
        elif cursor.kind == cindex.CursorKind.DESTRUCTOR:
            # print("find DESTRUCTOR")
            method = NativeFunction(cursor)
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
