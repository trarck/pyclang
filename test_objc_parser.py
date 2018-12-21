from cparser.parser import Parser

opts = {
    'prefix': '',
    'headers': None,
    'replace_headers':None,
    'classes': None,
     'clang_args': [],
    'search_path': '',
    'cpp_ns': None,
    'skip': '',
    'macro_judgement': None,
    'hpp_headers':  None,
    'cpp_headers': None,
    'win32_clang_flags':  None
}
parser = Parser(opts)
parser.parse_file("data/e.m")
print("methods:%d,class:%d" %(len(parser.methods),len(parser.parsed_classes)))
for key,nc in parser.parsed_classes.iteritems():
    implment_count=0
    for method in nc.methods:
        if method.is_implement:
            implment_count+=1
    print ("class:%s,files:%d,methods:%d-%d"%(key, len(nc.fields),len(nc.methods),implment_count))