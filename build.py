from tree_sitter import Language, Parser

Language.build_library(
  # Store the library in the `build` directory
  'build/languages.so',

  # Include one or more languages
  [
    'parsers/tree-sitter-php',
  ]
)
