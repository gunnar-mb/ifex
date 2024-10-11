# SPDX-FileCopyrightText: Copyright (c) 2024 MBition GmbH.
# SPDX-License-Identifier: MPL-2.0

# This file is part of the IFEX project
# vim: tw=120 ts=4 et

"""
## rule_translator.py

rule_translator implements a generic model-to-model translation function used to copy-and-transform values from one
hierarchical AST representation to another.  It is driven by an input data structure that describes the translation
rules to follow, and implemented by a generic function that can be used for many types of transformation.

## Translation definition

- The data structure (table) describes the mapping from the types (classes) of the input AST to the output AST
- Every type that is found in the input AST *should* have a mapping.  There is not yet perfect error
  reporting if something is missing, but it might be improved.
- For each class, the equivalent member variable that need to be mapped is listed.
- Member variable mappings are optional because any variable with Equal Name on each object
  will be copied automatically (with possible transformation, *if* the input data is listed as a
  complex type).
- Each attribute mapping can also optionally state the name of a transformation function (or lambda)
  If no function is stated, the value will be mapped directly.  Mapping means to follow the transformation
  rules of the type-mapping table *if* the value is an instance of an AST class, and in other
  cases simly copy the value as it is (typically a string, integer, etc.)
- In addition, it is possible to define global name-translations for attributes that are
  equivalent but have different name in the two AST class families.
- To *ignore* an attribute, map it to the None value.

See example table in rule_translator.py source for more information, or any of the implemented programs.

"""

from collections import OrderedDict
from dataclasses import dataclass
import os
import re
import sys


# -----------------------------------------------------------------------------
# Translation Table Helper-objects
# -----------------------------------------------------------------------------
#
# These classes help the table definition by defining something akin to a small DSL (Domain Specific Language) that aids
# us in expressing the translation table with things like "List Of" a certain type, or "Constant" when a given value is
# always supposed to be used, etc. Some ideas of representing the rules using python builtin primitives do not work.
# For example, using '[SomeClass]' to represent and array (list) of SomeClass is a valid statement in general, but
# does not work in our current translation table format because it is a key in a dict. Plain arrays are not a hashable
# value and therefore can't be used as a key. Similarly list(SomeClass) -> a type is not hashable.

# (Use frozen dataclasses to make them hashable.  The attributes are given values at construction time _only_.)
@dataclass(frozen=True)
class ListOf:
    itemtype: type

# Map to Unsupported to make a node type unsupported
@dataclass(frozen=True)
class Unsupported:
    pass

# To insert the same value for all translations
@dataclass(frozen=True)
class Constant:
    const_value: int # Temporary, might be reassigned another type

# To wrap a function that will be called at this stage in the attribute mapping
@dataclass(frozen=True)
class Preparation:
    func: callable
    pass


# -----------------------------------------------------------------------------
# Translation Table - Example, not used. The table be provided instead by the program
# that uses this module)
# -----------------------------------------------------------------------------

example = """
example_mapping = {

        # global_attribute_map: Attributes with identical name are normally automatically mapped.  If attributes have
        # different names we can avoid repeated mapping definitions by still defining them as equivalent in the
        # global_attribute_map.  Attributes defined here ill be mapped in *all* classes.  Note: To ignore an attribute,
        # map it to None!

        'global_attribute_map':  {
            # (Attribute in FROM-class on the left, attribute in TO-class on the right)
            'this' : 'that',
            'something_not_needed' : None
            },

        # type_map: Here follows Type (class) mappings with optional local attribute mappings
        'type_map': {
            (inmodule.ASTClass1, outmodule.MyASTClass) :
            # followed by array of attribute mapping

            # Here an array of tuples is used. (Format is subject to change)
            # (FROM-class on the left, TO-class on the right)
            # *optional* transformation function as third argument
            [ ('thiss', 'thatt'),
              ('name', 'thename', capitalize_name_string),
              ('zero_based_counter', 'one_based_counter', lambda x : x + 1),
              ('thing',  None)
             ]

            # Equally named types have no magic - it is still required to
            # define that they shall be transformed/copied over.
            (inmodule.AnotherType, outmodule.Anothertype), [
                # Use a Constant object to always set the same value in target attribute
                (Constant('int32'), 'datatype')
                ],
            # ListOf and other features are not yet implemented -> when the need arises
        }
}
"""

# -----------------------------------------------------------------------------
# In the following table it is possible to list additional functions that are required but cannot be covered by the
# one-to-one object mapping above.  A typical example is to recursively loop over a major container, *and* its children
# containers create a flat list of items.  Non-obvious mappings can be handled by processing the AST several times.
# Example: if in the input AST has typedefs defined on the global scope, as well as inside of a namespace/interface, but
# in the output AST we want them all collected on a global scope, then the direct mapping between AST objects does not
# apply well since that only creates a result that is analogous to the structure of the input AST.
# -----------------------------------------------------------------------------

# NOTE: This is not yet implemented -> when the need arises
ast_translation = {

}

# ----------------------------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------------------------

# TODO - add better logging
def _log(level, string):
    pass
    #print(f"{level}: {string}")

def is_builtin(x):
    return x.__class__.__module__ == 'builtins'

# This is really supposed to check if the instance is one of the AST classes, or possibly it could check if it is a class
# defined in the mapping table.  For now, however, this simple check for "not builtin" works well enough.
def is_composite_object(mapping_table, x):
    return not is_builtin(x)

# FIXME: Unused, but could be used for error checking
def has_mapping(mapping_table, x):
    return mapping_table['type_map'].get(x.__class__) is not None

# flatmap: Call function for each item in input_array, and flatten the result
# into one array. The passed function is expected to return an array for each call.
def flatmap(function, input_array):
    return [y for x in input_array for y in function(x)]

def underscore_combine_name(parent, item):
    return parent + "_" + item

# This function is used by the general translation to handle multiple mappings with the same target attribute.
# We don't want to overwrite and destroy the previous value with a new one, and if the target is a list
# then it is useful to be able to add to that list at multiple occasions -> append to it.
def set_attr(attrs_dict, attr_key, attr_value):
    if attr_key in attrs_dict:
        value = attrs_dict[attr_key]

        # If it's a list, we want to add to it instead of overwriting:
        if isinstance(value, list):
            value.append(attr_value)
            attrs_dict[attr_key] = value
            return
        else:
            _log("ERR", """Attribute {attr_key} already has a scalar (non-list) value.  Check for multiple translations
                  mapping to this one.  We should not overwrite it, and since it is not a list type, we can't append.""")
            _log("DEBUG" "Target value {value} was ignored.")
            return

    # If it's a new assignment, go ahead
    attrs_dict[attr_key] = attr_value

# ----------------------------------------------------------------------------
# --- MAIN conversion function ---
# ----------------------------------------------------------------------------

# Here we use a helper function to allow one, two, or three defined values
# in the mapping.  With normal decomposition of a tuple, only the last could
# be optional, like:
#     first, second, *maybe_more = (...tuple...)
# But a single value of type Preparation() does not need to be a tuple at all.
def eval_mapping(type_map_entry):
    if isinstance(type_map_entry, Preparation):
        # Return the function that is wrapped inside Preparation()
        return (type_map_entry.func, None, None, None)
    else:  # 3 or 4-value tuple is expected (transform_function is optional)
        input_arg, output_arg, *transform_function = type_map_entry
        return (None, input_arg, output_arg, transform_function)


# Common code - how to handle different composite value types, and lists
def transform_value_common(mapping_table, value, transform_function):
    # OrderedDict is used at least by Franca AST
    if isinstance(value, OrderedDict):
        value  = [transform(mapping_table, item) for name, item in value.items()]

    elif isinstance(value, list):
        value = [transform(mapping_table, item) for item in value]

    else: # Plain attribute -> use transformation function if it was defined
        value = transform_function(value)

    return value


def transform(mapping_table, input_obj):

    # Builtin types (str, int, ...) are assumed to be just values to copy without any change
    if is_builtin(input_obj):
        return input_obj

    # Find a translation rule in the metadata
    # Uses linear-search in mapping table until we find something matching input object.
    # Since the translation table is reasonably short, it should be OK for now.
    for (from_class, to_class), mappings in mapping_table['type_map'].items():

        # Does this transformation rule match input object?
        if from_class == input_obj.__class__:
            _log("INFO", f"Type mapping found: {from_class=} -> {to_class=}")

            # Comment: Here we might create an empty instance of the class and fill it with values using setattr(), but
            # that won't work since the redesign using dataclasses.  The AST classes now have a default constructor that
            # requires all mandatory fields to be specified when an instance is created.  Therefore we are forced to
            # follow this approach:  Gather all attributes in a dict and pass it into the constructor at the end using
            # python's dict to keyword-arguments capability.

            attributes = {}

            # To remember the args we have converted
            done_attrs = set()

            # First loop:  Perform the explicitly defined attribute conversions
            # for those that are specified in the translation table.

            for preparation_function, input_attr, output_attr, transform_function in [eval_mapping(m) for m in mappings]:
                _log("INFO", f"Attribute mapping found: {input_attr=} -> {output_attr=} with {transform_function=}")

                # TODO: It should be possible to let the preparation_function be a closure, with predefined parameters.
                # To be investigated.  Consider if it's better to go back to eval_mapping returning the function-wrapper
                # object (Preparation) and not just the function.

                # Call preparation function, if given.
                if preparation_function is not None:
                    preparation_function()
                    # prep function always has its own line in table, so skip to next object
                    continue

                # For simpler logic below, ensure transform can be called even if none is defined
                transform_function = transform_function[0] if transform_function else lambda _ : _

                # Explicitly ignored?

                if output_attr is None:
                    _log("DEBUG", f"Ignoring {input_attr=} for {type(input_obj)} because it was mapped to None")
                    continue

                # Explicitly unsupported?
                if output_attr is Unsupported:
                    if value is not None:
                        _log("ERR", f"Attribute {input_attr} has a value in {type(input_obj)}:{input_obj.name} but the feature ({input_attr}) is unsupported. ({value=})")
                    continue

                # Get input value, or constant value if specified
                if isinstance(input_attr, Constant):
                    set_attr(attributes, output_attr, input_attr.const_value)
                else:
                    value = getattr(input_obj, input_attr)
                    set_attr(attributes, output_attr, transform_value_common(mapping_table, value, transform_function))

                # Mark this attribute as handled
                done_attrs.add(input_attr)


            # Second loop: Any attributes that have the _same name_ in the input and output classes are assumed to be
            # mappable to each other.  Identical names do not need to be listed in the translation table unless they
            # need a custom transformation.  Here we find all matching names and map them (with recursive
            # transformation, as needed), but of course skip all attributes that have been handled explicitly
            # (done_attrs).  global_attribute_map also defines globally which attributes are considered identical.

            global_attribute_map = mapping_table['global_attribute_map']

            # Checking all values defined in input object...
            for attr, value in vars(input_obj).items():

                # ... unless already handled
                if attr in done_attrs:
                    continue

                # Translate attribute name according to global rules, if defined.
                attr = global_attribute_map.get(attr) if attr in global_attribute_map else attr

                # Check if to_class has an attribute with this name?
                if attr in to_class.__dataclass_fields__:
                    _log("DEBUG", f"Performing global or same-name auto-conversion for {attr=} from {from_class.__name__} to {to_class.__name__}\n")

                    # No transform function for same-name translations (this might change), therefore an identity lambda
                    set_attr(attributes, attr, transform_value_common(mapping_table, value, lambda _ : _))

                # No match found in to_class, and not explicitly ignored
                elif attr is not None:
                    _log("WARN", f"Attribute '{attr}' from Input AST:{input_obj.__class__.__name__} was not used in IFEX:{to_class.__name__}")

            # attributes now filled with values. Instantiate "to_class" object, and return it.
            _log("DEBUG", f"Creating and returning object of type {to_class} with {attributes=}")
            return to_class(**attributes)

    no_rule = f"No translation rule found for object {input_obj} of class {input_obj.__class__.__name__}"
    _log("ERR:", no_rule)
    raise TypeError(no_rule)
