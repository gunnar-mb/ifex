# SPDX-FileCopyrightText: Copyright (c) 2024 MBition GmbH.
# SPDX-License-Identifier: MPL-2.0

# This file is part of the IFEX project
# vim: tw=120 ts=4 et

# Have to define a search path to submodule to make this work (might be rearranged later)
import os
import sys
mydir = os.path.dirname(__file__)
for p in ['pyfranca', 'pyfranca/pyfranca']:
    if p not in sys.path:
        sys.path.append(os.path.join(mydir,p))

import ifex.model.ifex_ast as ifex
import other.franca.pyfranca.pyfranca as pyfranca
import other.franca.rule_translator as m2m
import pyfranca.ast as franca
import re

from ifex.model.ifex_ast_construction import add_constructors_to_ifex_ast_model, ifex_ast_as_yaml
from other.franca.rule_translator import Preparation, Constant, Unsupported

def array_type_name(francaitem):
    return translate_type_name(francaitem) + '[]'  # Unbounded arrays for now

def translate_type_name(francaitem):
    return translate_type(francaitem)

def concat_comments(list):
    return "\n".join(list)

# If enumerator values are not given, we must use auto-generated values.
# IFEX model requires all enumerators to be given values.
enum_count = -1
def reset_enumerator_counter():
    #print("***Resetting enum counter")
    global enum_count
    enum_count = -1

def translate_enumerator_value(franca_int_value):
    if franca_int_value is None:
        global enum_count
        enum_count = enum_count + 1
        return enum_count
    return translate_integer_constant(franca_int_value)

# Integer value is represented by an instance of IntegerValue class type, which has a "value" member
def translate_integer_constant(franca_int_value):
    return franca_int_value.value

# Tip: This translation table format is described in more detail in rule_translator.py
franca_to_ifex_mapping = {

        'global_attribute_map':  {
            # Franca-name   :  IFEX-name
            'comments' : 'description', # FIXME allow transform also here, e.g. concat comments
            'extends' : None,  # TODO
            'flags' : None
            },

        'type_map': {
            (franca.Interface,         ifex.Interface) : [],
            (franca.Package,           ifex.Namespace) : [
                # TEMPORARY: Translates only the first interface
                ('interfaces', 'interface', lambda x: x[0]),
                ('typecollections', 'namespaces') ],
            (franca.Method,            ifex.Method) : [
                ('in_args', 'input'),
                ('out_args', 'output'),
                ('namespace', None) ],
            (franca.Argument,          ifex.Argument) : [
                ('type', 'datatype', translate_type_name), ],
            (franca.Enumeration,       ifex.Enumeration) : [
                Preparation(reset_enumerator_counter),
                ('enumerators', 'options'),
                ('extends', Unsupported),

                # Franca only knows integer-based Enumerations so we hard-code the enumeration datatype to be
                # int32 in the corresponding IFEX representation
                (Constant('int32'), 'datatype')
                ],

            (franca.Enumerator,        ifex.Option) : [
                ('value', 'value', translate_enumerator_value)
                ],
            (franca.TypeCollection,    ifex.Namespace) : [
                ('structs', 'structs'),
                ('unions', None),  # TODO - use the variant type on IFEX side, need to check its implementation first
                ('arrays', 'typedefs'),
                ('typedefs', 'typedefs')
                ],
            (franca.Struct,            ifex.Struct) : [
                ('fields', 'members')
                ],
            (franca.StructField,       ifex.Member) : [
                ('type', 'datatype', translate_type_name)
                ] ,
            (franca.Array,             ifex.Typedef) : [
                ('type', 'datatype', array_type_name)
                ],
            (franca.Attribute,         ifex.Property) : [],
            (franca.Import,            ifex.Include) : [],

            # TODO: More mapping to do, much is not yet defined here
            (franca.Package,           ifex.Enumeration) : [],
            (franca.Package,           ifex.Struct) : [],
            }
        }

# --- Map fundamental/built-in types ---

type_translation = {
    franca.Boolean : "boolean",
    franca.ByteBuffer : "uint8[]",
    franca.ComplexType : "opaque", # FIXME this is actually a struct reference?
    franca.Double : "double",
    franca.Float : "float",
    franca.Int8 : "int8",
    franca.Int16 : "int16",
    franca.Int16 : "int16",
    franca.Int32 : "int32",
    franca.Int64 : "int64",
    franca.String : "string",
    franca.UInt8 : "uint8",
    franca.UInt16 : "uint16",
    franca.UInt32 : "uint32",
    franca.UInt64 : "uint64",
}

# ----------------------------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------------------------

def translate_type(t):
    if type(t) is franca.Enumeration:
        return t.name # FIXME use qualified name <InterfaceName>_<EnumerationName>, or change in the other place
    if type(t) is franca.Reference:
        return t.name
    if type(t) is franca.Array:
        # FIXME is size of array defined in FRANCA?
        converted_type = translate_type(t.type)
        converted_type = converted_type + '[]'
        return converted_type
    else:
        t2 = type_translation.get(type(t))
        return t2 if t2 is not None else t

# Rename fidl to ifex, for imports
def ifex_import_ref_from_fidl(fidl_file):
    return re.sub('.fidl$', '.ifex', fidl_file)

# Build the Franca AST
def parse_franca(fidl_file):
    processor = pyfranca.Processor()
    return processor.import_file(fidl_file)  # This returns the top level package

# --- Script entry point ---

if __name__ == '__main__':

    if len(sys.argv) != 2:
        print(f"Usage: python {os.path.basename(__file__)} <filename>")
        sys.exit(1)

    # Add the type-checking constructor mixin
    # FIXME Add this back later for strict checking
    #add_constructors_to_ifex_ast_model()

    try:
        # Parse franca input and create franca AST (top node is the Package definition)
        franca_ast = parse_franca(sys.argv[1])

        # Convert Franca AST to IFEX AST
        ifex_ast = m2m.transform(franca_to_ifex_mapping, franca_ast)

        # Output as YAML
        print(ifex_ast_as_yaml(ifex_ast))

    except FileNotFoundError:
        log("ERROR: File not found")
    except Exception as e:
        raise(e)
        log("ERROR: An unexpected error occurred: {}".format(e))
