from cpp_parser import Parser

opts = {
    'prefix': '',
    'headers': None,
    'replace_headers':None,
    'classes': None,
    'classes_need_extend':[],
    'clang_args': [],
    'target': '',
    'outdir': '',
    'search_path': '',
    'remove_prefix': '',
    'target_ns': '',
    'cpp_ns': None,
    'classes_have_no_parents': '',
    'base_classes_to_skip': '',
    'abstract_classes': '',
    'skip': '',
    'field': None,
    'rename_functions': None,
    'rename_classes':None,
    'out_file': None,
    'script_control_cpp':'no',
    'script_type': None,
    'macro_judgement': None,
    'hpp_headers':  None,
    'cpp_headers': None,
    'win32_clang_flags':  None
}
parser = Parser(opts)
parser.parse_file("data/a.cpp")
print(parser)