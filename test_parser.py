from cpp_parser import Parser

opts = {
    'prefix': '',
    'headers': None,
    'replace_headers':None,
    'classes': None,
     'clang_args': ["-x","c++","-ID:/c/cocos2d-x/cocos","-ID:/c/cocos2d-x/external/win32-specific/gles/include/OGLES","-ID:/c/cocos2d-x/external/glfw3/include/win32","-D_WINDOWS","-DWIN32","-D_USRDLL"],
    'search_path': '',
    'cpp_ns': None,
    'skip': '',
    'macro_judgement': None,
    'hpp_headers':  None,
    'cpp_headers': None,
    'win32_clang_flags':  None
}
parser = Parser(opts)
parser.parse_file("D:\\c\\cocos2d-x\\cocos\\base\\CCController-linux-win32.cpp")
print("methods:%d,class:%d" %(len(parser.methods),len(parser.parsed_classes)))
for key,nc in parser.parsed_classes.iteritems():
    implment_count=0
    for method in nc.methods:
        if method.is_implement:
            implment_count+=1
    print ("class:%s,files:%d,methods:%d-%d"%(key, len(nc.fields),len(nc.methods),implment_count))