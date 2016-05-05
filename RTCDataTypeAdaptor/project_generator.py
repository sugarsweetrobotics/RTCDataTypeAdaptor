import os, sys, optparse, traceback
import shutil

from jinja2 import Environment, FileSystemLoader
from . import __path__

idlparser = None
#import idl_parser

from idl_parser.parser import IDLParser

include_dirs = []

def parse_args(argv):
    optparser = optparse.OptionParser()
    optparser.add_option("-I", "--include", help="Include Directory", action="append", dest="include_dirs", default=[])
    optparser.add_option("-v", "--verbose", help="Verbose (default=false)", action="store_true", dest="verbose", default=False)
    optparser.add_option("-b", "--backend", help="Backend Language (default=c)", action="store", dest="backend", default='c')
    optparser.add_option("-o", "--outdir", help="Output Dir (default=out)", action="store", dest="outdir", default='out')
    options, args = optparser.parse_args(argv)
    backend = options.backend
    verbose = options.verbose
    outdir = options.outdir
    include_dirs = options.include_dirs
    return args, include_dirs, backend, verbose, outdir

def update_include_dirs(dirs):
    ret = []
    for d in dirs:
        ret.append(os.path.expandvars(d).replace('\\', '/').replace('//', '/'))
    return ret


def parse_global_module(gm, language, idl_identifier, idl_path, description='', version='1.0.0', vendor='VENDOR_NAME', author='AUTHOR_NAME', author_short='AUTHOR', base_dir=None, package_dir='.', verbose=False, outdir=None):
    if verbose: print('parse_global_module(%s, %s,  %s, %s, %s, %s, %s, %s, %s, %s, %s)' % (gm, language, idl_identifier, idl_path, description, version, vendor, author, author_short, base_dir, package_dir))
    cwd = os.getcwd()
    if base_dir is None:
        base_dir = cwd

    idl_filepath = os.path.join(base_dir, idl_path)
    if verbose: print('idl_filepath = %s' % idl_filepath)
    datatypes = parse_module(gm, idl_filepath)
    
    module_tree = parse_module_tree({}, gm, idl_filepath)

    idls = [ {'filename' : idl_identifier + '.idl' } ]
    includes = idlparser.includes(idl_filepath)
    include_idls = [ {'filename' : os.path.basename(f)} for f in includes ]
    
    template_backend_dir = os.path.join(__path__[0], 'template', language)
    if verbose: print('- template_backend_dir = %s' % template_backend_dir)
    if not os.path.isdir(template_backend_dir):
        if verbose: print 'Backend (%s) is not available' % language
        raise InvalidBackendException()
    os.chdir(template_backend_dir)

    if outdir == None:
        backend_dir = os.path.join(base_dir, language)
    else:
        backend_dir = os.path.join(base_dir, outdir)
    
    for root, dirs, files in os.walk('.'):
        env = Environment(loader=FileSystemLoader(root, encoding='utf8'), extensions=['jinja2.ext.do'])
        for f in files:
            if not f.endswith('.tpl'):
                continue

            project_dir = os.path.join(backend_dir, idl_identifier, root)
            if not os.path.isdir(project_dir):
                os.mkdir(project_dir)
            filename = f[:-4]

            file_tpl = env.get_template(filename + '.tpl')
            if verbose: print('- file_tpl = %s' % file_tpl)

            project = { 'name': idl_identifier,
                        'version': version,
                        'description': description,
                        'vendor': vendor,
                        'author': author,
                        'author_short': author_short }


            if filename.find('DATATYPE') < 0:
                #if root.find('include') > 0:
                    #print root, datatypes
                output_txt = file_tpl.render({'filename' : idl_identifier, 
                                              'project': project,
                                              'idls' : idls,
                                              'include_idls' : include_idls,
                                              'datatypes' : datatypes,
                                              'module_tree' : module_tree,
                                              })

                open(os.path.join(project_dir, filename), 'w').write(output_txt)
            else:
                #for d in datatypes:
                if True:
                    #if d:
                    if True:
                        #outputfilename = filename.replace('DATATYPE', d['full_path'].replace('::', '_'))
                        outputfilename = filename.replace('DATATYPE', idl_identifier)
                        output_txt = file_tpl.render({'filename': idl_identifier,
                                                      'project': project,
                                                      'idls' : idls,
                                                      'datatypes' : datatypes,
                                                      'module_tree' : module_tree,
                                                      })
                        if verbose: print('- output_txt = %s' % output_txt)

                        if verbose: print('- outputfilename = %s' % outputfilename)
                        open(os.path.join(project_dir, outputfilename), 'w').write(output_txt)
                    
    os.chdir(cwd)

type_dict = {
    'boolean' : 'uint8_t', 
    'octet': 'uint8_t',
    'char' : 'int8_t',
    'wchar' : 'int16_t',
    'short' : 'int16_t',
    'unsigned short' : 'uint16_t',
    'long' : 'int32_t',
    'unsigned long' : 'uint32_t',
    'long long' : 'int64_t',
    'unsigned long long' : 'uint64_t',
    'double' : 'double',
    'float' : 'float',
    }
             
    
def primitive_to_c(idltype):
    if idltype == 'string' or idltype == 'wstring':
        return 'error'
    return type_dict[idltype]


def parse_struct_member(member, context):
    ret = []
    if member.is_struct:
        for m in member.members:
            ret = ret + parse_member(m, context=context)
        return ret
            
def parse_member(m, context='', verbose=False):

    global idlparser
    if idlparser.is_primitive(m.type.name, except_string=True):
        t = primitive_to_c(m.type.name)
        ret = { 'type' : t,
                'name' : context + '.' +  m.name if len(context) > 0 else m.name, }
        return [ret]
    elif m.type.name == 'string':
        return [{ 'type' : 'string',
                  'name' : m.name,
                  'inner_type' : 'char' }]
    elif m.type.name == 'wstring':
        return [{ 'type' : 'wstring',
                  'name' : m.name,
                  'inner_type' : 'uint16_t' }]
    elif m.type.is_struct:
        if len(context) > 0:
            name = context + '.' + m.name
        else:
            name = m.name
        return parse_struct_member(m.type, context=name)
    elif m.type.is_sequence:
        if len(context) > 0:
            name = context + '.' + m.name
        else:
            name = m.name
        
        if idlparser.is_primitive(m.type.inner_type.name, except_string=True):
            typename = 'sequence<%s>' % (primitive_to_c(m.type.inner_type.name))
            return [{ 'type' : typename,
                      'name' : name,
                      'primitive_sequence' : 'True',
                      'inner_type' : primitive_to_c(m.type.inner_type.name),
                      'inner_truetype' : m.type.inner_type.name,},
                    ]
        elif m.type.inner_type.name == 'string':
            #sys.stdout.write('Error : parsing type %s\n' % m.type)
            return [{ 'type' : 'sequence<string>',
                      'primitive_sequence' : 'False',
                      'name' : name,
                      'inner_type' : 'string'}]
        elif m.type.inner_type.name == 'wstring':
            sys.stdout.write('Error : parsing type %s\n' % m.type)
            return [{ 'type' : 'sequence<wstring>',
                      'primitive_sequence' : 'False',
                      'name' : name,
                      'inner_type' : 'wstring' }]
        else:
            sys.stdout.write('Error : parsing type %s\n' % m.type)
            return [{ 'type' : 'error',
                      'name' : m.name }]
            
    else:
        sys.stdout.write('Error : parsing type %s\n' % m.type)
        return [{ 'type' : 'error',
                 'name' : m.name }]

    
def parse_struct(s, filename):
    args = []
    for m_ in s.members:
        if s.name == 'TimedLong':
            print m_.type
            print idlparser.is_primitive(m_.type.name)
        args = args + parse_member(m_)
    if s.name == 'TimeLong':
        print args
    return { 'name' : s.name,
             'full_path' : s.full_path,
             'arguments' : args,
             'members' : s.members,
    }
    


def parse_module(m, filename):
    ms = m.modules + [m]
    datatypes = []
    for m_ in m.modules + [m]:
        def filter_func(s):
            if s.filepath is None:
                return False
            fn = os.path.basename(filename)
            return s.filepath.find(fn) >= 0

        def parse_struct_local(s):
            return parse_struct(s, filename=filename)
        datatypes = datatypes + m_.for_each_struct(parse_struct_local, filter=filter_func)
    return datatypes


def parse_module_tree(tree, m, filename):

    def filter_func(s):
        if s.filepath is None:
            return False
        fn = os.path.basename(filename)
        return s.filepath.find(fn) >= 0

    def parse_struct_local(s):
        return parse_struct(s, filename=filename)

    tree['module'] = m
    tree['datatypes'] = m.for_each_struct(parse_struct_local, filter=filter_func)
    tree['children'] = []
    
    for m_ in m.modules:
        t = parse_module_tree({}, m_, filename)
        tree['children'].append(t)

    return tree



def generate_directory(idl_identifier, idlpath, backend, verbose=False, outdir=None):
    if verbose: print('generate_direcotry(%s, %s, %s)' % (idl_identifier, idlpath, backend))
    project_name = idl_identifier
    project_name_lower = project_name.lower()

    # make project dir
    base_dir = '.'
    if outdir == None:
        backend_dir = os.path.join(base_dir, backend)
    else:
        backend_dir = os.path.join(base_dir, outdir)
    if not os.path.isdir( backend_dir ):
        print('- creating %s' % (backend_dir))
        os.mkdir(backend_dir)
        
    project_dir = os.path.join(backend_dir, project_name)
    if not os.path.isdir(project_dir):
        print('- creating %s' % (project_dir))
        os.mkdir(project_dir)

    idl_dir = os.path.join(project_dir, 'idl')
    if not os.path.isdir(idl_dir):
        print('- creating %s' % (idl_dir))
        os.mkdir(idl_dir)

    dst_ = os.path.join(project_dir, 'idl', os.path.basename(idlpath))
    print('- copying %s to %s' % (idlpath, dst_))
    shutil.copy(idlpath, dst_)

    includes = idlparser.includes(idlpath)
    for i in includes:
        shutil.copy(i, os.path.join(project_dir, 'idl', os.path.basename(i)))        

    
def main(argv):
    args, include_dirs, language, verbose, outdir = parse_args(argv)
    include_dirs = update_include_dirs(include_dirs)
    if verbose:
        print(' Include Dir = %s' % (include_dirs))
    for arg in args[1:]:
        global idlparser
        idlparser = IDLParser(idl_dirs=include_dirs)
        with open(arg, 'r') as f:
            project_name = os.path.basename(arg)[:-4]
            generate_directory(project_name, arg, language, verbose=verbose, outdir=outdir)

            global_module = idlparser.load(f.read(), filepath=arg)
            parse_global_module(global_module, language, project_name, arg, verbose=verbose, outdir=outdir)


if __name__ == '__main__':
    main(sys.argv)
