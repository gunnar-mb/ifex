-----------------------

# LAYERS CONCEPT

The VSC approach implements a layered approach to the definition of interfaces,
and potentially other aspects of a system.  The core interface file (Interface
Description Language, or Interface Description Model) shall contain only a
_generic_ interface description that can be as widely applicable as possible.

As such, it avoids including specific information that only applies in certain
interface contexts, such as anything specific to the chosen transport protocol,
the programming language, and so on.

Each new **Layer Type** defines what new metadata it provides to the overall
model.  A Layer Type Specification may be written as a human-readable document,
but is often provided as a "YAML schema" type of file, that can be used to
programatically validate layer input against formal rules.

Layers do not always need to add new _types_ of information.  It is possible to
'overlay' files that are of the same core interface (IDL) schema as an original
file, for the purpose of adding details that were not defined, removing nodes,
or even redefining/changing the definition of some things defined in the
original file.

In other words, tools are expected to process multiple IDL files and to merge
their contents according to predefined rules.  Conflicting information could,
for example be handled by writing a warning, or to let the last provided layer
file to take precedence over previous definitions.  (Refer to detailed
documentation for each tool).

Example:

**File: `comfort-service.yml`**  
```YAML
name: comfort
  typedefs:
    - name: movement_t
      datatype: int16
      min: -1000
      max: 1000
      description: The movement of a seat component
```

**File: `redefine-movement-type.yml`**  
```YAML
name: comfort
  typedefs:
    - name: movement_t
      datatype: int8 # Replaces int16 of the original type
```

The combined YAML structure to be processed will look like this:

```YAML
name: comfort
  typedefs:
    - name: movement_t
      datatype: int8 # Replaced datatype
      min: -1000
      max: 1000
      description: The movement of a seat component
```

## Deployment file object list extensions

If a deployment file's object list element (e.g. `events`) is also
defined in the VSC file, the VSC's list will traversed recursively and
extended by the deployment file's corresponding list.

**FIXME** Possibly add description on how various edge cases are resolved.

Example:

**File: `comfort-service.yml`**  
```YAML
name: comfort
events:
  - name: seat_moving
    description:  The event of a seat starting or stopping movement
    in:
      - name: status
        datatype: uint8
      - name: row
        datatype: uint8

```

**File: `add_seat_moving_in_parameter.yml`**  
```YAML
name: comfort
events:
- name: seat_moving: 
    in:
      - name: extended_status_text
        datatype: string
```

The combined YAML structure to be processed will look like this:

```YAML
name: comfort
events:
  - name: seat_moving
    description:  The event of a seat starting or stopping movement
    in:
      - name: status
        datatype: uint8
      - name: row
        datatype: uint8
      - name: extended_status_text
        datatype: string
```



There is not a fixed list of layer types - some may be standardized and
defined, and therefore documented, but the design is there to allow many
extensions that have not yet been invented or agreed upon.


# DEPLOYMENT LAYER

Deployment layer, a.k.a. Deployment Model files, is a specialization of the
general layers concept.  This terminology is used to indicate a type of layer
that in adds additional metadata that is directly related to the interface 
described in the IDL.  It is information needed to process, or interpret, VSC
interface files in a particular target environment.

An example of deployment file data is a DBUS interface specification to be used
for a namespace, or a SOME/IP method ID to be used for a method call.  

By separating the extension data into their own deployment files the
core VSC specification can be kept independent of deployment details
such as network protocols and topology.

An example of a VSC file sample and a deployment file extension to
that sample is given below:


**File: `comfort-service.yml`**  
```YAML
name: comfort
namespaces:
  - name: seats
    description: Seat interface and datatypes.

    structs: ...
    methods: ...
   ...
```

**File: `comfort-dbus-deployment.yml`**  

```YAML
name: comfort
namespaces: 
  - name: seats
    dbus_interface: com.genivi.cabin.seat.v1
```

The combined YAML structure to be processed will look like this:

```YAML
name: comfort
namespaces: 
  - name: seats
    description: Seat interface and datatypes.
    dbus_interface: com.genivi.cabin.seat.v1

    structs: ...
    methods: ...
```

The semantic difference between a regular VSC file included by an
`includes` list object and a deployment file is that the deployment
file can follow a different specification/schema and add keys that
are not allowed in the plain IDL layer.  In the example above, the
`dbus_interface` key-value pair can only be added in a deployment file since
`dbus_interface` is not a part of the regular VSC IDL file syntax.

----------

# VSC FILE SYNTAX, SEMANTICS AND STRUCTURE

A Vehicle Service Catalog is stored in one or more YAML files.  The
root of each YAML file is assumed to be a `namespace` object and needs
to contain at least a `name` key, and, optionally, a `description`. In
addition to this other namespaces, `includes`, `datatypes`, `methods`,
`events`, and `properties` can be specified.

A complete VSC file example is given below:

**NOTE: This example might be outdated**

```YAML
---
name: comfort
major_version: 2
minor_version: 1
description: A collection of interfaces pertaining to cabin comfort.

# Include generic error enumeration to reside directly
# under comfort namespace
includes:
  - file: vsc-error.yml
    description: Include standard VSC error codes used by this namespace

namespaces:
  - name: seats
    description: Seat interface and datatypes.

    typedefs:
      - name: movement_t
        datatype: uint16
  
    structs:
      - name: position_t
        description: The position of the entire seat
        members:
          - name: base
            datatype: movement_t
            description: The position of the base 0 front, 1000 back
    
          - name: recline
            datatype: movement_t
            description: The position of the backrest 0 upright, 1000 flat
    
    enumerations:
      - name: seat_component_t
        datatype: uint8
        options:
          - name: base
            value: 0
          - name: recline
            value: 1
    
    methods:
      - name: move
        description: Set the desired seat position
        in: 
          - name: seat
            description: The desired seat position
            datatype: movement.seat_t
    
    
    events:
      - name: seat_moving
        description: The event of a seat beginning movement
        in:
          - name: status
            description: The movement status, moving (1), not moving (0)
            datatype: uint8
    
    properties:
      - name: seat_moving
        description: Specifies if a seat is moving or not
        type: sensor
        datatype: uint8
```


The following chapters specifies all YAML objects and their keys
supported by VSC.  The "Lark grammar" specification refers to the Lark
grammar that can be found [here](https://github.com/lark-parser/lark).
The terminals used in the grammar (`LETTER`, `DIGIT`, etc) are
imported from
[common.lark](https://github.com/lark-parser/lark/blob/master/lark/grammars/common.lark)