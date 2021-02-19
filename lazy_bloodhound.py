import argparse
import tree_sitter

from datetime import datetime
from os import path, listdir
from pathlib import Path

CONFIG = {
    "current_source": None,
    "debug_info": False,
    "symbol_table": {},
    "verbose": False,
    "num_files_analyzed": 0,
    "alerts": 0,
}

# == Helper functions ==========================================
def get_php_parser():
    php_language = tree_sitter.Language('build/languages.so', 'php')
    parser = tree_sitter.Parser()
    parser.set_language(php_language)
    return parser

def read_source_file(filename):
    f = open(filename, 'r', encoding="utf-8", errors='ignore')
    src = f.read()
    f.close()
    return str.encode(src)

def get_aruments_from_function_args_node(node):
    args_as_text = []
    args_as_node = []
    current_arg = ""
    for element in node:
        if element.type in ["(", ")"]:
            # handle final argument on closing paren.
            if current_arg != "" and element.type == ")":
                args_as_text.append(current_arg)
            # else, do nothing
        elif element.type in ["binary_expression", "variable_name"]:
            current_arg += get_node_text(element)
            args_as_node.append(element)
        elif element.type == ",":
            args_as_text.append(current_arg)
            current_arg = ""
        else:
            if CONFIG["verbose"]:
                print("Unsupported arg element: {}".format(element))
    return args_as_text, args_as_node

def get_node_text(node):
    src = CONFIG["current_source"].decode("utf-8").split("\n")
    start_line = node.start_point[0]
    start_char = node.start_point[1]
    end_line = node.end_point[0] + 1
    end_char = node.end_point[1]
    lines = src[start_line:end_line]
    if lines[0] != lines[-1]:
        lines[0] = lines[0][start_char:]
        lines[-1] = lines[-1][:end_char]
    else:
        lines[0] = lines[0][start_char:end_char]
    lines = "\n".join(lines)
    return lines

def get_var_nodes_from_binary_expression(node, var_nodes=None):
    """
    Given a `binary_expression` node, recursively walk the
    tree collecting all avriables contained within.
    """
    if type(node) != tree_sitter.Node:
        raise TypeError('argument must be a tree_sitter.Node type')
    if var_nodes == None:
        var_nodes = []
    if node.type == "binary_expression":
        for child in node.children:
            if child.type == "variable_name":
                var = get_node_text(child)
                var_nodes.append(var)
            elif child.type == "binary_expression":
                var_nodes = get_var_nodes_from_binary_expression(child, var_nodes)
            else:
                #print(child.type)
                pass
    var_nodes = list(set(var_nodes)) # remove duplicates
    return var_nodes

def print_symbol_table():
    print("// SYMBOL_TABLE:")
    symbol_table = CONFIG['symbol_table']
    for key in symbol_table:
        print("  Symbol: {}".format(key))
        for symbol in symbol_table[key]:
            print("    Assigned on line: {}".format(symbol['line']))
            print("    Type:             {}".format(symbol['type']))
            print("    Value:            {}".format(symbol['value']))
            print("    Variable:         {}".format(symbol['variable']))
            print("    Node:             {}".format(symbol['node']))


# == Main parser functions =====================================
def tree_walker(tree):
    cursor = tree.walk()
    row = ""
    rows = []
    finished_row = False
    visited_children = False
    indent_level = 0
    display_name = None
    
    if cursor.node.is_named:
        display_name = cursor.node.type
    
    while True:
        if visited_children:
            if display_name:
                finished_row = True
            if cursor.goto_next_sibling():
                visited_children = False
            elif cursor.goto_parent():
                visited_children = True
                indent_level -= 1
            else:
                break
        else:
            if display_name:
                if finished_row:
                    row += ""
                    rows.append(row)
                    finished_row = False
                start = cursor.node.start_point
                end = cursor.node.end_point
                field_name = cursor.current_field_name()
                if field_name:
                    field_name += ": "
                else:
                    field_name = ""
                finished_row = True
            
            if cursor.goto_first_child():
                visited_children = False
                indent_level += 1
                statement_dispatcher(cursor)
            else:
                visited_children = True


def statement_dispatcher(cursor):
    statement_handlers = {
        'arguments':                    process_arguments,
        'assignment_expression':        process_assignment_expression,
        'binary_expression':            process_binary_expression,
        'comment':                      process_comment,
        'compound_statement':           process_compound_statement,
        'class':                        process_class,
        'class_declaration':            process_class_declaration,
        'declaration_list':             process_declaration_list,
        'echo':                         process_echo,
        'echo_statement':               process_echo_statement,
        'else':                         process_else,
        'else_clause':                  process_else_clause,
        'expression_statement':         process_expression_statement,
        'formal_parameters':            process_formal_parameters,
        'function':                     process_function,
        'function_call_expression':     process_function_call_expression, 
        'function_definition':          process_function_definition,
        'if':                           process_if,
        'if_statement':                 process_if_statement,
        'include':                      process_include,
        'include_expression':           process_include_expression,
        'integer':                      process_integer,
        'member_call_expression':       process_member_call_expression,
        'method_declaration':           process_method_declaration,
        'name':                         process_name,
        'new':                          process_new,
        'object_creation_expression':   process_object_creation_expression,
        'parenthesized_expression':     proces_parenthesized_expression,
        'php_tag':                      process_php_tag_start,
        'program':                      process_program,
        'public':                       process_public,
        'qualified_name':               process_qualified_name,
        'string':                       process_string,
        'text':                         process_text,
        'text_interpolation':           process_text_interpolation,
        'trait':                        process_trait,
        'trait_declaration':            process_trait_declaration,
        'use':                          process_use,
        'use_declaration':              process_use_declaration,
        'variable_name':                process_variable_name,
        'visibility_modifier':          process_visibility_modifier,
        '?>':                           process_php_tag_end,
        '->':                           process_token_arrow,
        ',':                            process_token_comma,
        '{':                            process_token_curly_open,
        '}':                            process_token_curly_close,
        '$':                            process_token_dollarsign,
        '.':                            process_token_dot,
        '=':                            process_token_equal,
        '==':                           process_token_equal_equal,
        '!=':                           process_token_not_equal,
        '&&':                           process_token_logical_and,
        '(':                            process_token_paren_open,
        ')':                            process_token_paren_close,
        ';':                            process_token_semicolon,
    }
    try:
        statement_handlers[cursor.node.type](cursor)
    except KeyError:
        if CONFIG["debug_info"]:
            print("[!] Unhandled node: {}".format(cursor.node.type))


# == Node parser functions =====================================
def process_arguments(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_assignment_expression(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))
    if CONFIG["verbose"]: print("Variable Assignment:")

    line_number = cursor.node.start_point[0] + 1
    variable_name = get_node_text(cursor.node.children[0])
    value_node = cursor.node.children[2]
    value_text = get_node_text(value_node)
    value_type = value_node.type

    symbol_data = {
        'line': line_number,
        'node': cursor.node,
        'type': value_type,
        'value': {},
        'variable': variable_name,
    }

    if value_type == "function_call_expression":
        func_children = [ child for child in value_node.children ]
        func_name = get_node_text(func_children[0])
        symbol_data["value"] = {
            "value": value_text,
            "function_name": func_name,
        }
    else:
        symbol_data["value"] = {
            "value": value_text,
        }

    if CONFIG["verbose"]:
        print("  line    : {}".format(line_number))
        print("  variable: {}".format(variable_name))
        print("  value   : {}".format(value_text))
        print("  type    : {}".format(value_type))
        print('-'*50)

    symbol_table = CONFIG["symbol_table"]
    if variable_name not in symbol_table:
        symbol_table[variable_name] = []
    symbol_table[variable_name].append(symbol_data)

def process_binary_expression(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_class(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_class_declaration(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_comment(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_compound_statement(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_declaration_list(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_echo(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_echo_statement(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_else(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_else_clause(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_expression_statement(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_formal_parameters(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_function(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_function_call_expression(cursor):
    symbol_table = CONFIG["symbol_table"]
    verbose = CONFIG["verbose"]

    line = cursor.node.start_point[0]+1          # source line number
    function_name_node = cursor.node.children[0] # function being called
    function_args_node = cursor.node.children[1] # argument list
    function_name = get_node_text(function_name_node)
    function_args = get_node_text(function_args_node)

    text_args, node_args = get_aruments_from_function_args_node(function_args_node.children)
    for i, arg in enumerate(text_args):
        if function_name in ["system", "exec"]:
            if arg.find("$_") >= 0:
                print("[!] Alert: Possible command injection on line {}".format(line))
                print("    >>> {}({})".format(function_name, ",".join(text_args)))
                CONFIG["alerts"] += 1

    if verbose:
        print("Line: {}: {}".format(line, cursor.node))
        print("Function Call:")
        print("  line    : {}".format(line))
        print("  function: {}".format(function_name))
        print("  args    : {}".format(function_args))
        for i, arg in enumerate(text_args):
            print("    arg{} : {}".format(i+1, arg))
        print('-'*50)

def process_function_definition(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_if(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_if_statement(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_include(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_include_expression(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_integer(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_member_call_expression(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_method_declaration(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_name(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_new(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_object_creation_expression(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def proces_parenthesized_expression(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_php_tag_start(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_php_tag_end(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_program(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_public(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_qualified_name(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_string(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_text(cursor):
    if CONFIG["verbose"]: 
        print("Encountered non-PHP text:")
        print(get_node_text(cursor.node))

def process_text_interpolation(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_token_arrow(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_token_comma(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_token_dollarsign(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_token_dot(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_token_equal(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_token_equal_equal(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_token_not_equal(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_token_curly_close(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_token_curly_open(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_token_logical_and(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_token_paren_close(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_token_paren_open(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_token_semicolon(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_trait(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_trait_declaration(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_use(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_use_declaration(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_variable_name(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))

def process_visibility_modifier(cursor):
    if CONFIG["verbose"]: print("Line: {}: {}".format(cursor.node.start_point[0]+1, cursor.node))


# == Analyzer ==================================================
def main(target):
    # check if `target` is a file or directory...
    if path.isfile(target):
        print("Analyzing file: {}".format(target))
        php_parser = get_php_parser()
        code = read_source_file(target)
        CONFIG["current_source"] = code
        tree = php_parser.parse(code)
        tree_walker(tree)
        CONFIG["num_files_analyzed"] += 1
    elif path.isdir(target):
        target_files = list(Path(target).rglob("*.[pP][hH][pP]"))
        for target_file in target_files:
            print("Analyzing file: {}".format(target_file))
            php_parser = get_php_parser()
            code = read_source_file(path.join(target, target_file))
            CONFIG["current_source"] = code
            tree = php_parser.parse(code)
            tree_walker(tree)
            CONFIG["num_files_analyzed"] += 1
    else:
        print("Invalid target type. Need a file or directory.")
    
    if CONFIG["debug_info"]:
        print_symbol_table()


# == Command line interface ====================================
if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description='A really lazy (but super cute) PHP static code analyzer v0.1.0')
    arg_parser.add_argument(
        'target',
        action='store',
        type=str,
        help='file /path/to/target.php or directory /path/to/dir/')
    arg_parser.add_argument(
        '-d',
        '--debug-info',
        action='store_true',
        help='print parser warnings')
    arg_parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='print all node data')
    args = arg_parser.parse_args()
    target = args.target
    CONFIG["debug_info"] = args.debug_info
    CONFIG["verbose"] = args.verbose
    if path.exists(target):
        start_time = datetime.now()
        main(target)
        print("\nFinished analyzing {} file(s) in {}. Found {} alerts.".format(CONFIG["num_files_analyzed"], datetime.now() - start_time, CONFIG["alerts"]))
    else:
        print("\nError: cannot find file '{}'.\nCheck the file path and try again.".format(target))
