----

# Fundamental Data Types

IFEX Core IDL contains a number of Fundamental Types.  Fundamental Types are either Primitive types, or other fundamental types.

The Primitive datatypes are defined to be identical to the Vehicle Signal Specification (VSS), and these match well to most other interface description languages and programming environments:

- int8, int16, int32, int64
- uint8, uint16, uint32, uint64 (unsigned)
- float, double
- string

The IFEX Fundamental datatypes also include:
- array
- map
- set
- variant

Each of those 4 are defined in relation to another (contained) existing datatype, which can be primitive or defined.

- An array is defined by adding `[]` to the end of a type:  `t[]`, where t can be any type.
    - An array can be given a fixed length by adding a number, such as:  t[42], or by using the arraysize key: `arraysize : 42`
- A Map type is defined by `map<t1, t2>` where t1 and t2 can be any type.  Map is a key-value mapping type, (called Map in many languagesor "dict" in python)
- A Set must be written as:  `set<t>`, where t is any type.  A Set is a container that guarantees each unique value to only be stored once.
- A Variant is written as :  `variant<t1, t2, ...>`, with an arbitrary number of types listed.  A Variant type indicates that the value can be of any one of the listed types.  This is known as "union" in c-style languages.

One more special datatype is defined as part of IFEX Core Definition:  
- `opaque` is a representation of a data type that is either not possible or not desired to describe in further detail.  It could be seen somewhat equivalent to a void-pointer in C-style languages or perhaps an unspecified array-of-bytes.  When transferring Opaque across a data protocol, it might use `Variant` if possible, or simply be an array-of-bytes, where the server and client knows how to re-interpret the value on the other side.

Defined datatypes are datatypes that are not Fundamental, and thus need to be defined before usage, namely **Enumeration**s, **Struct**s and **Typedef**s.  Typedefs are "type aliases" that give a (new) name to another datatype, while optionally adding additional characteristics such as constraints (limitation of allowed values, and so on).

